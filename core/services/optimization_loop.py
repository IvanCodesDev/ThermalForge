"""SolidWorks 模型优化反馈闭环编排服务。

编排流程：用户反馈 → LLM 规划 → SolidWorks 执行 → 产物登记 → 迭代/接受。
"""
from __future__ import annotations

import json
from uuid import UUID

from pydantic import BaseModel

from core.adapters.solidworks import SolidWorksAdapter
from core.agents import AgentRegistry, build_agent_registry
from core.agents.contracts import ExecutionContext
from core.agents.execution import (
    AgentExecutionService,
    build_default_quality_gates,
    build_default_tool_adapters,
)
from core.config import Settings, get_settings
from core.models.agent_pipeline import (
    AgentEvent,
    AgentPipeline,
    PipelineArtifact,
    PipelineState,
)
from core.models.optimization import (
    OptimizationFeedback,
    OptimizationIteration,
    OptimizationPlan,
    SolidWorksExecutionResult,
    SolidWorksOptimizationContract,
    SolidWorksOutputPlan,
    SubmitOptimizationFeedbackRequest,
)
from core.providers.openai_models import OpenAIModelsClient
from core.services.agent_pipeline import (
    AgentPipelineRuntime,
    PipelineConflictError,
    PipelineGateError,
    PipelineNotFoundError,
)


_OPTIMIZATION_PLANNING_PURPOSE = "model_optimization_planning"


class _FeedbackPayload(BaseModel):
    """LLM Agent 输入载荷。"""
    feedback_text: str
    target_component_id: str | None = None
    current_specification: dict
    current_artifacts: list[dict]
    iteration: int
    source_artifact_id: str
    source_format: str


class OptimizationLoopService:
    """编排优化反馈闭环：反馈 → LLM 规划 → SolidWorks 执行 → 产物登记。"""

    def __init__(
        self,
        settings: Settings | None = None,
        runtime: AgentPipelineRuntime | None = None,
        registry: AgentRegistry | None = None,
        client: OpenAIModelsClient | None = None,
        adapter: SolidWorksAdapter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runtime = runtime or AgentPipelineRuntime()
        self.registry = registry or build_agent_registry(self.settings)
        self.client = client or OpenAIModelsClient(self.settings)
        self.adapter = adapter or SolidWorksAdapter()
        self._execution_service: AgentExecutionService | None = None

    # ── 状态转换 ──

    def enter_optimization_loop(self, pipeline_id: UUID) -> AgentPipeline:
        """从 HYPER3D_DONE / GEOMETRY_READY / SOLIDWORKS_DONE 进入优化审核。"""
        with self.runtime._lock:
            item = self.runtime._require(pipeline_id)
            allowed = {
                PipelineState.HYPER3D_DONE,
                PipelineState.GEOMETRY_READY,
                PipelineState.SOLIDWORKS_DONE,
            }
            if item.state not in allowed:
                raise PipelineGateError(
                    f"当前状态 {item.state} 不允许进入优化闭环"
                )
            iteration_num = item.current_optimization_iteration + 1
            iterations = list(item.optimization_iterations)
            iterations.append(
                OptimizationIteration(
                    iteration=iteration_num,
                    status="feedback_received",
                ).model_dump()
            )
            updated = item.model_copy(update={
                "state": PipelineState.OPTIMIZATION_REVIEW,
                "current_optimization_iteration": iteration_num,
                "optimization_iterations": iterations,
                "events": item.events + [AgentEvent(
                    agent="optimization_loop",
                    action="optimization_loop_entered",
                    state=PipelineState.OPTIMIZATION_REVIEW,
                    detail={"iteration": iteration_num},
                )],
            })
            self.runtime._save_pipeline(updated)
            return updated.model_copy(deep=True)

    async def submit_feedback(
        self,
        pipeline_id: UUID,
        request: SubmitOptimizationFeedbackRequest,
    ) -> AgentPipeline:
        """提交反馈 → LLM 解析 → 生成优化计划。"""
        with self.runtime._lock:
            item = self.runtime._require(pipeline_id)
            if item.state != PipelineState.OPTIMIZATION_REVIEW:
                raise PipelineGateError("必须先进入优化审核状态")

            iteration_num = item.current_optimization_iteration
            feedback = OptimizationFeedback(
                iteration=iteration_num,
                feedback_text=request.feedback_text,
                target_component_id=request.target_component_id,
                submitted_by=request.submitted_by,
            )

            iterations = list(item.optimization_iterations)
            idx = _find_iteration_index(iterations, iteration_num)
            if idx is not None:
                iterations[idx]["feedback"] = feedback.model_dump(mode="json")
                iterations[idx]["status"] = "planning"

            updated = item.model_copy(update={
                "state": PipelineState.OPTIMIZATION_PLANNED,
                "optimization_iterations": iterations,
                "events": item.events + [AgentEvent(
                    agent="human_feedback",
                    action="optimization_feedback_submitted",
                    state=PipelineState.OPTIMIZATION_PLANNED,
                    detail={
                        "iteration": iteration_num,
                        "feedback_text": request.feedback_text,
                    },
                )],
            })
            self.runtime._save_pipeline(updated)

        # 调用 LLM Agent 解析反馈
        plan = await self._run_planning_agent(updated, feedback)

        # 保存优化计划
        with self.runtime._lock:
            item = self.runtime._require(pipeline_id)
            iterations = list(item.optimization_iterations)
            idx = _find_iteration_index(iterations, iteration_num)
            if idx is not None:
                iterations[idx]["plan"] = plan.model_dump(mode="json")
                iterations[idx]["status"] = "planned"
            updated = item.model_copy(update={
                "optimization_iterations": iterations,
                "events": item.events + [AgentEvent(
                    agent="optimization_planning_agent",
                    action="optimization_plan_generated",
                    state=PipelineState.OPTIMIZATION_PLANNED,
                    detail={
                        "iteration": iteration_num,
                        "instruction_count": len(plan.instructions),
                    },
                )],
            })
            self.runtime._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def compile_solidworks(self, pipeline_id: UUID) -> AgentPipeline:
        """编译 SolidWorks 契约。"""
        with self.runtime._lock:
            item = self.runtime._require(pipeline_id)
            if item.state != PipelineState.OPTIMIZATION_PLANNED:
                raise PipelineGateError("必须先完成优化规划")

            iteration_num = item.current_optimization_iteration
            iterations = list(item.optimization_iterations)
            idx = _find_iteration_index(iterations, iteration_num)
            if idx is None or iterations[idx].get("plan") is None:
                raise PipelineGateError("当前迭代没有优化计划")

            plan = OptimizationPlan.model_validate(iterations[idx]["plan"])

            # 查找源产物
            source_artifact = _find_source_artifact(item.artifacts)
            if source_artifact is None:
                raise PipelineGateError("没有可用的源模型产物")

            source_format = plan.source_format
            source_uri = source_artifact.uri

            # GLB 需要预处理为 STL（此处记录，实际转换在 adapter 层处理）
            if source_format == "glb":
                source_format = "stl"
                source_uri = source_uri.rsplit(".", 1)[0] + ".stl"

            workspace_dir = f"data/optimization/{pipeline_id}/iter{iteration_num}"
            contract = SolidWorksOptimizationContract(
                id=f"sw-opt-{pipeline_id}-iter{iteration_num}",
                pipeline_id=pipeline_id,
                iteration=iteration_num,
                source_model_uri=source_uri,
                source_format=source_format,
                operations=plan.instructions,
                output_plan=SolidWorksOutputPlan(
                    workspace_dir=workspace_dir,
                ),
            )

            iterations[idx]["solidworks_contract"] = contract.model_dump(mode="json")
            iterations[idx]["status"] = "executing"

            updated = item.model_copy(update={
                "state": PipelineState.SOLIDWORKS_SUBMITTED,
                "solidworks_contract": contract.model_dump(mode="json"),
                "optimization_iterations": iterations,
                "events": item.events + [AgentEvent(
                    agent="solidworks_compiler_agent",
                    action="solidworks_contract_compiled",
                    state=PipelineState.SOLIDWORKS_SUBMITTED,
                    detail={"iteration": iteration_num},
                )],
            })
            self.runtime._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def execute_solidworks(self, pipeline_id: UUID) -> AgentPipeline:
        """执行 SolidWorks 优化并登记结果。"""
        with self.runtime._lock:
            item = self.runtime._require(pipeline_id)
            if item.state != PipelineState.SOLIDWORKS_SUBMITTED:
                raise PipelineGateError("必须先编译 SolidWorks 契约")
            if not item.solidworks_contract:
                raise PipelineGateError("SolidWorks 契约不存在")
            contract = SolidWorksOptimizationContract.model_validate(
                item.solidworks_contract
            )
            iteration_num = item.current_optimization_iteration

        # 执行 SolidWorks
        result = self.adapter.execute(contract)

        # 构建产物
        artifacts: list[PipelineArtifact] = []
        if result.step_path:
            step_uri = "file:///" + result.step_path.replace("\\", "/")
            artifacts.append(PipelineArtifact(
                id=f"sw-step-iter{contract.iteration}",
                role="solidworks_step",
                uri=step_uri,
                provider="solidworks",
                fidelity="optimized_cad",
            ))
        if result.stl_path:
            stl_uri = "file:///" + result.stl_path.replace("\\", "/")
            artifacts.append(PipelineArtifact(
                id=f"sw-stl-iter{contract.iteration}",
                role="solidworks_stl",
                uri=stl_uri,
                provider="solidworks",
                fidelity="optimized_mesh",
            ))
        for i, preview in enumerate(result.preview_paths):
            preview_uri = "file:///" + preview.replace("\\", "/")
            artifacts.append(PipelineArtifact(
                id=f"sw-preview-iter{contract.iteration}-{i}",
                role="solidworks_preview",
                uri=preview_uri,
                provider="solidworks",
                fidelity="metadata",
            ))

        with self.runtime._lock:
            item = self.runtime._require(pipeline_id)
            iterations = list(item.optimization_iterations)
            idx = _find_iteration_index(iterations, iteration_num)
            if idx is not None:
                iterations[idx]["result"] = result.model_dump(mode="json")
                iterations[idx]["artifacts"] = [a.model_dump(mode="json") for a in artifacts]
                iterations[idx]["status"] = "completed" if result.status == "ok" else "failed"

            updated = item.model_copy(update={
                "state": PipelineState.SOLIDWORKS_DONE if result.status == "ok" else PipelineState.OPTIMIZATION_REVIEW,
                "artifacts": item.artifacts + artifacts,
                "optimization_iterations": iterations,
                "events": item.events + [AgentEvent(
                    agent="solidworks_adapter",
                    action="solidworks_execution_completed" if result.status == "ok" else "solidworks_execution_failed",
                    state=PipelineState.SOLIDWORKS_DONE if result.status == "ok" else PipelineState.OPTIMIZATION_REVIEW,
                    detail={
                        "iteration": iteration_num,
                        "status": result.status,
                        "error": result.error,
                    },
                )],
            })
            self.runtime._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def accept_optimization(
        self, pipeline_id: UUID, *, accepted: bool, reviewed_by: str
    ) -> AgentPipeline:
        """用户接受或拒绝优化结果。"""
        with self.runtime._lock:
            item = self.runtime._require(pipeline_id)
            if item.state not in {PipelineState.SOLIDWORKS_DONE, PipelineState.OPTIMIZATION_REVIEW}:
                raise PipelineGateError("当前状态不允许接受优化")
            state = PipelineState.COMPLETED if accepted else PipelineState.REJECTED
            updated = item.model_copy(update={
                "state": state,
                "revision": item.revision + 1,
                "events": item.events + [AgentEvent(
                    agent="human_review_gate",
                    action="optimization_accepted" if accepted else "optimization_rejected",
                    state=state,
                    detail={"reviewed_by": reviewed_by},
                )],
            })
            self.runtime._save_pipeline(updated)
            return updated.model_copy(deep=True)

    # ── LLM Agent 调用 ──

    async def _run_planning_agent(
        self, pipeline: AgentPipeline, feedback: OptimizationFeedback
    ) -> OptimizationPlan:
        """调用 optimization_planning_agent 解析反馈。"""
        agent = self.registry.get("optimization_planning_agent")
        prompt = self.registry.prompts.get(agent.prompt_id)

        source_artifact = _find_source_artifact(pipeline.artifacts)
        source_format = "step"
        if source_artifact:
            if source_artifact.fidelity == "concept_mesh":
                source_format = "glb"
            elif source_artifact.fidelity in ("optimized_cad", "engineering_proxy"):
                source_format = "step"

        payload = _FeedbackPayload(
            feedback_text=feedback.feedback_text,
            target_component_id=feedback.target_component_id,
            current_specification=(
                pipeline.specification.model_dump(mode="json")
                if pipeline.specification else {}
            ),
            current_artifacts=[a.model_dump(mode="json") for a in pipeline.artifacts],
            iteration=feedback.iteration,
            source_artifact_id=source_artifact.id if source_artifact else "",
            source_format=source_format,
        )

        async def governed_provider(model, prompt_text, governed_payload):
            response = await self.client.create_response(
                model=model,
                instructions=prompt_text,
                input_data=[{
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": json.dumps(governed_payload, ensure_ascii=False),
                    }],
                }],
                metadata={
                    "purpose": _OPTIMIZATION_PLANNING_PURPOSE,
                    "agent_id": agent.id,
                    "agent_version": agent.version,
                    "prompt_id": prompt.id,
                    "prompt_hash": prompt.sha256,
                },
            )
            return OpenAIModelsClient.extract_json_object(response)

        self._execution_service = AgentExecutionService(
            self.registry,
            governed_provider,
            tools=build_default_tool_adapters(),
            quality_gates=build_default_quality_gates(),
        )
        output = await self._execution_service.execute(
            agent.id,
            payload,
            ExecutionContext(
                project_id=str(pipeline.id),
                pipeline_id=pipeline.id,
            ),
        )
        return OptimizationPlan.model_validate(output)


# ── 辅助函数 ──

def _find_iteration_index(iterations: list[dict], iteration_num: int) -> int | None:
    """在序列化后的迭代列表中查找指定迭代的索引。"""
    for i, it in enumerate(iterations):
        if isinstance(it, dict) and it.get("iteration") == iteration_num:
            return i
    return None


def _find_source_artifact(artifacts: list[PipelineArtifact]) -> PipelineArtifact | None:
    """从产物列表中查找最新的可用源模型。"""
    for a in reversed(artifacts):
        if a.fidelity in ("concept_mesh", "engineering_proxy", "optimized_cad"):
            return a
    return None

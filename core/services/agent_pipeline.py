"""数据手册、工程几何与 Hyper3D 之间的可审计 Agent 编排运行时。"""
from __future__ import annotations

from pathlib import Path
from threading import RLock
from uuid import UUID

from pydantic import RootModel

from core.agents import AgentRegistry, build_agent_registry
from core.agents.contracts import ExecutionContext
from core.agents.execution import (
    AgentExecutionService,
    build_default_quality_gates,
    build_default_tool_adapters,
)
from core.config import PROJECT_ROOT, Settings, get_settings
from core.persistence import DocumentNotFoundError, SQLiteDocumentStore
from core.models.agent_pipeline import (
    AgentEvent,
    AgentPipeline,
    CreatePipelineRequest,
    EngineeringSpecification,
    FrontendPipelineManifest,
    Hyper3DGenerationContract,
    PipelineArtifact,
    PipelineState,
    PipelineStatus,
    SpecificationExtractionResult,
    ValidationReport,
)
from core.providers.openai_models import OpenAIModelsClient
from core.services.provenance import ProvenanceCompletionReport


SPECIFICATION_EXTRACTION_PURPOSE = "engineering_specification_extraction"


class SpecificationSourceContents(RootModel[dict[str, str]]):
    pass


class SpecificationExtractionService:
    def __init__(
        self,
        settings: Settings,
        client: OpenAIModelsClient,
        registry: AgentRegistry | None = None,
    ):
        self.settings = settings
        self.client = client
        self.registry = registry or build_agent_registry(settings)
        self.agent = self.registry.get("specification_agent")
        self.prompt = self.registry.prompts.get(self.agent.prompt_id)

    async def extract(
        self,
        pipeline: AgentPipeline,
        source_contents: dict[str, str],
    ) -> SpecificationExtractionResult:
        source_by_id = {source.id: source for source in pipeline.sources}
        inputs: list[dict[str, object]] = []
        for source_id, content in source_contents.items():
            source = source_by_id.get(source_id)
            if source is None:
                raise PipelineConflictError(f"source {source_id} 不属于当前 pipeline")
            inputs.append({
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": f"来源 ID: {source_id}\n文件名: {source.filename}\n媒体类型: {source.media_type or 'unknown'}\n内容:\n{content}",
                }],
            })
        if not inputs:
            raise PipelineConflictError("规格提取至少需要一项 source_contents")

        async def governed_provider(
            model: str,
            prompt: str,
            governed_payload: dict[str, object],
        ) -> dict[str, object]:
            response = await self.client.create_response(
                model=model,
                instructions=prompt,
                input_data=inputs,
                metadata={
                    "purpose": SPECIFICATION_EXTRACTION_PURPOSE,
                    "agent_id": self.agent.id,
                    "agent_version": self.agent.version,
                    "prompt_id": self.prompt.id,
                    "prompt_hash": self.prompt.sha256,
                },
            )
            return OpenAIModelsClient.extract_json_object(response)

        self.execution_service = AgentExecutionService(
            self.registry,
            governed_provider,
            tools=build_default_tool_adapters(),
            quality_gates=build_default_quality_gates(),
        )
        output = await self.execution_service.execute(
            self.agent.id,
            SpecificationSourceContents(source_contents),
            ExecutionContext(project_id=str(pipeline.id), pipeline_id=pipeline.id),
        )
        return SpecificationExtractionResult.model_validate(output)


class PipelineNotFoundError(LookupError):
    pass


class PipelineConflictError(ValueError):
    pass


class PipelineGateError(PermissionError):
    pass


class AgentPipelineRuntime:
    def __init__(self, store: SQLiteDocumentStore | None = None) -> None:
        settings = get_settings()
        if store is None and settings.is_real:
            configured = Path(settings.database_path)
            store = SQLiteDocumentStore(configured if configured.is_absolute() else PROJECT_ROOT / configured)
        self._store = store
        self._items: dict[UUID, AgentPipeline] = {}
        self._lock = RLock()

    def create(self, request: CreatePipelineRequest) -> AgentPipeline:
        pipeline = AgentPipeline(
            sources=request.sources,
            events=[AgentEvent(agent="intake_agent", action="sources_ingested", state=PipelineState.INGESTED, detail={"product_name": request.product_name, "initial_requirements": request.initial_requirements})],
        )
        with self._lock:
            self._save_pipeline(pipeline)
        return pipeline.model_copy(deep=True)

    def get(self, pipeline_id: UUID) -> AgentPipeline:
        with self._lock:
            if self._store is not None:
                try:
                    return AgentPipeline.model_validate(self._store.get("agent_pipeline", str(pipeline_id)))
                except DocumentNotFoundError as exc:
                    raise PipelineNotFoundError(str(exc)) from exc
            item = self._items.get(pipeline_id)
            if item is None:
                raise PipelineNotFoundError(f"pipeline {pipeline_id} 不存在")
            return item.model_copy(deep=True)

    def record_extracted_specification(
        self,
        pipeline_id: UUID,
        result: SpecificationExtractionResult,
        *,
        agent_definition,
        prompt_definition,
    ) -> AgentPipeline:
        with self._lock:
            item = self._require(pipeline_id)
            if item.state not in {PipelineState.INGESTED, PipelineState.SPEC_REVIEW}:
                raise PipelineConflictError(f"当前状态 {item.state} 不允许提取规格")
            updated = item.model_copy(update={
                "state": PipelineState.SPEC_REVIEW,
                "specification": result.specification,
                "component_semantic_candidates": result.component_semantic_candidates,
                "revision": item.revision + 1,
                "events": item.events + [AgentEvent(
                    agent=agent_definition.id,
                    agent_version=agent_definition.version,
                    prompt_id=prompt_definition.id,
                    prompt_hash=prompt_definition.sha256,
                    model=agent_definition.model,
                    skills=list(agent_definition.skills),
                    tools=list(agent_definition.tools),
                    action="specification_extracted",
                    state=PipelineState.SPEC_REVIEW,
                    detail={
                        "provider": "openai",
                        "purpose": SPECIFICATION_EXTRACTION_PURPOSE,
                        "unresolved": result.specification.unresolved,
                    },
                )],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def propose_specification(self, pipeline_id: UUID, specification: EngineeringSpecification) -> AgentPipeline:
        with self._lock:
            item = self._require(pipeline_id)
            if item.state not in {PipelineState.INGESTED, PipelineState.SPEC_REVIEW}:
                raise PipelineConflictError(f"当前状态 {item.state} 不允许提交规格")
            updated = item.model_copy(update={
                "state": PipelineState.SPEC_REVIEW,
                "specification": specification,
                "revision": item.revision + 1,
                "events": item.events + [AgentEvent(agent="specification_agent", action="specification_proposed", state=PipelineState.SPEC_REVIEW, detail={"unresolved": specification.unresolved})],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def review_specification(self, pipeline_id: UUID, *, accepted: bool, reviewed_by: str, expected_revision: int) -> AgentPipeline:
        with self._lock:
            item = self._require(pipeline_id)
            if item.revision != expected_revision:
                raise PipelineConflictError(f"pipeline revision 已是 {item.revision}，不是 {expected_revision}")
            if item.state != PipelineState.SPEC_REVIEW or item.specification is None:
                raise PipelineGateError("必须先生成待审核的工程规格")
            state = PipelineState.SPEC_CONFIRMED if accepted else PipelineState.REJECTED
            specification = item.specification
            if accepted:
                specification = specification.model_copy(update={"revision": specification.revision + 1})
            updated = item.model_copy(update={
                "state": state,
                "specification": specification,
                "revision": item.revision + 1,
                "events": item.events + [AgentEvent(agent="human_review_gate", action="accepted" if accepted else "rejected", state=state, detail={"reviewed_by": reviewed_by})],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def register_geometry(self, pipeline_id: UUID, artifacts: list[PipelineArtifact]) -> AgentPipeline:
        with self._lock:
            item = self._require(pipeline_id)
            if item.state != PipelineState.SPEC_CONFIRMED:
                raise PipelineGateError("工程规格经人工确认后才能生成确定性几何")
            if not any(asset.fidelity == "engineering_proxy" for asset in artifacts):
                raise PipelineGateError("缺少 engineering_proxy 几何")
            updated = item.model_copy(update={
                "state": PipelineState.GEOMETRY_READY,
                "artifacts": item.artifacts + artifacts,
                "events": item.events + [AgentEvent(agent="geometry_agent", action="engineering_geometry_registered", state=PipelineState.GEOMETRY_READY)],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def compile_hyper3d(self, pipeline_id: UUID) -> AgentPipeline:
        with self._lock:
            item = self._require(pipeline_id)
            if item.state != PipelineState.GEOMETRY_READY or item.specification is None:
                raise PipelineGateError("必须先完成已确认规格对应的工程代理几何")
            renders = [asset.id for asset in item.artifacts if asset.role == "reference_render"][:5]
            if not renders:
                raise PipelineGateError("至少需要一张由工程代理模型渲染的参考图")
            spec = item.specification
            categories = ", ".join(component.category for component in spec.components) or "robot arm components"
            prompt = (
                f"Mechanically plausible {spec.product_name}. Preserve the supplied engineering-proxy multi-view proportions. "
                f"Visible component regions: {categories}. Create coherent printable protective shell surfaces with assembly seams, "
                "service panels, cable routing and realistic joint clearances. No floating parts, no text, no invented interfaces."
            )
            contract = Hyper3DGenerationContract(prompt=prompt, image_asset_ids=renders, bbox_condition=spec.overall_bbox_mm)
            updated = item.model_copy(update={
                "state": PipelineState.HYPER3D_READY,
                "hyper3d_contract": contract,
                "events": item.events + [AgentEvent(agent="hyper3d_compiler_agent", action="rodin_contract_compiled", state=PipelineState.HYPER3D_READY, detail={"image_count": len(renders)})],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def mark_hyper3d_submitted(self, pipeline_id: UUID, task_uuid: str) -> AgentPipeline:
        with self._lock:
            item = self._require(pipeline_id)
            if item.state != PipelineState.HYPER3D_READY:
                raise PipelineGateError("Hyper3D 请求契约尚未准备完成")
            updated = item.model_copy(update={
                "state": PipelineState.HYPER3D_SUBMITTED,
                "hyper3d_task_uuid": task_uuid,
                "events": item.events + [AgentEvent(agent="hyper3d_agent", action="rodin_submitted", state=PipelineState.HYPER3D_SUBMITTED, detail={"task_uuid": task_uuid})],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def register_hyper3d_result(self, pipeline_id: UUID, task_uuid: str, artifacts: list[PipelineArtifact]) -> AgentPipeline:
        with self._lock:
            item = self._require(pipeline_id)
            if item.state != PipelineState.HYPER3D_SUBMITTED or item.hyper3d_task_uuid != task_uuid:
                raise PipelineGateError("Hyper3D task UUID 与已提交任务不匹配")
            if not any(asset.provider == "hyper3d" and asset.fidelity == "concept_mesh" for asset in artifacts):
                raise PipelineGateError("结果必须包含 Hyper3D concept_mesh")
            updated = item.model_copy(update={
                "state": PipelineState.HYPER3D_DONE,
                "artifacts": item.artifacts + artifacts,
                "events": item.events + [AgentEvent(agent="hyper3d_agent", action="rodin_assets_registered", state=PipelineState.HYPER3D_DONE, detail={"task_uuid": task_uuid})],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def submit_validation(self, pipeline_id: UUID, report: ValidationReport) -> AgentPipeline:
        with self._lock:
            item = self._require(pipeline_id)
            if item.state != PipelineState.HYPER3D_DONE:
                raise PipelineGateError("必须先登记 Hyper3D 返回资产")
            state = PipelineState.COMPLETED if report.passed else PipelineState.VALIDATION_REVIEW
            updated = item.model_copy(update={
                "state": state,
                "validation": report,
                "events": item.events + [AgentEvent(agent="validation_agent", action="validation_passed" if report.passed else "validation_requires_review", state=state, detail=report.model_dump())],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def complete_with_provenance(
        self, pipeline_id: UUID, report: ProvenanceCompletionReport
    ) -> AgentPipeline:
        """The sole production completion transition; report is created server-side."""
        with self._lock:
            item = self._require(pipeline_id)
            if report.pipeline_id != pipeline_id or report.pipeline_revision != item.revision:
                raise PipelineGateError("provenance report does not match the current pipeline revision")
            if item.state != PipelineState.HYPER3D_DONE:
                raise PipelineGateError("pipeline is not ready for provenance completion")
            validation = ValidationReport(
                passed=True,
                findings=[f"provenance:{report.chain_hash}"],
            )
            updated = item.model_copy(update={
                "state": PipelineState.COMPLETED,
                "revision": item.revision + 1,
                "validation": validation,
                "events": item.events + [AgentEvent(
                    agent="provenance_completion_gate",
                    action="provenance_chain_verified",
                    state=PipelineState.COMPLETED,
                    detail={"chain_hash": report.chain_hash},
                )],
            })
            self._save_pipeline(updated)
            return updated.model_copy(deep=True)

    def status(self, pipeline_id: UUID) -> PipelineStatus:
        item = self.get(pipeline_id)
        return PipelineStatus(
            id=item.id,
            state=item.state,
            revision=item.revision,
            ready_for_hyper3d=item.state == PipelineState.HYPER3D_READY,
            hyper3d_task_uuid=item.hyper3d_task_uuid,
            validation_passed=item.validation.passed if item.validation is not None else None,
        )

    def frontend_manifest(self, pipeline_id: UUID) -> FrontendPipelineManifest:
        item = self.get(pipeline_id)
        if item.specification is None:
            raise PipelineGateError("工程规格尚未生成，无法输出前端 Manifest")
        return FrontendPipelineManifest(
            pipeline_id=item.id,
            revision=item.revision,
            state=item.state,
            product_name=item.specification.product_name,
            engineering_proxy=[asset for asset in item.artifacts if asset.fidelity == "engineering_proxy"],
            reference_renders=[asset for asset in item.artifacts if asset.role == "reference_render"],
            concept_meshes=[asset for asset in item.artifacts if asset.fidelity == "concept_mesh"],
            validation=item.validation,
        )

    def _require(self, pipeline_id: UUID) -> AgentPipeline:
        if self._store is not None:
            return self.get(pipeline_id)
        item = self._items.get(pipeline_id)
        if item is None:
            raise PipelineNotFoundError(f"pipeline {pipeline_id} 不存在")
        return item

    def _save_pipeline(self, pipeline: AgentPipeline) -> None:
        if self._store is not None:
            self._store.put_next("agent_pipeline", str(pipeline.id), pipeline.model_dump(mode="json"))
            return
        self._items[pipeline.id] = pipeline

"""ThermalForge 内置 Agent 定义。"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from core.agents.contracts import AgentDefinition, PromptDefinition, QualityGate, RetryPolicy, SkillDefinition, ToolDefinition
from core.agents.registry import AgentRegistry, PromptRegistry, SkillRegistry
from core.config import Settings
from core.models.agent_pipeline import EngineeringSpecification, Hyper3DGenerationContract, SpecificationExtractionResult, ValidationReport
from core.models.optimization import OptimizationPlan, SolidWorksOptimizationContract


def _prompt(prompt_id: str, template: str) -> PromptDefinition:
    return PromptDefinition(id=prompt_id, version="1.0.0", template=template, sha256=sha256(template.encode("utf-8")).hexdigest())


PROMPTS = (
    _prompt("specification_extraction.v1", "你是工程规格抽取 Agent。仅根据所给资料抽取信息，不确定项写入 unresolved，不得臆造。返回严格 JSON，结构必须符合 SpecificationExtractionResult：包含 specification 和 component_semantic_candidates。"),
    _prompt("hyper3d_compilation.v1", "将已确认工程规格编译为严格 Hyper3DGenerationContract，不得提交外部任务。"),
    _prompt("component_analysis.v1", "分析组件语义、材料和接口；证据不足时明确标记待审核。"),
    _prompt("simulation_planning.v1", "根据已确认规格制定可复现仿真计划，不执行 shell 或外部网络请求。"),
    _prompt("result_interpretation.v1", "解释仿真结果并输出验证报告，不得修改原始结果。"),
    _prompt("optimization_planning.v1", "你是模型优化规划 Agent。根据用户对 3D 模型的自然语言反馈，结合当前工程规格与模型产物信息，解析为结构化 OptimizationPlan。每个指令必须包含 operation_type（枚举：modify_dimension, add_feature, remove_feature, add_fillet, add_chamfer, thicken_wall, add_hole, add_cooling_fin, modify_sketch, change_appearance）、target_component、parameters 和 rationale。不得臆造模型中不存在的组件；不确定时写入 assumptions。返回严格 JSON，结构必须符合 OptimizationPlan。"),
    _prompt("solidworks_compilation.v1", "将已确认的 OptimizationPlan 编译为严格 SolidWorksOptimizationContract，确保 operations 中的参数可直接映射到 SolidWorks COM API 调用。不得提交外部任务。"),
)

SKILLS = (
    SkillDefinition(id="specification_extraction", version="1.0.0", description="从工程资料抽取带证据的规格"),
    SkillDefinition(id="hyper3d_contract_compilation", version="1.0.0", description="编译 Hyper3D 请求契约"),
    SkillDefinition(id="component_semantic_analysis", version="1.0.0", description="分析组件语义与接口"),
    SkillDefinition(id="simulation_planning", version="1.0.0", description="规划确定性工程仿真"),
    SkillDefinition(id="result_interpretation", version="1.0.0", description="解释仿真与验证结果"),
    SkillDefinition(id="optimization_planning", version="1.0.0", description="将自然语言反馈解析为结构化优化指令"),
    SkillDefinition(id="solidworks_contract_compilation", version="1.0.0", description="编译 SolidWorks 优化执行契约"),
)

TOOLS = (
    ToolDefinition(id="source_content_reader", description="读取调用方提供的来源内容"),
    ToolDefinition(id="engineering_schema_reader", description="读取已确认工程规格"),
    ToolDefinition(id="simulation_result_reader", description="读取调用方提供的仿真结果"),
    ToolDefinition(id="optimization_feedback_reader", description="读取用户提交的优化反馈与当前模型信息"),
    ToolDefinition(id="optimization_plan_reader", description="读取已确认的优化计划"),
)


def _schema(model: type[Any]) -> dict[str, Any]:
    return model.model_json_schema()


def build_agent_registry(settings: Settings) -> AgentRegistry:
    prompts = PromptRegistry(PROMPTS)
    skills = SkillRegistry(SKILLS)
    common_denied = ()
    definitions = (
        AgentDefinition(id="specification_agent", version="1.0.0", model=settings.openai_text_model, role="工程规格抽取", prompt_id="specification_extraction.v1", input_schema={"type": "object", "additionalProperties": {"type": "string"}}, output_schema=_schema(SpecificationExtractionResult), skills=("specification_extraction",), tools=("source_content_reader",), permissions=common_denied, quality_gates=(QualityGate(id="strict_output", description="输出通过 SpecificationExtractionResult 严格校验"), QualityGate(id="evidence_only", description="不得臆造来源中不存在的事实")), retry_policy=RetryPolicy(max_attempts=2, retryable_errors=("invalid_json",))),
        AgentDefinition(id="hyper3d_compiler_agent", version="1.0.0", model=settings.openai_text_model, role="Hyper3D 契约编译", prompt_id="hyper3d_compilation.v1", input_schema=_schema(EngineeringSpecification), output_schema=_schema(Hyper3DGenerationContract), skills=("hyper3d_contract_compilation",), tools=("engineering_schema_reader",), permissions=common_denied, quality_gates=(QualityGate(id="confirmed_spec", description="仅使用已确认工程规格"),)),
        AgentDefinition(id="component_analysis_agent", version="1.0.0", model=settings.openai_text_model, role="组件语义分析", prompt_id="component_analysis.v1", input_schema=_schema(EngineeringSpecification), output_schema={"type": "array", "items": {"type": "object"}}, skills=("component_semantic_analysis",), tools=("engineering_schema_reader",), permissions=common_denied),
        AgentDefinition(id="simulation_planner_agent", version="1.0.0", model=settings.openai_text_model, role="仿真规划", prompt_id="simulation_planning.v1", input_schema=_schema(EngineeringSpecification), output_schema={"type": "object"}, skills=("simulation_planning",), tools=("engineering_schema_reader",), permissions=common_denied, quality_gates=(QualityGate(id="reproducible", description="计划必须包含可复现输入"),)),
        AgentDefinition(id="result_interpreter_agent", version="1.0.0", model=settings.openai_text_model, role="结果解释", prompt_id="result_interpretation.v1", input_schema={"type": "object"}, output_schema=_schema(ValidationReport), skills=("result_interpretation",), tools=("simulation_result_reader",), permissions=common_denied),
        AgentDefinition(id="optimization_planning_agent", version="1.0.0", model=settings.openai_text_model, role="模型优化规划", prompt_id="optimization_planning.v1", input_schema={"type": "object", "properties": {"feedback_text": {"type": "string"}, "target_component_id": {"type": ["string", "null"]}, "current_specification": {"type": "object"}, "current_artifacts": {"type": "array"}, "iteration": {"type": "integer"}, "source_artifact_id": {"type": "string"}, "source_format": {"type": "string"}}, "required": ["feedback_text", "iteration"]}, output_schema=_schema(OptimizationPlan), skills=("optimization_planning",), tools=("optimization_feedback_reader",), permissions=common_denied, quality_gates=(QualityGate(id="strict_output", description="输出通过 OptimizationPlan 严格校验"), QualityGate(id="feasibility_check", description="指令不得引用模型中不存在的组件")), retry_policy=RetryPolicy(max_attempts=2, retryable_errors=("invalid_json",))),
        AgentDefinition(id="solidworks_compiler_agent", version="1.0.0", model=settings.openai_text_model, role="SolidWorks 契约编译", prompt_id="solidworks_compilation.v1", input_schema=_schema(OptimizationPlan), output_schema=_schema(SolidWorksOptimizationContract), skills=("solidworks_contract_compilation",), tools=("optimization_plan_reader",), permissions=common_denied, quality_gates=(QualityGate(id="confirmed_plan", description="仅使用已确认优化计划"),)),
    )
    return AgentRegistry(settings, prompts, skills, TOOLS, definitions)

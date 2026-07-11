"""项目数据模型 — 3D 结构创作系统的顶层容器。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectStatus:
    created = "created"
    parsing = "parsing"
    parsed = "parsed"
    generating = "generating"
    generated = "generated"
    decomposed = "decomposed"
    analyzed = "analyzed"
    completed = "completed"


class ProjectInputs(BaseModel):
    pdf_filename: str | None = None
    pdf_extracted_text: str | None = None
    text_description: str = ""
    structure_images: list[str] = Field(default_factory=list)


class ModelAsset(BaseModel):
    id: str
    type: Literal["whole", "decomposed"] = "whole"
    format: Literal["glb", "obj"] = "glb"
    url: str
    source: Literal["hyper3d", "hyper3d_bang", "uploaded", "solidworks"] = "uploaded"
    fidelity: str = "concept_mesh"
    filename: str = ""


class AgentStepStatus(BaseModel):
    id: str
    label: str
    status: Literal["pending", "running", "done", "failed"] = "pending"
    agent_id: str | None = None
    detail: str = ""


class ComponentSummary(BaseModel):
    id: str
    name: str
    display_name: str = ""
    semantic_type: str = "unknown"
    face_count: int = 0
    vertex_count: int = 0
    description: str = ""
    design_rationale: str = ""
    thermal_role: str = ""
    aesthetics_note: str = ""
    model_spec: str = ""
    confidence: str = ""


class Project(BaseModel):
    id: str
    name: str
    created_at: str
    status: str = ProjectStatus.created
    inputs: ProjectInputs = Field(default_factory=ProjectInputs)
    engineering_state_id: str | None = None
    model_assets: list[ModelAsset] = Field(default_factory=list)
    components: list[ComponentSummary] = Field(default_factory=list)
    steps: list[AgentStepStatus] = Field(default_factory=list)
    description: str = ""

    def default_steps(self) -> list[AgentStepStatus]:
        return [
            AgentStepStatus(id="parse", label="输入解析", agent_id="specification_agent"),
            AgentStepStatus(id="image_prompts", label="多视图提示词", agent_id="foc_arm_multiview_prompt_agent"),
            AgentStepStatus(id="image_generation", label="图片生成"),
            AgentStepStatus(id="model_creation", label="3D 模型创作"),
            AgentStepStatus(id="decomposition", label="Bang 分件"),
            AgentStepStatus(id="component_analysis", label="组件语义分析", agent_id="component_analysis_agent"),
            AgentStepStatus(id="component_explanation", label="组件说明生成"),
        ]

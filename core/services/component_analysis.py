"""Bang 下载文件标准化与组件分析服务。"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, Field

from core.models.components import (
    ComponentAsset,
    ComponentManifest,
    ComponentRecord,
    GeometrySummary,
    MaterialCandidate,
)
from core.providers.openai_models import OpenAIModelsClient
from core.services.component_prompt import SYSTEM_INSTRUCTIONS, compile_component_input


class ComponentAnalysisRequest(BaseModel):
    decomposition_task_uuid: str = Field(min_length=1)
    strength: int = Field(default=6, ge=2, le=12)
    source_model_url: str | None = None
    files: list[ComponentAsset]
    geometry_by_filename: dict[str, GeometrySummary] = Field(default_factory=dict)
    engineering_brief: dict[str, Any] = Field(default_factory=dict)
    use_ai: bool = False


class ComponentAnalyzer:
    def __init__(self, openai_client: OpenAIModelsClient | None = None):
        self.openai_client = openai_client

    async def analyze(self, request: ComponentAnalysisRequest) -> ComponentManifest:
        components: list[ComponentRecord] = []
        for index, asset in enumerate(request.files):
            geometry = request.geometry_by_filename.get(asset.filename, GeometrySummary())
            if request.use_ai:
                if not self.openai_client:
                    raise ValueError("use_ai=true 时必须配置 OpenAI client")
                component = await self._analyze_with_ai(index, asset, geometry, request.engineering_brief)
            else:
                component = self._deterministic_proposal(index, asset, geometry)
            components.append(component)
        return ComponentManifest(
            decomposition_task_uuid=request.decomposition_task_uuid,
            source_model_url=request.source_model_url,
            strength=request.strength,
            components=components,
        )

    async def _analyze_with_ai(
        self,
        index: int,
        asset: ComponentAsset,
        geometry: GeometrySummary,
        brief: dict[str, Any],
    ) -> ComponentRecord:
        response = await self.openai_client.create_response(
            input_data=compile_component_input(
                part_index=index,
                geometry=geometry,
                engineering_brief=brief,
                image_urls=asset.preview_urls,
            ),
            instructions=SYSTEM_INSTRUCTIONS,
            metadata={"workflow": "thermalforge_component_analysis", "part_index": str(index)},
        )
        payload = self.openai_client.extract_json_object(response)
        payload.update({"source_part_index": index, "asset": asset, "geometry": geometry})
        return ComponentRecord.model_validate(payload)

    @staticmethod
    def _deterministic_proposal(
        index: int,
        asset: ComponentAsset,
        geometry: GeometrySummary,
    ) -> ComponentRecord:
        stem = PurePosixPath(asset.filename.replace("\\", "/")).stem
        return ComponentRecord(
            source_part_index=index,
            asset=asset,
            display_name=f"待识别组件 {index + 1}",
            semantic_type="unknown",
            alternative_types=[],
            geometry=geometry,
            material_candidates=[
                MaterialCandidate(
                    name="待工程确认",
                    confidence=0.0,
                    visual_evidence=[f"Bang 输出文件名: {stem}"],
                    engineering_basis=["需结合工程 Brief、尺寸、载荷和制造约束选材"],
                )
            ],
            recommended_material=None,
            thermal_role="待识别；不得仅凭分件序号推断热学作用。",
            structural_role="待识别；需检查装配位置、接触面和载荷路径。",
            manufacturing_processes=[],
            design_rationale=["当前仅完成几何分件，尚未形成可信工程语义。"],
            risks=["组件边界可能过分割或欠分割。", "概念网格无法证明真实材料和可制造性。"],
            validation_tasks=["渲染子模型前/顶/侧及等轴测视图并执行多模态识别。", "由工程师确认组件名称、边界和材料。"],
            confidence=0.0,
        )


def normalize_hyper3d_download(payload: dict[str, Any]) -> list[ComponentAsset]:
    """把 Hyper3D download.list 标准化为稳定的前端资产契约。"""
    files = payload.get("list")
    if not isinstance(files, list):
        raise ValueError("Hyper3D 下载响应缺少 list")
    assets: list[ComponentAsset] = []
    for item in files:
        if not isinstance(item, dict) or not item.get("url") or not item.get("name"):
            raise ValueError("Hyper3D 下载条目必须包含 url 和 name")
        filename = str(item["name"])
        suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lstrip(".").lower() or "unknown"
        assets.append(ComponentAsset(url=str(item["url"]), filename=filename, format=suffix))
    return assets

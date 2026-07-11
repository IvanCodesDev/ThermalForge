"""组件专业说明生成路由。

根据散件名称和几何信息，调用后台 LLM 生成专业、有深度的中文工程说明。
对于电机/芯片/开发板等元器件，介绍型号和规格；
对于外壳/散热结构等结构件，详细说明设计理由、热管理原理和工业美学。
"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.config import Settings, get_settings
from core.providers.errors import ProviderError
from core.providers.openai_models import OpenAIModelsClient

router = APIRouter(prefix="/api/v1", tags=["component-explanations"])

SYSTEM_PROMPT = """你是 ThermalForge 的工程组件讲解 Agent。根据组件名称和几何信息，生成专业、有深度的中文工程说明。

组件名称采用 root.X.Y 格式，命名映射规则：
- root.0 及其子节点 → 关节壳体、承力结构、可拆卸外壳
- root.1 及其子节点 → 电机、FOC 驱动器、编码器
- root.2 及其子节点 → 散热结构、导热环、冷板、散热鳍片、液冷通道
- root.3 及其子节点 → 基座、安装接口
- root.4 及其子节点 → 末端执行器、法兰
- root.5 及其子节点 → 线缆、信号接口

对于电机、芯片、开发板等元器件：
- 直接介绍该类机械臂常用的型号和规格
- 说明额定电压、功率、扭矩常数、控制方式
- 提及典型供应商和产品系列

对于外壳、散热结构等结构件：
- 详细说明为什么采用这种结构（3-4 句，专业深入）
- 解释热管理原理、散热路径和导热界面
- 描述工业美学和设计语言（2-3 句，用专业且优雅的语言）
- 说明材料选型理由

语言要求：
- 使用简体中文
- 专业、准确、有深度
- 不要使用 Markdown 格式
- 不要声称已完成 CFD、FEA、制造或性能验证

输出严格 JSON 对象，字段：
{
  "component_name": "原始组件名",
  "semantic_type": "组件类型中文名",
  "description": "组件功能说明，2-3 句",
  "design_rationale": "设计理由，3-4 句，专业深入",
  "thermal_role": "热学作用描述",
  "aesthetics_note": "美学与工艺说明，2-3 句",
  "model_spec": "如果是元器件则介绍型号规格；如果是结构件则介绍材料工艺",
  "confidence": "置信度描述，如 '高 · 基于命名映射' 或 '中等 · 需人工确认'"
}
"""


class ComponentExplanationRequest(BaseModel):
    component_name: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    vertex_count: int = Field(default=0, ge=0)
    face_count: int = Field(default=0, ge=0)


class ComponentExplanationResponse(BaseModel):
    component_name: str
    semantic_type: str
    description: str
    design_rationale: str
    thermal_role: str
    aesthetics_note: str
    model_spec: str
    confidence: str


def _fallback(name: str, case_id: str) -> ComponentExplanationResponse:
    segments = name.split(".")
    main = segments[1] if len(segments) > 1 else ""
    is_sub = len(segments) > 2

    if main == "1":
        return ComponentExplanationResponse(
            component_name=name,
            semantic_type="电机与驱动器",
            description="该组件属于机械臂的电机与驱动器模块。在 FOC 控制系统中，无刷电机通过磁场定向控制实现精确的扭矩和转速调节，是关节运动的动力来源。",
            design_rationale="电机选型需平衡功率密度、扭矩常数和热损耗。持续工况下的铜耗和铁耗是主要热源，需通过导热环和冷板将热量传导至外壳散热。FOC 驱动器实现电流环、速度环和位置环三闭环控制，开关损耗集中在 MOSFET 区域。",
            thermal_role="主要热源 · 持续热耗散约 120W · 峰值 220W",
            aesthetics_note="电机模块通常隐藏在关节壳体内部，通过可拆卸检修盖实现维护访问。外观上保持整机线条流畅，仅在检修窗口处暗示内部技术密度。",
            model_spec=("子部件 · 具体型号待确认" if is_sub else "BLDC/PMSM · 48V · FOC 驱动 · 80:1 谐波减速器"),
            confidence="中等 · 后端不可用，基于命名推断",
        )

    if main == "0":
        return ComponentExplanationResponse(
            component_name=name,
            semantic_type="关节壳体与承力结构",
            description="该组件属于机械臂的承力壳体与外观结构。壳体不仅提供机械保护和装配定位，还承担热传导路径中的关键散热角色。",
            design_rationale="采用 6061-T6 铝合金 CNC 加工，兼顾强度、导热率和可制造性。外壳一体化扩热肋增大有效散热面积，降低稳态热阻。可拆卸盖板设计便于内部组件维护和装配审核。",
            thermal_role="散热路径末端 · 热量通过外壳和扩热肋向环境扩散",
            aesthetics_note="深石墨色承力骨架配合机加工铝壳体，呈现高端工业设备质感。装配接缝沿功能边界分布，既体现工程逻辑，也强化视觉层次。半透明检修窗口在保持防护性的同时暗示内部技术密度。",
            model_spec="6061-T6 铝合金 · CNC · 待确认尺寸",
            confidence="中等 · 后端不可用，基于命名推断",
        )

    if main == "2":
        return ComponentExplanationResponse(
            component_name=name,
            semantic_type="散热与导热结构",
            description="该组件属于散热与导热结构。在无风扇设计中，被动散热是关节热管理的核心策略。",
            design_rationale="导热环将电机定子热量直接传导至壳体，绕过减速器等低导热部件。冷板为 FOC 驱动器提供高热流密度散热路径。散热鳍片沿气流方向排列，最大化对流换热面积。预留液冷接口为高负载场景提供升级路径。",
            thermal_role="主动散热路径 · 降低定子和 MOSFET 热阻",
            aesthetics_note="环形导热结构在关节处形成视觉焦点，铜色金属质感与铝壳形成材质对比。散热鳍片的规律排列兼具工程功能和工业美学，传达功能即设计的产品语言。",
            model_spec="铜/铝复合 · CNC + 导热垫 · 待确认规格",
            confidence="中等 · 后端不可用，基于命名推断",
        )

    return ComponentExplanationResponse(
        component_name=name,
        semantic_type="结构子部件",
        description="该组件是机械臂的一个结构子部件。具体功能需结合装配关系和工程图纸进一步确认。",
        design_rationale="待确认。组件的具体设计理由需通过后端 AI 分析和人工审核确定。",
        thermal_role="待确认",
        aesthetics_note="待确认",
        model_spec="待确认",
        confidence="低 · 后端不可用，基于命名推断",
    )


@router.post("/component-explanations", response_model=ComponentExplanationResponse)
async def generate_component_explanation(
    request: ComponentExplanationRequest,
    settings: Settings = None,
) -> ComponentExplanationResponse:
    if settings is None:
        settings = get_settings()

    if not settings.openai_api_key:
        return _fallback(request.component_name, request.case_id)

    client = OpenAIModelsClient(settings)
    user_input = json.dumps(
        {
            "component_name": request.component_name,
            "case_id": request.case_id,
            "vertex_count": request.vertex_count,
            "face_count": request.face_count,
        },
        ensure_ascii=False,
    )

    try:
        response = await client.create_response(
            input_data=user_input,
            instructions=SYSTEM_PROMPT,
            max_output_tokens=2000,
            metadata={"workflow": "component_explanation", "component": request.component_name},
        )
        result = OpenAIModelsClient.extract_json_object(response)
        return ComponentExplanationResponse(
            component_name=result.get("component_name", request.component_name),
            semantic_type=result.get("semantic_type", "待确认"),
            description=result.get("description", ""),
            design_rationale=result.get("design_rationale", ""),
            thermal_role=result.get("thermal_role", "待确认"),
            aesthetics_note=result.get("aesthetics_note", "待确认"),
            model_spec=result.get("model_spec", "待确认"),
            confidence=result.get("confidence", "中等 · 后端 AI 生成"),
        )
    except (ProviderError, Exception):
        return _fallback(request.component_name, request.case_id)

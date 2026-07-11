"""运行 FOC 机械臂关节热设计模拟，并保存完整、脱敏的后端输出。"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import Settings
from core.models.components import ComponentAsset, GeometrySummary
from core.providers.errors import ProviderError
from core.providers.hyper3d import Hyper3DClient
from core.providers.openai_models import OpenAIModelsClient
from core.services.component_analysis import ComponentAnalysisRequest, ComponentAnalyzer
from core.workbench.runtime import LocalWorkbenchRuntime

OUTPUT = ROOT / "outputs" / "foc_robot_arm_backend_output.json"

ENGINEERING_INPUT = """
设计一套基于 FOC 的六轴协作机械臂肘关节模组。关节内部包含 48V 永磁同步电机、FOC 驱动器、编码器和 80:1 谐波减速器。
持续机械输出约 350W，电机与功率器件持续热耗散按 120W 设计，短时峰值热耗散 220W。关节外包络 160 mm × 140 mm × 110 mm，环境温度 35°C，
电机绕组目标低于 100°C，MOSFET 壳温目标低于 85°C。关节外壳优先采用 6061-T6 铝合金 CNC 加工，整套散热结构质量不超过 850g。
无独立风扇，采用外壳一体化扩热肋、驱动板到底板导热垫、定子到壳体导热环；预留可选液冷环形流道，但第一版以自然对流加传导为主。
要求外壳、驱动器冷板/底板、导热环、减速器接口、密封盖和线缆接口可独立识别和审核。
""".strip()

RODIN_PROMPT = """
Engineering concept mesh of a compact FOC-controlled collaborative robot elbow joint thermal enclosure, 160 x 140 x 110 mm overall envelope. Cylindrical 6061 aluminum housing around a PMSM and harmonic reducer, integrated external heat spreading ribs, removable electronics cold plate/baseplate, stator thermal ring, sealed rear cover, cable gland and reducer mounting flange. Mechanically plausible assembly seams and fasteners, no random decorative parts, no labels, no text. Separate visible functional regions suitable for later component segmentation. Industrial product design, orthographic-consistent proportions, neutral studio background.
""".strip()


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


async def main() -> None:
    settings = Settings()
    runtime = LocalWorkbenchRuntime(ROOT / "data" / "seed_library.json")
    brief = runtime.extract_brief(ENGINEERING_INPUT)
    confirmed = runtime.confirm_brief(
        brief.id,
        accepted=True,
        confirmed_by="demo_scenario_owner",
        expected_revision=brief.revision,
    )
    evaluation = runtime.evaluate_brief(brief.id)

    openai = OpenAIModelsClient(settings)
    hyper3d = Hyper3DClient(settings)
    external: dict[str, Any] = {}

    try:
        llm = await openai.create_response(
            input_data=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "请把以下 FOC 机械臂关节工程输入整理为热设计决策摘要。"
                                "只输出一个 JSON 对象，字段为 architecture、heat_paths、components、materials、risks、validation_tasks。\n"
                                + ENGINEERING_INPUT
                            ),
                        }
                    ],
                }
            ],
            instructions="你是机械臂关节热设计工程师。区分明确输入、工程假设和待验证事项，不要声称已完成 CFD。",
            max_output_tokens=1800,
            metadata={"workflow": "foc_robot_arm_demo"},
        )
        external["gpt_5_6_sol"] = {"status": "success", "response": llm}
    except ProviderError as exc:
        external["gpt_5_6_sol"] = {
            "status": "failed",
            "error": {"provider": exc.provider, "message": exc.message, "details": exc.details},
        }

    rodin_response: dict[str, Any] | None = None
    try:
        rodin_response = await hyper3d.submit(
            prompt=RODIN_PROMPT,
            images=[],
            options={
                "tier": "Gen-2",
                "geometry_file_format": "glb",
                "material": "PBR",
                "mesh_mode": "Quad",
                "quality": "high",
                "preview_render": True,
            },
        )
        external["hyper3d_rodin"] = {"status": "submitted", "response": rodin_response}
    except ProviderError as exc:
        external["hyper3d_rodin"] = {
            "status": "failed",
            "error": {"provider": exc.provider, "message": exc.message, "details": exc.details},
        }

    proposed_assets = [
        ComponentAsset(url="pending://bang/part-0.glb", filename="part-0.glb", format="glb"),
        ComponentAsset(url="pending://bang/part-1.glb", filename="part-1.glb", format="glb"),
        ComponentAsset(url="pending://bang/part-2.glb", filename="part-2.glb", format="glb"),
    ]
    manifest = await ComponentAnalyzer().analyze(
        ComponentAnalysisRequest(
            decomposition_task_uuid="pending-until-rodin-done-and-bang-submitted",
            source_model_url=None,
            strength=5,
            files=proposed_assets,
            geometry_by_filename={
                "part-0.glb": GeometrySummary(bbox_mm=(160, 140, 110)),
                "part-1.glb": GeometrySummary(bbox_mm=(115, 80, 8)),
                "part-2.glb": GeometrySummary(bbox_mm=(92, 92, 12)),
            },
            engineering_brief=brief.model_dump(mode="json"),
            use_ai=False,
        )
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "FOC 六轴协作机械臂肘关节热设计",
        "configured_models": {
            "text_model": settings.openai_text_model,
            "openai_base_url": settings.openai_base_url,
            "hyper3d_base_url": settings.hyper3d_base_url,
            "credentials_present": {
                "openai": bool(settings.openai_api_key),
                "hyper3d": bool(settings.hyper3d_api_key),
            },
        },
        "engineering_input": ENGINEERING_INPUT,
        "engineering_brief": _serialize(brief),
        "confirmed_brief": _serialize(confirmed),
        "screening_evaluation": _serialize(evaluation),
        "concept_3d_prompt": RODIN_PROMPT,
        "external_calls": external,
        "component_manifest_before_bang_completion": _serialize(manifest),
        "next_async_steps": [
            "轮询 Rodin jobs.subscription_key，直到全部 Done。",
            "使用 Rodin 响应 uuid 调用 download 获取整体模型。",
            "使用同一个 Rodin uuid 作为 asset_id 提交 Bang。",
            "轮询 Bang jobs.subscription_key，完成后使用 Bang 响应 uuid 下载子模型。",
            "对子模型计算几何统计并渲染多视角，再调用 /api/v1/components/analyze?use_ai=true。",
            "人工确认组件边界、材料候选和装配关系后再进入 CAD/CFD/FEA 验证。",
        ],
        "disclaimers": [
            "screening_evaluation 为集总热模型，不是 CFD。",
            "Rodin/Bang 输出为概念网格，不是可制造 CAD。",
            "材料和组件语义需要人工确认。",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "external_status": {k: v["status"] for k, v in external.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

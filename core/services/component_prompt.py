"""组件多模态识别的结构化 Prompt 编译器。"""
from __future__ import annotations

import json
from typing import Any

from core.models.components import GeometrySummary


SYSTEM_INSTRUCTIONS = """你是 ThermalForge 的工程组件分析器。输入是概念网格子模型的多视角图片、几何统计和工程 Brief。请识别组件可能的工程语义，并严格区分视觉推测与已证实事实。不得把 PBR 外观当作真实工程材料证明。输出必须是单个 JSON 对象，不使用 Markdown。"""


def compile_component_input(
    *,
    part_index: int,
    geometry: GeometrySummary,
    engineering_brief: dict[str, Any],
    image_urls: list[str],
) -> list[dict[str, Any]]:
    schema = {
        "display_name": "中文组件名",
        "semantic_type": "housing|baseplate|channel_layer|interface|fastener|seal|heat_spreader|unknown",
        "alternative_types": ["备选类型"],
        "material_candidates": [
            {
                "name": "材料候选",
                "confidence": 0.0,
                "visual_evidence": ["仅可观察证据"],
                "engineering_basis": ["结合工况的选材依据"],
            }
        ],
        "recommended_material": "候选名称或 null",
        "thermal_role": "热学作用",
        "structural_role": "结构作用",
        "manufacturing_processes": ["可能工艺"],
        "design_rationale": ["为什么这样设计"],
        "risks": ["风险"],
        "validation_tasks": ["必须执行的验证"],
        "confidence": 0.0,
    }
    text = {
        "part_index": part_index,
        "geometry": geometry.model_dump(mode="json"),
        "engineering_brief": engineering_brief,
        "required_output_schema": schema,
        "rules": [
            "证据不足时 semantic_type 使用 unknown",
            "材料置信度不得因颜色或金属光泽单独超过 0.6",
            "设计理由必须关联热、结构、装配或制造约束",
            "validation_tasks 至少说明如何确认材料和组件身份",
        ],
    }
    content: list[dict[str, Any]] = [{"type": "input_text", "text": json.dumps(text, ensure_ascii=False)}]
    content.extend({"type": "input_image", "image_url": url} for url in image_urls)
    return [{"role": "user", "content": content}]

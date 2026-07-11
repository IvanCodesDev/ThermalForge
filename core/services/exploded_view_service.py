"""
Exploded view service: OBJ parsing, part classification, and LLM description generation.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Optional

from core.models.exploded_view import (
    ExplodedPart,
    ExplodedViewResult,
    PartCategory,
    PartDescription,
    PartGeometryInfo,
)
from core.providers.errors import ProviderError
from core.providers.openai_models import OpenAIModelsClient


# ---------------------------------------------------------------------------
# OBJ Parser
# ---------------------------------------------------------------------------

def parse_obj_file(obj_path: str | Path) -> list[dict]:
    """
    Parse a Wavefront OBJ file and extract per-object metadata.

    Returns a list of dicts with keys:
        obj_name, vertex_count, face_count,
        bbox_min, bbox_max, centroid, size, volume, dominant_axis
    """
    obj_path = Path(obj_path)
    if not obj_path.exists():
        raise FileNotFoundError(f"OBJ file not found: {obj_path}")

    parts: list[dict] = []
    current_name = "default"
    v_count = 0
    f_count = 0
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    cx = cy = cz = 0.0  # centroid accumulators
    started = False

    def _flush():
        nonlocal v_count, f_count, min_x, min_y, min_z, max_x, max_y, max_z, cx, cy, cz, started
        if not started:
            return
        dx = max_x - min_x
        dy = max_y - min_y
        dz = max_z - min_z
        vol = dx * dy * dz
        if v_count > 0:
            cx /= v_count
            cy /= v_count
            cz /= v_count
        # dominant axis
        if dx >= dy and dx >= dz:
            dom = "x"
        elif dy >= dx and dy >= dz:
            dom = "y"
        else:
            dom = "z"
        parts.append({
            "obj_name": current_name,
            "vertex_count": v_count,
            "face_count": f_count,
            "bbox_min": [min_x, min_y, min_z],
            "bbox_max": [max_x, max_y, max_z],
            "centroid": [cx, cy, cz],
            "size": [dx, dy, dz],
            "volume": vol,
            "dominant_axis": dom,
        })
        # reset
        v_count = 0
        f_count = 0
        min_x = min_y = min_z = float("inf")
        max_x = max_y = max_z = float("-inf")
        cx = cy = cz = 0.0
        started = False

    with open(obj_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("o "):
                _flush()
                current_name = line[2:].strip()
                started = True
            elif line.startswith("v "):
                parts_split = line.split()
                if len(parts_split) >= 4:
                    x = float(parts_split[1])
                    y = float(parts_split[2])
                    z = float(parts_split[3])
                    if x < min_x: min_x = x
                    if y < min_y: min_y = y
                    if z < min_z: min_z = z
                    if x > max_x: max_x = x
                    if y > max_y: max_y = y
                    if z > max_z: max_z = z
                    cx += x
                    cy += y
                    cz += z
                    v_count += 1
                    started = True
            elif line.startswith("f "):
                f_count += 1

    _flush()
    return parts


# ---------------------------------------------------------------------------
# Part Classification
# ---------------------------------------------------------------------------

# Robot arm part naming patterns (from Blender export tree structure)
# root.0.x.x.x → main body / arm segments
# root.1, root.2, ... → smaller components (gripper, sensors, cables)

def _classify_part(part_data: dict, index: int, total: int, all_parts: list[dict]) -> tuple[PartCategory, str, str]:
    """
    Classify a part based on geometry and naming heuristics.

    Returns (category, display_name, reason).
    """
    name = part_data["obj_name"]
    v_count = part_data["vertex_count"]
    vol = part_data["volume"]
    size = part_data["size"]
    centroid = part_data["centroid"]
    dom = part_data["dominant_axis"]

    # Sort all parts by volume to understand relative sizes
    vols_sorted = sorted([p["volume"] for p in all_parts])
    vol_rank = sum(1 for v in vols_sorted if v < vol)
    vol_percentile = vol_rank / max(len(vols_sorted), 1)

    # The two largest parts (root.0.0.0.0.0 and root.0.0.0.0.1) are the base/turntable
    if name in ("root.0.0.0.0.0", "root.0.0.0.0.1"):
        if name == "root.0.0.0.0.0":
            return (PartCategory.HOUSING, "底座外壳", "体积最大的部件，位于模型底部，为机械臂提供稳定支撑基座")
        else:
            return (PartCategory.HOUSING, "底座转台", "第二大部件，与底座外壳配合，实现基座旋转自由度")

    # root.0.0.0.1, root.0.0.0.2 — small parts near the base → base motors
    if name in ("root.0.0.0.1", "root.0.0.0.2"):
        return (PartCategory.MOTOR, f"基座伺服电机 IKI1602-{name.split('.')[-1]}", "位于底座区域的小型圆柱形部件，判断为基座旋转/俯仰电机")

    # root.0.0.1 through root.0.0.5 — arm link segments
    arm_idx = None
    if name.startswith("root.0.0.") and name.count(".") == 3:
        try:
            arm_idx = int(name.split(".")[-1])
        except ValueError:
            pass
    if arm_idx is not None and 1 <= arm_idx <= 5:
        return (PartCategory.STRUCTURAL, f"大臂连杆段 {arm_idx}", "机械臂大臂的连杆段，承担主臂的结构承载")

    # root.0.1 — large mid section → shoulder motor housing
    if name == "root.0.1":
        return (PartCategory.MOTOR, "肩部伺服电机 IKI1602-01", "位于大臂与底座连接处的电机，驱动肩部俯仰运动")

    # root.0.2.0 through root.0.2.3 — forearm segments
    forearm_idx = None
    if name.startswith("root.0.2.") and name.count(".") == 3:
        try:
            forearm_idx = int(name.split(".")[-1])
        except ValueError:
            pass
    if forearm_idx is not None and 0 <= forearm_idx <= 3:
        return (PartCategory.STRUCTURAL, f"小臂连杆段 {forearm_idx + 1}", "小臂连杆段，连接肘部到腕部")

    # root.0.3 through root.0.9 — joint motors and connectors
    if name.startswith("root.0.") and name.count(".") == 2:
        try:
            mid_idx = int(name.split(".")[-1])
        except ValueError:
            mid_idx = -1
        if mid_idx in (3, 4, 5):
            return (PartCategory.MOTOR, f"肘部伺服电机 IKI1602-{mid_idx:02d}", "肘部关节电机，驱动小臂弯曲运动")
        elif mid_idx in (6, 7):
            return (PartCategory.JOINT, f"腕部关节组件 {mid_idx - 5}", "腕部关节连接组件，实现末端多自由度旋转")
        elif mid_idx in (8, 9):
            return (PartCategory.MOTOR, f"腕部伺服电机 IKI1602-{mid_idx:02d}", "腕部微型电机，驱动末端执行器旋转")

    # root.0.10, root.0.11, root.0.12 — gripper area
    if name in ("root.0.10", "root.0.11", "root.0.12"):
        idx = int(name.split(".")[-1])
        if idx == 10:
            return (PartCategory.GRIPPER, "末端夹持器基座", "夹持器安装基座，连接腕部与夹爪")
        elif idx == 11:
            return (PartCategory.GRIPPER, "夹爪左指", "夹持器左侧夹爪，直接接触被抓取物体")
        else:
            return (PartCategory.GRIPPER, "夹爪右指", "夹持器右侧夹爪，与左指配合实现夹取动作")

    # root.1 through root.5 — smaller accessories
    if name in ("root.1", "root.2", "root.3", "root.4", "root.5"):
        idx = int(name.split(".")[-1])
        if idx == 1:
            return (PartCategory.ELECTRONIC, "主控板", "机械臂主控制器电路板，负责运动规划和电机驱动")
        elif idx == 2:
            return (PartCategory.CABLE, "线缆束", "电机驱动线缆束，连接控制器与各关节电机")
        elif idx == 3:
            return (PartCategory.SENSOR, "力矩传感器", "末端力矩传感器，提供力反馈用于精密操作")
        elif idx == 4:
            return (PartCategory.COOLING, "散热鳍片组", "电机散热鳍片组，增强持续工作时的热散逸能力")
        elif idx == 5:
            return (PartCategory.FASTENER, "紧固件组", "标准紧固件集合，包括螺栓、螺母和垫圈")

    # Fallback: classify by volume
    if vol_percentile > 0.8:
        return (PartCategory.STRUCTURAL, f"结构件 {index + 1}", "体积较大的结构件")
    elif vol_percentile < 0.2:
        return (PartCategory.FASTENER, f"小零件 {index + 1}", "体积较小的零件")
    else:
        return (PartCategory.UNKNOWN, f"部件 {index + 1}", "未分类部件")


def build_exploded_parts(parsed: list[dict]) -> list[ExplodedPart]:
    """Convert raw parsed data into ExplodedPart objects with classification."""
    parts: list[ExplodedPart] = []
    for i, pd in enumerate(parsed):
        category, display_name, reason = _classify_part(pd, i, len(parsed), parsed)
        geom = PartGeometryInfo(
            vertex_count=pd["vertex_count"],
            face_count=pd["face_count"],
            bounding_box_min=pd["bbox_min"],
            bounding_box_max=pd["bbox_max"],
            centroid=pd["centroid"],
            size=pd["size"],
            volume_estimate=pd["volume"],
            dominant_axis=pd["dominant_axis"],
        )
        parts.append(ExplodedPart(
            part_id=f"part-{i + 1:02d}",
            obj_name=pd["obj_name"],
            display_name=display_name,
            category=category,
            geometry=geom,
            classification_reason=reason,
            sort_order=i,
        ))
    return parts


# ---------------------------------------------------------------------------
# LLM Description Generator
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
你是 ThermalForge 的机械工程组件分析专家。你的任务是为机械臂的每个散装零件生成专业、详尽的中文描述。

## 规则

1. **电机类（motor）**：直接给出型号（如 IKI1602-XX），列出关键规格参数（扭矩、转速、电压、功率），简要说明其在机械臂中的位置和作用。不需要长篇设计说明。
2. **电子元器件类（electronic）**：给出型号或类型（如 STM32F407 主控板），说明功能和在系统中的作用。
3. **传感器类（sensor）**：给出型号，说明测量原理和安装位置。
4. **结构件/外壳/散热结构（structural/housing/cooling）**：需要详细说明：
   - 为什么采用这种结构设计（力学、热学、制造工艺角度）
   - 结构参数（壁厚、散热翅片间距等）
   - 美学性分析（造型语言、视觉平衡、工业设计考量）
   - 材料选择理由
   说得专业、漂亮、有深度。
5. **夹持器/关节/紧固件/线缆**：简要说明功能和设计要点。

## 输出格式

为每个零件输出一个 JSON 对象，放在一个 JSON 数组中。每个对象包含：
- part_id: 零件ID
- title: 标题（如"基座伺服电机 IKI1602-01"）
- subtitle: 一句话副标题
- model_number: 型号（电机/芯片/传感器才填，其他为null）
- summary: 一句话总结
- description: 详尽描述（结构件要长，电机/电子件可适中）
- design_rationale: 设计理由（仅结构件/外壳/散热件填写，其他为null）
- specifications: 规格参数字典（电机/电子件必填）
- aesthetic_notes: 美学分析（仅外壳/结构件/散热件填写）
- material: 推测材料

只输出 JSON 数组，不要其他内容。\
"""

def _build_parts_context(parts: list[ExplodedPart], model_context: str) -> str:
    """Build the text context describing all parts for the LLM."""
    lines = [f"模型背景: {model_context}", f"总零件数: {len(parts)}", "", "零件列表:"]
    for p in parts:
        g = p.geometry
        lines.append(f"""
--- {p.part_id} ---
OBJ名称: {p.obj_name}
显示名称: {p.display_name}
分类: {p.category.value}
分类理由: {p.classification_reason}
顶点数: {g.vertex_count}
面数: {g.face_count}
包围盒: [{g.bounding_box_min[0]:.3f}, {g.bounding_box_min[1]:.3f}, {g.bounding_box_min[2]:.3f}] → [{g.bounding_box_max[0]:.3f}, {g.bounding_box_max[1]:.3f}, {g.bounding_box_max[2]:.3f}]
尺寸: {g.size[0]:.3f} × {g.size[1]:.3f} × {g.size[2]:.3f}
质心: [{g.centroid[0]:.3f}, {g.centroid[1]:.3f}, {g.centroid[2]:.3f}]
体积(包围盒): {g.volume_estimate:.6f}
主轴: {g.dominant_axis}
""")
    return "\n".join(lines)


async def generate_descriptions(
    parts: list[ExplodedPart],
    client: OpenAIModelsClient,
    model_context: str = "六轴机械臂，使用 IKI1602 系列伺服电机",
) -> list[PartDescription]:
    """Generate LLM descriptions for all parts in a single batch call."""
    context = _build_parts_context(parts, model_context)

    payload_input = [
        {"type": "input_text", "text": context},
    ]

    resp = await client.create_response(
        input_data=payload_input,
        instructions=SYSTEM_PROMPT,
        model="gpt-5.6-sol",
        temperature=0.7,
        max_output_tokens=16000,
    )

    raw_text = ""
    if "output_text" in resp:
        raw_text = resp["output_text"]
    else:
        for item in resp.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    raw_text += content.get("text", "")

    # Extract JSON array from response
    raw_text = raw_text.strip()
    # Remove markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines)

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse LLM response as JSON: {raw_text[:500]}")
        else:
            raise ValueError(f"No JSON array found in LLM response: {raw_text[:500]}")

    descriptions: list[PartDescription] = []
    for item in data:
        part_id = item.get("part_id", "")
        # Find the corresponding part to get category
        part = next((p for p in parts if p.part_id == part_id), None)
        category = part.category if part else PartCategory.UNKNOWN

        desc = PartDescription(
            part_id=part_id,
            category=category,
            title=item.get("title", ""),
            subtitle=item.get("subtitle", ""),
            model_number=item.get("model_number"),
            summary=item.get("summary", ""),
            description=item.get("description", ""),
            design_rationale=item.get("design_rationale"),
            specifications=item.get("specifications", {}),
            aesthetic_notes=item.get("aesthetic_notes"),
            material=item.get("material"),
        )
        descriptions.append(desc)

    return descriptions


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

async def parse_and_describe(
    obj_path: str | Path,
    model_name: str,
    client: OpenAIModelsClient,
    model_context: str = "六轴机械臂，使用 IKI1602 系列伺服电机",
) -> ExplodedViewResult:
    """Full pipeline: parse OBJ → classify → generate descriptions."""
    parsed = parse_obj_file(obj_path)
    parts = build_exploded_parts(parsed)
    descriptions = await generate_descriptions(parts, client, model_context)

    return ExplodedViewResult(
        model_id=f"exploded-{model_name}",
        model_name=model_name,
        source_file=str(obj_path),
        total_parts=len(parts),
        parts=parts,
        descriptions=descriptions,
    )

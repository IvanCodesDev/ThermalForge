"""
ThermalForge 参数中枢编排（ParameterHub）

把「理解层 → 参数中枢 → 生成层」打通的核心契约对象：
- match_user_to_library(user_input, top_k)：用户意图向量 ↔ 库案例意图向量，余弦最近邻检索。
- recommend_structure(user_input)：按器件类型 / 介质 / 约束启发式，映射出结构模板参数（leaf_vein / channel / flat），
  作为长期 CadQuery 生成或短期匹配检索的入口。

依赖：
- core.models.user_input.UserInput（意图层）
- core.models.library.LibraryEntry（库条目层）
- core.engine.matcher.cosine（余弦相似度，与几何匹配共用同一工具）
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Tuple

from .models.user_input import UserInput
from .models.library import LibraryEntry
from .engine.matcher import cosine


class ParameterHub:
    """参数中枢：用户输入 ↔ 库案例 同空间匹配 + 意图→结构模板推荐。"""

    def __init__(self, entries: List[LibraryEntry]):
        self.entries = entries

    # ---- 加载 ----
    @classmethod
    def from_library_json(cls, path: Path) -> "ParameterHub":
        import json
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        # 兼容两种格式：纯 list，或 {"cases": [...]}（engine.matcher.Library 格式）
        if isinstance(raw, dict) and "cases" in raw:
            cases = raw["cases"]
        else:
            cases = raw
        entries = []
        for c in cases:
            # 旧格式（只有几何，无 device_context）→ 跳过或包成无上下文条目
            if "device_context" not in c:
                continue
            entries.append(LibraryEntry.from_dict(c))
        return cls(entries)

    # ---- 意图匹配 ----
    def match_user_to_library(self, user_input: UserInput, top_k: int = 3,
                              require_medium: bool = False) -> List[Tuple[LibraryEntry, float]]:
        """用户意图向量与库案例意图向量做余弦检索，返回 (条目, 相似度) 降序。"""
        q = user_input.to_vector()
        scored: List[Tuple[LibraryEntry, float]] = []
        for e in self.entries:
            if len(e.constraint_vector) != len(q):
                continue
            sim = cosine(q, e.constraint_vector)
            if require_medium and e.structure.get("cooling_medium") != user_input.preferred_medium():
                sim *= 0.85  # 介质不符轻微降权，不硬筛
            scored.append((e, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ---- 意图 → 结构模板推荐 ----
    def recommend_structure(self, user_input: UserInput) -> Dict[str, Any]:
        """按意图启发式推荐一个结构模板参数 dict（可直接喂 from_dict / /generate）。"""
        dt = user_input.device_type
        medium = user_input.preferred_medium()
        size = max(
            user_input.dimensions.get("length_mm", 0.0),
            user_input.dimensions.get("width_mm", 0.0),
            user_input.dimensions.get("outer_dia_mm", 0.0),
        ) or 60.0
        weight_sensitive = user_input.max_weight_g <= 40.0

        # 具身结构级（主攻）：关节电机 / 灵巧手 / MOSFET 驱动器
        if dt in ("关节电机", "灵巧手模组", "MOSFET/驱动器"):
            if medium == "liquid":
                return {
                    "structure_type": "channel",
                    "channel_pattern": "serpentine",
                    "cooling_medium": "liquid",
                    "length_scale": size,
                    "channel_length": size,
                    "channel_count": max(8, int(user_input.power_w // 2)),
                    "serpentine_turns": max(3, int(user_input.power_w // 4)),
                }
            # 气冷：轻量 → 叶脉扩散；不敏感 → pin-fin 弱气流
            if weight_sensitive:
                return {
                    "structure_type": "leaf_vein",
                    "vein_archetype": "fractal_tree",
                    "cooling_medium": "air",
                    "length_scale": size,
                    "branch_levels": 5 if user_input.power_w > 25 else 4,
                    "boundary_shape": "circle",
                }
            return {
                "structure_type": "channel",
                "channel_pattern": "pinfin",
                "cooling_medium": "air",
                "length_scale": size,
                "channel_count": max(20, int(user_input.power_w * 1.5)),
            }

        # 传感器舱（密闭难散热）→ 通风流道
        if dt == "传感器舱":
            return {
                "structure_type": "channel",
                "channel_pattern": "serpentine",
                "cooling_medium": "air",
                "length_scale": size,
                "channel_length": size,
                "serpentine_turns": 4,
            }

        # 无人机动力（电机 / 电调）：螺旋桨洗流强制风冷，重量极敏感
        if dt in ("无人机动力电机", "无人机电调"):
            if weight_sensitive:
                return {
                    "structure_type": "leaf_vein",
                    "vein_archetype": "fractal_tree",
                    "cooling_medium": "forced_air",
                    "length_scale": size,
                    "branch_levels": 5 if user_input.power_w > 200 else 4,
                    "boundary_shape": "circle",
                }
            return {
                "structure_type": "channel",
                "channel_pattern": "pinfin",
                "cooling_medium": "forced_air",
                "length_scale": size,
                "channel_count": max(30, int(user_input.power_w)),  # 约每 W 1 针
                "channel_height": 6,
                "boundary_shape": "circle",
            }

        # 工业变频器 / 小批量功率电子：气冷针翅或液冷冷板
        if dt == "工业变频器":
            if medium == "liquid":
                return {
                    "structure_type": "channel",
                    "channel_pattern": "parallel",
                    "cooling_medium": "liquid",
                    "length_scale": size,
                    "channel_length": size,
                    "channel_count": max(10, int(user_input.power_w // 2)),
                }
            return {
                "structure_type": "channel",
                "channel_pattern": "pinfin",
                "cooling_medium": "air",
                "length_scale": size,
                "channel_count": max(24, int(user_input.power_w)),
            }

        # 医疗激光 / 高功率光学模块：精密温控 → 液冷平行冷板
        if dt == "医疗激光模块":
            return {
                "structure_type": "channel",
                "channel_pattern": "parallel",
                "cooling_medium": "liquid",
                "length_scale": size,
                "channel_length": size,
                "channel_count": max(12, int(user_input.power_w // 2)),
            }

        # Jetson / 边缘计算盒（PCB 级，复用成熟方案打底）→ 平行液冷冷板
        # PRD：PCB 级复用成熟方案，不主攻；给一个标准冷板模板即可
        return {
            "structure_type": "channel",
            "channel_pattern": "parallel",
            "cooling_medium": "liquid",
            "length_scale": size,
            "channel_length": size,
            "channel_count": max(10, int(user_input.power_w // 2)),
        }

"""零依赖 STEP（ISO-10303-21 / AP214）解析器（特性一 · F1-P0-1）。

仅使用标准库 ``re`` + ``pathlib``，不引入 numpy / OCC / steputils。
解析 DATA 段重建实体图，抽取：

* ``CARTESIAN_POINT`` 全部坐标 → 包围盒 ``bbox_mm``；
* ``CYLINDRICAL_SURFACE`` / ``CIRCLE`` 的半径与轴（经 ``AXIS2_PLACEMENT_3D``
  关联其 ``axis`` DIRECTION 与 ``location`` CARTESIAN_POINT）；
* 顶层零件数 ``part_count``（启发式：NEXT_ASSEMBLY_USAGE_OCCURRENCE，缺失时
  退化为实体计数）。

坐标为科学计数法（如 ``2.761748817475512000E-015``），统一用 ``float()`` 解析。
聚类（同轴分桶）在 ``core/services/engineering_state_from_step.py`` 完成。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CylinderFeature:
    """单个圆柱面/圆（解析产物，非契约）。"""

    entity_id: str
    kind: str  # "cylindrical_surface" | "circle"
    radius_mm: float
    axis: tuple[float, float, float]
    center_mm: tuple[float, float, float]
    length_mm: float | None
    part_id: str
    axis_resolved: bool = True


@dataclass
class StepParseResult:
    """STEP 解析结果。"""

    source_id: str
    bbox_mm: tuple[float, float, float]
    part_count: int
    cylinders: list[CylinderFeature]
    unit_declared: bool = False


_ENTITY_RE = re.compile(
    r"^#(\d+)\s*=\s*([A-Za-z_][A-Za-z_0-9]*)\s*\((.*)\)\s*;?\s*$", re.DOTALL
)


def _split_top_args(param: str) -> list[str]:
    """将顶层参数串按逗号拆分为 token，忽略括号/字符串内的逗号。"""
    args: list[str] = []
    depth = 0
    current: list[str] = []
    in_str = False
    for ch in param:
        if ch == "'":
            in_str = not in_str
            current.append(ch)
        elif in_str:
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        args.append(tail)
    return args


def _parse_coords(token: str) -> tuple[float, float, float] | None:
    token = token.strip()
    if not (token.startswith("(") and token.endswith(")")):
        return None
    parts = _split_top_args(token[1:-1])
    if len(parts) != 3:
        return None
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError:
        return None


def _safe_float(token: str) -> float | None:
    token = token.strip().rstrip(")")
    try:
        return float(token)
    except ValueError:
        return None


class _Entity:
    __slots__ = ("eid", "etype", "args")

    def __init__(self, eid: str, etype: str, args: list[str]) -> None:
        self.eid = eid
        self.etype = etype
        self.args = args


class StepReader:
    """零依赖 STEP 词法解析器 + 几何抽取。"""

    def parse(self, path: Path) -> StepParseResult:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        data = self._extract_data_section(text)
        entities = self._build_entities(data)
        cylinders = self._extract_cylinders(entities)
        bbox = self._bbox(entities)
        part_count = self._part_count(entities)
        source_id = f"step:{Path(path).name}"
        unit_declared = "LENGTH_UNIT" in data
        return StepParseResult(
            source_id=source_id,
            bbox_mm=bbox,
            part_count=part_count,
            cylinders=cylinders,
            unit_declared=unit_declared,
        )

    # ----- 段落 / 实体 -----

    def _extract_data_section(self, text: str) -> str:
        idx = text.find("DATA;")
        if idx == -1:
            return text
        return text[idx + len("DATA;"):]

    def _build_entities(self, data: str) -> dict[str, _Entity]:
        entities: dict[str, _Entity] = {}
        buffer: list[str] = []
        for line in data.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            buffer.append(stripped)
            if not stripped.endswith(";"):
                continue
            blob = " ".join(buffer)
            buffer = []
            match = _ENTITY_RE.match(blob)
            if not match:
                continue
            eid, etype, raw = match.group(1), match.group(2), match.group(3)
            entities[eid] = _Entity(eid=eid, etype=etype, args=_split_top_args(raw))
        return entities

    # ----- 几何抽取 -----

    def _extract_cylinders(self, entities: dict[str, _Entity]) -> list[CylinderFeature]:
        features: list[CylinderFeature] = []
        for ent in entities.values():
            if ent.etype not in ("CYLINDRICAL_SURFACE", "CIRCLE"):
                continue
            if len(ent.args) < 3:
                continue
            radius = _safe_float(ent.args[2])
            if radius is None:
                continue
            axis, center, resolved = self._axis_and_center(ent.args[1], entities)
            if axis is None:
                axis = (0.0, 0.0, 1.0)
            if center is None:
                center = (0.0, 0.0, 0.0)
            features.append(
                CylinderFeature(
                    entity_id="#" + ent.eid,
                    kind=ent.etype.lower(),
                    radius_mm=radius,
                    axis=axis,
                    center_mm=center,
                    length_mm=None,
                    part_id="part-0",
                    axis_resolved=resolved,
                )
            )
        return features

    def _axis_and_center(
        self, placement_ref: str, entities: dict[str, _Entity]
    ) -> tuple[tuple[float, float, float] | None, tuple[float, float, float] | None, bool]:
        """从圆柱/圆的 placement 引用解析出 (axis, center, resolved)。"""
        eid = self._ref(placement_ref)
        if eid is None:
            return None, None, False
        ent = entities.get(eid)
        if ent is None:
            return None, None, False
        if ent.etype == "AXIS2_PLACEMENT_3D":
            if len(ent.args) < 3:
                return None, None, False
            loc_ent = entities.get(self._ref(ent.args[1]) or "")
            axis_ent = entities.get(self._ref(ent.args[2]) or "")
            center = self._point_of(loc_ent)
            axis = self._direction_of(axis_ent)
            return axis, center, axis is not None and center is not None
        if ent.etype == "CARTESIAN_POINT":
            return (0.0, 0.0, 1.0), self._point_of(ent), True
        return None, None, False

    @staticmethod
    def _ref(token: str) -> str | None:
        token = token.strip()
        if token.startswith("#"):
            return token[1:]
        return None

    @staticmethod
    def _point_of(ent: _Entity | None) -> tuple[float, float, float] | None:
        if ent is None or ent.etype != "CARTESIAN_POINT":
            return None
        return _parse_coords(ent.args[1]) if len(ent.args) > 1 else None

    @staticmethod
    def _direction_of(ent: _Entity | None) -> tuple[float, float, float] | None:
        if ent is None or ent.etype != "DIRECTION":
            return None
        return _parse_coords(ent.args[1]) if len(ent.args) > 1 else None

    def _bbox(self, entities: dict[str, _Entity]) -> tuple[float, float, float]:
        pts: list[tuple[float, float, float]] = []
        for ent in entities.values():
            if ent.etype == "CARTESIAN_POINT" and len(ent.args) > 1:
                coord = _parse_coords(ent.args[1])
                if coord is not None:
                    pts.append(coord)
        if not pts:
            return (0.0, 0.0, 0.0)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

    def _part_count(self, entities: dict[str, _Entity]) -> int:
        nauo = sum(1 for e in entities.values() if e.etype == "NEXT_ASSEMBLY_USAGE_OCCURRENCE")
        if nauo > 0:
            return nauo
        bodies = sum(
            1 for e in entities.values() if e.etype in ("MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS")
        )
        return max(bodies, 1)

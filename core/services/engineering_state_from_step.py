"""STEP 解析结果 → EngineeringState 构建器（特性一 · F1-P0-2）。

Builder 模式：``StepParseResult`` → ``EngineeringState(revision=1)``。
所有 ``TracedValue`` 均带至少 1 条 ``evidence``（满足 ``min_length=1`` 强约束）。

关键裁定落实：
* OQ1：关节电机参数全走默认 BLDC 目录 + 领域默认；``status=assumed``；
  ``unresolved`` 留 1 条「电机参数待用户确认」。
* OQ3：分瓣角/翅片推导不出，由 handoff 编译器默认（此处不处理）。
* OQ5：默认材质表由知识库默认材质表提供（此处直接填充 8 字段，
  handoff 编译器仍保留补缺逻辑）。
* OQ6：圆柱面用**同轴分桶**聚类为关节候选；轴不唯一 / 圆柱稀少时
  标注 ``assumed`` / ``needs_review`` 并在 ``unresolved`` 留痕（零圆柱兜底占位关节）。
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from core.knowledge.defaults import BldcDefaults, MATERIAL_PROPERTY_KEYS
from core.engine.step_reader import CylinderFeature, StepParseResult
from core.models.agent_pipeline import EngineeringValue, EvidenceRef
from core.models.engineering_state import (
    Component,
    CoordinateSystem,
    EngineeringState,
    Interface,
    Joint,
    Material,
    OperatingCase,
    ThermalLoad,
    TracedValue,
    Units,
    UnresolvedItem,
    ValueStatus,
)

DEFAULT_JOINT_OUTER_GAP_MM = 5.0
DEFAULT_SHELL_WALL_MM = 3.0
DEFAULT_AXIAL_LENGTH_MM = 20.0
COAXIAL_DIST_TOL_MM = 5.0
COAXIAL_ANGLE_COS = 0.999  # 约 2.5°

_MATERIAL_UNITS: dict[str, str | None] = {
    "density_kg_m3": "kg/m3",
    "thermal_conductivity_w_mk": "W/mK",
    "specific_heat_j_kgk": "J/kgK",
    "coefficient_thermal_expansion_1_k": "1/K",
    "youngs_modulus_pa": "Pa",
    "poissons_ratio": None,
    "yield_strength_pa": "Pa",
    "ultimate_tensile_strength_pa": "Pa",
}


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float] | None:
    norm = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if norm == 0:
        return None
    return (v[0] / norm, v[1] / norm, v[2] / norm)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _mean_point(pts: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    s: list[float] = [0.0, 0.0, 0.0]
    for p in pts:
        s[0] += p[0]
        s[1] += p[1]
        s[2] += p[2]
    n = len(pts) or 1
    return (s[0] / n, s[1] / n, s[2] / n)


def _point_line_distance(
    pt: tuple[float, float, float],
    line_pt: tuple[float, float, float],
    line_dir: tuple[float, float, float],
) -> float:
    w = (pt[0] - line_pt[0], pt[1] - line_pt[1], pt[2] - line_pt[2])
    cross = (
        w[1] * line_dir[2] - w[2] * line_dir[1],
        w[2] * line_dir[0] - w[0] * line_dir[2],
        w[0] * line_dir[1] - w[1] * line_dir[0],
    )
    return math.sqrt(cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2])


class StepToEngineeringStateBuilder:
    """将 STEP 解析结果构建为版本化 EngineeringState。"""

    def build(
        self, project_id: str, result: StepParseResult, source_path: Path
    ) -> EngineeringState:
        source_id = result.source_id
        joints, joint_unresolved = self._cluster_joints(result.cylinders, source_id)
        materials = self._default_materials(source_id)
        thermal_loads = self._default_thermal_loads(joints, source_id)
        operating_cases = self._default_operating_cases(thermal_loads, source_id)

        unit_status = "extracted" if result.unit_declared else "assumed"
        units = Units(
            length=self._tv("mm", unit_status, source_id, "header:unit"),
            angle=self._tv("deg", unit_status, source_id, "header:unit"),
            temperature=self._tv("C", unit_status, source_id, "header:unit"),
            power=self._tv("W", unit_status, source_id, "header:unit"),
        )
        coord = CoordinateSystem(
            handedness=self._tv("right", "assumed", source_id, "header:coord"),
            up_axis=self._tv("z", "assumed", source_id, "header:coord"),
            origin_mm=self._tv((0.0, 0.0, 0.0), "assumed", source_id, "header:coord"),
        )
        unresolved = [
            UnresolvedItem(
                id="unresolved-motor-params",
                description=self._tv(
                    "电机参数待用户确认（默认采用 BLDC 目录 + 领域默认）",
                    "assumed",
                    "default:bldc",
                    "default:bldc",
                ),
            ),
            *joint_unresolved,
        ]
        return EngineeringState(
            project_id=project_id,
            revision=1,
            units=units,
            coordinate_system=coord,
            joints=joints,
            components=[],
            materials=materials,
            interfaces=[],
            thermal_loads=thermal_loads,
            operating_cases=operating_cases,
            approvals=[],
            unresolved=unresolved,
        )

    # ----- joints（同轴分桶聚类）-----

    def _cluster_joints(
        self, cylinders: list[CylinderFeature], source_id: str
    ) -> tuple[list[Joint], list[UnresolvedItem]]:
        surfaces = [c for c in cylinders if c.kind == "cylindrical_surface" and c.axis_resolved]
        if not surfaces:
            placeholder = self._placeholder_joint(source_id)
            extra = [
                UnresolvedItem(
                    id="unresolved-no-cylinder",
                    description=self._tv(
                        "未检出圆柱面，已生成 1 个 needs_review 占位关节",
                        "needs_review",
                        source_id,
                        "default:geometry",
                    ),
                )
            ]
            return [placeholder], extra
        buckets = self._coaxial_buckets(surfaces)
        joints = [self._joint_from_bucket(bucket, i, source_id) for i, bucket in enumerate(buckets)]
        return joints, []

    def _coaxial_buckets(self, features: list[CylinderFeature]) -> list[list[CylinderFeature]]:
        buckets: list[list[CylinderFeature]] = []
        for feature in features:
            placed = False
            for bucket in buckets:
                if self._coaxial(bucket[0], feature):
                    bucket.append(feature)
                    placed = True
                    break
            if not placed:
                buckets.append([feature])
        return buckets

    @staticmethod
    def _coaxial(a: CylinderFeature, b: CylinderFeature) -> bool:
        ax = _normalize(a.axis)
        bx = _normalize(b.axis)
        if ax is None or bx is None:
            return False
        if abs(_dot(ax, bx)) < COAXIAL_ANGLE_COS:
            return False
        if _point_line_distance(b.center_mm, a.center_mm, ax) > COAXIAL_DIST_TOL_MM:
            return False
        if _point_line_distance(a.center_mm, b.center_mm, bx) > COAXIAL_DIST_TOL_MM:
            return False
        return True

    def _joint_from_bucket(
        self, bucket: list[CylinderFeature], idx: int, source_id: str
    ) -> Joint:
        radii = [f.radius_mm for f in bucket]
        inner = min(radii)
        outer = max(radii)
        if outer <= inner + 1e-6:
            outer = inner + DEFAULT_JOINT_OUTER_GAP_MM
        axis = self._consensus_axis(bucket)
        axis_status = self._axis_status(bucket)
        center = _mean_point([f.center_mm for f in bucket])
        span = self._axial_span(bucket, axis)
        mean_radius = (inner + outer) / 2.0
        axial = max(span + 2.0 * mean_radius, DEFAULT_AXIAL_LENGTH_MM)
        geo_status = "extracted" if (len(bucket) >= 2 and axis_status == "extracted") else "assumed"
        return Joint(
            id=f"joint-{idx + 1}",
            axis=self._tv(axis, axis_status, source_id, f"cluster:{idx + 1}"),
            rotation_range_deg=self._tv((-180.0, 180.0), "assumed", source_id, "default:geometry"),
            outer_radius_mm=self._tv(outer, geo_status, source_id, f"cluster:{idx + 1}"),
            inner_radius_mm=self._tv(inner, geo_status, source_id, f"cluster:{idx + 1}"),
            axial_length_mm=self._tv(axial, "assumed", source_id, f"cluster:{idx + 1}"),
            shell_wall_thickness_mm=self._tv(
                DEFAULT_SHELL_WALL_MM, "assumed", source_id, "default:geometry"
            ),
        )

    def _consensus_axis(self, bucket: list[CylinderFeature]) -> tuple[float, float, float]:
        vecs = [_normalize(f.axis) for f in bucket]
        vecs = [v for v in vecs if v is not None]
        if not vecs:
            return (0.0, 0.0, 1.0)
        s: list[float] = [0.0, 0.0, 0.0]
        for v in vecs:
            s[0] += v[0]
            s[1] += v[1]
            s[2] += v[2]
        normalized = _normalize(tuple(s))
        return normalized if normalized is not None else vecs[0]

    @staticmethod
    def _axis_status(bucket: list[CylinderFeature]) -> str:
        vecs = [_normalize(f.axis) for f in bucket]
        vecs = [v for v in vecs if v is not None]
        if len(vecs) < 2:
            return "assumed"
        for i in range(len(vecs)):
            for j in range(i + 1, len(vecs)):
                if abs(_dot(vecs[i], vecs[j])) < COAXIAL_ANGLE_COS:
                    return "assumed"
        return "extracted"

    @staticmethod
    def _axial_span(bucket: list[CylinderFeature], axis: tuple[float, float, float]) -> float:
        projections = [_dot(f.center_mm, axis) for f in bucket]
        return max(projections) - min(projections)

    def _placeholder_joint(self, source_id: str) -> Joint:
        return Joint(
            id="joint-1",
            axis=self._tv((0.0, 0.0, 1.0), "needs_review", source_id, "default:geometry"),
            rotation_range_deg=self._tv(
                (-180.0, 180.0), "needs_review", source_id, "default:geometry"
            ),
            outer_radius_mm=self._tv(30.0, "needs_review", source_id, "default:geometry"),
            inner_radius_mm=self._tv(20.0, "needs_review", source_id, "default:geometry"),
            axial_length_mm=self._tv(
                DEFAULT_AXIAL_LENGTH_MM, "needs_review", source_id, "default:geometry"
            ),
            shell_wall_thickness_mm=self._tv(
                DEFAULT_SHELL_WALL_MM, "needs_review", source_id, "default:geometry"
            ),
        )

    # ----- materials / thermal / operating -----

    def _default_materials(self, source_id: str) -> list[Material]:
        materials: list[Material] = []
        for material_id, props in BldcDefaults.DEFAULT_MATERIALS.items():
            properties: dict[str, EngineeringValue] = {}
            for key in MATERIAL_PROPERTY_KEYS:
                properties[key] = EngineeringValue(
                    value=props[key],
                    unit=_MATERIAL_UNITS.get(key),
                    confidence=1.0,
                    status="assumed",
                    evidence=[
                        EvidenceRef(
                            source_id="default:material",
                            locator=f"materials.{material_id}.{key}",
                        )
                    ],
                )
            materials.append(
                Material(
                    id=props["material_id"],
                    name=self._tv(
                        props["name"], "assumed", "default:material", f"materials.{material_id}.name"
                    ),
                    properties=properties,
                )
            )
        return materials

    def _default_thermal_loads(
        self, joints: list[Joint], source_id: str
    ) -> list[ThermalLoad]:
        heat_w = BldcDefaults.default_motor_thermal_load_w()
        loads: list[ThermalLoad] = []
        for joint in joints:
            loads.append(
                ThermalLoad(
                    id=f"load-{joint.id}",
                    component_id=self._tv(joint.id, "assumed", "default:bldc", "default:bldc"),
                    heat_w=self._tv(heat_w, "assumed", "default:bldc", "default:bldc"),
                )
            )
        return loads

    def _default_operating_cases(
        self, thermal_loads: list[ThermalLoad], source_id: str
    ) -> list[OperatingCase]:
        if not thermal_loads:
            return []
        load_ids = [tl.id for tl in thermal_loads]
        return [
            OperatingCase(
                id="case-nominal",
                name=self._tv("nominal", "assumed", source_id, "default:geometry"),
                ambient_temperature_c=self._tv(25.0, "assumed", source_id, "default:geometry"),
                duty_cycle=self._tv(1.0, "assumed", source_id, "default:geometry"),
                thermal_load_ids=self._tv(load_ids, "assumed", source_id, "default:geometry"),
            )
        ]

    # ----- helpers -----

    @staticmethod
    def _tv(value: Any, status: str, source_id: str, locator: str) -> TracedValue[Any]:
        return TracedValue(
            value=value,
            status=ValueStatus(status),
            evidence=[EvidenceRef(source_id=source_id, locator=locator)],
        )

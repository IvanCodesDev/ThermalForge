"""叶脉方向与形态的多目标候选优化器。

目标不是替代 CFD，而是负责：参数替换 → 候选生成 → 调仿真接口 → 排序 → 输出最优解。
真实仿真后端接入后，本模块无需改动。
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List

from ..models.schema import LeafVeinParams
from .generator import generate
from .simulation import SimulationBackend, SimulationContext, SimulationOutcome


@dataclass
class OptimizationWeights:
    thermal: float = 0.70
    aesthetics: float = 0.20
    mass: float = 0.10

    def normalized(self) -> "OptimizationWeights":
        total = max(self.thermal + self.aesthetics + self.mass, 1e-9)
        return OptimizationWeights(
            thermal=self.thermal / total,
            aesthetics=self.aesthetics / total,
            mass=self.mass / total,
        )


@dataclass
class CandidateResult:
    candidate_id: str
    params: Dict[str, Any]
    aesthetics_score: float
    thermal_score: float
    mass_score: float
    total_score: float
    simulation: Dict[str, Any]
    geometry: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def aesthetics_score(params: LeafVeinParams) -> float:
    """0-100 的可解释形态评分占位。

    它不是审美真理，只是用于首轮搜索：对称、有机分叉、渐缩和适度复杂度得分高。
    后续可被渲染图视觉模型评分替换。
    """
    symmetry = params.symmetry
    taper = 1.0 - min(abs(params.branch_ratio - 0.68) / 0.38, 1.0)
    angle = 1.0 - min(abs(params.branch_angle - 38.0) / 37.0, 1.0)
    complexity = 1.0 - min(abs(params.branch_levels - 4.0) / 3.0, 1.0)
    organic = 1.0 - min(abs(params.tortuosity - 1.35) / 1.65, 1.0)
    return round(100.0 * (0.30 * symmetry + 0.20 * taper + 0.20 * angle + 0.15 * complexity + 0.15 * organic), 2)


def build_leaf_candidates(
    base: LeafVeinParams,
    flow_directions_deg: Iterable[float],
    branch_angles: Iterable[float] | None = None,
) -> List[LeafVeinParams]:
    angles = list(branch_angles or [base.branch_angle])
    candidates: List[LeafVeinParams] = []
    for direction in flow_directions_deg:
        for branch_angle in angles:
            item = deepcopy(base)
            item.flow_direction_deg = float(direction) % 360.0
            item.branch_angle = float(branch_angle)
            candidates.append(item)
    return candidates


def optimize_leaf_direction(
    base: LeafVeinParams,
    context: SimulationContext,
    backend: SimulationBackend,
    flow_directions_deg: Iterable[float] = (0, 45, 90, 135, 180, 225, 270, 315),
    branch_angles: Iterable[float] | None = None,
    weights: OptimizationWeights | None = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    weights = (weights or OptimizationWeights()).normalized()
    candidates = build_leaf_candidates(base, flow_directions_deg, branch_angles)
    raw: List[tuple[LeafVeinParams, SimulationOutcome, Dict[str, Any], float]] = []

    for params in candidates:
        _, stats = generate(params)
        sim = backend.evaluate_candidate(params, context)
        raw.append((params, sim, stats.__dict__, aesthetics_score(params)))

    temperatures = [item[1].t_hotspot_c for item in raw]
    masses = [item[1].mass_g for item in raw]
    t_min, t_max = min(temperatures), max(temperatures)
    m_min, m_max = min(masses), max(masses)

    ranked: List[CandidateResult] = []
    for index, (params, sim, geometry, aesthetic) in enumerate(raw, start=1):
        thermal = 100.0 if t_max == t_min else 100.0 * (t_max - sim.t_hotspot_c) / (t_max - t_min)
        mass = 100.0 if m_max == m_min else 100.0 * (m_max - sim.mass_g) / (m_max - m_min)
        total = weights.thermal * thermal + weights.aesthetics * aesthetic + weights.mass * mass
        ranked.append(CandidateResult(
            candidate_id=f"LV-CAND-{index:03d}",
            params=params.to_dict(),
            aesthetics_score=round(aesthetic, 2),
            thermal_score=round(thermal, 2),
            mass_score=round(mass, 2),
            total_score=round(total, 2),
            simulation=sim.to_dict(),
            geometry=geometry,
        ))

    ranked.sort(key=lambda item: item.total_score, reverse=True)
    return {
        "status": "completed",
        "backend": backend.name,
        "source_model_path": context.source_model_path,
        "weights": asdict(weights),
        "searched_candidates": len(ranked),
        "best": ranked[0].to_dict() if ranked else None,
        "ranking": [item.to_dict() for item in ranked[:max(1, top_k)]],
        "handoff": {
            "simulation_interface": "SimulationBackend.evaluate_candidate(params, context)",
            "external_backend_ready": True,
            "note": "当前使用快速估算；真实 ANSYS/SpaceClaim 求解由团队后续实现 ExternalSimulationBackend。",
        },
    }

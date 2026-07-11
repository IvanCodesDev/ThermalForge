from .generator import (
    generate,
    generate_leaf_vein,
    generate_channel,
    generate_flat,
    GeometryStats,
)
from .thermal import evaluate, compare, ThermalResult, MATERIALS, MEDIUM_H
from .matcher import Library, cosine, query_from_params
from .simulation import SimulationBackend, SimulationContext, SimulationOutcome, LumpedSimulationBackend, ExternalSimulationBackend
from .optimizer import OptimizationWeights, optimize_leaf_direction, build_leaf_candidates, aesthetics_score

__all__ = [
    "generate", "generate_leaf_vein", "generate_channel", "generate_flat", "GeometryStats",
    "evaluate", "compare", "ThermalResult", "MATERIALS", "MEDIUM_H",
    "Library", "cosine", "query_from_params",
    "SimulationBackend", "SimulationContext", "SimulationOutcome",
    "LumpedSimulationBackend", "ExternalSimulationBackend",
    "OptimizationWeights", "optimize_leaf_direction", "build_leaf_candidates", "aesthetics_score",
]

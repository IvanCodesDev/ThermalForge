from dataclasses import dataclass
from typing import Literal

from app.thermal.schemas import InterferenceRisk

SOLUTION_CATALOG_VERSION = "thermal-solutions-v1"


@dataclass(frozen=True, slots=True)
class SolutionDefinition:
    id: str
    title: str
    tag: str
    features: tuple[str, ...]
    resistance_base: float
    airflow_coefficient: float
    minimum_resistance_factor: float
    maximum_resistance_factor: float
    capacity_factor: float
    added_mass_percent: float
    interference_risk: InterferenceRisk
    compatibility_score: float
    cost_score: float
    risk_score: float
    materials: tuple[str, ...]
    manufacturing_methods: tuple[
        Literal["sheet", "cnc", "additive", "assembly"],
        ...,
    ]
    geometry_anchors: tuple[str, ...]

    def resistance_factor(self, airflow_mps: float) -> float:
        factor = self.resistance_base - airflow_mps * self.airflow_coefficient
        return min(
            max(factor, self.minimum_resistance_factor),
            self.maximum_resistance_factor,
        )


SOLUTION_CATALOG: tuple[SolutionDefinition, ...] = (
    SolutionDefinition(
        id="flat-baseline",
        title="平板基线",
        tag="对照组",
        features=("成本低", "结构简单", "散热提升有限"),
        resistance_base=0.95,
        airflow_coefficient=0,
        minimum_resistance_factor=0.95,
        maximum_resistance_factor=0.95,
        capacity_factor=1.02,
        added_mass_percent=2.2,
        interference_risk="低",
        compatibility_score=76,
        cost_score=95,
        risk_score=94,
        materials=("AL-6061-T6", "C1100"),
        manufacturing_methods=("sheet", "cnc", "assembly"),
        geometry_anchors=("原厂安装面", "壳体热点区域"),
    ),
    SolutionDefinition(
        id="vein-bridge",
        title="可逆导热桥 + 叶脉热扩散结构",
        tag="推荐方案",
        features=(
            "适合局部热点扩散",
            "不破坏原厂关节",
            "可拆卸维护",
        ),
        resistance_base=0.78,
        airflow_coefficient=0,
        minimum_resistance_factor=0.78,
        maximum_resistance_factor=0.78,
        capacity_factor=1.06,
        added_mass_percent=6.8,
        interference_risk="低",
        compatibility_score=96,
        cost_score=72,
        risk_score=90,
        materials=("AL-6061-T6", "C1100", "柔性石墨导热界面"),
        manufacturing_methods=("cnc", "assembly"),
        geometry_anchors=("原厂孔位", "外壳热点区域", "导热桥接触面"),
    ),
    SolutionDefinition(
        id="pin-fin",
        title="低矮 pin-fin 圆柱阵列",
        tag="气流增强",
        features=("适合弱风或运动气流", "空气侧换热增强", "需防尘防碰撞"),
        resistance_base=0.88,
        airflow_coefficient=0.12,
        minimum_resistance_factor=0.67,
        maximum_resistance_factor=0.88,
        capacity_factor=1.08,
        added_mass_percent=7.6,
        interference_risk="中",
        compatibility_score=78,
        cost_score=64,
        risk_score=58,
        materials=("AL-6061-T6",),
        manufacturing_methods=("cnc", "additive"),
        geometry_anchors=("迎风面", "外壳热点区域", "运动包络边界"),
    ),
    SolutionDefinition(
        id="gyroid",
        title="TPMS / Gyroid 热点块",
        tag="高性能样件",
        features=("适合明确风道或液冷", "高比表面积", "不作为默认主方案"),
        resistance_base=0.91,
        airflow_coefficient=0.14,
        minimum_resistance_factor=0.63,
        maximum_resistance_factor=0.91,
        capacity_factor=1.12,
        added_mass_percent=9.6,
        interference_risk="中",
        compatibility_score=72,
        cost_score=36,
        risk_score=46,
        materials=("AL-6061-T6",),
        manufacturing_methods=("additive",),
        geometry_anchors=("热点体积", "风道入口", "风道出口"),
    ),
)

_CATALOG_BY_ID = {solution.id: solution for solution in SOLUTION_CATALOG}


def get_solution(solution_id: str) -> SolutionDefinition:
    return _CATALOG_BY_ID[solution_id]

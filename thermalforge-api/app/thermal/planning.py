from collections.abc import Iterable

from app.engineering.schemas import EngineeringBrief
from app.thermal.catalog import get_solution
from app.thermal.schemas import (
    AnalysisAssumption,
    AnalysisInputs,
    AnalysisPlan,
    CandidateEvaluation,
    ThermalAnalysisRequest,
    ThermalAnalysisResult,
)

_HEAT_SOURCE_IDS = (
    (("电机", "motor", "绕组"), "motor-winding"),
    (("mosfet", "驱控", "功率器件"), "mosfet"),
    (("减速", "gearbox"), "gearbox"),
    (("轴承", "bearing"), "bearing"),
    (("连接器", "connector"), "connector"),
    (("线束", "harness"), "harness"),
    (("jetson", "soc", "计算"), "jetson"),
)

_CONSTRAINT_IDS = (
    (("运动包络", "motion envelope"), "motion-envelope"),
    (("可拆卸", "removable"), "removable"),
    (("重复安装", "repeatable"), "repeatable"),
    (("轴承", "bearing"), "bearing-clearance"),
    (("编码器", "encoder"), "encoder-clearance"),
    (("线束", "cable", "harness"), "cable-clearance"),
    (("孔位", "螺丝孔", "screw"), "screw-clearance"),
    (("不改电机", "motor untouched"), "motor-untouched"),
    (("不改减速", "reducer untouched"), "reducer-untouched"),
    (("不开壳", "sealed"), "sealed-case"),
)


def _contains_any(value: str, tokens: Iterable[str]) -> bool:
    normalized = value.casefold()
    return any(token.casefold() in normalized for token in tokens)


def _source_id(name: str, index: int, used: set[str]) -> str:
    candidate = next(
        (
            identifier
            for tokens, identifier in _HEAT_SOURCE_IDS
            if _contains_any(name, tokens)
        ),
        f"heat-source-{index + 1}",
    )
    if candidate not in used:
        used.add(candidate)
        return candidate
    duplicate = f"{candidate}-{index + 1}"
    used.add(duplicate)
    return duplicate


def _joint_id(project_title: str) -> str:
    joint_names = (
        ("knee", ("膝", "knee")),
        ("hip", ("髋", "hip")),
        ("ankle", ("踝", "ankle")),
        ("shoulder", ("肩", "shoulder")),
        ("elbow", ("肘", "elbow")),
        ("wrist", ("腕", "wrist")),
    )
    return next(
        (
            identifier
            for identifier, tokens in joint_names
            if _contains_any(project_title, tokens)
        ),
        "unspecified",
    )


def _map_constraints(brief: EngineeringBrief) -> list[str]:
    source_constraints = [
        *brief.mounting_constraints,
        *brief.required_features,
        *brief.prohibited_changes,
    ]
    mapped = [
        identifier
        for tokens, identifier in _CONSTRAINT_IDS
        if any(_contains_any(value, tokens) for value in source_constraints)
    ]
    if brief.mass_budget is not None:
        mapped.append("weight-limit")
    return list(dict.fromkeys(mapped))


def build_analysis_plan(brief: EngineeringBrief) -> AnalysisPlan:
    assumptions: list[AnalysisAssumption] = []
    used_source_ids: set[str] = set()
    heat_sources = {
        _source_id(source.name, index, used_source_ids): source.power_w
        for index, source in enumerate(brief.heat_sources)
    }
    total_power_w = sum(heat_sources.values())
    effective_power_w = sum(
        source.power_w * ((source.duty_cycle_percent or 100) / 100)
        for source in brief.heat_sources
    )
    duty_cycle_percent = (
        effective_power_w / total_power_w * 100 if total_power_w else 100
    )
    if any(
        source.duty_cycle_percent is None for source in brief.heat_sources
    ):
        assumptions.append(
            AnalysisAssumption(
                key="duty_cycle_percent",
                value=f"{duty_cycle_percent:.3g}%",
                reason="未提供全部热源占空比，缺失项按连续负载计算。",
                impact="high",
            )
        )

    ambient_temperature_c = (
        brief.environment.ambient_temp_c
        if brief.environment is not None
        else 25
    )
    if brief.environment is None:
        assumptions.append(
            AnalysisAssumption(
                key="ambient_temperature_c",
                value="25°C",
                reason="工程摘要缺少环境温度，使用室温工程基线。",
                impact="high",
            )
        )

    thermal_limits = [
        source.maximum_temperature_c
        for source in brief.heat_sources
        if source.maximum_temperature_c is not None
    ]
    thermal_limit_c = min(thermal_limits) if thermal_limits else 80
    if not thermal_limits:
        assumptions.append(
            AnalysisAssumption(
                key="thermal_limit_c",
                value="80°C",
                reason="未提供器件热保护阈值，使用保守工程基线。",
                impact="high",
            )
        )

    airflow_mps = (
        brief.environment.airflow_m_s
        if brief.environment is not None
        and brief.environment.airflow_m_s is not None
        else 0.1
    )
    if (
        brief.environment is None
        or brief.environment.airflow_m_s is None
    ):
        assumptions.append(
            AnalysisAssumption(
                key="airflow_mps",
                value="0.1m/s",
                reason="未提供有效风速，按近自然对流环境估算。",
                impact="medium",
            )
        )

    initial_temperature_c = min(
        ambient_temperature_c + 5,
        thermal_limit_c - 0.1,
    )
    assumptions.extend(
        [
            AnalysisAssumption(
                key="initial_temperature_c",
                value=f"{initial_temperature_c:.3g}°C",
                reason="未提供冷启动温度，按环境温度上浮计算。",
                impact="medium",
            ),
            AnalysisAssumption(
                key="duration_minutes",
                value="15min",
                reason="未提供任务持续时间，采用固定工程评估窗口。",
                impact="high",
            ),
            AnalysisAssumption(
                key="component_mass_kg",
                value="1.8kg",
                reason="EngineeringBrief 尚未包含关节基体质量。",
                impact="high",
            ),
            AnalysisAssumption(
                key="measurement_curve",
                value="未提供",
                reason="当前使用一阶集总参数 RC 工程估算，尚未用样机曲线校准。",
                impact="high",
            ),
        ]
    )

    request = ThermalAnalysisRequest(
        hardware_id="robot-joint",
        joint_id=_joint_id(brief.project_title),
        heat_sources=heat_sources,
        constraints=_map_constraints(brief),
        optimization_goals=[
            "delay-limit",
            "lower-hotspot",
            "weight-limit",
            "original-structure",
        ],
        inputs=AnalysisInputs(
            ambient_temperature_c=ambient_temperature_c,
            initial_temperature_c=initial_temperature_c,
            thermal_limit_c=thermal_limit_c,
            duration_minutes=15,
            duty_cycle_percent=duty_cycle_percent,
            airflow_mps=airflow_mps,
            component_mass_kg=1.8,
        ),
        measurements=[],
    )
    return AnalysisPlan(request=request, assumptions=assumptions)


def _manufacturing_rejections(
    brief: EngineeringBrief,
    solution_id: str,
) -> list[str]:
    solution = get_solution(solution_id)
    constraints = " ".join(brief.manufacturing_constraints)
    rejections: list[str] = []
    if _contains_any(
        constraints,
        ("禁止3d打印", "不允许3d打印", "禁止增材", "不允许增材"),
    ) and all(method == "additive" for method in solution.manufacturing_methods):
        rejections.append("manufacturing_method_prohibited")
    material_constraints = " ".join(brief.material_constraints)
    if _contains_any(material_constraints, ("禁用铝", "不得使用铝")) and all(
        material.startswith("AL-") for material in solution.materials
    ):
        rejections.append("material_prohibited")
    return rejections


def evaluate_candidates(
    *,
    brief: EngineeringBrief,
    request: ThermalAnalysisRequest,
    analysis: ThermalAnalysisResult,
) -> list[CandidateEvaluation]:
    evaluations: list[CandidateEvaluation] = []
    maximum_mass_percent = (
        brief.mass_budget.maximum_added_mass_percent
        if brief.mass_budget is not None
        else None
    )
    maximum_mass_g = (
        brief.mass_budget.maximum_added_mass_g
        if brief.mass_budget is not None
        else None
    )

    for candidate in analysis.candidates:
        definition = get_solution(candidate.solution_id)
        added_mass_g = (
            request.inputs.component_mass_kg
            * 1_000
            * candidate.added_mass_percent
            / 100
        )
        rejection_codes: list[str] = []
        if (
            maximum_mass_percent is not None
            and candidate.added_mass_percent > maximum_mass_percent
        ) or (
            maximum_mass_g is not None
            and added_mass_g > maximum_mass_g
        ):
            rejection_codes.append("mass_budget_exceeded")
        if (
            "motion-envelope" in request.constraints
            and candidate.interference_risk != "低"
        ):
            rejection_codes.append("motion_envelope_risk")
        rejection_codes.extend(
            _manufacturing_rejections(brief, candidate.solution_id)
        )
        rejection_codes = list(dict.fromkeys(rejection_codes))
        evaluations.append(
            CandidateEvaluation(
                solution_id=candidate.solution_id,
                title=definition.title,
                eligible=not rejection_codes,
                rejection_codes=rejection_codes,
                thermal_score=candidate.score,
                cost_score=definition.cost_score,
                risk_score=definition.risk_score,
                added_mass_g=round(added_mass_g, 1),
                added_mass_percent=candidate.added_mass_percent,
                max_temperature_c=candidate.max_temperature_c,
                hotspot_reduction_c=candidate.hotspot_reduction_c,
                interference_risk=candidate.interference_risk,
            )
        )
    return evaluations

import math
from collections.abc import Sequence

from app.thermal.catalog import SOLUTION_CATALOG, SolutionDefinition
from app.thermal.schemas import (
    CandidateResult,
    MeasurementPoint,
    RecommendationGrade,
    ThermalAnalysisRequest,
    ThermalAnalysisResult,
    ThermalCaseResult,
    ThermalCurvePoint,
)

_HARDWARE_RESISTANCE: dict[str, float] = {
    "robot-joint": 1.13,
    "motor": 1.04,
    "driver-board": 1.38,
    "compute-box": 1.2,
    "sensor": 1.72,
    "power": 0.92,
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _round(value: float, precision: int = 2) -> float:
    """Match JavaScript Math.round so Golden Fixtures remain cross-language stable."""
    factor = 10.0**precision
    return math.floor(value * factor + 0.5) / factor


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _find_time_to_limit(
    curve: Sequence[ThermalCurvePoint],
    thermal_limit_c: float,
) -> float | None:
    for index, point in enumerate(curve):
        if point.temperature_c < thermal_limit_c:
            continue
        if index == 0:
            return _round(point.time_s / 60)

        previous = curve[index - 1]
        temperature_span = point.temperature_c - previous.temperature_c
        ratio = (
            0
            if temperature_span == 0
            else (thermal_limit_c - previous.temperature_c) / temperature_span
        )
        interpolated_time = previous.time_s + (
            point.time_s - previous.time_s
        ) * _clamp(ratio, 0, 1)
        return _round(interpolated_time / 60)
    return None


def _summarize_curve(
    curve: list[ThermalCurvePoint],
    thermal_limit_c: float,
    thermal_resistance_k_per_w: float,
    effective_capacity_j_per_k: float,
) -> ThermalCaseResult:
    return ThermalCaseResult(
        curve=curve,
        max_temperature_c=_round(
            max(point.temperature_c for point in curve),
            1,
        ),
        time_to_limit_minutes=_find_time_to_limit(curve, thermal_limit_c),
        thermal_resistance_k_per_w=_round(thermal_resistance_k_per_w, 3),
        effective_capacity_j_per_k=_round(effective_capacity_j_per_k, 1),
    )


def _simulate_constant_power(
    *,
    duration_minutes: float,
    initial_temperature_c: float,
    ambient_temperature_c: float,
    power_w: float,
    thermal_resistance_k_per_w: float,
    effective_capacity_j_per_k: float,
) -> list[ThermalCurvePoint]:
    duration_s = duration_minutes * 60
    step_s = max(5, min(30, duration_s / 60))
    time_constant_s = thermal_resistance_k_per_w * effective_capacity_j_per_k
    steady_temperature = (
        ambient_temperature_c + power_w * thermal_resistance_k_per_w
    )
    curve: list[ThermalCurvePoint] = []
    time_s = 0.0

    while time_s < duration_s:
        temperature_c = steady_temperature + (
            initial_temperature_c - steady_temperature
        ) * math.exp(-time_s / time_constant_s)
        curve.append(
            ThermalCurvePoint(
                time_s=_round(time_s, 1),
                temperature_c=_round(temperature_c, 2),
            )
        )
        time_s += step_s

    final_temperature_c = steady_temperature + (
        initial_temperature_c - steady_temperature
    ) * math.exp(-duration_s / time_constant_s)
    curve.append(
        ThermalCurvePoint(
            time_s=_round(duration_s, 1),
            temperature_c=_round(final_temperature_c, 2),
        )
    )
    return curve


def _simulate_measured_power(
    request: ThermalAnalysisRequest,
    thermal_resistance_k_per_w: float,
    effective_capacity_j_per_k: float,
) -> list[ThermalCurvePoint]:
    first_point, *remaining_points = request.measurements
    curve = [
        ThermalCurvePoint(
            time_s=first_point.time_s,
            temperature_c=first_point.temperature_c,
        )
    ]
    temperature_c = first_point.temperature_c
    previous_point = first_point
    time_constant_s = thermal_resistance_k_per_w * effective_capacity_j_per_k

    for point in remaining_points:
        delta_time_s = point.time_s - previous_point.time_s
        decay = math.exp(-delta_time_s / time_constant_s)
        interval_power_w = (previous_point.power_w + point.power_w) / 2
        steady_temperature = (
            request.inputs.ambient_temperature_c
            + interval_power_w * thermal_resistance_k_per_w
        )
        temperature_c = steady_temperature + (
            temperature_c - steady_temperature
        ) * decay
        curve.append(
            ThermalCurvePoint(
                time_s=point.time_s,
                temperature_c=_round(temperature_c, 2),
            )
        )
        previous_point = point
    return curve


def _calibrate_measured_model(
    request: ThermalAnalysisRequest,
) -> tuple[float, float]:
    points = request.measurements
    first_point = points[0]
    last_point = points[-1]
    max_temperature_c = max(point.temperature_c for point in points)
    average_power_w = _average([point.power_w for point in points])
    temperature_rise = max(
        max_temperature_c - request.inputs.ambient_temperature_c,
        0.5,
    )
    resistance = _clamp(
        temperature_rise / max(average_power_w, 0.1),
        0.03,
        8,
    )
    target_temperature = first_point.temperature_c + (
        max_temperature_c - first_point.temperature_c
    ) * 0.632
    target_point = next(
        (
            point
            for point in points
            if point.temperature_c >= target_temperature
        ),
        None,
    )
    fallback_tau_s = max((last_point.time_s - first_point.time_s) / 3, 10)
    time_constant_s = max(
        (
            target_point.time_s
            if target_point is not None
            else first_point.time_s + fallback_tau_s
        )
        - first_point.time_s,
        10,
    )
    return resistance, _clamp(time_constant_s / resistance, 20, 100_000)


def _improvement_percent(
    baseline_minutes: float | None,
    candidate_minutes: float | None,
    duration_minutes: float,
) -> float | None:
    if baseline_minutes is None:
        return None
    if baseline_minutes <= 0:
        return 0
    effective_candidate = (
        candidate_minutes if candidate_minutes is not None else duration_minutes
    )
    return _round(
        max(
            0,
            (
                (effective_candidate - baseline_minutes)
                / baseline_minutes
                * 100
            ),
        ),
        1,
    )


def _goal_weight(goals: Sequence[str], *ids: str) -> float:
    indexes = [goals.index(identifier) for identifier in ids if identifier in goals]
    if not indexes:
        return 0.55
    return _clamp(1 - min(indexes) * 0.1, 0.5, 1)


def _recommendation_score(
    *,
    request: ThermalAnalysisRequest,
    baseline: ThermalCaseResult,
    candidate: CandidateResult,
    compatibility_score: float,
) -> float:
    thermal_headroom = max(
        baseline.max_temperature_c - request.inputs.ambient_temperature_c,
        1,
    )
    cooling_score = _clamp(
        candidate.hotspot_reduction_c / thermal_headroom * 260,
        0,
        100,
    )
    delay_score = (
        cooling_score
        if candidate.time_to_limit_improvement_percent is None
        else _clamp(candidate.time_to_limit_improvement_percent * 1.8, 0, 100)
    )
    mass_score = _clamp(100 - candidate.added_mass_percent * 7, 0, 100)
    risk_score = (
        100
        if candidate.interference_risk == "低"
        else 62
        if candidate.interference_risk == "中"
        else 25
    )
    cooling_weight = _goal_weight(
        request.optimization_goals,
        "lower-hotspot",
    )
    delay_weight = _goal_weight(
        request.optimization_goals,
        "delay-limit",
        "task-duration",
    )
    mass_weight = _goal_weight(request.optimization_goals, "weight-limit")
    compatibility_weight = _goal_weight(
        request.optimization_goals,
        "original-structure",
        "maintainability",
        "interference-risk",
    )
    total_weight = (
        cooling_weight + delay_weight + mass_weight + compatibility_weight
    )
    score = (
        cooling_score * cooling_weight
        + delay_score * delay_weight
        + mass_score * mass_weight
        + ((compatibility_score + risk_score) / 2) * compatibility_weight
    ) / total_weight

    if (
        "weight-limit" in request.constraints
        and candidate.added_mass_percent > 8
    ):
        score -= 24
    if (
        "motion-envelope" in request.constraints
        and candidate.interference_risk != "低"
    ):
        score -= 10
    if (
        "removable" in request.constraints
        and candidate.solution_id == "vein-bridge"
    ):
        score += 5
    return _round(_clamp(score, 0, 100), 1)


def _grade_for_score(score: float) -> RecommendationGrade:
    if score >= 78:
        return "A"
    if score >= 64:
        return "B"
    if score >= 48:
        return "C"
    return "D"


def _create_candidate(
    *,
    request: ThermalAnalysisRequest,
    baseline: ThermalCaseResult,
    profile: SolutionDefinition,
    baseline_resistance: float,
    baseline_capacity: float,
) -> CandidateResult:
    resistance = baseline_resistance * profile.resistance_factor(
        request.inputs.airflow_mps
    )
    capacity = baseline_capacity * profile.capacity_factor
    curve = (
        _simulate_measured_power(request, resistance, capacity)
        if request.measurements
        else _simulate_constant_power(
            duration_minutes=request.inputs.duration_minutes,
            initial_temperature_c=request.inputs.initial_temperature_c,
            ambient_temperature_c=request.inputs.ambient_temperature_c,
            power_w=sum(request.heat_sources.values())
            * (request.inputs.duty_cycle_percent / 100),
            thermal_resistance_k_per_w=resistance,
            effective_capacity_j_per_k=capacity,
        )
    )
    summarized = _summarize_curve(
        curve,
        request.inputs.thermal_limit_c,
        resistance,
        capacity,
    )
    duration_minutes = (
        request.measurements[-1].time_s / 60
        if request.measurements
        else request.inputs.duration_minutes
    )
    candidate = CandidateResult(
        **summarized.model_dump(),
        solution_id=profile.id,
        added_mass_percent=profile.added_mass_percent,
        interference_risk=profile.interference_risk,
        hotspot_reduction_c=_round(
            baseline.max_temperature_c - summarized.max_temperature_c,
            1,
        ),
        time_to_limit_improvement_percent=_improvement_percent(
            baseline.time_to_limit_minutes,
            summarized.time_to_limit_minutes,
            duration_minutes,
        ),
        score=0,
        grade="D",
    )
    score = _recommendation_score(
        request=request,
        baseline=baseline,
        candidate=candidate,
        compatibility_score=profile.compatibility_score,
    )
    return candidate.model_copy(
        update={
            "score": score,
            "grade": _grade_for_score(score),
        }
    )


def _measurement_curve(
    measurements: Sequence[MeasurementPoint],
) -> list[ThermalCurvePoint]:
    return [
        ThermalCurvePoint(
            time_s=point.time_s,
            temperature_c=point.temperature_c,
            power_w=point.power_w,
        )
        for point in measurements
    ]


def calculate_thermal_analysis(
    request: ThermalAnalysisRequest,
    *,
    generated_at: str,
) -> ThermalAnalysisResult:
    has_measurements = len(request.measurements) >= 3
    estimated_total_power_w = sum(request.heat_sources.values())
    total_power_w = (
        _average([point.power_w for point in request.measurements])
        if has_measurements
        else estimated_total_power_w
    )
    if has_measurements:
        resistance, capacity = _calibrate_measured_model(request)
    else:
        resistance = (
            _HARDWARE_RESISTANCE.get(request.hardware_id, 1.2)
            / (1 + request.inputs.airflow_mps * 0.6)
        )
        capacity = request.inputs.component_mass_kg * 155

    baseline_curve = (
        _measurement_curve(request.measurements)
        if has_measurements
        else _simulate_constant_power(
            duration_minutes=request.inputs.duration_minutes,
            initial_temperature_c=request.inputs.initial_temperature_c,
            ambient_temperature_c=request.inputs.ambient_temperature_c,
            power_w=estimated_total_power_w
            * (request.inputs.duty_cycle_percent / 100),
            thermal_resistance_k_per_w=resistance,
            effective_capacity_j_per_k=capacity,
        )
    )
    baseline = _summarize_curve(
        baseline_curve,
        request.inputs.thermal_limit_c,
        resistance,
        capacity,
    )
    candidates = sorted(
        (
            _create_candidate(
                request=request,
                baseline=baseline,
                profile=profile,
                baseline_resistance=resistance,
                baseline_capacity=capacity,
            )
            for profile in SOLUTION_CATALOG
        ),
        key=lambda candidate: candidate.score,
        reverse=True,
    )
    threshold_delta = (
        baseline.max_temperature_c - request.inputs.thermal_limit_c
    )
    risk_level = (
        "High"
        if threshold_delta >= 5
        else "Medium"
        if threshold_delta >= -5 or baseline.time_to_limit_minutes is not None
        else "Low"
    )

    return ThermalAnalysisResult(
        id=f"analysis-{generated_at}",
        generated_at=generated_at,
        source=(
            "measured-calibrated"
            if has_measurements
            else "engineering-estimate"
        ),
        method_label=(
            "CSV 实测曲线校准 + 一阶 RC 热模型"
            if has_measurements
            else "一阶集总参数 RC 工程估算"
        ),
        total_power_w=_round(total_power_w, 1),
        baseline=baseline,
        candidates=candidates,
        recommended_solution_id=candidates[0].solution_id,
        risk_level=risk_level,
        warnings=(
            ["候选结构结果由实测基线校准推算，生产前仍需样机复测。"]
            if has_measurements
            else [
                "当前结果为工程估算，不等同于 CFD/FEA 或认证测试结果。",
                "上传实测 CSV 可用真实温升曲线校准模型。",
            ]
        ),
    )

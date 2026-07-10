import type {
  AnalysisRequest,
  CandidateResult,
  InterferenceRisk,
  RecommendationGrade,
  ThermalAnalysisResult,
  ThermalCaseResult,
  ThermalCurvePoint,
} from './types'

interface SolutionProfile {
  solutionId: string
  resistanceFactor: (airflowMps: number) => number
  capacityFactor: number
  addedMassPercent: number
  interferenceRisk: InterferenceRisk
  compatibilityScore: number
}

const HARDWARE_RESISTANCE: Record<string, number> = {
  'robot-joint': 1.13,
  motor: 1.04,
  'driver-board': 1.38,
  'compute-box': 1.2,
  sensor: 1.72,
  power: 0.92,
}

const SOLUTION_PROFILES: SolutionProfile[] = [
  {
    solutionId: 'flat-baseline',
    resistanceFactor: () => 0.95,
    capacityFactor: 1.02,
    addedMassPercent: 2.2,
    interferenceRisk: '低',
    compatibilityScore: 76,
  },
  {
    solutionId: 'vein-bridge',
    resistanceFactor: () => 0.78,
    capacityFactor: 1.06,
    addedMassPercent: 6.8,
    interferenceRisk: '低',
    compatibilityScore: 96,
  },
  {
    solutionId: 'pin-fin',
    resistanceFactor: (airflowMps) =>
      clamp(0.88 - airflowMps * 0.12, 0.67, 0.88),
    capacityFactor: 1.08,
    addedMassPercent: 7.6,
    interferenceRisk: '中',
    compatibilityScore: 78,
  },
  {
    solutionId: 'gyroid',
    resistanceFactor: (airflowMps) =>
      clamp(0.91 - airflowMps * 0.14, 0.63, 0.91),
    capacityFactor: 1.12,
    addedMassPercent: 9.6,
    interferenceRisk: '中',
    compatibilityScore: 72,
  },
]

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum)
}

function round(value: number, precision = 2): number {
  const factor = 10 ** precision
  return Math.round(value * factor) / factor
}

function average(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function findTimeToLimit(
  curve: ThermalCurvePoint[],
  thermalLimitC: number,
): number | null {
  for (let index = 0; index < curve.length; index += 1) {
    const point = curve[index]!
    if (point.temperatureC < thermalLimitC) continue
    if (index === 0) return round(point.timeS / 60)

    const previous = curve[index - 1]!
    const temperatureSpan = point.temperatureC - previous.temperatureC
    const ratio =
      temperatureSpan === 0
        ? 0
        : (thermalLimitC - previous.temperatureC) / temperatureSpan
    const interpolatedTime =
      previous.timeS + (point.timeS - previous.timeS) * clamp(ratio, 0, 1)
    return round(interpolatedTime / 60)
  }

  return null
}

function summarizeCurve(
  curve: ThermalCurvePoint[],
  thermalLimitC: number,
  thermalResistanceKPerW: number,
  effectiveCapacityJPerK: number,
): ThermalCaseResult {
  return {
    curve,
    maxTemperatureC: round(
      Math.max(...curve.map((point) => point.temperatureC)),
      1,
    ),
    timeToLimitMinutes: findTimeToLimit(curve, thermalLimitC),
    thermalResistanceKPerW: round(thermalResistanceKPerW, 3),
    effectiveCapacityJPerK: round(effectiveCapacityJPerK, 1),
  }
}

function simulateConstantPower(
  durationMinutes: number,
  initialTemperatureC: number,
  ambientTemperatureC: number,
  powerW: number,
  thermalResistanceKPerW: number,
  effectiveCapacityJPerK: number,
): ThermalCurvePoint[] {
  const durationS = durationMinutes * 60
  const stepS = Math.max(5, Math.min(30, durationS / 60))
  const timeConstantS = thermalResistanceKPerW * effectiveCapacityJPerK
  const steadyTemperature =
    ambientTemperatureC + powerW * thermalResistanceKPerW
  const curve: ThermalCurvePoint[] = []

  for (let timeS = 0; timeS < durationS; timeS += stepS) {
    const temperatureC =
      steadyTemperature +
      (initialTemperatureC - steadyTemperature) *
        Math.exp(-timeS / timeConstantS)
    curve.push({
      timeS: round(timeS, 1),
      temperatureC: round(temperatureC, 2),
    })
  }

  const finalTemperatureC =
    steadyTemperature +
    (initialTemperatureC - steadyTemperature) *
      Math.exp(-durationS / timeConstantS)
  curve.push({
    timeS: round(durationS, 1),
    temperatureC: round(finalTemperatureC, 2),
  })
  return curve
}

function simulateMeasuredPower(
  request: AnalysisRequest,
  thermalResistanceKPerW: number,
  effectiveCapacityJPerK: number,
): ThermalCurvePoint[] {
  const [firstPoint, ...remainingPoints] = request.measurements
  if (!firstPoint) return []

  const curve: ThermalCurvePoint[] = [
    {
      timeS: firstPoint.timeS,
      temperatureC: firstPoint.temperatureC,
    },
  ]
  let temperatureC = firstPoint.temperatureC
  let previousPoint = firstPoint
  const timeConstantS = thermalResistanceKPerW * effectiveCapacityJPerK

  for (const point of remainingPoints) {
    const deltaTimeS = point.timeS - previousPoint.timeS
    const decay = Math.exp(-deltaTimeS / timeConstantS)
    const intervalPowerW = (previousPoint.powerW + point.powerW) / 2
    const steadyTemperature =
      request.inputs.ambientTemperatureC +
      intervalPowerW * thermalResistanceKPerW
    temperatureC =
      steadyTemperature + (temperatureC - steadyTemperature) * decay
    curve.push({
      timeS: point.timeS,
      temperatureC: round(temperatureC, 2),
    })
    previousPoint = point
  }

  return curve
}

function calibrateMeasuredModel(request: AnalysisRequest): {
  resistance: number
  capacity: number
} {
  const points = request.measurements
  const firstPoint = points[0]!
  const lastPoint = points.at(-1)!
  const maxTemperatureC = Math.max(
    ...points.map((point) => point.temperatureC),
  )
  const averagePowerW = average(points.map((point) => point.powerW))
  const temperatureRise = Math.max(
    maxTemperatureC - request.inputs.ambientTemperatureC,
    0.5,
  )
  const resistance = clamp(
    temperatureRise / Math.max(averagePowerW, 0.1),
    0.03,
    8,
  )
  const targetTemperature =
    firstPoint.temperatureC +
    (maxTemperatureC - firstPoint.temperatureC) * 0.632
  const targetPoint = points.find(
    (point) => point.temperatureC >= targetTemperature,
  )
  const fallbackTauS = Math.max(
    (lastPoint.timeS - firstPoint.timeS) / 3,
    10,
  )
  const timeConstantS = Math.max(
    (targetPoint?.timeS ?? firstPoint.timeS + fallbackTauS) - firstPoint.timeS,
    10,
  )

  return {
    resistance,
    capacity: clamp(timeConstantS / resistance, 20, 100_000),
  }
}

function improvementPercent(
  baselineMinutes: number | null,
  candidateMinutes: number | null,
  durationMinutes: number,
): number | null {
  if (baselineMinutes === null) return null
  if (baselineMinutes <= 0) return 0
  const effectiveCandidate = candidateMinutes ?? durationMinutes
  return round(
    Math.max(0, ((effectiveCandidate - baselineMinutes) / baselineMinutes) * 100),
    1,
  )
}

function goalWeight(goals: string[], ...ids: string[]): number {
  const indexes = ids
    .map((id) => goals.indexOf(id))
    .filter((index) => index >= 0)
  if (indexes.length === 0) return 0.55
  const highestPriority = Math.min(...indexes)
  return clamp(1 - highestPriority * 0.1, 0.5, 1)
}

function recommendationScore(
  request: AnalysisRequest,
  baseline: ThermalCaseResult,
  candidate: Omit<CandidateResult, 'score' | 'grade'>,
  compatibilityScore: number,
): number {
  const thermalHeadroom = Math.max(
    baseline.maxTemperatureC - request.inputs.ambientTemperatureC,
    1,
  )
  const coolingScore = clamp(
    (candidate.hotspotReductionC / thermalHeadroom) * 260,
    0,
    100,
  )
  const delayScore =
    candidate.timeToLimitImprovementPercent === null
      ? coolingScore
      : clamp(candidate.timeToLimitImprovementPercent * 1.8, 0, 100)
  const massScore = clamp(100 - candidate.addedMassPercent * 7, 0, 100)
  const riskScore =
    candidate.interferenceRisk === '低'
      ? 100
      : candidate.interferenceRisk === '中'
        ? 62
        : 25

  const coolingWeight = goalWeight(
    request.optimizationGoals,
    'lower-hotspot',
  )
  const delayWeight = goalWeight(
    request.optimizationGoals,
    'delay-limit',
    'task-duration',
  )
  const massWeight = goalWeight(request.optimizationGoals, 'weight-limit')
  const compatibilityWeight = goalWeight(
    request.optimizationGoals,
    'original-structure',
    'maintainability',
    'interference-risk',
  )
  const totalWeight =
    coolingWeight + delayWeight + massWeight + compatibilityWeight

  let score =
    (coolingScore * coolingWeight +
      delayScore * delayWeight +
      massScore * massWeight +
      ((compatibilityScore + riskScore) / 2) * compatibilityWeight) /
    totalWeight

  if (
    request.constraints.includes('weight-limit') &&
    candidate.addedMassPercent > 8
  ) {
    score -= 24
  }
  if (
    request.constraints.includes('motion-envelope') &&
    candidate.interferenceRisk !== '低'
  ) {
    score -= 10
  }
  if (
    request.constraints.includes('removable') &&
    candidate.solutionId === 'vein-bridge'
  ) {
    score += 5
  }

  return round(clamp(score, 0, 100), 1)
}

function gradeForScore(score: number): RecommendationGrade {
  if (score >= 78) return 'A'
  if (score >= 64) return 'B'
  if (score >= 48) return 'C'
  return 'D'
}

function createCandidate(
  request: AnalysisRequest,
  baseline: ThermalCaseResult,
  profile: SolutionProfile,
  baselineResistance: number,
  baselineCapacity: number,
): CandidateResult {
  const resistance =
    baselineResistance * profile.resistanceFactor(request.inputs.airflowMps)
  const capacity = baselineCapacity * profile.capacityFactor
  const curve =
    request.measurements.length > 0
      ? simulateMeasuredPower(request, resistance, capacity)
      : simulateConstantPower(
          request.inputs.durationMinutes,
          request.inputs.initialTemperatureC,
          request.inputs.ambientTemperatureC,
          Object.values(request.heatSources).reduce(
            (sum, power) => sum + power,
            0,
          ) *
            (request.inputs.dutyCyclePercent / 100),
          resistance,
          capacity,
        )
  const summarized = summarizeCurve(
    curve,
    request.inputs.thermalLimitC,
    resistance,
    capacity,
  )
  const durationMinutes =
    request.measurements.length > 0
      ? request.measurements.at(-1)!.timeS / 60
      : request.inputs.durationMinutes
  const candidateWithoutScore = {
    ...summarized,
    solutionId: profile.solutionId,
    addedMassPercent: profile.addedMassPercent,
    interferenceRisk: profile.interferenceRisk,
    hotspotReductionC: round(
      baseline.maxTemperatureC - summarized.maxTemperatureC,
      1,
    ),
    timeToLimitImprovementPercent: improvementPercent(
      baseline.timeToLimitMinutes,
      summarized.timeToLimitMinutes,
      durationMinutes,
    ),
  }
  const score = recommendationScore(
    request,
    baseline,
    candidateWithoutScore,
    profile.compatibilityScore,
  )

  return {
    ...candidateWithoutScore,
    score,
    grade: gradeForScore(score),
  }
}

export function validateAnalysisRequest(request: AnalysisRequest): string[] {
  const errors: string[] = []
  const { inputs } = request
  const heatSourcePowers = Object.values(request.heatSources)
  const totalPowerW = heatSourcePowers.reduce(
    (sum, power) => sum + power,
    0,
  )

  if (
    heatSourcePowers.some(
      (power) => !Number.isFinite(power) || power < 0,
    )
  ) {
    errors.push('热源功率必须是大于等于 0W 的有效数字')
  }
  if (totalPowerW <= 0 && request.measurements.length === 0) {
    errors.push('请至少选择一个功率大于 0W 的热源')
  }
  if (request.measurements.length > 0 && request.measurements.length < 3) {
    errors.push('实测数据至少需要 3 个有效点')
  }
  if (request.measurements.length > 5_000) {
    errors.push('实测数据最多支持 5000 个点')
  }
  if (
    request.measurements.length >= 3 &&
    average(request.measurements.map((point) => point.powerW)) <= 0
  ) {
    errors.push('实测数据的平均功率必须大于 0W')
  }
  for (let index = 1; index < request.measurements.length; index += 1) {
    if (
      request.measurements[index]!.timeS <=
      request.measurements[index - 1]!.timeS
    ) {
      errors.push('实测数据时间必须严格递增')
      break
    }
  }
  if (inputs.ambientTemperatureC < -40 || inputs.ambientTemperatureC > 100) {
    errors.push('环境温度需在 -40℃ 到 100℃ 之间')
  }
  if (inputs.initialTemperatureC < -40 || inputs.initialTemperatureC > 200) {
    errors.push('初始温度需在 -40℃ 到 200℃ 之间')
  }
  if (inputs.thermalLimitC <= inputs.ambientTemperatureC) {
    errors.push('热保护阈值必须高于环境温度')
  }
  if (inputs.thermalLimitC > 250) {
    errors.push('热保护阈值不能超过 250℃')
  }
  if (inputs.durationMinutes < 0.5 || inputs.durationMinutes > 120) {
    errors.push('任务时长需在 0.5 到 120 分钟之间')
  }
  if (inputs.dutyCyclePercent < 1 || inputs.dutyCyclePercent > 100) {
    errors.push('负载占空比需在 1% 到 100% 之间')
  }
  if (inputs.airflowMps < 0 || inputs.airflowMps > 20) {
    errors.push('环境风速需在 0 到 20m/s 之间')
  }
  if (inputs.componentMassKg <= 0 || inputs.componentMassKg > 100) {
    errors.push('对象质量需大于 0kg 且不超过 100kg')
  }

  return errors
}

export function calculateThermalAnalysis(
  request: AnalysisRequest,
  generatedAt = new Date().toISOString(),
): ThermalAnalysisResult {
  const validationErrors = validateAnalysisRequest(request)
  if (validationErrors.length > 0) {
    throw new Error(validationErrors.join('；'))
  }

  const hasMeasurements = request.measurements.length >= 3
  const estimatedTotalPowerW = Object.values(request.heatSources).reduce(
    (sum, power) => sum + power,
    0,
  )
  const totalPowerW = hasMeasurements
    ? average(request.measurements.map((point) => point.powerW))
    : estimatedTotalPowerW
  const model = hasMeasurements
    ? calibrateMeasuredModel(request)
    : {
        resistance:
          (HARDWARE_RESISTANCE[request.hardwareId] ?? 1.2) /
          (1 + request.inputs.airflowMps * 0.6),
        capacity: request.inputs.componentMassKg * 155,
      }
  const baselineCurve = hasMeasurements
    ? request.measurements
    : simulateConstantPower(
        request.inputs.durationMinutes,
        request.inputs.initialTemperatureC,
        request.inputs.ambientTemperatureC,
        estimatedTotalPowerW * (request.inputs.dutyCyclePercent / 100),
        model.resistance,
        model.capacity,
      )
  const baseline = summarizeCurve(
    baselineCurve,
    request.inputs.thermalLimitC,
    model.resistance,
    model.capacity,
  )
  const candidates = SOLUTION_PROFILES.map((profile) =>
    createCandidate(
      request,
      baseline,
      profile,
      model.resistance,
      model.capacity,
    ),
  ).sort((left, right) => right.score - left.score)
  const recommendedSolutionId = candidates[0]!.solutionId
  const thresholdDelta =
    baseline.maxTemperatureC - request.inputs.thermalLimitC
  const riskLevel =
    thresholdDelta >= 5
      ? 'High'
      : thresholdDelta >= -5 || baseline.timeToLimitMinutes !== null
        ? 'Medium'
        : 'Low'

  return {
    id: `analysis-${generatedAt}`,
    generatedAt,
    source: hasMeasurements
      ? 'measured-calibrated'
      : 'engineering-estimate',
    methodLabel: hasMeasurements
      ? 'CSV 实测曲线校准 + 一阶 RC 热模型'
      : '一阶集总参数 RC 工程估算',
    totalPowerW: round(totalPowerW, 1),
    baseline,
    candidates,
    recommendedSolutionId,
    riskLevel,
    warnings: hasMeasurements
      ? ['候选结构结果由实测基线校准推算，生产前仍需样机复测。']
      : [
          '当前结果为工程估算，不等同于 CFD/FEA 或认证测试结果。',
          '上传实测 CSV 可用真实温升曲线校准模型。',
        ],
  }
}

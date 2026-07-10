export interface AnalysisInputs {
  ambientTemperatureC: number
  initialTemperatureC: number
  thermalLimitC: number
  durationMinutes: number
  dutyCyclePercent: number
  airflowMps: number
  componentMassKg: number
}

export interface MeasurementPoint {
  timeS: number
  temperatureC: number
  powerW: number
}

export interface ThermalCurvePoint {
  timeS: number
  temperatureC: number
  powerW?: number
}

export interface ThermalCaseResult {
  curve: ThermalCurvePoint[]
  maxTemperatureC: number
  timeToLimitMinutes: number | null
  thermalResistanceKPerW: number
  effectiveCapacityJPerK: number
}

export type InterferenceRisk = '低' | '中' | '高'
export type RecommendationGrade = 'A' | 'B' | 'C' | 'D'

export interface CandidateResult extends ThermalCaseResult {
  solutionId: string
  score: number
  grade: RecommendationGrade
  addedMassPercent: number
  interferenceRisk: InterferenceRisk
  hotspotReductionC: number
  timeToLimitImprovementPercent: number | null
}

export interface AnalysisRequest {
  hardwareId: string
  jointId: string
  heatSources: Record<string, number>
  constraints: string[]
  optimizationGoals: string[]
  inputs: AnalysisInputs
  measurements: MeasurementPoint[]
}

export interface ThermalAnalysisResult {
  id: string
  generatedAt: string
  source: 'engineering-estimate' | 'measured-calibrated'
  methodLabel: string
  totalPowerW: number
  baseline: ThermalCaseResult
  candidates: CandidateResult[]
  recommendedSolutionId: string
  riskLevel: 'Low' | 'Medium' | 'High'
  warnings: string[]
}

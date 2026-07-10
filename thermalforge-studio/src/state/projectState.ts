import type {
  AnalysisInputs,
  MeasurementPoint,
  ThermalAnalysisResult,
  ThermalCurvePoint,
} from '../analysis/types'

export const PROJECT_STORAGE_KEY = 'thermalforge-project-v1'

export const STEP_IDS = [
  'dashboard',
  'scenario',
  'hardware',
  'constraints',
  'structures',
  'results',
  'report',
] as const

export type StepId = (typeof STEP_IDS)[number]

export interface ThermalProjectState {
  currentStep: StepId
  projectName: string
  scenarioId: string
  hardwareId: string
  jointId: string
  heatSources: Record<string, number>
  constraints: string[]
  optimizationGoals: string[]
  selectedSolutionId: string
  analysisInputs: AnalysisInputs
  measurements: MeasurementPoint[]
  analysisResult: ThermalAnalysisResult | null
}

export type ProjectAction =
  | { type: 'setStep'; step: StepId }
  | { type: 'selectScenario'; scenarioId: string }
  | { type: 'selectHardware'; hardwareId: string }
  | { type: 'selectJoint'; jointId: string }
  | {
      type: 'toggleHeatSource'
      sourceId: string
      defaultPower: number
    }
  | { type: 'setHeatPower'; sourceId: string; power: number }
  | { type: 'toggleConstraint'; constraintId: string }
  | { type: 'moveGoal'; fromIndex: number; toIndex: number }
  | { type: 'selectSolution'; solutionId: string }
  | {
      type: 'setAnalysisInput'
      field: keyof AnalysisInputs
      value: number
    }
  | { type: 'setMeasurements'; measurements: MeasurementPoint[] }
  | { type: 'clearMeasurements' }
  | { type: 'completeAnalysis'; result: ThermalAnalysisResult }
  | { type: 'reset' }

interface StorageReader {
  getItem(key: string): string | null
}

interface StorageWriter {
  setItem(key: string, value: string): void
}

const DEFAULT_CONSTRAINTS = [
  'sealed-case',
  'warranty-seal',
  'motor-untouched',
  'reducer-untouched',
  'cable-clearance',
  'bearing-clearance',
  'weight-limit',
]

const DEFAULT_GOALS = [
  'delay-limit',
  'lower-hotspot',
  'weight-limit',
  'original-structure',
  'task-duration',
  'manufacturing-cost',
  'maintainability',
  'interference-risk',
]

export function createDefaultProjectState(): ThermalProjectState {
  return {
    currentStep: 'dashboard',
    projectName: '膝关节热优化 Demo',
    scenarioId: 'humanoid-rescue',
    hardwareId: 'robot-joint',
    jointId: 'knee',
    heatSources: {
      'motor-winding': 60,
      mosfet: 20,
    },
    constraints: [...DEFAULT_CONSTRAINTS],
    optimizationGoals: [...DEFAULT_GOALS],
    selectedSolutionId: 'vein-bridge',
    analysisInputs: {
      ambientTemperatureC: 25,
      initialTemperatureC: 30,
      thermalLimitC: 80,
      durationMinutes: 15,
      dutyCyclePercent: 85,
      airflowMps: 0.3,
      componentMassKg: 1.8,
    },
    measurements: [],
    analysisResult: null,
  }
}

export function moveGoal<T>(
  goals: readonly T[],
  fromIndex: number,
  toIndex: number,
): T[] {
  if (
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= goals.length ||
    toIndex >= goals.length ||
    fromIndex === toIndex
  ) {
    return [...goals]
  }

  const reordered = [...goals]
  const [moved] = reordered.splice(fromIndex, 1)
  reordered.splice(toIndex, 0, moved)
  return reordered
}

export function projectReducer(
  state: ThermalProjectState,
  action: ProjectAction,
): ThermalProjectState {
  const invalidate = (
    changes: Partial<ThermalProjectState>,
  ): ThermalProjectState => ({
    ...state,
    ...changes,
    analysisResult: null,
  })

  switch (action.type) {
    case 'setStep':
      return { ...state, currentStep: action.step }
    case 'selectScenario':
      return invalidate({ scenarioId: action.scenarioId })
    case 'selectHardware':
      return invalidate({ hardwareId: action.hardwareId })
    case 'selectJoint':
      return invalidate({ jointId: action.jointId })
    case 'toggleHeatSource': {
      const heatSources = { ...state.heatSources }
      if (action.sourceId in heatSources) {
        delete heatSources[action.sourceId]
      } else {
        heatSources[action.sourceId] = action.defaultPower
      }
      return invalidate({ heatSources })
    }
    case 'setHeatPower':
      if (!(action.sourceId in state.heatSources)) {
        return state
      }
      return invalidate({
        heatSources: {
          ...state.heatSources,
          [action.sourceId]: Math.max(0, action.power),
        },
      })
    case 'toggleConstraint': {
      const selected = state.constraints.includes(action.constraintId)
      return invalidate({
        constraints: selected
          ? state.constraints.filter((id) => id !== action.constraintId)
          : [...state.constraints, action.constraintId],
      })
    }
    case 'moveGoal':
      return invalidate({
        optimizationGoals: moveGoal(
          state.optimizationGoals,
          action.fromIndex,
          action.toIndex,
        ),
      })
    case 'selectSolution':
      return { ...state, selectedSolutionId: action.solutionId }
    case 'setAnalysisInput':
      if (!Number.isFinite(action.value)) {
        return state
      }
      return invalidate({
        analysisInputs: {
          ...state.analysisInputs,
          [action.field]: action.value,
        },
      })
    case 'setMeasurements':
      return invalidate({ measurements: [...action.measurements] })
    case 'clearMeasurements':
      return invalidate({ measurements: [] })
    case 'completeAnalysis':
      return {
        ...state,
        analysisResult: action.result,
        selectedSolutionId: action.result.recommendedSolutionId,
      }
    case 'reset':
      return createDefaultProjectState()
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isMeasurementPoint(value: unknown): value is MeasurementPoint {
  return (
    isRecord(value) &&
    isFiniteNumber(value.timeS) &&
    value.timeS >= 0 &&
    isFiniteNumber(value.temperatureC) &&
    isFiniteNumber(value.powerW) &&
    value.powerW >= 0
  )
}

function isThermalCurvePoint(value: unknown): value is ThermalCurvePoint {
  return (
    isRecord(value) &&
    isFiniteNumber(value.timeS) &&
    value.timeS >= 0 &&
    isFiniteNumber(value.temperatureC) &&
    (value.powerW === undefined ||
      (isFiniteNumber(value.powerW) && value.powerW >= 0))
  )
}

function isThermalCaseResult(value: unknown): boolean {
  return (
    isRecord(value) &&
    Array.isArray(value.curve) &&
    value.curve.length > 0 &&
    value.curve.every(isThermalCurvePoint) &&
    isFiniteNumber(value.maxTemperatureC) &&
    (value.timeToLimitMinutes === null ||
      isFiniteNumber(value.timeToLimitMinutes)) &&
    isFiniteNumber(value.thermalResistanceKPerW) &&
    isFiniteNumber(value.effectiveCapacityJPerK)
  )
}

function isThermalAnalysisResult(
  value: unknown,
): value is ThermalAnalysisResult {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.generatedAt === 'string' &&
    (value.source === 'engineering-estimate' ||
      value.source === 'measured-calibrated') &&
    typeof value.methodLabel === 'string' &&
    isFiniteNumber(value.totalPowerW) &&
    isThermalCaseResult(value.baseline) &&
    Array.isArray(value.candidates) &&
    value.candidates.length > 0 &&
    value.candidates.every(
      (candidate) =>
        isThermalCaseResult(candidate) &&
        isRecord(candidate) &&
        typeof candidate.solutionId === 'string' &&
        isFiniteNumber(candidate.score) &&
        (candidate.grade === 'A' ||
          candidate.grade === 'B' ||
          candidate.grade === 'C' ||
          candidate.grade === 'D') &&
        isFiniteNumber(candidate.addedMassPercent) &&
        (candidate.interferenceRisk === '低' ||
          candidate.interferenceRisk === '中' ||
          candidate.interferenceRisk === '高') &&
        isFiniteNumber(candidate.hotspotReductionC) &&
        (candidate.timeToLimitImprovementPercent === null ||
          isFiniteNumber(candidate.timeToLimitImprovementPercent)),
    ) &&
    typeof value.recommendedSolutionId === 'string' &&
    (value.riskLevel === 'Low' ||
      value.riskLevel === 'Medium' ||
      value.riskLevel === 'High') &&
    Array.isArray(value.warnings) &&
    value.warnings.every((warning) => typeof warning === 'string')
  )
}

function isStepId(value: unknown): value is StepId {
  return typeof value === 'string' && STEP_IDS.includes(value as StepId)
}

export function loadProjectState(
  storage: StorageReader,
): ThermalProjectState {
  const defaults = createDefaultProjectState()

  try {
    const raw = storage.getItem(PROJECT_STORAGE_KEY)
    if (!raw) {
      return defaults
    }

    const saved: unknown = JSON.parse(raw)
    if (!isRecord(saved)) {
      return defaults
    }

    return {
      ...defaults,
      currentStep: isStepId(saved.currentStep)
        ? saved.currentStep
        : defaults.currentStep,
      projectName:
        typeof saved.projectName === 'string'
          ? saved.projectName
          : defaults.projectName,
      scenarioId:
        typeof saved.scenarioId === 'string'
          ? saved.scenarioId
          : defaults.scenarioId,
      hardwareId:
        typeof saved.hardwareId === 'string'
          ? saved.hardwareId
          : defaults.hardwareId,
      jointId:
        typeof saved.jointId === 'string' ? saved.jointId : defaults.jointId,
      heatSources: isRecord(saved.heatSources)
        ? Object.fromEntries(
            Object.entries(saved.heatSources).filter(
              (entry): entry is [string, number] =>
                typeof entry[1] === 'number' &&
                Number.isFinite(entry[1]) &&
                entry[1] >= 0,
            ),
          )
        : defaults.heatSources,
      constraints: Array.isArray(saved.constraints)
        ? saved.constraints.filter(
            (value): value is string => typeof value === 'string',
          )
        : defaults.constraints,
      optimizationGoals: Array.isArray(saved.optimizationGoals)
        ? saved.optimizationGoals.filter(
            (value): value is string => typeof value === 'string',
          )
        : defaults.optimizationGoals,
      selectedSolutionId:
        typeof saved.selectedSolutionId === 'string'
          ? saved.selectedSolutionId
          : defaults.selectedSolutionId,
      analysisInputs: isRecord(saved.analysisInputs)
        ? {
            ambientTemperatureC: isFiniteNumber(
              saved.analysisInputs.ambientTemperatureC,
            )
              ? saved.analysisInputs.ambientTemperatureC
              : defaults.analysisInputs.ambientTemperatureC,
            initialTemperatureC: isFiniteNumber(
              saved.analysisInputs.initialTemperatureC,
            )
              ? saved.analysisInputs.initialTemperatureC
              : defaults.analysisInputs.initialTemperatureC,
            thermalLimitC: isFiniteNumber(
              saved.analysisInputs.thermalLimitC,
            )
              ? saved.analysisInputs.thermalLimitC
              : defaults.analysisInputs.thermalLimitC,
            durationMinutes: isFiniteNumber(
              saved.analysisInputs.durationMinutes,
            )
              ? saved.analysisInputs.durationMinutes
              : defaults.analysisInputs.durationMinutes,
            dutyCyclePercent: isFiniteNumber(
              saved.analysisInputs.dutyCyclePercent,
            )
              ? saved.analysisInputs.dutyCyclePercent
              : defaults.analysisInputs.dutyCyclePercent,
            airflowMps: isFiniteNumber(saved.analysisInputs.airflowMps)
              ? saved.analysisInputs.airflowMps
              : defaults.analysisInputs.airflowMps,
            componentMassKg: isFiniteNumber(
              saved.analysisInputs.componentMassKg,
            )
              ? saved.analysisInputs.componentMassKg
              : defaults.analysisInputs.componentMassKg,
          }
        : defaults.analysisInputs,
      measurements: Array.isArray(saved.measurements)
        ? saved.measurements.filter(isMeasurementPoint).slice(0, 5_000)
        : defaults.measurements,
      analysisResult: isThermalAnalysisResult(saved.analysisResult)
        ? saved.analysisResult
        : null,
    }
  } catch {
    return defaults
  }
}

export function saveProjectState(
  storage: StorageWriter,
  state: ThermalProjectState,
): void {
  storage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(state))
}

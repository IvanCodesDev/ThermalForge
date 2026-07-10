import { describe, expect, it } from 'vitest'
import type { ThermalAnalysisResult } from '../analysis/types'
import {
  createDefaultProjectState,
  loadProjectState,
  moveGoal,
  projectReducer,
} from './projectState'

describe('project state', () => {
  it('starts with the approved demo defaults', () => {
    const state = createDefaultProjectState()

    expect(state.scenarioId).toBe('humanoid-rescue')
    expect(state.hardwareId).toBe('robot-joint')
    expect(state.jointId).toBe('knee')
    expect(state.heatSources).toEqual({
      'motor-winding': 60,
      mosfet: 20,
    })
    expect(state.constraints).toContain('sealed-case')
    expect(state.constraints).toContain('weight-limit')
    expect(state.selectedSolutionId).toBe('vein-bridge')
    expect(state.analysisInputs.ambientTemperatureC).toBe(25)
    expect(state.measurements).toEqual([])
    expect(state.analysisResult).toBeNull()
  })

  it('adds and removes optional heat sources without losing power presets', () => {
    const initial = createDefaultProjectState()
    const withGearbox = projectReducer(initial, {
      type: 'toggleHeatSource',
      sourceId: 'gearbox',
      defaultPower: 10,
    })
    const withoutMotor = projectReducer(withGearbox, {
      type: 'toggleHeatSource',
      sourceId: 'motor-winding',
      defaultPower: 60,
    })

    expect(withGearbox.heatSources.gearbox).toBe(10)
    expect(withoutMotor.heatSources['motor-winding']).toBeUndefined()
    expect(withoutMotor.heatSources.gearbox).toBe(10)
  })

  it('moves optimization goals and ignores invalid indexes', () => {
    expect(moveGoal(['delay-limit', 'lower-hotspot', 'weight'], 0, 2)).toEqual([
      'lower-hotspot',
      'weight',
      'delay-limit',
    ])
    expect(moveGoal(['a', 'b'], -1, 1)).toEqual(['a', 'b'])
    expect(moveGoal(['a', 'b'], 0, 4)).toEqual(['a', 'b'])
  })

  it('invalidates a completed analysis whenever a calculation input changes', () => {
    const result = { id: 'analysis-test' } as ThermalAnalysisResult
    const analyzed = {
      ...createDefaultProjectState(),
      analysisResult: result,
    }

    const changedInput = projectReducer(analyzed, {
      type: 'setAnalysisInput',
      field: 'ambientTemperatureC',
      value: 32,
    })
    expect(changedInput.analysisInputs.ambientTemperatureC).toBe(32)
    expect(changedInput.analysisResult).toBeNull()

    const changedPower = projectReducer(analyzed, {
      type: 'setHeatPower',
      sourceId: 'motor-winding',
      power: 100,
    })
    expect(changedPower.analysisResult).toBeNull()
  })

  it('stores imported measurements and the explicit analysis result', () => {
    const initial = createDefaultProjectState()
    const measurements = [
      { timeS: 0, temperatureC: 30, powerW: 80 },
      { timeS: 60, temperatureC: 40, powerW: 80 },
      { timeS: 120, temperatureC: 50, powerW: 80 },
    ]
    const withMeasurements = projectReducer(initial, {
      type: 'setMeasurements',
      measurements,
    })
    const result = {
      id: 'analysis-test',
      recommendedSolutionId: 'pin-fin',
    } as ThermalAnalysisResult
    const analyzed = projectReducer(withMeasurements, {
      type: 'completeAnalysis',
      result,
    })

    expect(withMeasurements.measurements).toEqual(measurements)
    expect(analyzed.analysisResult).toBe(result)
    expect(analyzed.selectedSolutionId).toBe('pin-fin')
  })

  it('falls back to defaults when a saved draft is malformed', () => {
    const storage = {
      getItem: () => '{broken-json',
    }

    expect(loadProjectState(storage).scenarioId).toBe('humanoid-rescue')
  })
})

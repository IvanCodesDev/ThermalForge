import { describe, expect, it } from 'vitest'
import type { AnalysisRequest } from './types'
import { calculateThermalAnalysis } from './thermalEngine'

const BASE_REQUEST: AnalysisRequest = {
  hardwareId: 'robot-joint',
  jointId: 'knee',
  heatSources: {
    'motor-winding': 60,
    mosfet: 20,
  },
  constraints: [
    'sealed-case',
    'warranty-seal',
    'motor-untouched',
    'reducer-untouched',
    'cable-clearance',
    'bearing-clearance',
    'weight-limit',
  ],
  optimizationGoals: [
    'delay-limit',
    'lower-hotspot',
    'weight-limit',
    'original-structure',
  ],
  inputs: {
    ambientTemperatureC: 25,
    initialTemperatureC: 30,
    thermalLimitC: 80,
    durationMinutes: 15,
    dutyCyclePercent: 85,
    airflowMps: 0.3,
    componentMassKg: 1.8,
  },
  measurements: [],
}

describe('thermal analysis engine', () => {
  it('turns explicit manual inputs into comparable thermal outputs', () => {
    const result = calculateThermalAnalysis(BASE_REQUEST, '2026-07-10T12:00:00Z')

    expect(result.source).toBe('engineering-estimate')
    expect(result.totalPowerW).toBe(80)
    expect(result.baseline.curve.length).toBeGreaterThan(10)
    expect(result.baseline.curve[0]?.temperatureC).toBeCloseTo(30, 1)
    expect(result.baseline.maxTemperatureC).toBeGreaterThan(30)
    expect(result.candidates).toHaveLength(4)
    expect(result.recommendedSolutionId).toBeTruthy()

    const recommended = result.candidates.find(
      (candidate) => candidate.solutionId === result.recommendedSolutionId,
    )
    expect(recommended).toBeDefined()
    expect(recommended!.maxTemperatureC).toBeLessThan(
      result.baseline.maxTemperatureC,
    )
    expect(recommended!.curve).toHaveLength(result.baseline.curve.length)
  })

  it('raises the predicted hotspot when heat-source power increases', () => {
    const lowPower = calculateThermalAnalysis(BASE_REQUEST)
    const highPower = calculateThermalAnalysis({
      ...BASE_REQUEST,
      heatSources: {
        'motor-winding': 100,
        mosfet: 40,
      },
    })

    expect(highPower.totalPowerW).toBe(140)
    expect(highPower.baseline.maxTemperatureC).toBeGreaterThan(
      lowPower.baseline.maxTemperatureC,
    )
  })

  it('uses imported measurements as the baseline and marks the result calibrated', () => {
    const measurements = [
      { timeS: 0, temperatureC: 31, powerW: 75 },
      { timeS: 60, temperatureC: 38, powerW: 78 },
      { timeS: 120, temperatureC: 46, powerW: 80 },
      { timeS: 180, temperatureC: 54, powerW: 81 },
      { timeS: 240, temperatureC: 61, powerW: 80 },
    ]
    const result = calculateThermalAnalysis({
      ...BASE_REQUEST,
      measurements,
    })

    expect(result.source).toBe('measured-calibrated')
    expect(result.baseline.curve).toEqual(measurements)
    expect(result.baseline.maxTemperatureC).toBe(61)
    expect(result.totalPowerW).toBeCloseTo(78.8, 1)
  })

  it('keeps threshold metrics finite when the object starts above its limit', () => {
    const result = calculateThermalAnalysis({
      ...BASE_REQUEST,
      inputs: {
        ...BASE_REQUEST.inputs,
        initialTemperatureC: 85,
      },
    })

    expect(result.baseline.timeToLimitMinutes).toBe(0)
    for (const candidate of result.candidates) {
      expect(candidate.timeToLimitImprovementPercent).toBe(0)
      expect(Number.isFinite(candidate.score)).toBe(true)
    }
  })
})

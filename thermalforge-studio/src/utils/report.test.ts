import { describe, expect, it } from 'vitest'
import { calculateThermalAnalysis } from '../analysis/thermalEngine'
import { createDefaultProjectState } from '../state/projectState'
import { buildReportText, createReportFilename } from './report'

describe('thermal diagnosis report', () => {
  it('refuses to export a report before a real analysis has run', () => {
    expect(() => buildReportText(createDefaultProjectState())).toThrow(
      /尚未生成热分析输出/,
    )
  })

  it('includes the selected setup and calculated result metrics', () => {
    const initial = createDefaultProjectState()
    const analysisResult = calculateThermalAnalysis({
      hardwareId: initial.hardwareId,
      jointId: initial.jointId,
      heatSources: initial.heatSources,
      constraints: initial.constraints,
      optimizationGoals: initial.optimizationGoals,
      inputs: initial.analysisInputs,
      measurements: initial.measurements,
    })
    const state = {
      ...initial,
      analysisResult,
      selectedSolutionId: analysisResult.recommendedSolutionId,
    }
    const candidate = analysisResult.candidates.find(
      (item) => item.solutionId === state.selectedSolutionId,
    )!
    const report = buildReportText(state)

    expect(report).toContain('ThermalForge Studio')
    expect(report).toContain('人形机器人救援任务')
    expect(report).toContain('膝关节')
    expect(report).toContain('电机绕组：60W')
    expect(report).toContain('MOSFET / 驱控板：20W')
    expect(report).toContain(
      `优化前最高温度：${analysisResult.baseline.maxTemperatureC.toFixed(1)}℃`,
    )
    expect(report).toContain(
      `热点温降：${candidate.hotspotReductionC.toFixed(1)}℃`,
    )
    expect(report).toContain(analysisResult.methodLabel)
  })

  it('creates a filesystem-safe report filename', () => {
    expect(createReportFilename('膝关节 / Demo:01')).toMatch(
      /^ThermalForge-膝关节-Demo-01-\d{4}-\d{2}-\d{2}\.txt$/,
    )
  })
})

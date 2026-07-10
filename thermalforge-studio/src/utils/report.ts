import {
  CONSTRAINTS,
  HARDWARE_OPTIONS,
  HEAT_SOURCES,
  JOINT_OPTIONS,
  SCENARIOS,
  SOLUTIONS,
  findLabel,
} from '../data/content'
import type { CandidateResult, ThermalAnalysisResult } from '../analysis/types'
import type { ThermalProjectState } from '../state/projectState'

function formatHeatSources(state: ThermalProjectState): string[] {
  return Object.entries(state.heatSources).map(([sourceId, power]) => {
    const label = findLabel(HEAT_SOURCES, sourceId)
    return `${label}：${power}W`
  })
}

function formatConstraints(state: ThermalProjectState): string[] {
  return state.constraints.map((id) => findLabel(CONSTRAINTS, id))
}

function requireAnalysis(state: ThermalProjectState): {
  analysis: ThermalAnalysisResult
  candidate: CandidateResult
} {
  if (!state.analysisResult) {
    throw new Error('尚未生成热分析输出，请先运行热分析')
  }

  const candidate =
    state.analysisResult.candidates.find(
      (item) => item.solutionId === state.selectedSolutionId,
    ) ?? state.analysisResult.candidates[0]
  if (!candidate) {
    throw new Error('热分析输出中没有可用候选方案')
  }

  return { analysis: state.analysisResult, candidate }
}

function formatLimitTime(minutes: number | null, durationMinutes: number): string {
  return minutes === null
    ? `未达到（>${durationMinutes.toFixed(1)}min）`
    : `${minutes.toFixed(1)}min`
}

export function buildReportText(state: ThermalProjectState): string {
  const { analysis, candidate } = requireAnalysis(state)
  const scenario = SCENARIOS.find((item) => item.id === state.scenarioId)
  const solution = SOLUTIONS.find(
    (item) => item.id === candidate.solutionId,
  )
  const durationMinutes =
    (analysis.baseline.curve.at(-1)?.timeS ?? 0) / 60
  const sourceLabel =
    analysis.source === 'measured-calibrated' ? '实测校准' : '工程估算'

  return [
    'ThermalForge Studio',
    '机器人关节热诊断与热结构生成报告',
    '========================================',
    '',
    '一、项目基本信息',
    `项目名称：${state.projectName}`,
    `任务场景：${scenario?.title ?? state.scenarioId}`,
    `目标硬件：${findLabel(HARDWARE_OPTIONS, state.hardwareId)}`,
    `关节类型：${
      state.hardwareId === 'robot-joint'
        ? findLabel(JOINT_OPTIONS, state.jointId)
        : 'N/A'
    }`,
    `环境温度：${state.analysisInputs.ambientTemperatureC}℃`,
    `初始温度：${state.analysisInputs.initialTemperatureC}℃`,
    `热保护阈值：${state.analysisInputs.thermalLimitC}℃`,
    `任务时长：${state.analysisInputs.durationMinutes}min`,
    `负载占空比：${state.analysisInputs.dutyCyclePercent}%`,
    `环境风速：${state.analysisInputs.airflowMps}m/s`,
    `对象质量：${state.analysisInputs.componentMassKg}kg`,
    `数据来源：${sourceLabel}`,
    `计算方法：${analysis.methodLabel}`,
    '',
    '二、热源设置',
    ...formatHeatSources(state).map((item) => `- ${item}`),
    '',
    '三、安装约束',
    ...formatConstraints(state).map((item) => `- ${item}`),
    '',
    '四、热诊断结果',
    `热点对象：${findLabel(HARDWARE_OPTIONS, state.hardwareId)}`,
    `最高温度：${analysis.baseline.maxTemperatureC.toFixed(1)}℃`,
    `原始方案达到 ${state.analysisInputs.thermalLimitC}℃ 时间：${formatLimitTime(
      analysis.baseline.timeToLimitMinutes,
      durationMinutes,
    )}`,
    `热保护风险：${analysis.riskLevel}`,
    '',
    '五、推荐结构方案',
    `结构类型：${solution?.title ?? candidate.solutionId}`,
    `综合评分：${candidate.score.toFixed(1)} / 100`,
    `推荐等级：${candidate.grade}`,
    '安装位置：关节外壳热点邻近区域',
    '材料建议：6061-T6 铝合金 + 柔性导热垫',
    '制造方式：CNC / 金属 3D 打印 / 混合制造',
    '',
    '六、A/B 测试结果',
    `优化前最高温度：${analysis.baseline.maxTemperatureC.toFixed(1)}℃`,
    `优化后最高温度：${candidate.maxTemperatureC.toFixed(1)}℃`,
    `热点温降：${candidate.hotspotReductionC.toFixed(1)}℃`,
    `优化后达到 ${state.analysisInputs.thermalLimitC}℃ 时间：${formatLimitTime(
      candidate.timeToLimitMinutes,
      durationMinutes,
    )}`,
    `Time-to-limit 提升：${
      candidate.timeToLimitImprovementPercent === null
        ? 'N/A'
        : `${candidate.timeToLimitMinutes === null ? '≥' : ''}${candidate.timeToLimitImprovementPercent.toFixed(1)}%`
    }`,
    `单对象增重：${candidate.addedMassPercent.toFixed(1)}%`,
    `干涉风险：${candidate.interferenceRisk}`,
    '',
    '七、安装与风险提示',
    '- 避开线束、轴承座、编码器与螺丝孔',
    '- 不改变原厂安全保护阈值',
    '- 注意可触摸表面温度',
    '- 注意灰尘积聚与运动碰撞风险',
    '',
    '八、模型边界',
    ...analysis.warnings.map((warning) => `- ${warning}`),
  ].join('\n')
}

export function buildAbReportText(state: ThermalProjectState): string {
  const { analysis, candidate } = requireAnalysis(state)
  const durationMinutes =
    (analysis.baseline.curve.at(-1)?.timeS ?? 0) / 60
  return [
    'ThermalForge Studio · A/B 热性能测试报告',
    `项目：${state.projectName}`,
    `方法：${analysis.methodLabel}`,
    '',
    '指标                 原始方案      优化方案',
    `最高热点温度         ${analysis.baseline.maxTemperatureC.toFixed(1)}℃          ${candidate.maxTemperatureC.toFixed(1)}℃`,
    `达到 ${state.analysisInputs.thermalLimitC}℃ 时间        ${formatLimitTime(
      analysis.baseline.timeToLimitMinutes,
      durationMinutes,
    )}         ${formatLimitTime(candidate.timeToLimitMinutes, durationMinutes)}`,
    `单对象增重           0%           +${candidate.addedMassPercent.toFixed(1)}%`,
    `干涉风险             —            ${candidate.interferenceRisk}`,
    `推荐等级             —            ${candidate.grade}`,
    '',
    `结论：热点温度下降 ${candidate.hotspotReductionC.toFixed(1)}℃，综合评分 ${candidate.score.toFixed(1)}。`,
  ].join('\n')
}

export function buildManufacturingAdvice(
  state: ThermalProjectState,
): string {
  const { candidate } = requireAnalysis(state)
  const solution = SOLUTIONS.find(
    (item) => item.id === candidate.solutionId,
  )

  return [
    'ThermalForge Studio · 制造建议',
    `候选结构：${solution?.title ?? candidate.solutionId}`,
    `本次预测增重：${candidate.addedMassPercent.toFixed(1)}%`,
    `本次干涉风险：${candidate.interferenceRisk}`,
    '',
    '推荐材料：6061-T6 铝合金',
    '导热界面：1.0mm 可压缩柔性导热垫',
    '推荐工艺：主体 CNC，复杂叶脉结构可选金属 3D 打印',
    '表面处理：黑色阳极氧化，接触面保留精加工面',
    '装配方式：可逆抱箍 / 原孔位转接，不破坏原厂壳体',
    `质量评估：${
      candidate.addedMassPercent <= 8
        ? '预测增重满足 8% 上限'
        : '预测增重超过 8%，进入制造前需减重优化'
    }`,
  ].join('\n')
}

export function buildStructureFile(state: ThermalProjectState): string {
  const { analysis, candidate } = requireAnalysis(state)
  return JSON.stringify(
    {
      format: 'thermalforge-structure-v2',
      analysisId: analysis.id,
      analysisSource: analysis.source,
      solutionId: candidate.solutionId,
      jointId: state.jointId,
      heatSources: state.heatSources,
      constraints: state.constraints,
      calculatedOutput: {
        score: candidate.score,
        grade: candidate.grade,
        maxTemperatureC: candidate.maxTemperatureC,
        hotspotReductionC: candidate.hotspotReductionC,
        addedMassPercent: candidate.addedMassPercent,
        interferenceRisk: candidate.interferenceRisk,
      },
      note: 'Three.js/CAD 结构生成接口预留数据，不包含最终生产几何。',
    },
    null,
    2,
  )
}

export function createReportFilename(projectName: string): string {
  const printableName = Array.from(projectName, (character) =>
    character.charCodeAt(0) < 32 ? '-' : character,
  ).join('')
  const safeName = printableName
    .trim()
    .replace(/[<>:"/\\|?*]+/g, '-')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
  const date = new Date().toISOString().slice(0, 10)
  return `ThermalForge-${safeName || 'report'}-${date}.txt`
}

export function downloadText(
  filename: string,
  content: string,
  mimeType = 'text/plain;charset=utf-8',
): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

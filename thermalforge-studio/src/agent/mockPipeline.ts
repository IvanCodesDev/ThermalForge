import type { AgentStage, MockStage } from './agentTypes'

export const MOCK_STAGES: readonly MockStage[] = [
  {
    id: 'reading',
    label: '读取工程资料',
    message: '资料已接收，正在提取热源、尺寸与安装边界。',
    progress: 14,
    durationMs: 900,
  },
  {
    id: 'briefing',
    label: '建立工程约束',
    message: '约束摘要已建立：保留原厂关节，可拆卸，增重控制在 8% 内。',
    progress: 32,
    durationMs: 900,
  },
  {
    id: 'thermal',
    label: '优化热增强结构',
    message: '已选择可逆导热桥与叶脉扩散外壳，优先降低局部热点。',
    progress: 52,
    durationMs: 1000,
  },
  {
    id: 'multiview',
    label: '生成一致多视图',
    message: '母图、前/左/后/顶视图与肘关节剖面图正在生成并检查完整性。',
    progress: 72,
    durationMs: 1100,
  },
  {
    id: 'modeling',
    label: '构建三维模型',
    message: '多视图已通过检查，正在装配关节基座与热增强外壳。',
    progress: 88,
    durationMs: 1300,
  },
  {
    id: 'ready',
    label: '设计已就绪',
    message: '六视图和概念网格已就绪。可切换模型、爆炸分件并查看设计依据。',
    progress: 100,
    durationMs: 0,
  },
] as const

export function getMockStage(stage: AgentStage): MockStage | undefined {
  return MOCK_STAGES.find((candidate) => candidate.id === stage)
}

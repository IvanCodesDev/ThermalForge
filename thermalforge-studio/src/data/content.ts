export interface Scenario {
  id: string
  title: string
  description: string
  problems: string[]
  code: string
}

export interface OptionItem {
  id: string
  label: string
  description?: string
}

export interface HeatSource extends OptionItem {
  powers: [number, number, number]
  unit: 'W'
}

export interface Solution {
  id: string
  letter: string
  title: string
  tag: string
  features: string[]
  tone: 'baseline' | 'recommended' | 'airflow' | 'advanced'
}

export const SCENARIOS: Scenario[] = [
  {
    id: 'humanoid-rescue',
    code: 'RESCUE-01',
    title: '人形机器人救援任务',
    description:
      '负重、爬坡、长时间站立保持，膝关节和踝关节容易热降额。',
    problems: ['膝关节过热', '任务中断', '连续运行能力下降'],
  },
  {
    id: 'quadruped-patrol',
    code: 'PATROL-02',
    title: '四足机器人连续行走',
    description:
      '长时间巡检、爬坡和负载行走时，髋关节、膝关节温升明显。',
    problems: ['行走一段时间后限流', '姿态稳定性下降', '电机温度报警'],
  },
  {
    id: 'robotic-arm',
    code: 'PICK-03',
    title: '机械臂长时间抓取',
    description:
      '低速高扭矩任务下，肩关节、肘关节、末端执行器持续发热。',
    problems: ['长时间抓取后关节发烫', '精度下降', '控制器降额'],
  },
  {
    id: 'university-team',
    code: 'RACE-04',
    title: '高校机器人队比赛调试',
    description:
      '训练、比赛和演示过程中，电机、驱控板、计算模块容易过热。',
    problems: ['没有完整热模型', '只有热像仪和日志', '需要快速出报告'],
  },
]

export const HARDWARE_OPTIONS: OptionItem[] = [
  {
    id: 'robot-joint',
    label: '机器人关节',
    description: '关节模组与外壳完整热路径',
  },
  { id: 'motor', label: '电机', description: '绕组、定子与壳体散热' },
  {
    id: 'driver-board',
    label: '驱控板',
    description: 'MOSFET 与功率器件热点',
  },
  {
    id: 'compute-box',
    label: 'Jetson / 计算盒',
    description: 'SoC 与边缘计算模块',
  },
  {
    id: 'sensor',
    label: '传感器模块',
    description: '视觉与定位传感器',
  },
  {
    id: 'power',
    label: '电池 / 电源模块',
    description: '电芯、BMS 与连接器',
  },
]

export const JOINT_OPTIONS: OptionItem[] = [
  { id: 'knee', label: '膝关节' },
  { id: 'hip', label: '髋关节' },
  { id: 'ankle', label: '踝关节' },
  { id: 'shoulder', label: '肩关节' },
  { id: 'elbow', label: '肘关节' },
  { id: 'wrist', label: '腕关节' },
]

export const HEAT_SOURCES: HeatSource[] = [
  {
    id: 'motor-winding',
    label: '电机绕组',
    description: '主要连续发热源',
    powers: [30, 60, 100],
    unit: 'W',
  },
  {
    id: 'mosfet',
    label: 'MOSFET / 驱控板',
    description: '高热流密度局部热点',
    powers: [10, 20, 40],
    unit: 'W',
  },
  {
    id: 'gearbox',
    label: '减速器',
    description: '摩擦与传动损耗',
    powers: [5, 10, 20],
    unit: 'W',
  },
  {
    id: 'bearing',
    label: '轴承',
    description: '高速与偏载摩擦热',
    powers: [3, 6, 12],
    unit: 'W',
  },
  {
    id: 'connector',
    label: '电源连接器',
    description: '接触电阻热点',
    powers: [2, 5, 10],
    unit: 'W',
  },
  {
    id: 'harness',
    label: '线束接触点',
    description: '端子与线束连接热',
    powers: [2, 4, 8],
    unit: 'W',
  },
  {
    id: 'jetson',
    label: 'Jetson SoC',
    description: '边缘计算芯片负载',
    powers: [15, 30, 60],
    unit: 'W',
  },
]

export const CONSTRAINTS: OptionItem[] = [
  { id: 'sealed-case', label: '不开壳' },
  { id: 'warranty-seal', label: '不破坏封签' },
  { id: 'motor-untouched', label: '不改电机' },
  { id: 'reducer-untouched', label: '不改减速器' },
  { id: 'driver-untouched', label: '不改驱控参数' },
  { id: 'bearing-clearance', label: '避开轴承座' },
  { id: 'encoder-clearance', label: '避开编码器' },
  { id: 'cable-clearance', label: '避开线束' },
  { id: 'screw-clearance', label: '避开螺丝孔' },
  { id: 'motion-envelope', label: '不超出运动包络' },
  { id: 'removable', label: '可拆卸' },
  { id: 'repeatable', label: '可重复安装' },
  { id: 'weight-limit', label: '增重 ≤ 8%' },
]

export const OPTIMIZATION_GOALS: OptionItem[] = [
  { id: 'delay-limit', label: '延后热降额' },
  { id: 'lower-hotspot', label: '降低最高热点温度' },
  { id: 'weight-limit', label: '增重不超过 8%' },
  { id: 'original-structure', label: '不破坏原厂结构' },
  { id: 'task-duration', label: '提高连续任务时长' },
  { id: 'manufacturing-cost', label: '降低制造成本' },
  { id: 'maintainability', label: '保持可维护性' },
  { id: 'interference-risk', label: '降低干涉风险' },
]

export const SOLUTIONS: Solution[] = [
  {
    id: 'flat-baseline',
    letter: 'A',
    title: '平板基线',
    tag: '对照组',
    tone: 'baseline',
    features: ['成本低', '结构简单', '散热提升有限'],
  },
  {
    id: 'vein-bridge',
    letter: 'B',
    title: '可逆导热桥 + 叶脉热扩散结构',
    tag: '推荐方案',
    tone: 'recommended',
    features: [
      '适合局部热点扩散',
      '不破坏原厂关节',
      '视觉效果强',
      '黑客松主推',
    ],
  },
  {
    id: 'pin-fin',
    letter: 'C',
    title: '低矮 pin-fin 圆柱阵列',
    tag: '气流增强',
    tone: 'airflow',
    features: [
      '适合弱风或机器人运动气流',
      '空气侧换热更强',
      '需要注意灰尘和碰撞',
    ],
  },
  {
    id: 'gyroid',
    letter: 'D',
    title: 'TPMS / Gyroid 热点块',
    tag: '高性能样件',
    tone: 'advanced',
    features: [
      '适合明确风道或液冷',
      '金属 3D 打印展示效果好',
      '不作为默认主方案',
    ],
  },
]

export function findLabel(
  options: readonly OptionItem[],
  id: string,
  fallback = id,
): string {
  return options.find((option) => option.id === id)?.label ?? fallback
}

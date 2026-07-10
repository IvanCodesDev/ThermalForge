import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Clock3,
  FileClock,
  Flame,
  Plus,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { ModelViewport } from '../components/ModelViewport'
import { PageHeader } from '../components/PageHeader'
import { WorkflowFooter } from '../components/WorkflowFooter'
import {
  HARDWARE_OPTIONS,
  JOINT_OPTIONS,
  SCENARIOS,
  SOLUTIONS,
  findLabel,
} from '../data/content'
import type { ThermalCurvePoint } from '../analysis/types'
import type { WorkflowPageProps } from '../types'

function createMetricTrendPath(curve: ThermalCurvePoint[]): string {
  const minimumTime = curve[0]?.timeS ?? 0
  const maximumTime = curve.at(-1)?.timeS ?? minimumTime + 1
  const temperatures = curve.map((point) => point.temperatureC)
  const minimumTemperature = Math.min(...temperatures)
  const maximumTemperature = Math.max(...temperatures)
  const timeSpan = Math.max(maximumTime - minimumTime, 1)
  const temperatureSpan = Math.max(maximumTemperature - minimumTemperature, 1)

  return curve
    .map((point, index) => {
      const x = ((point.timeS - minimumTime) / timeSpan) * 240
      const y =
        49 - ((point.temperatureC - minimumTemperature) / temperatureSpan) * 42
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

export function DashboardPage({ state, onNavigate }: WorkflowPageProps) {
  const analysis = state.analysisResult
  const candidate =
    analysis?.candidates.find(
      (item) => item.solutionId === state.selectedSolutionId,
    ) ?? analysis?.candidates[0]
  const solution = candidate
    ? (SOLUTIONS.find((item) => item.id === candidate.solutionId)?.title ??
      candidate.solutionId)
    : '暂无推荐'
  const metrics = [
    {
      label: '最高热点温度',
      value: analysis
        ? `${analysis.baseline.maxTemperatureC.toFixed(1)}℃`
        : '待分析',
      meta: analysis
        ? `阈值 ${state.analysisInputs.thermalLimitC}℃ · ${analysis.methodLabel}`
        : '运行热分析后生成',
      tone: 'temperature',
      icon: Flame,
    },
    {
      label: '预计热保护时间',
      value: analysis
        ? analysis.baseline.timeToLimitMinutes === null
          ? '窗口内未触发'
          : `${analysis.baseline.timeToLimitMinutes.toFixed(1)}min`
        : '待计算',
      meta: analysis ? '由本次温升曲线读取' : '无固定示例数据',
      tone: 'countdown',
      icon: Clock3,
    },
    {
      label: '当前风险等级',
      value: analysis?.riskLevel ?? '未评估',
      meta: analysis ? '基于阈值与峰值判断' : '等待有效输出',
      tone: 'risk',
      icon: ShieldAlert,
    },
    {
      label: '当前结构方案',
      value: solution,
      meta: candidate
        ? `${candidate.score.toFixed(1)} 分 · Grade ${candidate.grade}`
        : '运行后按目标自动排序',
      tone: 'solution',
      icon: Sparkles,
    },
  ]
  const scenario =
    SCENARIOS.find((item) => item.id === state.scenarioId)?.title ??
    state.scenarioId
  const hardware = findLabel(HARDWARE_OPTIONS, state.hardwareId)
  const joint =
    state.hardwareId === 'robot-joint'
      ? findLabel(JOINT_OPTIONS, state.jointId)
      : ''

  return (
    <div className="page dashboard-page">
      <PageHeader
        eyebrow="Project overview · 01"
        title="机器人关节热诊断与热结构生成平台"
        description="快速识别机器人热点、评估热保护风险，并生成满足安装约束的可逆热增强结构。"
        aside={
          <div className="header-button-group">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => onNavigate('report')}
            >
              <FileClock aria-hidden="true" />
              历史诊断报告
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={() => onNavigate('scenario')}
            >
              <Plus aria-hidden="true" />
              新建热优化项目
            </button>
          </div>
        }
      />

      <section className="quick-status-card">
        <div className="glow-bg" aria-hidden="true" />
        <div className="status-title">
          <span className="icon-disc">
            <Activity aria-hidden="true" />
          </span>
          <div>
            <strong>系统状态</strong>
            <small>
              {analysis ? `TF-${analysis.id.slice(-12)}` : '尚未生成分析输出'}
            </small>
          </div>
        </div>
        <div className="status-values">
          <div>
            <span>诊断对象</span>
            <strong>{hardware}{joint ? ` · ${joint}` : ''}</strong>
          </div>
          <div>
            <span>任务工况</span>
            <strong>{scenario}</strong>
          </div>
          <div>
            <span>数据链路</span>
            <strong className={analysis ? 'status-online' : undefined}>
              {state.measurements.length > 0
                ? `${state.measurements.length} 点实测`
                : '参数输入'}
            </strong>
          </div>
        </div>
        <button
          className="pill-outline"
          type="button"
          onClick={() => onNavigate(analysis ? 'results' : 'hardware')}
        >
          {analysis ? '查看本次输出' : '完善输入'}
        </button>
      </section>

      <section className="metric-grid" aria-label="热诊断核心指标">
        {metrics.map((metric) => {
          const Icon = metric.icon
          const trendCurve =
            metric.tone === 'solution'
              ? candidate?.curve
              : analysis?.baseline.curve
          const trendPath = trendCurve
            ? createMetricTrendPath(trendCurve)
            : null
          return (
            <article
              key={metric.label}
              className={`metric-card metric-${metric.tone}`}
            >
              <div className="glow-bg" aria-hidden="true" />
              <div className="metric-card-head">
                <div>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.meta}</small>
                </div>
                <span className="metric-icon">
                  <Icon aria-hidden="true" />
                </span>
              </div>
              <div className="metric-trend" aria-hidden="true">
                {trendPath ? (
                  <svg viewBox="0 0 240 54" preserveAspectRatio="none">
                    <defs>
                      <linearGradient
                        id={`metric-fill-${metric.tone}`}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop offset="0%" stopColor="#ff5500" stopOpacity=".3" />
                        <stop offset="100%" stopColor="#ff5500" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <path
                      className="metric-trend-fill"
                      d={`${trendPath} L240,54 L0,54 Z`}
                      fill={`url(#metric-fill-${metric.tone})`}
                    />
                    <path className="metric-trend-line" d={trendPath} />
                  </svg>
                ) : (
                  <span className="metric-no-output">NO CALCULATED OUTPUT</span>
                )}
              </div>
            </article>
          )
        })}
      </section>

      <section className="dashboard-main-grid">
        <ModelViewport
          maxTemperatureC={analysis?.baseline.maxTemperatureC}
          ambientTemperatureC={state.analysisInputs.ambientTemperatureC}
        />

        <aside className="recommendation-card">
          <div className="recommendation-radial" aria-hidden="true" />
          <ArrowUpRight className="recommendation-arrow" aria-hidden="true" />
          <div className="recommendation-content">
            <span className="recommendation-label">
              <i aria-hidden="true" />
              AI Thermal Diagnosis
            </span>
            <h3>
              {analysis
                ? `${hardware}${joint ? ` ${joint}` : ''}热分析已完成`
                : '等待明确输入后生成热诊断'}
            </h3>
            <p>
              {analysis && candidate
                ? `本次${analysis.source === 'measured-calibrated' ? '实测校准' : '工程估算'}推荐“${solution}”，预测热点温降 ${candidate.hotspotReductionC.toFixed(1)}℃，综合评分 ${candidate.score.toFixed(1)}。`
                : '先填写环境温度、任务时长、热源功率等工况；也可上传实测 CSV。系统只在运行分析后展示动态输出。'}
            </p>
            <button
              type="button"
              onClick={() => onNavigate(analysis ? 'results' : 'hardware')}
              className="recommendation-action"
            >
              {analysis ? '查看分析输出' : '填写输入并开始'}
              <ArrowRight aria-hidden="true" />
            </button>
          </div>
        </aside>
      </section>

      <WorkflowFooter
        nextLabel={analysis ? '查看分析输出' : '填写分析输入'}
        onNext={() => onNavigate(analysis ? 'results' : 'hardware')}
      />
    </div>
  )
}

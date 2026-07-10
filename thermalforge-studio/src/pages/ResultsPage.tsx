import {
  ArrowDownRight,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  ShieldCheck,
  Thermometer,
  Weight,
} from 'lucide-react'
import { PageHeader } from '../components/PageHeader'
import {
  TemperatureCurve,
  ThermalMap,
} from '../components/ResultVisuals'
import { WorkflowFooter } from '../components/WorkflowFooter'
import { SOLUTIONS } from '../data/content'
import type { WorkflowPageProps } from '../types'

function formatLimitTime(
  minutes: number | null,
  durationMinutes: number,
): string {
  return minutes === null
    ? `未达到（>${durationMinutes.toFixed(1)}min）`
    : `${minutes.toFixed(1)}min`
}

export function ResultsPage({ state, onNavigate }: WorkflowPageProps) {
  const analysis = state.analysisResult

  if (!analysis) {
    return (
      <div className="page">
        <PageHeader
          eyebrow="A/B validation · 06"
          title="热性能对比结果"
          description="结果区只展示由当前输入真实计算得到的数据，不再使用固定示例占位。"
          aside={<span className="validation-badge is-pending">等待有效输出</span>}
        />
        <section className="analysis-empty-state">
          <span className="empty-state-icon">
            <BarChart3 aria-hidden="true" />
          </span>
          <span className="section-kicker">No calculated output</span>
          <h3>尚未运行热分析</h3>
          <p>
            请先确认工况参数或上传实测 CSV，再从结构生成页运行分析。输入发生变化后，旧结果会自动失效，避免展示过期结论。
          </p>
          <div>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => onNavigate('hardware')}
            >
              检查输入
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={() => onNavigate('structures')}
            >
              前往运行分析
              <ArrowRight aria-hidden="true" />
            </button>
          </div>
        </section>
        <WorkflowFooter
          previousLabel="返回结构方案"
          onPrevious={() => onNavigate('structures')}
        />
      </div>
    )
  }

  const candidate =
    analysis.candidates.find(
      (item) => item.solutionId === state.selectedSolutionId,
    ) ?? analysis.candidates[0]!
  const solution =
    SOLUTIONS.find((item) => item.id === candidate.solutionId)?.title ??
    candidate.solutionId
  const durationMinutes =
    Math.max(
      analysis.baseline.curve.at(-1)?.timeS ?? 0,
      candidate.curve.at(-1)?.timeS ?? 0,
    ) / 60
  const improvementLabel =
    candidate.timeToLimitImprovementPercent === null
      ? 'N/A'
      : `${candidate.timeToLimitMinutes === null ? '≥' : ''}+${candidate.timeToLimitImprovementPercent.toFixed(1)}%`
  const resultRows = [
    {
      label: '最高热点温度',
      original: `${analysis.baseline.maxTemperatureC.toFixed(1)}℃`,
      optimized: `${candidate.maxTemperatureC.toFixed(1)}℃`,
      highlight: true,
    },
    {
      label: '热点温降',
      original: '—',
      optimized: `-${candidate.hotspotReductionC.toFixed(1)}℃`,
      highlight: true,
    },
    {
      label: `达到 ${state.analysisInputs.thermalLimitC}℃ 时间`,
      original: formatLimitTime(
        analysis.baseline.timeToLimitMinutes,
        durationMinutes,
      ),
      optimized: formatLimitTime(candidate.timeToLimitMinutes, durationMinutes),
      highlight: false,
    },
    {
      label: 'Time-to-limit 提升',
      original: '—',
      optimized: improvementLabel,
      highlight: true,
    },
    {
      label: '单对象增重',
      original: '0%',
      optimized: `+${candidate.addedMassPercent.toFixed(1)}%`,
      highlight: false,
    },
    {
      label: '干涉风险',
      original: '—',
      optimized: candidate.interferenceRisk,
      highlight: false,
    },
    {
      label: '综合推荐等级',
      original: '—',
      optimized: candidate.grade,
      highlight: true,
    },
  ]
  const sourceLabel =
    analysis.source === 'measured-calibrated'
      ? '实测校准输出'
      : '工程估算输出'

  return (
    <div className="page">
      <PageHeader
        eyebrow="A/B validation · 06"
        title="热性能对比结果"
        description="将原始关节与推荐结构置于相同工况下，对比热点温度、热降额时间、增重与干涉风险。"
        aside={
          <span className="validation-badge">
            {analysis.source === 'measured-calibrated' ? (
              <Database aria-hidden="true" />
            ) : (
              <CheckCircle2 aria-hidden="true" />
            )}
            {sourceLabel}
          </span>
        }
      />

      <section className="result-highlight-grid" aria-label="关键优化结果">
        <article>
          <span className="result-highlight-icon">
            <Thermometer aria-hidden="true" />
          </span>
          <div>
            <small>热点温降</small>
            <strong>-{candidate.hotspotReductionC.toFixed(1)}℃</strong>
            <span>由同一输入工况计算</span>
          </div>
          <ArrowDownRight aria-hidden="true" />
        </article>
        <article>
          <span className="result-highlight-icon">
            <Clock3 aria-hidden="true" />
          </span>
          <div>
            <small>Time-to-limit</small>
            <strong>{improvementLabel}</strong>
            <span>
              {analysis.baseline.timeToLimitMinutes === null
                ? '基线未触发阈值'
                : `阈值 ${state.analysisInputs.thermalLimitC}℃`}
            </span>
          </div>
          <ArrowDownRight aria-hidden="true" />
        </article>
        <article>
          <span className="result-highlight-icon">
            <Weight aria-hidden="true" />
          </span>
          <div>
            <small>单关节增重</small>
            <strong>+{candidate.addedMassPercent.toFixed(1)}%</strong>
            <span>
              {state.constraints.includes('weight-limit')
                ? '约束 ≤ 8%'
                : '未启用增重约束'}
            </span>
          </div>
          <CheckCircle2 aria-hidden="true" />
        </article>
        <article>
          <span className="result-highlight-icon">
            <ShieldCheck aria-hidden="true" />
          </span>
          <div>
            <small>综合推荐等级</small>
            <strong>{candidate.grade}</strong>
            <span>{candidate.score.toFixed(1)} 分 · {candidate.interferenceRisk}干涉风险</span>
          </div>
          <CheckCircle2 aria-hidden="true" />
        </article>
      </section>

      <section className="thermal-comparison-section">
        <div className="section-heading">
          <div>
            <span className="section-kicker">Infrared comparison</span>
            <h3>优化前后热像对比</h3>
          </div>
          <span className="comparison-condition">
            环境温度 {state.analysisInputs.ambientTemperatureC}℃ ·{' '}
            {sourceLabel}
          </span>
        </div>
        <div className="thermal-map-grid">
          <ThermalMap
            variant="before"
            maxTemperatureC={analysis.baseline.maxTemperatureC}
            scaleMinimumC={state.analysisInputs.ambientTemperatureC}
            scaleMaximumC={Math.max(
              analysis.baseline.maxTemperatureC,
              state.analysisInputs.thermalLimitC,
            )}
          />
          <ThermalMap
            variant="after"
            maxTemperatureC={candidate.maxTemperatureC}
            scaleMinimumC={state.analysisInputs.ambientTemperatureC}
            scaleMaximumC={Math.max(
              analysis.baseline.maxTemperatureC,
              state.analysisInputs.thermalLimitC,
            )}
          />
        </div>
      </section>

      <div className="result-detail-grid">
        <TemperatureCurve
          baseline={analysis.baseline.curve}
          optimized={candidate.curve}
          thermalLimitC={state.analysisInputs.thermalLimitC}
        />

        <section className="result-table-card">
          <div className="card-heading">
            <div>
              <span className="section-kicker">Core metrics</span>
              <h3>核心指标</h3>
            </div>
            <span className="grade-pill">Grade {candidate.grade}</span>
          </div>

          <div className="result-table" role="table" aria-label="核心指标对比">
            <div className="result-table-head" role="row">
              <span role="columnheader">指标</span>
              <span role="columnheader">原始方案</span>
              <span role="columnheader">优化后</span>
            </div>
            {resultRows.map((row) => (
              <div className="result-table-row" role="row" key={row.label}>
                <span role="cell">{row.label}</span>
                <span role="cell">{row.original}</span>
                <strong
                  role="cell"
                  className={row.highlight ? 'is-highlighted' : ''}
                >
                  {row.optimized}
                </strong>
              </div>
            ))}
          </div>
        </section>
      </div>

      <aside className="result-conclusion">
        <div className="glow-bg" aria-hidden="true" />
        <span className="conclusion-icon">
          <CheckCircle2 aria-hidden="true" />
        </span>
        <div className="conclusion-copy">
          <span className="section-kicker">Engineering conclusion</span>
          <h3>当前选择：{solution}</h3>
          <p>
            基于本次{sourceLabel}，最高温度从{' '}
            {analysis.baseline.maxTemperatureC.toFixed(1)}℃ 降至{' '}
            {candidate.maxTemperatureC.toFixed(1)}℃，热点温降{' '}
            {candidate.hotspotReductionC.toFixed(1)}℃，预计增重{' '}
            {candidate.addedMassPercent.toFixed(1)}%，干涉风险为
            {candidate.interferenceRisk}。
          </p>
        </div>
        <button
          className="button button-primary"
          type="button"
          onClick={() => onNavigate('report')}
        >
          生成完整报告
        </button>
      </aside>

      <aside className="analysis-method-note">
        <strong>{analysis.methodLabel}</strong>
        <span>总热负载 {analysis.totalPowerW.toFixed(1)}W</span>
        <p>{analysis.warnings.join(' ')}</p>
      </aside>

      <WorkflowFooter
        previousLabel="返回结构方案"
        nextLabel="生成诊断报告"
        onPrevious={() => onNavigate('structures')}
        onNext={() => onNavigate('report')}
      />
    </div>
  )
}

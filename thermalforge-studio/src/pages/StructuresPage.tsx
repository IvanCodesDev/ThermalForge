import {
  ArrowRight,
  AlertCircle,
  Check,
  Cpu,
  Layers3,
  Play,
  Sparkles,
  Weight,
  Wind,
} from 'lucide-react'
import { useState } from 'react'
import {
  calculateThermalAnalysis,
  validateAnalysisRequest,
} from '../analysis/thermalEngine'
import { PageHeader } from '../components/PageHeader'
import { WorkflowFooter } from '../components/WorkflowFooter'
import {
  CONSTRAINTS,
  HARDWARE_OPTIONS,
  HEAT_SOURCES,
  JOINT_OPTIONS,
  SCENARIOS,
  SOLUTIONS,
  findLabel,
} from '../data/content'
import type { WorkflowPageProps } from '../types'

function SolutionVisual({ solutionId }: { solutionId: string }) {
  return (
    <div className={`solution-visual solution-visual-${solutionId}`}>
      <div className="visual-grid" aria-hidden="true" />
      {solutionId === 'flat-baseline' ? (
        <span className="flat-plate" aria-hidden="true" />
      ) : null}
      {solutionId === 'vein-bridge' ? (
        <div className="vein-structure" aria-hidden="true">
          <span className="vein-trunk" />
          <span className="vein-branch branch-1" />
          <span className="vein-branch branch-2" />
          <span className="vein-branch branch-3" />
          <span className="vein-branch branch-4" />
          <span className="vein-bridge" />
        </div>
      ) : null}
      {solutionId === 'pin-fin' ? (
        <div className="pin-fin-array" aria-hidden="true">
          {Array.from({ length: 20 }, (_, index) => (
            <i key={index} />
          ))}
        </div>
      ) : null}
      {solutionId === 'gyroid' ? (
        <div className="gyroid-block" aria-hidden="true">
          {Array.from({ length: 9 }, (_, index) => (
            <i key={index} />
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function StructuresPage({
  state,
  dispatch,
  onNavigate,
}: WorkflowPageProps) {
  const [previewGenerated, setPreviewGenerated] = useState(false)
  const [analysisErrors, setAnalysisErrors] = useState<string[]>([])
  const analysisRequest = {
    hardwareId: state.hardwareId,
    jointId: state.jointId,
    heatSources: state.heatSources,
    constraints: state.constraints,
    optimizationGoals: state.optimizationGoals,
    inputs: state.analysisInputs,
    measurements: state.measurements,
  }
  const analysis = state.analysisResult
  const selectedSolution =
    SOLUTIONS.find((item) => item.id === state.selectedSolutionId) ??
    SOLUTIONS[1]
  const selectedCandidate = analysis?.candidates.find(
    (candidate) => candidate.solutionId === state.selectedSolutionId,
  )

  const runAnalysis = (navigateAfterRun: boolean) => {
    const errors = validateAnalysisRequest(analysisRequest)
    if (errors.length > 0) {
      setAnalysisErrors(errors)
      return
    }

    const result = calculateThermalAnalysis(analysisRequest)
    dispatch({ type: 'completeAnalysis', result })
    setAnalysisErrors([])
    setPreviewGenerated(false)
    if (navigateAfterRun) {
      onNavigate('results')
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Generative structure · 05"
        title="生成候选热增强结构"
        description="基于热源、安装约束与目标优先级，比较不同结构路线，而不是默认宣称单一结构在所有工况下最优。"
        aside={
          <span
            className={
              analysis ? 'generation-status is-complete' : 'generation-status'
            }
          >
            <i aria-hidden="true" />
            {analysis ? '输出已生成' : '等待运行分析'}
          </span>
        }
      />

      <section className="input-summary-card">
        <div className="glow-bg" aria-hidden="true" />
        <div className="summary-title">
          <Layers3 aria-hidden="true" />
          <span>
            <strong>当前输入摘要</strong>
            <small>TF-GEN-001</small>
          </span>
        </div>
        <dl>
          <div>
            <dt>场景</dt>
            <dd>
              {SCENARIOS.find((item) => item.id === state.scenarioId)?.title ??
                state.scenarioId}
            </dd>
          </div>
          <div>
            <dt>对象</dt>
            <dd>
              {findLabel(HARDWARE_OPTIONS, state.hardwareId)}
              {state.hardwareId === 'robot-joint'
                ? ` · ${findLabel(JOINT_OPTIONS, state.jointId)}`
                : ''}
            </dd>
          </div>
          <div>
            <dt>热源</dt>
            <dd>
              {Object.entries(state.heatSources)
                .map(
                  ([id, power]) =>
                    `${findLabel(HEAT_SOURCES, id)} ${power}W`,
                )
                .join(' + ')}
            </dd>
          </div>
          <div>
            <dt>关键约束</dt>
            <dd>
              {state.constraints
                .slice(0, 4)
                .map((id) => findLabel(CONSTRAINTS, id))
                .join(' / ')}
            </dd>
          </div>
          <div>
            <dt>工况</dt>
            <dd>
              {state.analysisInputs.ambientTemperatureC}℃ ·{' '}
              {state.analysisInputs.durationMinutes}min ·{' '}
              {state.analysisInputs.dutyCyclePercent}% 占空比
            </dd>
          </div>
          <div>
            <dt>数据源</dt>
            <dd>
              {state.measurements.length > 0
                ? `${state.measurements.length} 点实测 CSV`
                : '参数工程估算'}
            </dd>
          </div>
        </dl>
      </section>

      <section className="analysis-run-strip" aria-label="热分析运行控制">
        <div>
          <span className="section-kicker">Input → Model → Output</span>
          <h3>{analysis ? '分析输出已就绪' : '输入确认后，运行一次热分析'}</h3>
          <p>
            {analysis
              ? `${analysis.methodLabel} · ${new Date(
                  analysis.generatedAt,
                ).toLocaleString('zh-CN')}`
              : '系统不会展示预设结果；只有点击运行后，才会按当前输入生成候选曲线、评分与推荐。'}
          </p>
        </div>
        <button
          className="button button-primary"
          type="button"
          onClick={() => runAnalysis(false)}
        >
          <Play aria-hidden="true" />
          {analysis ? '按当前输入重新分析' : '运行热分析并生成输出'}
        </button>
      </section>

      {analysisErrors.length > 0 ? (
        <div className="analysis-error-list" role="alert">
          <AlertCircle aria-hidden="true" />
          <div>
            <strong>输入尚不能运行</strong>
            {analysisErrors.map((error) => (
              <span key={error}>{error}</span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="structure-layout">
        <section className="solution-grid" aria-label="候选热增强结构">
          {SOLUTIONS.map((solution) => {
            const selected = state.selectedSolutionId === solution.id
            const candidate = analysis?.candidates.find(
              (item) => item.solutionId === solution.id,
            )
            return (
              <button
                key={solution.id}
                type="button"
                className={[
                  'solution-card',
                  `solution-${solution.tone}`,
                  selected ? 'is-selected' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                aria-pressed={selected}
                onClick={() => {
                  setPreviewGenerated(false)
                  dispatch({
                    type: 'selectSolution',
                    solutionId: solution.id,
                  })
                }}
              >
                <div className="solution-card-head">
                  <span className="solution-letter">{solution.letter}</span>
                  <span className="solution-tag">
                    {candidate
                      ? `${candidate.score.toFixed(0)} 分 · Grade ${candidate.grade}`
                      : solution.tag}
                  </span>
                  <span className="solution-check">
                    <Check aria-hidden="true" />
                  </span>
                </div>
                <SolutionVisual solutionId={solution.id} />
                <div className="solution-copy">
                  <h3>{solution.title}</h3>
                  {candidate ? (
                    <dl className="candidate-output-preview">
                      <div>
                        <dt>最高温度</dt>
                        <dd>{candidate.maxTemperatureC.toFixed(1)}℃</dd>
                      </div>
                      <div>
                        <dt>热点温降</dt>
                        <dd>-{candidate.hotspotReductionC.toFixed(1)}℃</dd>
                      </div>
                    </dl>
                  ) : null}
                  <ul>
                    {solution.features.map((feature) => (
                      <li key={feature}>
                        <i aria-hidden="true" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
              </button>
            )
          })}
        </section>

        <aside className="solution-reason-card">
          <div className="reason-card-glow" aria-hidden="true" />
          <div className="reason-card-heading">
            <span className="icon-disc">
              <Sparkles aria-hidden="true" />
            </span>
            <div>
              <span className="section-kicker">
                {analysis ? 'Calculated output' : 'Candidate preview'}
              </span>
              <h3>
                {analysis
                  ? `方案 ${selectedSolution.letter} · ${selectedCandidate?.score.toFixed(0) ?? '—'} 分`
                  : `先运行分析，再生成推荐`}
              </h3>
            </div>
          </div>

          <p className="reason-copy">
            {analysis ? (
              <>
                当前选中 <strong>{selectedSolution.title}</strong>，模型预测最高温度
                <strong>
                  {' '}
                  {selectedCandidate?.maxTemperatureC.toFixed(1) ?? '—'}℃
                </strong>
                ，相较原始结构降低
                <strong>
                  {' '}
                  {selectedCandidate?.hotspotReductionC.toFixed(1) ?? '—'}℃
                </strong>
                。候选评分同时纳入热性能、增重、干涉风险与目标优先级。
              </>
            ) : (
              <>
                这里不会预先宣称某个方案最优。系统会读取你填写的环境温度、热源功率、任务时长、约束条件与可选实测
                CSV，再计算四个候选结构的温升曲线和综合评分。
              </>
            )}
          </p>

          <div className="reason-metrics">
            <div>
              <Cpu aria-hidden="true" />
              <span>
                推荐等级<strong>{selectedCandidate?.grade ?? '待计算'}</strong>
              </span>
            </div>
            <div>
              <Weight aria-hidden="true" />
              <span>
                预计增重
                <strong>
                  {selectedCandidate
                    ? `+${selectedCandidate.addedMassPercent.toFixed(1)}%`
                    : '待计算'}
                </strong>
              </span>
            </div>
            <div>
              <Wind aria-hidden="true" />
              <span>
                干涉风险
                <strong>{selectedCandidate?.interferenceRisk ?? '待计算'}</strong>
              </span>
            </div>
          </div>

          <div className="tpms-note">
            <strong>关于 TPMS / Gyroid</strong>
            <p>
              更适合具有明确风道或液冷流道的场景；在自然对流或弱气流下，不一定优于低矮
              pin-fin。
            </p>
          </div>

          <div className="reason-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setPreviewGenerated(true)}
            >
              <Play aria-hidden="true" />
              {previewGenerated ? '预览已生成' : '生成结构预览'}
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={() =>
                analysis ? onNavigate('results') : runAnalysis(true)
              }
            >
              {analysis ? '查看本次分析输出' : '运行分析并查看输出'}
              <ArrowRight aria-hidden="true" />
            </button>
          </div>

          {previewGenerated ? (
            <div className="preview-complete" role="status">
              <Check aria-hidden="true" />
              {selectedSolution.title}预览已写入项目草稿
            </div>
          ) : null}
        </aside>
      </div>

      <WorkflowFooter
        previousLabel="返回安装约束"
        nextLabel={analysis ? '查看热性能结果' : '运行分析并查看结果'}
        onPrevious={() => onNavigate('constraints')}
        onNext={() => (analysis ? onNavigate('results') : runAnalysis(true))}
      />
    </div>
  )
}

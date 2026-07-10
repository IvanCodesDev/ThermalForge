import {
  AlertTriangle,
  Box,
  CheckCircle2,
  Download,
  Factory,
  FileText,
  MapPin,
  ShieldCheck,
  TestTube2,
  Thermometer,
  Timer,
  Wrench,
} from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { WorkflowFooter } from '../components/WorkflowFooter'
import {
  HARDWARE_OPTIONS,
  HEAT_SOURCES,
  JOINT_OPTIONS,
  SCENARIOS,
  SOLUTIONS,
  findLabel,
} from '../data/content'
import type { WorkflowPageProps } from '../types'
import {
  buildAbReportText,
  buildManufacturingAdvice,
  buildReportText,
  buildStructureFile,
  createReportFilename,
  downloadText,
} from '../utils/report'

const REPORT_SECTIONS = [
  { id: 'basic', label: '项目基本信息', icon: FileText },
  { id: 'diagnosis', label: '热诊断结果', icon: Thermometer },
  { id: 'solution', label: '推荐结构方案', icon: Box },
  { id: 'comparison', label: 'A/B 测试结果', icon: TestTube2 },
  { id: 'risk', label: '安装与风险提示', icon: ShieldCheck },
]

export function ReportPage({
  state,
  onNavigate,
}: WorkflowPageProps) {
  const [activeSection, setActiveSection] = useState('basic')
  const [downloadStatus, setDownloadStatus] = useState('')
  const analysis = state.analysisResult
  const scenario =
    SCENARIOS.find((item) => item.id === state.scenarioId)?.title ??
    state.scenarioId
  const candidate =
    analysis?.candidates.find(
      (item) => item.solutionId === state.selectedSolutionId,
    ) ?? analysis?.candidates[0]
  const solution =
    SOLUTIONS.find((item) => item.id === candidate?.solutionId)?.title ??
    candidate?.solutionId ??
    '尚未生成'
  const durationMinutes = analysis
    ? (analysis.baseline.curve.at(-1)?.timeS ?? 0) / 60
    : state.analysisInputs.durationMinutes
  const formatLimitTime = (minutes: number | null) =>
    minutes === null
      ? `未达到（>${durationMinutes.toFixed(1)}min）`
      : `${minutes.toFixed(1)}min`

  const triggerDownload = (
    label: string,
    filename: string,
    content: string,
    mimeType?: string,
  ) => {
    downloadText(filename, content, mimeType)
    setDownloadStatus(`${label}已开始下载`)
    window.setTimeout(() => setDownloadStatus(''), 3500)
  }

  if (!analysis || !candidate) {
    return (
      <div className="page">
        <PageHeader
          eyebrow="Delivery package · 07"
          title="生成热诊断与结构优化报告"
          description="报告只汇总已运行分析的真实输入与计算输出，不提供固定示例报告。"
          aside={
            <span className="report-ready-badge is-pending">
              <AlertTriangle aria-hidden="true" />
              等待分析输出
            </span>
          }
        />
        <section className="analysis-empty-state">
          <span className="empty-state-icon">
            <FileText aria-hidden="true" />
          </span>
          <span className="section-kicker">No reportable output</span>
          <h3>当前没有可导出的报告数据</h3>
          <p>
            请先运行热分析。报告中的峰值温度、阈值时间、候选评分和推荐结论都会从该次输出生成。
          </p>
          <button
            className="button button-primary"
            type="button"
            onClick={() => onNavigate('structures')}
          >
            前往运行热分析
          </button>
        </section>
        <WorkflowFooter
          previousLabel="返回结构方案"
          onPrevious={() => onNavigate('structures')}
        />
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Delivery package · 07"
        title="生成热诊断与结构优化报告"
        description="汇总项目输入、诊断结果、候选结构、A/B 测试与制造建议，形成可追溯的完整交付闭环。"
        aside={
          <span className="report-ready-badge">
            <CheckCircle2 aria-hidden="true" />
            {analysis.source === 'measured-calibrated'
              ? '实测校准报告可导出'
              : '工程估算报告可导出'}
          </span>
        }
      />

      <div className="report-layout">
        <aside className="report-outline">
          <div className="outline-heading">
            <span>报告目录</span>
            <small>5 个模块</small>
          </div>
          <nav aria-label="报告预览目录">
            {REPORT_SECTIONS.map((section, index) => {
              const Icon = section.icon
              return (
                <button
                  key={section.id}
                  type="button"
                  className={
                    activeSection === section.id ? 'is-active' : undefined
                  }
                  onClick={() => setActiveSection(section.id)}
                >
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <Icon aria-hidden="true" />
                  {section.label}
                </button>
              )
            })}
          </nav>
          <div className="report-progress">
            <span>
              <strong>100%</strong>
              内容完整度
            </span>
            <i>
              <b />
            </i>
          </div>
        </aside>

        <section className="report-preview">
          <div className="report-document-header">
            <div className="report-brand-mark">
              <span>TF</span>
            </div>
            <div>
              <span>ThermalForge Studio</span>
              <h3>机器人关节热诊断与结构优化报告</h3>
              <p>
                报告编号 {analysis.id.replace('analysis-', 'TF-')} · Version 2.0
              </p>
            </div>
            <span className="report-grade">
              <small>推荐等级</small>
              {candidate.grade}
            </span>
          </div>

          {activeSection === 'basic' ? (
            <div className="report-section">
              <h4>01 / 项目基本信息</h4>
              <div className="report-info-grid">
                <div>
                  <small>项目名称</small>
                  <strong>{state.projectName}</strong>
                </div>
                <div>
                  <small>任务场景</small>
                  <strong>{scenario}</strong>
                </div>
                <div>
                  <small>目标硬件</small>
                  <strong>
                    {findLabel(HARDWARE_OPTIONS, state.hardwareId)}
                    {state.hardwareId === 'robot-joint'
                      ? ` · ${findLabel(JOINT_OPTIONS, state.jointId)}`
                      : ''}
                  </strong>
                </div>
                <div>
                  <small>环境 / 工况</small>
                  <strong>
                    {state.analysisInputs.ambientTemperatureC}℃ ·{' '}
                    {durationMinutes.toFixed(1)}min ·{' '}
                    {state.analysisInputs.dutyCyclePercent}% 占空比
                  </strong>
                </div>
                <div>
                  <small>数据与方法</small>
                  <strong>
                    {analysis.source === 'measured-calibrated'
                      ? `${state.measurements.length} 点实测 CSV`
                      : '参数工程估算'}{' '}
                    · {analysis.methodLabel}
                  </strong>
                </div>
              </div>
              <div className="report-source-list">
                <h5>热源设置</h5>
                {Object.entries(state.heatSources).map(([id, power]) => (
                  <span key={id}>
                    <i aria-hidden="true" />
                    {findLabel(HEAT_SOURCES, id)}
                    <strong>{power}W</strong>
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          {activeSection === 'diagnosis' ? (
            <div className="report-section">
              <h4>02 / 热诊断结果</h4>
              <div className="report-diagnosis-hero">
                <span className="diagnosis-heat-orb" aria-hidden="true" />
                <div>
                  <small>最高热点温度</small>
                  <strong>{analysis.baseline.maxTemperatureC.toFixed(1)}℃</strong>
                  <p>
                    由当前热源、工况和
                    {analysis.source === 'measured-calibrated'
                      ? '实测温升曲线'
                      : 'RC 热模型'}
                    计算。
                  </p>
                </div>
              </div>
              <div className="report-metric-row">
                <div>
                  <MapPin aria-hidden="true" />
                  <span>
                    总热负载<strong>{analysis.totalPowerW.toFixed(1)}W</strong>
                  </span>
                </div>
                <div>
                  <Timer aria-hidden="true" />
                  <span>
                    达到 {state.analysisInputs.thermalLimitC}℃
                    <strong>
                      {formatLimitTime(
                        analysis.baseline.timeToLimitMinutes,
                      )}
                    </strong>
                  </span>
                </div>
                <div>
                  <AlertTriangle aria-hidden="true" />
                  <span>热保护风险<strong>{analysis.riskLevel}</strong></span>
                </div>
              </div>
            </div>
          ) : null}

          {activeSection === 'solution' ? (
            <div className="report-section">
              <h4>03 / 推荐结构方案</h4>
              <div className="report-solution-card">
                <div className="mini-vein-visual" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </div>
                <div>
                  <span className="recommended-chip">当前方案</span>
                  <h5>{solution}</h5>
                  <p>
                    综合评分 {candidate.score.toFixed(1)} / 100；预测热点温降{' '}
                    {candidate.hotspotReductionC.toFixed(1)}℃，增重{' '}
                    {candidate.addedMassPercent.toFixed(1)}%，干涉风险
                    {candidate.interferenceRisk}。
                  </p>
                </div>
              </div>
              <dl className="manufacturing-grid">
                <div><dt>材料建议</dt><dd>6061-T6 铝合金</dd></div>
                <div><dt>导热界面</dt><dd>柔性导热垫</dd></div>
                <div><dt>制造方式</dt><dd>CNC / 金属 3D 打印</dd></div>
                <div><dt>装配方式</dt><dd>可逆抱箍 / 转接件</dd></div>
              </dl>
            </div>
          ) : null}

          {activeSection === 'comparison' ? (
            <div className="report-section">
              <h4>04 / A/B 测试结果</h4>
              <div className="report-ab-grid">
                <div>
                  <small>优化前</small>
                  <strong>{analysis.baseline.maxTemperatureC.toFixed(1)}℃</strong>
                  <span>
                    {formatLimitTime(analysis.baseline.timeToLimitMinutes)}
                  </span>
                </div>
                <span className="ab-arrow">→</span>
                <div className="is-optimized">
                  <small>优化后</small>
                  <strong>{candidate.maxTemperatureC.toFixed(1)}℃</strong>
                  <span>{formatLimitTime(candidate.timeToLimitMinutes)}</span>
                </div>
              </div>
              <div className="report-result-list">
                <span>
                  热点温降
                  <strong>-{candidate.hotspotReductionC.toFixed(1)}℃</strong>
                </span>
                <span>
                  Time-to-limit
                  <strong>
                    {candidate.timeToLimitImprovementPercent === null
                      ? 'N/A'
                      : `${candidate.timeToLimitMinutes === null ? '≥' : ''}+${candidate.timeToLimitImprovementPercent.toFixed(1)}%`}
                  </strong>
                </span>
                <span>
                  增重比例
                  <strong>+{candidate.addedMassPercent.toFixed(1)}%</strong>
                </span>
                <span>干涉风险<strong>{candidate.interferenceRisk}</strong></span>
              </div>
            </div>
          ) : null}

          {activeSection === 'risk' ? (
            <div className="report-section">
              <h4>05 / 安装与风险提示</h4>
              <div className="risk-note-list">
                {[
                  '避开线束、轴承座与编码器',
                  '不改变原厂安全保护阈值',
                  '注意可触摸表面温度',
                  '定期检查灰尘积聚与碰撞痕迹',
                ].map((note) => (
                  <div key={note}>
                    <CheckCircle2 aria-hidden="true" />
                    <span>{note}</span>
                  </div>
                ))}
              </div>
              <div className="report-warning">
                <AlertTriangle aria-hidden="true" />
                <p>
                  {analysis.warnings.join(' ')}
                  最终生产结构仍应结合真实材料参数、装配公差及机器人整机安全测试确认。
                </p>
              </div>
            </div>
          ) : null}

          <footer className="report-document-footer">
            <span>ThermalForge Studio · Generated report</span>
            <span>07 / 07</span>
          </footer>
        </section>

        <aside className="export-panel">
          <div className="glow-bg" aria-hidden="true" />
          <div className="panel-heading">
            <span className="panel-step">EX</span>
            <div>
              <h3>导出交付物</h3>
              <p>选择需要下载的文件</p>
            </div>
          </div>

          <div className="export-list">
            <button
              type="button"
              onClick={() =>
                triggerDownload(
                  '热诊断报告',
                  createReportFilename(state.projectName),
                  buildReportText(state),
                )
              }
            >
              <span className="export-icon"><FileText aria-hidden="true" /></span>
              <span><strong>导出热诊断报告</strong><small>完整项目诊断内容 · TXT</small></span>
              <Download aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() =>
                triggerDownload(
                  'A/B 测试报告',
                  'ThermalForge-AB-test-report.txt',
                  buildAbReportText(state),
                )
              }
            >
              <span className="export-icon"><TestTube2 aria-hidden="true" /></span>
              <span><strong>导出 A/B 测试报告</strong><small>热性能对比数据 · TXT</small></span>
              <Download aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() =>
                triggerDownload(
                  '制造建议',
                  'ThermalForge-manufacturing-advice.txt',
                  buildManufacturingAdvice(state),
                )
              }
            >
              <span className="export-icon"><Factory aria-hidden="true" /></span>
              <span><strong>导出制造建议</strong><small>材料与工艺建议 · TXT</small></span>
              <Download aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() =>
                triggerDownload(
                  '结构接口文件',
                  'ThermalForge-structure.json',
                  buildStructureFile(state),
                  'application/json;charset=utf-8',
                )
              }
            >
              <span className="export-icon"><Box aria-hidden="true" /></span>
              <span><strong>下载结构文件</strong><small>Three.js / CAD 接口数据 · JSON</small></span>
              <Download aria-hidden="true" />
            </button>
          </div>

          <div className="export-note">
            <Wrench aria-hidden="true" />
            <p>
              当前结构文件为后续 Three.js 与 CAD 生成模块预留的标准化接口数据。
            </p>
          </div>
        </aside>
      </div>

      {downloadStatus ? (
        <div className="toast" role="status" aria-live="polite">
          <CheckCircle2 aria-hidden="true" />
          {downloadStatus}
        </div>
      ) : null}

      <WorkflowFooter
        previousLabel="返回性能对比"
        nextLabel="返回项目总览"
        onPrevious={() => onNavigate('results')}
        onNext={() => onNavigate('dashboard')}
      />
    </div>
  )
}

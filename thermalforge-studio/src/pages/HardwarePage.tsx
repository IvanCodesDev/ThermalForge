import {
  BatteryCharging,
  Box,
  Check,
  CircuitBoard,
  Cog,
  Cpu,
  Database,
  Download,
  Flame,
  Gauge,
  ScanEye,
  SlidersHorizontal,
  Upload,
  X,
  Zap,
} from 'lucide-react'
import { useState } from 'react'
import {
  createMeasurementCsvTemplate,
  parseMeasurementCsv,
} from '../analysis/csvParser'
import type { AnalysisInputs } from '../analysis/types'
import { PageHeader } from '../components/PageHeader'
import { WorkflowFooter } from '../components/WorkflowFooter'
import {
  HARDWARE_OPTIONS,
  HEAT_SOURCES,
  JOINT_OPTIONS,
} from '../data/content'
import type { WorkflowPageProps } from '../types'
import { downloadText } from '../utils/report'

const HARDWARE_ICONS = {
  'robot-joint': Cog,
  motor: Gauge,
  'driver-board': CircuitBoard,
  'compute-box': Cpu,
  sensor: ScanEye,
  power: BatteryCharging,
} as const

interface OperatingInputDefinition {
  field: keyof AnalysisInputs
  label: string
  unit: string
  min: number
  max: number
  step: number
  hint: string
  replacedByCsv?: boolean
}

const OPERATING_INPUTS: OperatingInputDefinition[] = [
  {
    field: 'ambientTemperatureC',
    label: '环境温度',
    unit: '℃',
    min: -40,
    max: 100,
    step: 1,
    hint: '模型散热边界条件',
  },
  {
    field: 'initialTemperatureC',
    label: '初始温度',
    unit: '℃',
    min: -40,
    max: 200,
    step: 1,
    hint: '任务开始时对象温度',
    replacedByCsv: true,
  },
  {
    field: 'thermalLimitC',
    label: '热保护阈值',
    unit: '℃',
    min: -20,
    max: 250,
    step: 1,
    hint: '计算 Time-to-limit',
  },
  {
    field: 'durationMinutes',
    label: '任务时长',
    unit: 'min',
    min: 0.5,
    max: 120,
    step: 0.5,
    hint: '工程估算时间窗口',
    replacedByCsv: true,
  },
  {
    field: 'dutyCyclePercent',
    label: '负载占空比',
    unit: '%',
    min: 1,
    max: 100,
    step: 1,
    hint: '平均功率折算比例',
    replacedByCsv: true,
  },
  {
    field: 'airflowMps',
    label: '环境风速',
    unit: 'm/s',
    min: 0,
    max: 20,
    step: 0.1,
    hint: '影响对流热阻',
  },
  {
    field: 'componentMassKg',
    label: '对象质量',
    unit: 'kg',
    min: 0.01,
    max: 100,
    step: 0.1,
    hint: '用于估算等效热容',
  },
]

export function HardwarePage({
  state,
  dispatch,
  onNavigate,
}: WorkflowPageProps) {
  const [csvStatus, setCsvStatus] = useState<{
    tone: 'success' | 'error'
    message: string
  } | null>(null)
  const totalPower = Object.values(state.heatSources).reduce(
    (sum, power) => sum + power,
    0,
  )
  const isJoint = state.hardwareId === 'robot-joint'
  const hasMeasurements = state.measurements.length > 0
  const measurementDurationMinutes = hasMeasurements
    ? (state.measurements.at(-1)!.timeS / 60).toFixed(1)
    : '0'
  const measurementTemperatures = state.measurements.map(
    (point) => point.temperatureC,
  )
  const measurementAveragePower = hasMeasurements
    ? (
        state.measurements.reduce((sum, point) => sum + point.powerW, 0) /
        state.measurements.length
      ).toFixed(1)
    : '0'

  const handleCsvFile = async (file: File | undefined) => {
    if (!file) return

    try {
      if (file.size > 2 * 1024 * 1024) {
        throw new Error('CSV 文件不能超过 2MB')
      }
      const measurements = parseMeasurementCsv(await file.text())
      dispatch({ type: 'setMeasurements', measurements })
      dispatch({
        type: 'setAnalysisInput',
        field: 'initialTemperatureC',
        value: measurements[0]!.temperatureC,
      })
      dispatch({
        type: 'setAnalysisInput',
        field: 'durationMinutes',
        value: measurements.at(-1)!.timeS / 60,
      })
      setCsvStatus({
        tone: 'success',
        message: `已导入 ${measurements.length} 个实测点，后续结果将使用实测曲线校准。`,
      })
    } catch (error) {
      setCsvStatus({
        tone: 'error',
        message:
          error instanceof Error ? error.message : 'CSV 读取失败，请检查文件。',
      })
    }
  }

  const downloadCsvTemplate = () => {
    downloadText(
      'ThermalForge-measurement-template.csv',
      createMeasurementCsvTemplate(),
      'text/csv;charset=utf-8',
    )
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Thermal path · 03"
        title="选择诊断硬件与主要热源"
        description="完整热路径从内部热源开始，经壳体扩散后传递到环境；请选择对象、部位与当前工况功率。"
        aside={
          <div className="power-summary">
            <Zap aria-hidden="true" />
            <span>
              当前总热负载
              <strong>{totalPower}W</strong>
            </span>
          </div>
        }
      />

      <div className="hardware-layout">
        <section className="form-panel hardware-panel">
          <div className="glow-bg" aria-hidden="true" />
          <div className="panel-heading">
            <span className="panel-step">01</span>
            <div>
              <h3>硬件对象预选</h3>
              <p>定义需要建立热路径的主体</p>
            </div>
          </div>
          <div className="hardware-option-list">
            {HARDWARE_OPTIONS.map((hardware) => {
              const Icon =
                HARDWARE_ICONS[
                  hardware.id as keyof typeof HARDWARE_ICONS
                ] ?? Box
              const selected = state.hardwareId === hardware.id

              return (
                <button
                  key={hardware.id}
                  type="button"
                  className={
                    selected ? 'hardware-option is-selected' : 'hardware-option'
                  }
                  aria-pressed={selected}
                  onClick={() =>
                    dispatch({
                      type: 'selectHardware',
                      hardwareId: hardware.id,
                    })
                  }
                >
                  <span className="option-icon">
                    <Icon aria-hidden="true" />
                  </span>
                  <span>
                    <strong>{hardware.label}</strong>
                    <small>{hardware.description}</small>
                  </span>
                  <Check className="option-check" aria-hidden="true" />
                </button>
              )
            })}
          </div>
        </section>

        <section className="form-panel joint-panel">
          <div className="glow-bg" aria-hidden="true" />
          <div className="panel-heading">
            <span className="panel-step">02</span>
            <div>
              <h3>关节类型</h3>
              <p>{isJoint ? '选择主要诊断部位' : '仅机器人关节对象需要选择'}</p>
            </div>
          </div>

          {isJoint ? (
            <div className="joint-grid">
              {JOINT_OPTIONS.map((joint, index) => {
                const selected = state.jointId === joint.id
                return (
                  <button
                    key={joint.id}
                    type="button"
                    className={
                      selected ? 'joint-option is-selected' : 'joint-option'
                    }
                    aria-pressed={selected}
                    onClick={() =>
                      dispatch({
                        type: 'selectJoint',
                        jointId: joint.id,
                      })
                    }
                  >
                    <span className="joint-visual">
                      <i />
                      <b>{String(index + 1).padStart(2, '0')}</b>
                    </span>
                    <strong>{joint.label}</strong>
                    <small>{selected ? '当前诊断对象' : '点击选择'}</small>
                  </button>
                )
              })}
            </div>
          ) : (
            <div className="empty-selection">
              <Box aria-hidden="true" />
              <strong>已选择独立硬件对象</strong>
              <p>系统将直接分析所选硬件，不再要求指定关节类型。</p>
            </div>
          )}
        </section>

        <section className="form-panel heat-source-panel">
          <div className="glow-bg" aria-hidden="true" />
          <div className="panel-heading">
            <span className="panel-step">03</span>
            <div>
              <h3>主要热源</h3>
              <p>支持多选并设置负载功率</p>
            </div>
          </div>

          <div className="heat-source-list">
            {HEAT_SOURCES.map((source) => {
              const selected = source.id in state.heatSources
              const currentPower = state.heatSources[source.id]

              return (
                <article
                  key={source.id}
                  className={
                    selected ? 'heat-source-row is-selected' : 'heat-source-row'
                  }
                >
                  <button
                    className="heat-source-toggle"
                    type="button"
                    aria-pressed={selected}
                    onClick={() =>
                      dispatch({
                        type: 'toggleHeatSource',
                        sourceId: source.id,
                        defaultPower: source.powers[1],
                      })
                    }
                  >
                    <span className="source-checkbox">
                      <Check aria-hidden="true" />
                    </span>
                    <span>
                      <strong>{source.label}</strong>
                      <small>{source.description}</small>
                    </span>
                  </button>

                  <div className="power-presets" aria-label={`${source.label}功率`}>
                    {source.powers.map((power, index) => (
                      <button
                        key={power}
                        type="button"
                        disabled={!selected}
                        className={
                          selected && currentPower === power ? 'is-active' : ''
                        }
                        onClick={() =>
                          dispatch({
                            type: 'setHeatPower',
                            sourceId: source.id,
                            power,
                          })
                        }
                        aria-label={`${source.label}${['低', '中', '高'][index]}负载 ${power}瓦`}
                      >
                        <small>{['低', '中', '高'][index]}</small>
                        {power}W
                      </button>
                    ))}
                  </div>
                </article>
              )
            })}
          </div>
        </section>
      </div>

      <section className="operating-input-card" aria-labelledby="operating-input-title">
        <div className="glow-bg" aria-hidden="true" />
        <div className="operating-input-heading">
          <div className="panel-heading">
            <span className="panel-step">04</span>
            <div>
              <h3 id="operating-input-title">明确工况输入</h3>
              <p>填写工程参数，或导入同一工况下的温度 / 功率时间序列</p>
            </div>
          </div>
          <span
            className={
              hasMeasurements
                ? 'input-source-badge is-measured'
                : 'input-source-badge'
            }
          >
            {hasMeasurements ? (
              <Database aria-hidden="true" />
            ) : (
              <SlidersHorizontal aria-hidden="true" />
            )}
            {hasMeasurements ? '实测 CSV 校准' : '参数工程估算'}
          </span>
        </div>

        <div className="operating-input-layout">
          <div className="parameter-input-panel">
            <div className="input-subheading">
              <div>
                <strong>工况参数</strong>
                <small>所有参数都会直接进入热模型</small>
              </div>
              <span>INPUT A</span>
            </div>
            <div className="operating-field-grid">
              {OPERATING_INPUTS.map((input) => {
                const csvOverridesField =
                  hasMeasurements && input.replacedByCsv
                return (
                  <label
                    className={
                      csvOverridesField
                        ? 'operating-field is-overridden'
                        : 'operating-field'
                    }
                    key={input.field}
                  >
                    <span>
                      <strong>{input.label}</strong>
                      <small>
                        {csvOverridesField ? '由 CSV 实测数据覆盖' : input.hint}
                      </small>
                    </span>
                    <span className="number-input-shell">
                      <input
                        type="number"
                        min={input.min}
                        max={input.max}
                        step={input.step}
                        value={state.analysisInputs[input.field]}
                        disabled={csvOverridesField}
                        onChange={(event) =>
                          dispatch({
                            type: 'setAnalysisInput',
                            field: input.field,
                            value: Number(event.target.value),
                          })
                        }
                      />
                      <b>{input.unit}</b>
                    </span>
                  </label>
                )
              })}
            </div>
          </div>

          <div className="measurement-input-panel">
            <div className="input-subheading">
              <div>
                <strong>实测数据（可选）</strong>
                <small>列名固定，时间必须严格递增</small>
              </div>
              <span>INPUT B</span>
            </div>

            {hasMeasurements ? (
              <div className="measurement-summary">
                <div className="measurement-summary-head">
                  <span className="measurement-file-icon">
                    <Database aria-hidden="true" />
                  </span>
                  <span>
                    <strong>实测曲线已载入</strong>
                    <small>{state.measurements.length} 个有效数据点</small>
                  </span>
                  <button
                    type="button"
                    aria-label="移除实测 CSV"
                    onClick={() => {
                      dispatch({ type: 'clearMeasurements' })
                      setCsvStatus(null)
                    }}
                  >
                    <X aria-hidden="true" />
                  </button>
                </div>
                <dl>
                  <div>
                    <dt>持续时间</dt>
                    <dd>{measurementDurationMinutes}min</dd>
                  </div>
                  <div>
                    <dt>温度范围</dt>
                    <dd>
                      {Math.min(...measurementTemperatures).toFixed(1)}–
                      {Math.max(...measurementTemperatures).toFixed(1)}℃
                    </dd>
                  </div>
                  <div>
                    <dt>平均功率</dt>
                    <dd>{measurementAveragePower}W</dd>
                  </div>
                </dl>
              </div>
            ) : (
              <label className="csv-dropzone">
                <Upload aria-hidden="true" />
                <strong>上传温升实测 CSV</strong>
                <span>time_s, temperature_c, power_w</span>
                <small>至少 3 行，最多 5000 行 · 仅本地解析</small>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) => {
                    void handleCsvFile(event.target.files?.[0])
                    event.target.value = ''
                  }}
                />
              </label>
            )}

            <button
              className="csv-template-button"
              type="button"
              onClick={downloadCsvTemplate}
            >
              <Download aria-hidden="true" />
              下载 CSV 模板
            </button>

            {csvStatus ? (
              <p
                className={`csv-status is-${csvStatus.tone}`}
                role={csvStatus.tone === 'error' ? 'alert' : 'status'}
              >
                {csvStatus.message}
              </p>
            ) : null}
          </div>
        </div>

        <footer className="input-contract-note">
          <span>输入契约</span>
          <p>
            无 CSV 时使用功率 × 占空比的一阶 RC 模型；有 CSV
            时以实测温升为基线并校准候选结构。任一输入改变后，旧输出立即失效。
          </p>
        </footer>
      </section>

      <aside className="thermal-path-strip">
        <Flame aria-hidden="true" />
        <span>
          <strong>完整热路径：</strong>
          内部热源
        </span>
        <i>→</i>
        <span>壳体接触界面</span>
        <i>→</i>
        <span>壳体内部扩散</span>
        <i>→</i>
        <span>壳体到空气</span>
      </aside>

      <WorkflowFooter
        previousLabel="返回场景预选"
        nextLabel="设置安装约束"
        onPrevious={() => onNavigate('scenario')}
        onNext={() => onNavigate('constraints')}
      />
    </div>
  )
}

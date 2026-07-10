import type { ThermalCurvePoint } from '../analysis/types'

interface ThermalMapProps {
  variant: 'before' | 'after'
  maxTemperatureC: number
  scaleMinimumC: number
  scaleMaximumC: number
}

export function ThermalMap({
  variant,
  maxTemperatureC,
  scaleMinimumC,
  scaleMaximumC,
}: ThermalMapProps) {
  const optimized = variant === 'after'

  return (
    <article className={`thermal-map thermal-map-${variant}`}>
      <div className="thermal-map-heading">
        <div>
          <span>{optimized ? '优化后' : '优化前'}</span>
          <strong>{maxTemperatureC.toFixed(1)}℃</strong>
        </div>
        <small>{optimized ? '预测热量扩散状态' : '当前基线热点状态'}</small>
      </div>
      <div
        className="thermal-image"
        role="img"
        aria-label={`${optimized ? '优化后' : '优化前'}热分布示意，最高温度 ${maxTemperatureC.toFixed(1)} 摄氏度`}
      >
        <span className="thermal-joint joint-shell" />
        <span className="thermal-joint joint-core" />
        <span className="thermal-joint joint-axis" />
        <span className="thermal-blob blob-primary" />
        <span className="thermal-blob blob-secondary" />
        <i className="thermal-crosshair" />
      </div>
      <div className="thermal-scale">
        <span>{scaleMinimumC.toFixed(0)}℃</span>
        <i />
        <span>{scaleMaximumC.toFixed(0)}℃</span>
      </div>
    </article>
  )
}

interface TemperatureCurveProps {
  baseline: ThermalCurvePoint[]
  optimized: ThermalCurvePoint[]
  thermalLimitC: number
}

const CHART = {
  left: 54,
  right: 616,
  top: 32,
  bottom: 265,
} as const

function buildPath(
  curve: ThermalCurvePoint[],
  toX: (timeS: number) => number,
  toY: (temperatureC: number) => number,
): string {
  return curve
    .map(
      (point, index) =>
        `${index === 0 ? 'M' : 'L'}${toX(point.timeS).toFixed(1)} ${toY(
          point.temperatureC,
        ).toFixed(1)}`,
    )
    .join(' ')
}

export function TemperatureCurve({
  baseline,
  optimized,
  thermalLimitC,
}: TemperatureCurveProps) {
  const allPoints = [...baseline, ...optimized]
  const minimumTimeS = Math.min(...allPoints.map((point) => point.timeS))
  const maximumTimeS = Math.max(...allPoints.map((point) => point.timeS))
  const temperatures = allPoints.map((point) => point.temperatureC)
  const rawMinimumTemperature = Math.min(...temperatures, thermalLimitC)
  const rawMaximumTemperature = Math.max(...temperatures, thermalLimitC)
  const temperaturePadding = Math.max(
    3,
    (rawMaximumTemperature - rawMinimumTemperature) * 0.12,
  )
  const minimumTemperature = Math.floor(
    rawMinimumTemperature - temperaturePadding,
  )
  const maximumTemperature = Math.ceil(
    rawMaximumTemperature + temperaturePadding,
  )
  const timeSpanS = Math.max(maximumTimeS - minimumTimeS, 1)
  const temperatureSpan = Math.max(maximumTemperature - minimumTemperature, 1)
  const toX = (timeS: number) =>
    CHART.left +
    ((timeS - minimumTimeS) / timeSpanS) * (CHART.right - CHART.left)
  const toY = (temperatureC: number) =>
    CHART.bottom -
    ((temperatureC - minimumTemperature) / temperatureSpan) *
      (CHART.bottom - CHART.top)
  const baselinePath = buildPath(baseline, toX, toY)
  const optimizedPath = buildPath(optimized, toX, toY)
  const baselineArea = `${baselinePath} L${CHART.right} ${CHART.bottom} L${CHART.left} ${CHART.bottom} Z`
  const optimizedArea = `${optimizedPath} L${CHART.right} ${CHART.bottom} L${CHART.left} ${CHART.bottom} Z`
  const yTicks = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4
    return {
      y: CHART.top + ratio * (CHART.bottom - CHART.top),
      value: maximumTemperature - ratio * temperatureSpan,
    }
  })
  const xTicks = Array.from({ length: 6 }, (_, index) => {
    const ratio = index / 5
    return {
      x: CHART.left + ratio * (CHART.right - CHART.left),
      minutes: (minimumTimeS + ratio * timeSpanS) / 60,
    }
  })
  const thresholdY = toY(thermalLimitC)

  return (
    <article className="curve-card">
      <div className="card-heading">
        <div>
          <span className="section-kicker">Transient response</span>
          <h3>本次输入生成的温升曲线</h3>
        </div>
        <div className="chart-legend" aria-label="曲线图例">
          <span>
            <i className="legend-original" /> 原始方案
          </span>
          <span>
            <i className="legend-optimized" /> 当前方案
          </span>
        </div>
      </div>

      <svg
        className="temperature-chart"
        viewBox="0 0 640 310"
        role="img"
        aria-label={`本次分析温升曲线，热保护阈值 ${thermalLimitC} 摄氏度`}
      >
        <defs>
          <linearGradient id="curveOriginalFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ff5500" stopOpacity=".2" />
            <stop offset="100%" stopColor="#ff5500" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="curveOptimizedFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00ff88" stopOpacity=".13" />
            <stop offset="100%" stopColor="#00ff88" stopOpacity="0" />
          </linearGradient>
        </defs>

        <g className="chart-grid">
          {yTicks.map((tick) => (
            <line
              key={`y-${tick.y}`}
              x1={CHART.left}
              x2={CHART.right}
              y1={tick.y}
              y2={tick.y}
            />
          ))}
          {xTicks.map((tick) => (
            <line
              key={`x-${tick.x}`}
              x1={tick.x}
              x2={tick.x}
              y1={CHART.top}
              y2={CHART.bottom}
            />
          ))}
        </g>

        <g className="chart-axis-labels">
          {yTicks.map((tick) => (
            <text key={`label-y-${tick.y}`} x="8" y={tick.y + 4}>
              {tick.value.toFixed(0)}℃
            </text>
          ))}
          {xTicks.map((tick, index) => (
            <text
              key={`label-x-${tick.x}`}
              x={tick.x}
              y="291"
              textAnchor={index === 0 ? 'start' : index === 5 ? 'end' : 'middle'}
            >
              {tick.minutes.toFixed(1)}
              {index === 5 ? 'min' : ''}
            </text>
          ))}
        </g>

        <path className="curve-fill-original" d={baselineArea} />
        <path className="curve-line-original" d={baselinePath} />
        <path className="curve-fill-optimized" d={optimizedArea} />
        <path className="curve-line-optimized" d={optimizedPath} />

        <line
          className="threshold-line"
          x1={CHART.left}
          x2={CHART.right}
          y1={thresholdY}
          y2={thresholdY}
        />
        <text
          className="threshold-label"
          x={CHART.right - 4}
          y={Math.max(CHART.top + 12, thresholdY - 8)}
          textAnchor="end"
        >
          {thermalLimitC}℃ 热保护阈值
        </text>
      </svg>
    </article>
  )
}

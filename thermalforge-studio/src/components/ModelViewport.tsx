import { Crosshair, Rotate3D, ScanLine, ZoomIn } from 'lucide-react'

interface ModelViewportProps {
  maxTemperatureC?: number
  ambientTemperatureC?: number
}

export function ModelViewport({
  maxTemperatureC,
  ambientTemperatureC = 25,
}: ModelViewportProps) {
  const hotspots = [
    { id: 'knee', label: '膝关节', offset: 0, className: 'is-critical' },
    { id: 'hip', label: '髋关节', offset: -12, className: 'is-warning' },
    { id: 'driver', label: '驱控板', offset: -4, className: 'is-critical' },
    { id: 'jetson', label: 'Jetson', offset: -17, className: 'is-notice' },
  ].map((hotspot) => ({
    ...hotspot,
    value:
      maxTemperatureC === undefined
        ? null
        : Math.max(
            ambientTemperatureC,
            maxTemperatureC + hotspot.offset,
          ).toFixed(0),
  }))
  const legendMaximum = maxTemperatureC
    ? Math.ceil(Math.max(maxTemperatureC, ambientTemperatureC + 10))
    : null

  return (
    <section className="model-viewport" data-testid="three-model-viewport">
      <div className="model-viewport-header">
        <div>
          <h3>机器人热拓扑预览</h3>
          <p>旋转、缩放、热点选择与部件聚焦</p>
        </div>
        <span className="live-status">
          <i aria-hidden="true" />
          Three.js Ready
        </span>
      </div>

      <div
        className="model-canvas-mount"
        data-three-mount="robot-thermal-scene"
        aria-label="机器人 Three.js 三维模型预留区域"
      >
        <div className="ambient-orbit orbit-one" aria-hidden="true" />
        <div className="ambient-orbit orbit-two" aria-hidden="true" />

        <div className="model-toolbar" aria-label="模型视图工具">
          <button type="button" aria-label="旋转模型">
            <Rotate3D aria-hidden="true" />
          </button>
          <button type="button" aria-label="放大模型">
            <ZoomIn aria-hidden="true" />
          </button>
          <button type="button" aria-label="聚焦热点">
            <Crosshair aria-hidden="true" />
          </button>
          <button type="button" aria-label="扫描模型">
            <ScanLine aria-hidden="true" />
          </button>
        </div>

        <div className="model-placeholder-assembly" aria-hidden="true">
          <span className="assembly-ring ring-outer" />
          <span className="assembly-ring ring-inner" />
          <span className="assembly-core" />
          <span className="assembly-arm arm-left" />
          <span className="assembly-arm arm-right" />
        </div>

        <div className="model-mount-label">
          <strong>3D 机器人模型挂载区</strong>
          <code>&lt;RobotThermalScene /&gt;</code>
          <span>后续可直接接入 GLTF / Three.js 热场材质</span>
        </div>

        <div className="hotspot-list">
          {hotspots.map((hotspot) => (
            <button
              key={hotspot.id}
              type="button"
              className={`hotspot hotspot-${hotspot.id} ${
                hotspot.value === null ? 'is-pending' : hotspot.className
              }`}
              aria-label={
                hotspot.value === null
                  ? `${hotspot.label}暂无分析温度`
                  : `${hotspot.label} ${hotspot.value}摄氏度`
              }
            >
              <i aria-hidden="true" />
              <span>
                <small>{hotspot.label}</small>
                <strong>{hotspot.value ?? '—'}</strong>
              </span>
            </button>
          ))}
        </div>

        <div className="heat-legend">
          <span>{ambientTemperatureC.toFixed(0)}℃</span>
          <i aria-hidden="true" />
          <span>{legendMaximum === null ? '待分析' : `${legendMaximum}℃`}</span>
        </div>
      </div>
    </section>
  )
}

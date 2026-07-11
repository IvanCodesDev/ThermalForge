import { ContactShadows, OrbitControls, useProgress } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Box, Combine, Info, RotateCcw, UnfoldHorizontal } from 'lucide-react'
import {
  Component,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { GltfViewerAsset } from './GltfViewerAsset'
import { StlViewerAsset } from './StlViewerAsset'
import type { ViewerManifest } from './viewerManifest'

interface ModelStageProps {
  manifest: ViewerManifest
  isExploded: boolean
  selectedPart: string | null
  onToggleExploded: () => void
  onSelectPart: (part: string | null) => void
}

interface ViewerErrorBoundaryProps {
  children: ReactNode
  onError: (error: Error) => void
}

interface ViewerErrorBoundaryState {
  failed: boolean
}

class ViewerErrorBoundary extends Component<
  ViewerErrorBoundaryProps,
  ViewerErrorBoundaryState
> {
  state: ViewerErrorBoundaryState = { failed: false }

  static getDerivedStateFromError(): ViewerErrorBoundaryState {
    return { failed: true }
  }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    this.props.onError(error)
  }

  render() {
    return this.state.failed ? null : this.props.children
  }
}

function AssetLoadingOverlay() {
  const { active, progress } = useProgress()
  if (!active) return null

  return (
    <div className="model-load-overlay" role="status">
      <span aria-hidden="true" />
      <strong>正在加载三维模型</strong>
      <small>{Math.round(progress)}%</small>
    </div>
  )
}

function ViewerAssetRenderer({
  manifest,
  selectedPart,
  isExploded,
  wireframe,
  onReady,
  onSelectPart,
}: Pick<
  ModelStageProps,
  'manifest' | 'selectedPart' | 'isExploded' | 'onSelectPart'
> & {
  wireframe: boolean
  onReady: () => void
}) {
  switch (manifest.asset.format) {
    case 'stl':
      return (
        <StlViewerAsset
          manifest={manifest}
          selectedPartId={selectedPart}
          wireframe={wireframe}
          onReady={onReady}
          onSelectPart={onSelectPart}
        />
      )
    case 'glb':
    case 'gltf':
      return (
        <GltfViewerAsset
          manifest={manifest}
          selectedPartId={selectedPart}
          isExploded={isExploded}
          wireframe={wireframe}
          onReady={onReady}
          onSelectPart={onSelectPart}
        />
      )
    default:
      throw new Error(`暂不支持 ${manifest.asset.format.toUpperCase()} 模型。`)
  }
}

export function ModelStage({
  manifest,
  isExploded,
  selectedPart,
  onToggleExploded,
  onSelectPart,
}: ModelStageProps) {
  const controlsRef = useRef<OrbitControlsImpl>(null)
  const variants = useMemo(
    () => {
      const availableVariants = manifest.variants ?? []
      return availableVariants.length > 0
        ? availableVariants
        : [
            {
              id: 'primary',
              label: manifest.name,
              asset: manifest.asset,
              transform: manifest.transform,
              capabilities: manifest.capabilities,
              parts: manifest.parts,
            },
          ]
    },
    [manifest],
  )
  const [activeVariantId, setActiveVariantId] = useState(
    variants[0]?.id ?? 'primary',
  )
  const [autoRotate, setAutoRotate] = useState(false)
  const [wireframe, setWireframe] = useState(false)
  const activeVariant =
    variants.find((variant) => variant.id === activeVariantId) ?? variants[0]
  const activeManifest = useMemo(
    () => ({
      ...manifest,
      asset: activeVariant.asset,
      transform: activeVariant.transform,
      capabilities: activeVariant.capabilities,
      parts: activeVariant.parts,
    }),
    [activeVariant, manifest],
  )
  const assetKey = `${manifest.id}:${manifest.revision}:${activeVariant.id}:${activeVariant.asset.id}`
  const [readyAssetKey, setReadyAssetKey] = useState<string | null>(null)
  const [assetError, setAssetError] = useState<{
    key: string
    message: string
  } | null>(null)
  const handleAssetReady = useCallback(
    () => setReadyAssetKey(assetKey),
    [assetKey],
  )
  const isAssetReady = readyAssetKey === assetKey
  const currentAssetError = assetError?.key === assetKey ? assetError.message : null
  const canInspect = isAssetReady && activeManifest.capabilities.selection
  const canExplode = isAssetReady && activeManifest.capabilities.explosion
  const effectiveExploded = isExploded && canExplode
  const inspectablePart = activeManifest.parts.find((part) => part.selectable)
  const isInspecting = selectedPart === inspectablePart?.id
  const assetClassification = activeManifest.notices.some((notice) =>
    /concept|概念|不是可制造|非可制造/i.test(notice),
  )
    ? 'CONCEPT MESH'
    : 'MODEL ASSET'

  useEffect(() => {
    setActiveVariantId(variants[0]?.id ?? 'primary')
    setAutoRotate(false)
    setWireframe(false)
    onSelectPart(null)
  }, [manifest.id, manifest.revision, onSelectPart, variants])

  const selectVariant = (variantId: string) => {
    if (variantId === activeVariant.id) {
      return
    }
    if (isExploded) {
      onToggleExploded()
    }
    onSelectPart(null)
    setActiveVariantId(variantId)
  }

  return (
    <section className="model-stage" aria-label="三维关节模型">
      <div className="model-stage-atmosphere" aria-hidden="true" />

      <div className="model-asset-label">
        <span>
          {assetClassification} · {activeManifest.asset.format.toUpperCase()}
        </span>
        <strong>{activeVariant.label}</strong>
      </div>

      {variants.length > 1 ? (
        <div className="model-variant-switch" aria-label="模型版本">
          {variants.map((variant) => (
            <button
              key={variant.id}
              type="button"
              aria-label={`切换到${variant.label}`}
              aria-pressed={variant.id === activeVariant.id}
              onClick={() => selectVariant(variant.id)}
            >
              {variant.label}
            </button>
          ))}
        </div>
      ) : null}

      <Canvas
        className="model-canvas"
        camera={{
          position: activeManifest.camera.position,
          fov: activeManifest.camera.fov,
          near: 0.1,
          far: 100,
        }}
        dpr={[1, 1.75]}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        shadows="basic"
        onPointerMissed={() => onSelectPart(null)}
        fallback={
          <div className="webgl-fallback">
            当前浏览器无法启用 WebGL，请查看设计说明或更换浏览器。
          </div>
        }
      >
        <ambientLight intensity={0.78} />
        <directionalLight
          position={[4, 7, 5]}
          intensity={3.8}
          color="#fff3df"
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <directionalLight
          position={[-5, 1, -4]}
          intensity={2.1}
          color="#79a2c3"
        />
        <pointLight
          position={[0, 3.8, -2]}
          intensity={30}
          distance={8}
          color="#ff5500"
        />

        <ViewerErrorBoundary
          key={assetKey}
          onError={(error) =>
            setAssetError({ key: assetKey, message: error.message })
          }
        >
          <Suspense fallback={null}>
            <ViewerAssetRenderer
              manifest={activeManifest}
              selectedPart={selectedPart}
              isExploded={effectiveExploded}
              wireframe={wireframe}
              onReady={handleAssetReady}
              onSelectPart={onSelectPart}
            />
          </Suspense>
        </ViewerErrorBoundary>

        <Suspense fallback={null}>
          <ContactShadows
            position={[0, -2.26, 0]}
            opacity={0.4}
            scale={9}
            blur={2.8}
            far={4.5}
            color="#000000"
          />
        </Suspense>

        <OrbitControls
          ref={controlsRef}
          makeDefault
          enablePan={false}
          minDistance={5}
          maxDistance={10}
          minPolarAngle={Math.PI * 0.22}
          maxPolarAngle={Math.PI * 0.72}
          target={activeManifest.camera.target}
          dampingFactor={0.06}
          enableDamping
          autoRotate={autoRotate}
          autoRotateSpeed={1.2}
        />
      </Canvas>

      <AssetLoadingOverlay />

      {currentAssetError ? (
        <div className="model-error-overlay" role="alert">
          <strong>模型未能载入</strong>
          <span>{currentAssetError}</span>
        </div>
      ) : null}

      <div className="model-controls" aria-label="模型控制">
        <button
          type="button"
          onClick={() => setAutoRotate((value) => !value)}
          disabled={!isAssetReady}
          aria-label={autoRotate ? '停止自动旋转' : '开启自动旋转'}
          aria-pressed={autoRotate}
        >
          <RotateCcw aria-hidden="true" />
          <span>{autoRotate ? '停止' : '旋转'}</span>
        </button>
        <button
          type="button"
          onClick={() => setWireframe((value) => !value)}
          disabled={!isAssetReady}
          aria-label={wireframe ? '关闭线框模式' : '开启线框模式'}
          aria-pressed={wireframe}
        >
          <Box aria-hidden="true" />
          <span>线框</span>
        </button>
        <button
          type="button"
          onClick={onToggleExploded}
          disabled={!canExplode}
          aria-label={effectiveExploded ? '合并模型' : '爆炸模型'}
          aria-pressed={effectiveExploded}
        >
          {effectiveExploded ? (
            <Combine aria-hidden="true" />
          ) : (
            <UnfoldHorizontal aria-hidden="true" />
          )}
          <span>{effectiveExploded ? '合并' : '爆炸'}</span>
        </button>
        <button
          type="button"
          onClick={() => controlsRef.current?.reset()}
          aria-label="重置模型视角"
        >
          <RotateCcw aria-hidden="true" />
          <span>重置</span>
        </button>
        <button
          type="button"
          onClick={() =>
            inspectablePart &&
            onSelectPart(isInspecting ? null : inspectablePart.id)
          }
          disabled={!canInspect || !inspectablePart}
          aria-label={isInspecting ? '关闭资产信息' : '查看资产信息'}
        >
          <Info aria-hidden="true" />
          <span>{isInspecting ? '关闭' : '信息'}</span>
        </button>
      </div>

      {!isAssetReady ? (
        <p className="model-interaction-hint">正在准备真实 CAD 模型</p>
      ) : !canInspect ? (
        <p className="model-interaction-hint">当前资产仅支持轨道查看</p>
      ) : (
        <p className="model-interaction-hint">
          {effectiveExploded
            ? '选择部件查看设计依据'
            : '点击模型或使用信息按钮查看资产信息'}
        </p>
      )}
    </section>
  )
}

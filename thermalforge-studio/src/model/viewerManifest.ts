import wallEStlUrl from '../../../3d/瓦力/temp/solidworksWALLE.stl?url'
import { API_BASE_URL } from '../api'
import type {
  ViewerLibrary as BackendViewerLibrary,
  ViewerManifest as BackendViewerManifest,
} from '../api'

export type ViewerAssetFormat = 'stl' | 'glb' | 'gltf' | 'obj'
export type ViewerVector3 = [number, number, number]
export type ViewerQuaternion = [number, number, number, number]

export interface ViewerAsset {
  id: string
  artifactId?: string
  url: string
  format: ViewerAssetFormat
  mimeType: string
  sha256?: string
  sizeBytes?: number
}

export interface ViewerTransform {
  translation: ViewerVector3
  rotation: ViewerQuaternion
  scale: ViewerVector3
}

export interface ViewerPartMetric {
  label: string
  value: string
}

export interface ViewerPart {
  id: string
  label: string
  description: string
  binding:
    | { kind: 'whole-asset' }
    | { kind: 'node-names'; names: string[] }
  selectable: boolean
  explode?: ViewerVector3
  metrics?: ViewerPartMetric[]
  tags?: string[]
}

export interface ViewerVariant {
  id: string
  label: string
  asset: ViewerAsset
  transform: ViewerTransform
  capabilities: ViewerManifest['capabilities']
  parts: ViewerPart[]
}

export interface ViewerManifest {
  schemaVersion: '1.0'
  id: string
  taskId: string | null
  revision: number
  name: string
  asset: ViewerAsset
  transform: ViewerTransform
  camera: {
    position: ViewerVector3
    target: ViewerVector3
    fov: number
  }
  capabilities: {
    selection: boolean
    explosion: boolean
    partDetails: boolean
  }
  parts: ViewerPart[]
  variants: ViewerVariant[]
  notices: string[]
}

export const DEFAULT_VIEWER_MANIFEST: ViewerManifest = {
  schemaVersion: '1.0',
  id: 'local-wall-e-stl-v1',
  taskId: null,
  revision: 1,
  name: 'Wall-E CAD 装配',
  asset: {
    id: 'wall-e-stl',
    url: wallEStlUrl,
    format: 'stl',
    mimeType: 'model/stl',
    sizeBytes: 6_034_584,
  },
  transform: {
    translation: [0, 0, 0],
    rotation: [0, -Math.SQRT1_2, 0, Math.SQRT1_2],
    scale: [1, 1, 1],
  },
  camera: {
    position: [5.2, 3.1, 7.4],
    target: [0, 0, 0],
    fov: 34,
  },
  capabilities: {
    selection: true,
    explosion: false,
    partDetails: true,
  },
  parts: [
    {
      id: 'wall-e-assembly',
      label: 'Wall-E 整体装配',
      description:
        '仓库中真实 CAD 导出的 STL 网格。当前文件已扁平化为单一网格，适合整机查看；部件树与装配变换需由 STEP 转换后的 GLB 提供。',
      binding: { kind: 'whole-asset' },
      selectable: true,
      metrics: [
        { label: '网格规模', value: '120,690 三角面' },
        { label: '文件体积', value: '5.76 MiB' },
        { label: '资产格式', value: 'Binary STL' },
      ],
      tags: ['真实 CAD 网格', '自动居中', '按包围盒适配'],
    },
  ],
  variants: [],
  notices: [
    '该 STL 不包含单位、材质或装配层级；当前按包围盒归一化显示。',
    '资产来源与公开分发许可尚未在仓库中声明。',
  ],
}

function resolveAssetUrl(url: string): string {
  if (/^[a-z][a-z\d+.-]*:/i.test(url) || !API_BASE_URL) {
    return url
  }
  return new URL(url, `${API_BASE_URL}/`).toString()
}

function formatBytes(sizeBytes: number): string {
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KiB`
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(2)} MiB`
}

export function fromBackendViewerManifest(
  source: BackendViewerManifest,
): ViewerManifest {
  const toAsset = (
    asset: BackendViewerManifest['asset'],
  ): ViewerAsset => ({
    id: asset.artifact_id,
    artifactId: asset.artifact_id,
    url: resolveAssetUrl(asset.url),
    format: asset.format,
    mimeType: asset.mime_type,
    sha256: asset.sha256,
    sizeBytes: asset.size_bytes,
  })
  const toTransform = (
    asset: BackendViewerManifest['asset'],
  ): ViewerTransform => ({
    translation: asset.transform?.translation ?? [0, 0, 0],
    rotation: asset.transform?.rotation ?? [0, 0, 0, 1],
    scale: asset.transform?.scale ?? [1, 1, 1],
  })
  const variants: ViewerVariant[] = (source.variants ?? []).map((variant) => {
    const parts = variant.parts ?? []
    return {
      id: variant.id,
      label: variant.label,
      asset: toAsset(variant.asset),
      transform: toTransform(variant.asset),
      capabilities: {
        selection: parts.length > 0,
        explosion: variant.supports_explosion ?? false,
        partDetails: parts.length > 0,
      },
      parts: parts.map((part) => {
        const nodeNames = part.node_names ?? []
        return {
          id: part.id,
          label: part.label,
          description: part.description,
          binding:
            part.binding === 'node_names'
              ? { kind: 'node-names' as const, names: nodeNames }
              : { kind: 'whole-asset' as const },
          selectable: true,
          explode: part.explode ?? undefined,
          tags:
            part.binding === 'node_names'
              ? ['后端节点绑定', ...nodeNames]
              : ['整体资产'],
        }
      }),
    }
  })
  const preferredVariant = variants.find(
    (variant) => variant.asset.artifactId === source.asset.artifact_id,
  )
  const format = source.asset.format
  const fidelity =
    source.asset.kind === 'normalized_model' ? '标准化模型' : '原始模型'
  const fallbackPart: ViewerPart = {
    id: `asset-${source.asset.artifact_id}`,
    label: `任务${fidelity}`,
    description:
      '该网格由任务产物清单加载，内容 URL 由后端按任务归属与批准状态校验。当前清单尚未提供装配部件绑定，因此按整体模型检视。',
    binding: { kind: 'whole-asset' },
    selectable: true,
    metrics: [
      { label: '产物类型', value: fidelity },
      { label: '文件体积', value: formatBytes(source.asset.size_bytes) },
      { label: '校验摘要', value: source.asset.sha256.slice(0, 12) },
    ],
    tags: ['后端任务产物', '已批准', format.toUpperCase()],
  }

  return {
    schemaVersion: source.schema_version ?? '1.0',
    id: `task-model-${source.asset.artifact_id}`,
    taskId: source.task_id,
    revision: 1,
    name: `任务工程模型 · ${format.toUpperCase()}`,
    asset: toAsset(source.asset),
    transform: toTransform(source.asset),
    camera: DEFAULT_VIEWER_MANIFEST.camera,
    capabilities: preferredVariant?.capabilities ?? {
      selection: true,
      explosion: false,
      partDetails: true,
    },
    parts: preferredVariant?.parts ?? [fallbackPart],
    variants,
    notices:
      source.notices && source.notices.length > 0
        ? source.notices
        : [
            '当前任务清单未包含装配树，部件选择和爆炸将在标准化 GLB 元数据接入后启用。',
          ],
  }
}

export function fromBackendViewerLibrary(
  source: BackendViewerLibrary,
): ViewerManifest | null {
  const models = source.models ?? []
  if (models.length === 0) {
    return null
  }

  const variants: ViewerVariant[] = models.map((model) => {
    const parts: ViewerPart[] = (model.parts ?? []).map((part) => {
      const nodeNames = part.node_names ?? []
      return {
        id: part.id,
        label: part.label,
        description: part.description,
        binding:
          part.binding === 'node_names'
            ? { kind: 'node-names' as const, names: nodeNames }
            : { kind: 'whole-asset' as const },
        selectable: true,
        explode: part.explode ?? undefined,
        tags:
          part.binding === 'node_names'
            ? ['案例节点绑定', ...nodeNames]
            : ['案例整体资产'],
      }
    })
    const libraryParts =
      parts.length > 0
        ? parts
        : [
            {
              id: `${model.id}-whole`,
              label: model.label,
              description: model.description,
              binding: { kind: 'whole-asset' as const },
              selectable: true,
              tags: ['案例整体资产'],
            },
          ]
    return {
      id: model.id,
      label: model.label,
      asset: {
        id: model.asset.artifact_id,
        artifactId: model.asset.artifact_id,
        url: resolveAssetUrl(model.asset.url),
        format: model.asset.format,
        mimeType: model.asset.mime_type,
        sha256: model.asset.sha256,
        sizeBytes: model.asset.size_bytes,
      },
      transform: {
        translation: model.asset.transform?.translation ?? [0, 0, 0],
        rotation: model.asset.transform?.rotation ?? [0, 0, 0, 1],
        scale: model.asset.transform?.scale ?? [1, 1, 1],
      },
      capabilities: {
        selection: libraryParts.length > 0,
        explosion: model.supports_explosion ?? false,
        partDetails: libraryParts.length > 0,
      },
      parts: libraryParts,
    }
  })
  const primary = variants[0]
  return {
    schemaVersion: source.schema_version ?? '1.0',
    id: 'curated-model-library-v1',
    taskId: null,
    revision: 1,
    name: '案例模型库',
    asset: primary.asset,
    transform: primary.transform,
    camera: DEFAULT_VIEWER_MANIFEST.camera,
    capabilities: primary.capabilities,
    parts: primary.parts,
    variants,
    notices: [
      ...new Set(models.flatMap((model) => model.notices ?? [])),
    ],
  }
}

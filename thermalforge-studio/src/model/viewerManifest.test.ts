import { describe, expect, it } from 'vitest'
import type {
  ViewerLibrary as BackendViewerLibrary,
  ViewerManifest as BackendViewerManifest,
} from '../api'
import {
  fromBackendViewerLibrary,
  fromBackendViewerManifest,
} from './viewerManifest'

describe('viewer manifest mapping', () => {
  it('maps backend variants, node parts, and fidelity notices', () => {
    const segmentedAsset = {
      artifact_id: 'segmented-1',
      kind: 'normalized_model' as const,
      url: '/v1/tasks/task-1/models/segmented-1/content',
      format: 'glb' as const,
      mime_type: 'model/gltf-binary',
      sha256: '1234567890abcdef',
      size_bytes: 4096,
      transform: {
        translation: [0, 0, 0] as [number, number, number],
        rotation: [0, 0, 0, 1] as [number, number, number, number],
        scale: [1, 1, 1] as [number, number, number],
      },
    }
    const source: BackendViewerManifest = {
      schema_version: '1.0',
      task_id: 'task-1',
      asset: segmentedAsset,
      variants: [
        {
          id: 'segmented',
          label: '分件参考模型',
          asset: segmentedAsset,
          supports_explosion: true,
          parts: [
            {
              id: 'segmented-part-1',
              label: '分件网格 01',
              description: '模型节点 root.0',
              binding: 'node_names',
              node_names: ['root.0'],
              explode: [0.55, 0, 0],
            },
          ],
        },
        {
          id: 'whole',
          label: '整体参考模型',
          asset: {
            ...segmentedAsset,
            artifact_id: 'whole-1',
            kind: 'raw_model',
          },
          supports_explosion: false,
          parts: [
            {
              id: 'whole-whole',
              label: '整体参考模型',
              description: '整体模型',
              binding: 'whole_asset',
              node_names: [],
              explode: null,
            },
          ],
        },
      ],
      notices: ['概念参考模型，不是可制造 CAD。'],
    }

    const manifest = fromBackendViewerManifest(source)

    expect(manifest.variants.map((variant) => variant.id)).toEqual([
      'segmented',
      'whole',
    ])
    expect(manifest.variants[0]?.parts[0]).toMatchObject({
      id: 'segmented-part-1',
      binding: { kind: 'node-names', names: ['root.0'] },
      explode: [0.55, 0, 0],
    })
    expect(manifest.variants[0]?.capabilities.explosion).toBe(true)
    expect(manifest.notices).toContain('概念参考模型，不是可制造 CAD。')
  })

  it('maps every curated library model into a selectable variant', () => {
    const source: BackendViewerLibrary = {
      schema_version: '1.0',
      models: [
        {
          id: 'foc-segmented',
          label: 'FOC 机械臂 · 分件参考',
          description: 'Bang 分件概念网格',
          asset: {
            artifact_id: 'foc-segmented',
            kind: 'normalized_model',
            url: '/v1/viewer-library/foc-segmented/content',
            format: 'glb',
            mime_type: 'model/gltf-binary',
            sha256: 'abc123',
            size_bytes: 4096,
            transform: {
              translation: [0, 0, 0],
              rotation: [0, 0, 0, 1],
              scale: [1, 1, 1],
            },
          },
          supports_explosion: true,
          parts: [
            {
              id: 'foc-segmented-part-1',
              label: '分件网格 01',
              description: '模型节点 root.0',
              binding: 'node_names',
              node_names: ['root.0'],
              explode: [0.55, 0, 0],
            },
          ],
          notices: ['概念网格，不是可制造 CAD。'],
        },
        {
          id: 'hyper3d-original',
          label: 'Hyper3D 机械臂 · 原始概念',
          description: '原始概念网格',
          asset: {
            artifact_id: 'hyper3d-original',
            kind: 'raw_model',
            url: '/v1/viewer-library/hyper3d-original/content',
            format: 'glb',
            mime_type: 'model/gltf-binary',
            sha256: 'def456',
            size_bytes: 8192,
            transform: {
              translation: [0, 0, 0],
              rotation: [0, 0, 0, 1],
              scale: [1, 1, 1],
            },
          },
          supports_explosion: false,
          parts: [],
          notices: ['概念网格，不是可制造 CAD。'],
        },
      ],
    }

    const manifest = fromBackendViewerLibrary(source)

    expect(manifest?.name).toBe('案例模型库')
    expect(manifest?.taskId).toBeNull()
    expect(manifest?.variants.map((variant) => variant.id)).toEqual([
      'foc-segmented',
      'hyper3d-original',
    ])
    expect(manifest?.variants[0]?.capabilities.explosion).toBe(true)
    expect(manifest?.variants[0]?.parts[0]?.binding).toEqual({
      kind: 'node-names',
      names: ['root.0'],
    })
  })
})

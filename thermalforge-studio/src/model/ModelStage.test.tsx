import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ModelStage } from './ModelStage'
import type { ViewerManifest } from './viewerManifest'

vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children }: { children: ReactNode }) => (
    <div data-testid="canvas">{children}</div>
  ),
}))

vi.mock('@react-three/drei', () => ({
  ContactShadows: () => null,
  OrbitControls: ({
    autoRotate,
  }: {
    autoRotate?: boolean
  }) => (
    <div data-testid="orbit-controls" data-auto-rotate={String(autoRotate)} />
  ),
  useProgress: () => ({ active: false, progress: 100 }),
}))

vi.mock('./GltfViewerAsset', async () => {
  const { useEffect } = await import('react')
  return {
    GltfViewerAsset: ({
      manifest,
      isExploded,
      wireframe,
      onReady,
    }: {
      manifest: ViewerManifest
      isExploded: boolean
      wireframe: boolean
      onReady: () => void
    }) => {
      useEffect(onReady, [onReady])
      return (
        <div
          data-testid="gltf-asset"
          data-asset={manifest.asset.id}
          data-exploded={String(isExploded)}
          data-wireframe={String(wireframe)}
        />
      )
    },
  }
})

vi.mock('./StlViewerAsset', () => ({
  StlViewerAsset: () => null,
}))

const segmentedAsset = {
  id: 'segmented',
  url: '/segmented.glb',
  format: 'glb' as const,
  mimeType: 'model/gltf-binary',
}

const MANIFEST: ViewerManifest = {
  schemaVersion: '1.0',
  id: 'task-model',
  taskId: 'task-1',
  revision: 1,
  name: '任务工程模型',
  asset: segmentedAsset,
  transform: {
    translation: [0, 0, 0],
    rotation: [0, 0, 0, 1],
    scale: [1, 1, 1],
  },
  camera: {
    position: [5, 3, 7],
    target: [0, 0, 0],
    fov: 34,
  },
  capabilities: {
    selection: true,
    explosion: true,
    partDetails: true,
  },
  parts: [
    {
      id: 'segment-1',
      label: '分件网格 01',
      description: '节点 root.0',
      binding: { kind: 'node-names', names: ['root.0'] },
      selectable: true,
      explode: [0.55, 0, 0],
    },
  ],
  variants: [
    {
      id: 'segmented',
      label: '分件参考模型',
      asset: segmentedAsset,
      transform: {
        translation: [0, 0, 0],
        rotation: [0, 0, 0, 1],
        scale: [1, 1, 1],
      },
      capabilities: {
        selection: true,
        explosion: true,
        partDetails: true,
      },
      parts: [
        {
          id: 'segment-1',
          label: '分件网格 01',
          description: '节点 root.0',
          binding: { kind: 'node-names', names: ['root.0'] },
          selectable: true,
          explode: [0.55, 0, 0],
        },
      ],
    },
    {
      id: 'whole',
      label: '整体参考模型',
      asset: { ...segmentedAsset, id: 'whole', url: '/whole.glb' },
      transform: {
        translation: [0, 0, 0],
        rotation: [0, 0, 0, 1],
        scale: [1, 1, 1],
      },
      capabilities: {
        selection: true,
        explosion: false,
        partDetails: true,
      },
      parts: [
        {
          id: 'whole-asset',
          label: '整体参考模型',
          description: '整体模型',
          binding: { kind: 'whole-asset' },
          selectable: true,
        },
      ],
    },
  ],
  notices: ['概念参考模型'],
}

function Harness() {
  const [isExploded, setExploded] = useState(false)
  const [selectedPart, setSelectedPart] = useState<string | null>(null)
  return (
    <ModelStage
      manifest={MANIFEST}
      isExploded={isExploded}
      selectedPart={selectedPart}
      onToggleExploded={() => setExploded((value) => !value)}
      onSelectPart={setSelectedPart}
    />
  )
}

describe('ModelStage controls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('switches variants and controls rotation, wireframe, and explosion', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await screen.findByTestId('gltf-asset')
    expect(screen.getByTestId('gltf-asset')).toHaveAttribute(
      'data-asset',
      'segmented',
    )

    await user.click(
      screen.getByRole('button', { name: '切换到整体参考模型' }),
    )
    expect(screen.getByTestId('gltf-asset')).toHaveAttribute(
      'data-asset',
      'whole',
    )
    expect(screen.getByRole('button', { name: '爆炸模型' })).toBeDisabled()

    await user.click(
      screen.getByRole('button', { name: '切换到分件参考模型' }),
    )
    await user.click(screen.getByRole('button', { name: '爆炸模型' }))
    expect(screen.getByTestId('gltf-asset')).toHaveAttribute(
      'data-exploded',
      'true',
    )

    await user.click(screen.getByRole('button', { name: '开启自动旋转' }))
    expect(screen.getByTestId('orbit-controls')).toHaveAttribute(
      'data-auto-rotate',
      'true',
    )

    await user.click(screen.getByRole('button', { name: '开启线框模式' }))
    expect(screen.getByTestId('gltf-asset')).toHaveAttribute(
      'data-wireframe',
      'true',
    )
  })

  it('keeps loading manifests created before variants were added', async () => {
    const legacyManifest = {
      ...MANIFEST,
      variants: undefined,
    } as unknown as ViewerManifest

    render(
      <ModelStage
        manifest={legacyManifest}
        isExploded={false}
        selectedPart={null}
        onToggleExploded={vi.fn()}
        onSelectPart={vi.fn()}
      />,
    )

    expect(await screen.findByTestId('gltf-asset')).toHaveAttribute(
      'data-asset',
      'segmented',
    )
  })
})

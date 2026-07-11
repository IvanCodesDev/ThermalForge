import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PartDetailSheet } from './PartDetailSheet'
import { DEFAULT_VIEWER_MANIFEST } from './viewerManifest'

describe('PartDetailSheet', () => {
  it('resolves a selected part from a non-default model variant', () => {
    render(
      <PartDetailSheet
        manifest={{
          ...DEFAULT_VIEWER_MANIFEST,
          variants: [
            {
              id: 'whole',
              label: '整体参考模型',
              asset: {
                ...DEFAULT_VIEWER_MANIFEST.asset,
                id: 'whole-model',
                format: 'glb',
              },
              transform: DEFAULT_VIEWER_MANIFEST.transform,
              capabilities: {
                selection: true,
                explosion: false,
                partDetails: true,
              },
              parts: [
                {
                  id: 'whole-part',
                  label: '整体模型资产',
                  description: '完整模型参考。',
                  binding: { kind: 'whole-asset' },
                  selectable: true,
                },
              ],
            },
          ],
        }}
        part="whole-part"
        onClose={vi.fn()}
      />,
    )

    expect(
      screen.getByRole('complementary', { name: '部件设计说明' }),
    ).toBeVisible()
    expect(screen.getByText('整体模型资产')).toBeVisible()
    expect(screen.getByText('GLB ASSET')).toBeVisible()
  })
})

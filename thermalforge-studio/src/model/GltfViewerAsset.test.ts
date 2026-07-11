import { describe, expect, it } from 'vitest'
import { buildPartNodeLookup } from './partNodeBindings'
import type { ViewerPart } from './viewerManifest'

describe('GLB part bindings', () => {
  it('matches dotted manifest names after GLTFLoader sanitizes them', () => {
    const part: ViewerPart = {
      id: 'segmented-part-1',
      label: '分件网格 01',
      description: '模型节点 root.0',
      binding: { kind: 'node-names', names: ['root.0'] },
      selectable: true,
      explode: [0.55, 0, 0],
    }

    const lookup = buildPartNodeLookup([part])

    expect(lookup.get('root.0')).toBe(part)
    expect(lookup.get('root0')).toBe(part)
  })
})

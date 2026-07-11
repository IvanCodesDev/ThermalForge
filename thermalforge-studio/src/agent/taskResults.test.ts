import { describe, expect, it } from 'vitest'
import {
  collectTaskEvidence,
  serializeTaskResults,
  type TaskResultBundle,
} from './taskResults'

describe('task result presentation', () => {
  it('recursively removes sensitive keys from objects and arrays', () => {
    const unsafe = {
      engineeringBrief: {
        project_title: 'FOC 关节',
        overall_confidence: 0.9,
        api_key: 'top-level-secret',
        nested: [
          {
            access_token: 'nested-secret',
            safe_value: 'preserved',
          },
        ],
      },
    } as unknown as TaskResultBundle

    const output = serializeTaskResults(unsafe, null)

    expect(output).not.toContain('top-level-secret')
    expect(output).not.toContain('nested-secret')
    expect(output).not.toContain('api_key')
    expect(output).not.toContain('access_token')
    expect(output).toContain('preserved')
    expect(output).not.toContain('viewer_manifest')
  })

  it('keeps document quotes traceable to artifact, chunk, and page', () => {
    const results: TaskResultBundle = {
      engineeringBrief: {
        project_title: 'FOC 关节',
        overall_confidence: 0.9,
        heat_sources: [
          {
            name: 'FOC 驱动器',
            power_w: 120,
            confidence: 0.95,
            evidence: [
              {
                source_kind: 'document',
                quote: '功率器件持续热耗散按 120 W 设计。',
                artifact_id: 'artifact-12345678',
                chunk_id: 'chunk-87654321',
                page_number: 3,
              },
            ],
          },
        ],
      },
    }

    expect(collectTaskEvidence(results)).toEqual([
      expect.objectContaining({
        label: '热源 · FOC 驱动器',
        quote: '功率器件持续热耗散按 120 W 设计。',
        source: '工程文档 · 产物 artifact · 片段 chunk-87 · 第 3 页',
      }),
    ])
  })
})

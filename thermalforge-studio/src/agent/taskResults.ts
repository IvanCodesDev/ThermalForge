import type {
  EngineeringBrief,
  EvidenceRef,
  ThermalAnalysisResult,
  ThermalDesignSpec,
} from '../api'
import type { ViewerManifest } from '../model/viewerManifest'

export interface TaskResultBundle {
  engineeringBrief?: EngineeringBrief
  thermalAnalysis?: ThermalAnalysisResult
  thermalDesign?: ThermalDesignSpec
}

export interface TaskEvidenceItem {
  id: string
  label: string
  quote: string
  source: string
}

const SENSITIVE_KEY =
  /(^|_)(api_?key|authorization|password|private_?key|secret|token)$/i

function evidenceSource(reference: EvidenceRef): string {
  if (reference.source_kind === 'user_prompt') {
    return '设计目标'
  }
  if (reference.source_kind === 'clarification') {
    return [
      '补充回答',
      reference.clarification_id
        ? `ID ${reference.clarification_id.slice(0, 8)}`
        : null,
    ]
      .filter(Boolean)
      .join(' · ')
  }
  return [
    '工程文档',
    reference.artifact_id ? `产物 ${reference.artifact_id.slice(0, 8)}` : null,
    reference.chunk_id ? `片段 ${reference.chunk_id.slice(0, 8)}` : null,
    reference.page_number ? `第 ${reference.page_number} 页` : null,
  ]
    .filter(Boolean)
    .join(' · ')
}

export function collectTaskEvidence(
  results: TaskResultBundle,
): TaskEvidenceItem[] {
  const brief = results.engineeringBrief
  if (!brief) {
    return []
  }

  const groups: Array<{ label: string; evidence: EvidenceRef[] }> = [
    ...(brief.heat_sources ?? []).map((source) => ({
      label: `热源 · ${source.name}`,
      evidence: source.evidence ?? [],
    })),
    ...(brief.environment
      ? [{ label: '运行环境', evidence: brief.environment.evidence ?? [] }]
      : []),
    ...(brief.envelope
      ? [{ label: '安装包络', evidence: brief.envelope.evidence ?? [] }]
      : []),
    ...(brief.mass_budget
      ? [{ label: '质量预算', evidence: brief.mass_budget.evidence ?? [] }]
      : []),
  ]
  const seen = new Set<string>()
  const items: TaskEvidenceItem[] = []
  groups.forEach((group) => {
    group.evidence.forEach((reference) => {
      const identity = `${reference.source_kind}:${reference.quote}:${reference.artifact_id ?? ''}:${reference.chunk_id ?? ''}:${reference.clarification_id ?? ''}`
      if (seen.has(identity)) {
        return
      }
      seen.add(identity)
      items.push({
        id: identity,
        label: group.label,
        quote: reference.quote,
        source: evidenceSource(reference),
      })
    })
  })
  return items
}

function sanitize(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sanitize)
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !SENSITIVE_KEY.test(key))
        .map(([key, item]) => [key, sanitize(item)]),
    )
  }
  return value
}

export function serializeTaskResults(
  results: TaskResultBundle,
  viewerManifest: ViewerManifest | null,
): string {
  return JSON.stringify(
    sanitize({
      engineering_brief: results.engineeringBrief,
      thermal_analysis: results.thermalAnalysis,
      thermal_design: results.thermalDesign,
      ...(viewerManifest ? { viewer_manifest: viewerManifest } : {}),
    }),
    null,
    2,
  )
}

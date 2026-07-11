import { Info, X } from 'lucide-react'
import type { ViewerManifest } from './viewerManifest'

interface PartDetailSheetProps {
  manifest: ViewerManifest
  part: string | null
  onClose: () => void
}

export function PartDetailSheet({
  manifest,
  part,
  onClose,
}: PartDetailSheetProps) {
  const selectedVariant = manifest.variants?.find((variant) =>
    variant.parts.some((candidate) => candidate.id === part),
  )
  const availableParts = selectedVariant?.parts ?? manifest.parts
  const selectedPart = availableParts.find((candidate) => candidate.id === part)
  if (!selectedPart) {
    return null
  }
  const partIndex = availableParts.indexOf(selectedPart) + 1
  const assetFormat = selectedVariant?.asset.format ?? manifest.asset.format

  return (
    <aside className="part-detail-sheet" aria-label="部件设计说明">
      <div className="part-detail-header">
        <span className="part-index">
          PART {String(partIndex).padStart(2, '0')}
        </span>
        <button type="button" aria-label="关闭部件说明" onClick={onClose}>
          <X aria-hidden="true" />
        </button>
      </div>

      <span className="eyebrow">{assetFormat.toUpperCase()} ASSET</span>
      <h2>{selectedPart.label}</h2>
      <p className="part-lede">{selectedPart.description}</p>

      <dl className="part-metrics">
        {selectedPart.metrics?.map((metric) => (
          <div key={metric.label}>
            <dt>{metric.label}</dt>
            <dd>{metric.value}</dd>
          </div>
        ))}
      </dl>

      <ul className="part-features">
        {selectedPart.tags?.map((feature) => (
          <li key={feature}>{feature}</li>
        ))}
      </ul>

      <p className="engineering-note">
        <Info aria-hidden="true" />
        {manifest.notices[0] ?? '模型信息来自当前任务的 Viewer Manifest。'}
      </p>
    </aside>
  )
}

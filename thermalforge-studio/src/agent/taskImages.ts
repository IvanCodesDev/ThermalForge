import { API_BASE_URL } from '../api'
import type { TaskImageAsset, TaskImageManifest } from '../api'

const VIEW_LABELS: Record<string, string> = {
  mother_three_quarter: '母图三季度视角',
  front: '正视图',
  left: '左视图',
  rear: '后视图',
  top: '俯视图',
  elbow_section: '肘关节剖面图',
}

export interface DisplayTaskImage extends TaskImageAsset {
  label: string
  resolvedUrl: string
}

function resolveImageUrl(url: string): string {
  if (/^[a-z][a-z\d+.-]*:/i.test(url) || !API_BASE_URL) {
    return url
  }
  return new URL(url, `${API_BASE_URL}/`).toString()
}

export function toDisplayTaskImages(
  manifest: TaskImageManifest | null,
): DisplayTaskImage[] {
  return (manifest?.images ?? []).map((image) => ({
    ...image,
    label: VIEW_LABELS[image.view_id] ?? image.view_id,
    resolvedUrl: resolveImageUrl(image.url),
  }))
}

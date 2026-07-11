import { PropertyBinding } from 'three'
import type { ViewerPart } from './viewerManifest'

export function buildPartNodeLookup(
  parts: ViewerPart[],
): Map<string, ViewerPart> {
  const result = new Map<string, ViewerPart>()
  parts.forEach((part) => {
    if (part.binding.kind !== 'node-names' || !part.selectable) {
      return
    }
    part.binding.names.forEach((name) => {
      result.set(name, part)
      result.set(PropertyBinding.sanitizeNodeName(name), part)
    })
  })
  return result
}

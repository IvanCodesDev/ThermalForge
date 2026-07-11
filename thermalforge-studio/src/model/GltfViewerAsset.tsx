import { useGLTF } from '@react-three/drei'
import type { ThreeEvent } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import { Box3, Mesh, Vector3 } from 'three'
import type { Material, Object3D } from 'three'
import { clone } from 'three/examples/jsm/utils/SkeletonUtils.js'
import { buildPartNodeLookup } from './partNodeBindings'
import type { ViewerManifest, ViewerPart } from './viewerManifest'

interface GltfViewerAssetProps {
  manifest: ViewerManifest
  selectedPartId: string | null
  isExploded: boolean
  wireframe: boolean
  onReady: () => void
  onSelectPart: (partId: string | null) => void
}

const TARGET_SIZE = 4.5

export function GltfViewerAsset({
  manifest,
  selectedPartId,
  isExploded,
  wireframe,
  onReady,
  onSelectPart,
}: GltfViewerAssetProps) {
  const gltf = useGLTF(manifest.asset.url)
  const prepared = useMemo(() => {
    const object = clone(gltf.scene)
    const originalPositions = new Map<string, Vector3>()

    object.traverse((child) => {
      originalPositions.set(child.uuid, child.position.clone())
      if (!(child instanceof Mesh)) return
      child.material = Array.isArray(child.material)
        ? child.material.map((material) => material.clone())
        : child.material.clone()
      child.castShadow = true
      child.receiveShadow = true
    })

    object.updateMatrixWorld(true)
    const bounds = new Box3().setFromObject(object)
    const center = bounds.getCenter(new Vector3())
    const size = bounds.getSize(new Vector3())
    const [scaleX, scaleY, scaleZ] = manifest.transform.scale
    const longestSide = Math.max(
      Math.abs(size.x * scaleX),
      Math.abs(size.y * scaleY),
      Math.abs(size.z * scaleZ),
    )

    return {
      center,
      object,
      originalPositions,
      scale: longestSide > 0 ? TARGET_SIZE / longestSide : 1,
    }
  }, [gltf.scene, manifest.transform.scale])

  const wholeAssetPart = manifest.parts.find(
    (part) => part.binding.kind === 'whole-asset' && part.selectable,
  )
  const partsByNodeName = useMemo(
    () => buildPartNodeLookup(manifest.parts),
    [manifest.parts],
  )

  useEffect(() => {
    onReady()
  }, [onReady, prepared])

  useEffect(
    () => () => {
      prepared.object.traverse((child) => {
        if (!(child instanceof Mesh)) return
        const materials = Array.isArray(child.material)
          ? child.material
          : [child.material]
        materials.forEach((material) => material.dispose())
      })
    },
    [prepared],
  )

  useEffect(() => {
    prepared.object.traverse((child) => {
      const original = prepared.originalPositions.get(child.uuid)
      if (!original) return
      const part = partsByNodeName.get(child.name)
      const offset = isExploded ? part?.explode : undefined
      child.position.set(
        original.x + (offset?.[0] ?? 0),
        original.y + (offset?.[1] ?? 0),
        original.z + (offset?.[2] ?? 0),
      )
    })
  }, [isExploded, partsByNodeName, prepared])

  useEffect(() => {
    prepared.object.traverse((child) => {
      if (!(child instanceof Mesh)) return
      const materials: Material[] = Array.isArray(child.material)
        ? child.material
        : [child.material]
      materials.forEach((material) => {
        if ('wireframe' in material) {
          const wireframeMaterial = material as Material & {
            wireframe: boolean
          }
          wireframeMaterial.wireframe = wireframe
          wireframeMaterial.needsUpdate = true
        }
      })
    })
  }, [prepared, wireframe])

  useEffect(
    () => () => {
      document.body.style.cursor = ''
    },
    [],
  )

  const findPartForObject = (object: Object3D): ViewerPart | undefined => {
    let current: Object3D | null = object
    while (current) {
      const part = partsByNodeName.get(current.name)
      if (part) return part
      if (current === prepared.object) break
      current = current.parent
    }
    return wholeAssetPart
  }

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    const part = findPartForObject(event.object)
    if (manifest.capabilities.selection && part) {
      onSelectPart(selectedPartId === part.id ? null : part.id)
    }
  }

  return (
    <group
      position={manifest.transform.translation}
      quaternion={manifest.transform.rotation}
      scale={manifest.transform.scale}
      onClick={handleClick}
      onPointerOver={(event) => {
        event.stopPropagation()
        if (findPartForObject(event.object)) {
          document.body.style.cursor = 'pointer'
        }
      }}
      onPointerOut={() => {
        document.body.style.cursor = ''
      }}
    >
      <group scale={prepared.scale * (selectedPartId ? 1.015 : 1)}>
        <primitive
          object={prepared.object}
          position={prepared.center.clone().multiplyScalar(-1)}
        />
      </group>
    </group>
  )
}

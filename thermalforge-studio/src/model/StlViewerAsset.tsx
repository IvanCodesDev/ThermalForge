import { useLoader } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import { Box3, Vector3 } from 'three'
import type { ThreeEvent } from '@react-three/fiber'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import type { ViewerManifest } from './viewerManifest'

interface StlViewerAssetProps {
  manifest: ViewerManifest
  selectedPartId: string | null
  wireframe: boolean
  onReady: () => void
  onSelectPart: (partId: string | null) => void
}

const TARGET_SIZE = 4.5

export function StlViewerAsset({
  manifest,
  selectedPartId,
  wireframe,
  onReady,
  onSelectPart,
}: StlViewerAssetProps) {
  const sourceGeometry = useLoader(STLLoader, manifest.asset.url)
  const geometry = useMemo(() => {
    const nextGeometry = sourceGeometry.clone()
    nextGeometry.computeBoundingBox()

    const bounds = nextGeometry.boundingBox ?? new Box3()
    const center = bounds.getCenter(new Vector3())
    const size = bounds.getSize(new Vector3())
    const [scaleX, scaleY, scaleZ] = manifest.transform.scale
    const longestSide = Math.max(
      Math.abs(size.x * scaleX),
      Math.abs(size.y * scaleY),
      Math.abs(size.z * scaleZ),
    )
    const scale = longestSide > 0 ? TARGET_SIZE / longestSide : 1

    nextGeometry.translate(-center.x, -center.y, -center.z)
    nextGeometry.scale(scale, scale, scale)
    nextGeometry.computeBoundingBox()
    nextGeometry.computeBoundingSphere()
    return nextGeometry
  }, [manifest.transform.scale, sourceGeometry])

  useEffect(() => {
    onReady()
  }, [onReady])

  useEffect(
    () => () => {
      document.body.style.cursor = ''
    },
    [],
  )

  const wholeAssetPart = manifest.parts.find(
    (part) => part.binding.kind === 'whole-asset' && part.selectable,
  )
  const isSelected = wholeAssetPart?.id === selectedPartId

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    if (manifest.capabilities.selection && wholeAssetPart) {
      onSelectPart(isSelected ? null : wholeAssetPart.id)
    }
  }

  return (
    <group
      position={manifest.transform.translation}
      quaternion={manifest.transform.rotation}
      scale={manifest.transform.scale}
    >
      <mesh
        geometry={geometry}
        castShadow
        receiveShadow
        onClick={handleClick}
        onPointerOver={(event) => {
          event.stopPropagation()
          if (wholeAssetPart) document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = ''
        }}
      >
        <meshStandardMaterial
          wireframe={wireframe}
          color={isSelected ? '#f4b56b' : '#c59658'}
          emissive={isSelected ? '#8c3516' : '#2c160a'}
          emissiveIntensity={isSelected ? 0.48 : 0.12}
          metalness={0.62}
          roughness={0.38}
        />
      </mesh>
    </group>
  )
}

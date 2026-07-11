import { RoundedBox } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { ThreeEvent } from '@react-three/fiber'
import { useRef } from 'react'
import { Group, MathUtils } from 'three'
import type {
  AgentStage,
  AgentStatus,
  ModelPart,
} from '../agent/agentTypes'

interface JointAssemblyProps {
  status: AgentStatus
  stage: AgentStage
  isExploded: boolean
  selectedPart: ModelPart | null
  onToggleExploded: () => void
  onSelectPart: (part: ModelPart | null) => void
}

const FIN_POSITIONS = [-0.72, -0.48, -0.24, 0, 0.24, 0.48, 0.72]

export function JointAssembly({
  status,
  stage,
  isExploded,
  selectedPart,
  onToggleExploded,
  onSelectPart,
}: JointAssemblyProps) {
  const interfaceRef = useRef<Group>(null)
  const shellRef = useRef<Group>(null)
  const canInspect = status === 'ready'
  const shellVisible = !['idle', 'reading', 'briefing'].includes(stage)

  useFrame((_, delta) => {
    if (interfaceRef.current) {
      interfaceRef.current.position.y = MathUtils.damp(
        interfaceRef.current.position.y,
        isExploded ? 0.5 : 0,
        7,
        delta,
      )
    }
    if (shellRef.current) {
      shellRef.current.position.y = MathUtils.damp(
        shellRef.current.position.y,
        isExploded ? 1.15 : 0,
        7,
        delta,
      )
    }
  })

  const handleAssemblyClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    if (canInspect) {
      onToggleExploded()
    }
  }

  const handleShellClick = (event: ThreeEvent<MouseEvent>) => {
    if (!canInspect || !isExploded) {
      return
    }

    event.stopPropagation()
    onSelectPart('thermal-shell')
  }

  return (
    <group
      rotation={[0.08, -0.32, -0.05]}
      onClick={handleAssemblyClick}
      dispose={null}
    >
      <group name="joint-base">
        <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
          <cylinderGeometry args={[1.18, 1.18, 2.4, 64]} />
          <meshStandardMaterial
            color="#454b4e"
            roughness={0.34}
            metalness={0.82}
          />
        </mesh>

        <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.74, 0.74, 2.54, 48]} />
          <meshStandardMaterial
            color="#292e31"
            roughness={0.2}
            metalness={0.92}
          />
        </mesh>

        {[-1.34, 1.34].map((position) => (
          <mesh
            key={position}
            position={[position, 0, 0]}
            rotation={[0, 0, Math.PI / 2]}
            castShadow
          >
            <cylinderGeometry args={[1.02, 1.02, 0.25, 64]} />
            <meshStandardMaterial
              color="#5a6164"
              roughness={0.28}
              metalness={0.88}
            />
          </mesh>
        ))}

        <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.38, 0.38, 3.25, 48]} />
          <meshStandardMaterial
            color="#a3a39c"
            roughness={0.18}
            metalness={0.96}
          />
        </mesh>

        <RoundedBox
          args={[1.75, 0.45, 1.28]}
          radius={0.12}
          smoothness={4}
          position={[0, -1.22, 0]}
          castShadow
        >
          <meshStandardMaterial
            color="#383e41"
            roughness={0.42}
            metalness={0.74}
          />
        </RoundedBox>

        <RoundedBox
          args={[0.8, 0.5, 1.68]}
          radius={0.12}
          smoothness={4}
          position={[0, -1.52, 0]}
          castShadow
        >
          <meshStandardMaterial
            color="#303538"
            roughness={0.48}
            metalness={0.68}
          />
        </RoundedBox>

        {[-0.52, 0.52].map((position) => (
          <mesh
            key={position}
            position={[position, -1.54, 0.64]}
            rotation={[Math.PI / 2, 0, 0]}
          >
            <cylinderGeometry args={[0.09, 0.09, 0.08, 24]} />
            <meshStandardMaterial color="#b2b1aa" metalness={0.9} />
          </mesh>
        ))}
      </group>

      <group ref={interfaceRef} name="thermal-interface">
        <RoundedBox
          args={[1.86, 0.08, 1.4]}
          radius={0.04}
          smoothness={3}
          position={[0, 1.12, 0]}
        >
          <meshStandardMaterial
            color="#c6c0ae"
            emissive="#6c6654"
            emissiveIntensity={0.16}
            roughness={0.58}
            metalness={0.2}
          />
        </RoundedBox>
      </group>

      <group
        ref={shellRef}
        name="thermal-shell"
        visible={shellVisible}
        onClick={handleShellClick}
      >
        <RoundedBox
          args={[2.02, 0.16, 1.52]}
          radius={0.08}
          smoothness={4}
          position={[0, 1.27, 0]}
          castShadow
        >
          <meshStandardMaterial
            color="#ff5500"
            emissive="#b52d06"
            emissiveIntensity={
              selectedPart === 'thermal-shell' ? 0.82 : 0.32
            }
            roughness={0.28}
            metalness={0.72}
          />
        </RoundedBox>

        {FIN_POSITIONS.map((position) => (
          <RoundedBox
            key={position}
            args={[0.09, 0.32, 1.25]}
            radius={0.025}
            smoothness={2}
            position={[position, 1.47, 0]}
            castShadow
          >
            <meshStandardMaterial
              color="#ff6a2d"
              emissive="#8d2206"
              emissiveIntensity={0.24}
              roughness={0.3}
              metalness={0.76}
            />
          </RoundedBox>
        ))}

        {[-0.42, 0, 0.42].map((rotation) => (
          <RoundedBox
            key={rotation}
            args={[0.06, 0.04, 1.05]}
            radius={0.02}
            smoothness={2}
            position={[0, 1.37, 0]}
            rotation={[0, rotation, 0]}
          >
            <meshStandardMaterial
              color="#ffb083"
              emissive="#ff5500"
              emissiveIntensity={0.45}
              roughness={0.32}
              metalness={0.68}
            />
          </RoundedBox>
        ))}
      </group>
    </group>
  )
}

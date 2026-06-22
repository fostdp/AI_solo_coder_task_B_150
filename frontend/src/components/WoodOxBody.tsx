import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Point3D } from '@/types'

interface WoodOxBodyProps {
  bodyInclination: number
  position?: [number, number, number]
  scale?: number
  showCOM?: boolean
  comPosition?: Point3D
}

export function WoodOxBody({
  bodyInclination,
  position = [0, 0, 0],
  scale = 1,
  showCOM = false,
  comPosition,
}: WoodOxBodyProps) {
  const groupRef = useRef<THREE.Group>(null)
  const bodyRef = useRef<THREE.Group>(null)

  const bodyMaterial = useMemo(
    () => new THREE.MeshStandardMaterial({
      color: '#8B4513',
      metalness: 0.1,
      roughness: 0.9,
    }),
    []
  )

  const frameMaterial = useMemo(
    () => new THREE.MeshStandardMaterial({
      color: '#5D3A1A',
      metalness: 0.2,
      roughness: 0.8,
    }),
    []
  )

  useFrame(() => {
    if (groupRef.current) {
      groupRef.current.position.set(...position)
      groupRef.current.scale.setScalar(scale)
    }
    if (bodyRef.current) {
      bodyRef.current.rotation.x = (bodyInclination * Math.PI) / 180
    }
  })

  return (
    <group ref={groupRef}>
      <group ref={bodyRef}>
        <mesh position={[100, 80, 0]}>
          <boxGeometry args={[250, 80, 100]} />
          <meshStandardMaterial {...bodyMaterial} />
        </mesh>

        <mesh position={[-50, 120, 0]}>
          <boxGeometry args={[80, 60, 70]} />
          <meshStandardMaterial {...bodyMaterial} />
        </mesh>

        <mesh position={[-90, 140, 0]}>
          <cylinderGeometry args={[15, 20, 50, 8]} />
          <meshStandardMaterial color="#4A3520" />
        </mesh>

        <mesh position={[-95, 165, -25]}>
          <sphereGeometry args={[8, 16, 16]} />
          <meshStandardMaterial color="#000" />
        </mesh>

        <mesh position={[-95, 165, 25]}>
          <sphereGeometry args={[8, 16, 16]} />
          <meshStandardMaterial color="#000" />
        </mesh>

        <mesh position={[-20, 120, 0]}>
          <coneGeometry args={[10, 30, 8]} />
          <meshStandardMaterial color="#4A3520" />
        </mesh>

        <mesh position={[200, 100, 0]}>
          <cylinderGeometry args={[8, 12, 100, 8]} />
          <meshStandardMaterial color="#5D3A1A" />
        </mesh>

        {[[-25, 40, -40], [-25, 40, 40], [175, 40, -40], [175, 40, 40]].map((pos, i) => (
          <mesh key={i} position={pos as [number, number, number]}>
            <cylinderGeometry args={[6, 6, 80, 8]} />
            <meshStandardMaterial {...frameMaterial} />
          </mesh>
        ))}

        <mesh position={[100, 40, -45]}>
          <cylinderGeometry args={[5, 5, 230, 8]} />
          <meshStandardMaterial {...frameMaterial} />
        </mesh>

        <mesh position={[100, 40, 45]}>
          <cylinderGeometry args={[5, 5, 230, 8]} />
          <meshStandardMaterial {...frameMaterial} />
        </mesh>

        <mesh position={[100, 120, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[10, 10, 260, 16]} />
          <meshStandardMaterial color="#B8860B" metalness={0.6} roughness={0.4} />
        </mesh>

        {showCOM && comPosition && (
          <group position={[comPosition.x, comPosition.y, comPosition.z]}>
            <mesh>
              <sphereGeometry args={[12, 16, 16]} />
              <meshStandardMaterial color="#00FF00" emissive="#00FF00" emissiveIntensity={0.5} transparent opacity={0.8} />
            </mesh>
            <mesh position={[0, 25, 0]}>
              <cylinderGeometry args={[2, 2, 30, 8]} />
              <meshBasicMaterial color="#00FF00" />
            </mesh>
          </group>
        )}
      </group>
    </group>
  )
}

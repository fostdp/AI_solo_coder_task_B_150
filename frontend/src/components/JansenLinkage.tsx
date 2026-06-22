import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Point3D } from '@/types'

interface JansenLinkageProps {
  crankAngle: number
  params: {
    crank_length: number
    rocker_length: number
    coupler_length: number
    ground_link: number
  }
  position?: [number, number, number]
  rotation?: [number, number, number]
  color?: string
  showLabels?: boolean
}

export function JansenLinkage({
  crankAngle,
  params,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
  color = '#8B4513',
  showLabels = false,
}: JansenLinkageProps) {
  const groupRef = useRef<THREE.Group>(null)

  const joints = useMemo(() => {
    const { crank_length: a, rocker_length: b, coupler_length: c, ground_link: d } = params
    const crankRad = (crankAngle * Math.PI) / 180

    const O: Point3D = { x: 0, y: 0, z: 0 }
    const D: Point3D = { x: d, y: 0, z: 0 }
    const B: Point3D = { x: a * Math.cos(crankRad), y: a * Math.sin(crankRad), z: 0 }

    const distBD = Math.sqrt((d - B.x) ** 2 + B.y ** 2)
    const clampedDist = Math.max(Math.abs(b - c), Math.min(b + c, distBD))

    let cosPhi = (b ** 2 + clampedDist ** 2 - c ** 2) / (2 * b * clampedDist)
    cosPhi = Math.max(-1, Math.min(1, cosPhi))
    const phi = Math.acos(cosPhi)

    const angleBD = Math.atan2(-B.y, d - B.x)
    const angleBC = angleBD + phi

    const C: Point3D = {
      x: B.x + b * Math.cos(angleBC),
      y: B.y + b * Math.sin(angleBC),
      z: 0,
    }

    const footOffset = 100
    const dirX = C.x - B.x
    const dirY = C.y - B.y
    const len = Math.sqrt(dirX * dirX + dirY * dirY)
    const E: Point3D = {
      x: C.x + (dirX / len) * footOffset,
      y: C.y + (dirY / len) * footOffset,
      z: 0,
    }

    return { O, B, C, D, E }
  }, [crankAngle, params])

  const linkMaterial = useMemo(
    () => new THREE.MeshStandardMaterial({ color, metalness: 0.3, roughness: 0.7 }),
    [color]
  )

  const jointMaterial = useMemo(
    () => new THREE.MeshStandardMaterial({ color: '#FFD700', metalness: 0.8, roughness: 0.2 }),
    []
  )

  const createLinkGeometry = (start: Point3D, end: Point3D, radius = 8) => {
    const dx = end.x - start.x
    const dy = end.y - start.y
    const length = Math.sqrt(dx * dx + dy * dy)

    const geometry = new THREE.CylinderGeometry(radius, radius, length, 16)
    geometry.translate(0, length / 2, 0)
    geometry.rotateX(Math.PI / 2)

    const angle = Math.atan2(dy, dx)
    const matrix = new THREE.Matrix4()
    matrix.makeRotationZ(angle)
    geometry.applyMatrix4(matrix)
    geometry.translate(start.x, start.y, start.z)

    return geometry
  }

  const jointPositions = Object.entries(joints) as [string, Point3D][]

  useFrame(() => {
    if (groupRef.current) {
      groupRef.current.position.set(...position)
      groupRef.current.rotation.set(...rotation)
    }
  })

  return (
    <group ref={groupRef}>
      <mesh geometry={createLinkGeometry(joints.O, joints.B)} material={linkMaterial} />
      <mesh geometry={createLinkGeometry(joints.B, joints.C)} material={linkMaterial} />
      <mesh geometry={createLinkGeometry(joints.C, joints.D)} material={linkMaterial} />
      <mesh geometry={createLinkGeometry(joints.C, joints.E, 10)} material={linkMaterial} />
      <mesh geometry={createLinkGeometry(joints.O, joints.D, 5)} material={linkMaterial} />

      {jointPositions.map(([name, pos]) => (
        <group key={name} position={[pos.x, pos.y, pos.z]}>
          <mesh geometry={new THREE.SphereGeometry(12, 16, 16)} material={jointMaterial} />
          {showLabels && (
            <sprite position={[0, 20, 0]} scale={[30, 15, 1]}>
              <spriteMaterial color="#000" />
            </sprite>
          )}
        </group>
      ))}

      <mesh position={[joints.E.x, joints.E.y, joints.E.z]}>
        <sphereGeometry args={[15, 16, 16]} />
        <meshStandardMaterial color="#FF4444" metalness={0.5} roughness={0.5} emissive="#FF0000" emissiveIntensity={0.2} />
      </mesh>
    </group>
  )
}

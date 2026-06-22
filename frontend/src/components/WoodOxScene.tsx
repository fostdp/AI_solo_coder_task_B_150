import { useRef, useMemo, useEffect, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Grid, ContactShadows, Environment } from '@react-three/drei'
import * as THREE from 'three'
import { JansenLinkage } from './JansenLinkage'
import { WoodOxBody } from './WoodOxBody'
import type { Point3D } from '@/types'
import { useAppStore } from '@/store/useAppStore'
import { simulationApi } from '@/utils/api'

interface TerrainProps {
  obstacleHeight: number
  obstaclePosition?: number
  showObstacle?: boolean
}

function Terrain({ obstacleHeight, obstaclePosition = 200, showObstacle = true }: TerrainProps) {
  const geometry = useMemo(() => {
    const geo = new THREE.PlaneGeometry(2000, 1000, 100, 50)
    const positions = geo.attributes.position

    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i)
      const y = positions.getY(i)

      let height = Math.sin(x * 0.01) * 5 + Math.sin(y * 0.02) * 3

      if (showObstacle && obstacleHeight > 0) {
        const distToObstacle = Math.abs(x - obstaclePosition)
        if (distToObstacle < 100) {
          const obstacleProfile = obstacleHeight * Math.cos((distToObstacle / 100) * Math.PI / 2)
          height = Math.max(height, obstacleProfile)
        }
      }

      positions.setZ(i, height)
    }

    geo.computeVertexNormals()
    return geo
  }, [obstacleHeight, obstaclePosition, showObstacle])

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow geometry={geometry}>
      <meshStandardMaterial
        color="#8B7355"
        roughness={1}
        metalness={0}
        flatShading
      />
    </mesh>
  )
}

interface FootTrajectoryProps {
  points: Point3D[]
  visible: boolean
}

function FootTrajectory({ points, visible }: FootTrajectoryProps) {
  const lineRef = useRef<THREE.Line>(null)

  const geometry = useMemo(() => {
    if (points.length < 2) return new THREE.BufferGeometry()

    const positions = new Float32Array(points.length * 3)
    points.forEach((p, i) => {
      positions[i * 3] = p.x
      positions[i * 3 + 1] = p.y
      positions[i * 3 + 2] = p.z || 0
    })

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return geo
  }, [points])

  if (!visible || points.length < 2) return null

  return (
    <line ref={lineRef} geometry={geometry}>
      <lineBasicMaterial color="#FF6B6B" linewidth={3} />
    </line>
  )
}

interface SceneContentProps {
  footTrajectory: Point3D[]
}

function SceneContent({ footTrajectory }: SceneContentProps) {
  const {
    crankAngle,
    bodyInclination,
    jansenParams,
    showTrajectory,
    showLinkages,
    obstacleHeight,
    isPlaying,
    simulationSpeed,
    setCrankAngle,
  } = useAppStore()

  const animRef = useRef(0)

  useFrame((_, delta) => {
    if (isPlaying) {
      animRef.current += delta * 30 * simulationSpeed
      const newAngle = (crankAngle + delta * 30 * simulationSpeed) % 360
      setCrankAngle(newAngle)
    }
  })

  const legOffset = 180

  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[500, 500, 300]} intensity={1} castShadow />
      <pointLight position={[-200, 300, 200]} intensity={0.5} color="#FFE4B5" />

      <WoodOxBody
        bodyInclination={bodyInclination}
        position={[100, 0, 0]}
        scale={1}
      />

      {showLinkages && (
        <>
          <JansenLinkage
            crankAngle={crankAngle}
            params={jansenParams}
            position={[-25, 0, -50]}
            rotation={[0, 0, 0]}
            color="#8B4513"
          />

          <JansenLinkage
            crankAngle={(crankAngle + legOffset) % 360}
            params={jansenParams}
            position={[-25, 0, 50]}
            rotation={[0, Math.PI, 0]}
            color="#A0522D"
          />

          <JansenLinkage
            crankAngle={crankAngle}
            params={jansenParams}
            position={[175, 0, -50]}
            rotation={[0, 0, 0]}
            color="#8B4513"
          />

          <JansenLinkage
            crankAngle={(crankAngle + legOffset) % 360}
            params={jansenParams}
            position={[175, 0, 50]}
            rotation={[0, Math.PI, 0]}
            color="#A0522D"
          />
        </>
      )}

      <FootTrajectory points={footTrajectory} visible={showTrajectory} />

      <Terrain obstacleHeight={obstacleHeight} obstaclePosition={400} />

      <Grid
        args={[2000, 2000]}
        position={[0, -5, 0]}
        cellSize={50}
        cellThickness={0.5}
        cellColor="#6B7280"
        sectionSize={200}
        sectionThickness={1}
        sectionColor="#9CA3AF"
        fadeDistance={1000}
        fadeStrength={1}
        followCamera={false}
      />

      <ContactShadows
        position={[0, -4.9, 0]}
        opacity={0.4}
        scale={2000}
        blur={2}
        far={100}
        resolution={512}
      />

      <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={100}
        maxDistance={2000}
        target={[100, 100, 0]}
      />

      <Environment preset="forest" />
    </>
  )
}

export function WoodOxScene() {
  const { jansenParams } = useAppStore()
  const [footTrajectory, setFootTrajectory] = useState<Point3D[]>([])

  useEffect(() => {
    const fetchTrajectory = async () => {
      try {
        const res = await simulationApi.getFootTrajectory(0, 360, 720, {
          crank_length: jansenParams.crank_length,
          rocker_length: jansenParams.rocker_length,
          coupler_length: jansenParams.coupler_length,
          ground_link: jansenParams.ground_link,
        })
        if (res.data?.trajectory) {
          setFootTrajectory(res.data.trajectory)
        }
      } catch (error) {
        const fallback: Point3D[] = []
        for (let i = 0; i <= 360; i++) {
          const rad = (i * Math.PI) / 180
          fallback.push({
            x: 300 * Math.cos(rad) + 150,
            y: 150 * Math.sin(rad),
            z: 0,
          })
        }
        setFootTrajectory(fallback)
      }
    }

    fetchTrajectory()
  }, [jansenParams])

  return (
    <Canvas
      shadows
      camera={{ position: [400, 300, 400], fov: 50 }}
      gl={{ antialias: true }}
    >
      <color attach="background" args={['#E8E4D9']} />
      <fog attach="fog" args={['#E8E4D9', 800, 2000]} />
      <SceneContent footTrajectory={footTrajectory} />
    </Canvas>
  )
}

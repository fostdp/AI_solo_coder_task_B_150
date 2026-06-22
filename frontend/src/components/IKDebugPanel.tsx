import React, { useState, useCallback, useMemo } from 'react'
import { Card, Slider, Button, Space, Table, Tag, Switch, Form, InputNumber, Typography, Divider } from 'antd'
import { PlayCircleOutlined, BugOutlined, ReloadOutlined } from '@ant-design/icons'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { FabrikSolver, IKJoint, Point3D, IKDebugger, IKSolution } from '../utils/ikSolver'

const { Title, Text } = Typography

interface IKDebugPanelProps {
  jansenParams: {
    crankLength: number
    rockerLength: number
    couplerLength: number
    groundLink: number
  }
  onIKSolution?: (solution: IKSolution) => void
}

const IKDebugPanel: React.FC<IKDebugPanelProps> = ({ jansenParams, onIKSolution }) => {
  const [form] = Form.useForm()
  const [targetPosition, setTargetPosition] = useState<Point3D>({ x: 300, y: -200, z: 0 })
  const [basePosition, setBasePosition] = useState<Point3D>({ x: 0, y: 0, z: 0 })
  const [enableDebug, setEnableDebug] = useState(false)
  const [autoSolve, setAutoSolve] = useState(true)
  const [maxIterations, setMaxIterations] = useState(20)
  const [tolerance, setTolerance] = useState(0.1)
  const [solution, setSolution] = useState<IKSolution | null>(null)
  const [debugHistory, setDebugHistory] = useState<any[]>([])
  const [currentIteration, setCurrentIteration] = useState<number>(0)
  const [isAnimating, setIsAnimating] = useState(false)

  const solver = useMemo(() => new FabrikSolver({
    maxIterations,
    tolerance,
    enableJointLimits: true
  }), [maxIterations, tolerance])

  const debugger = useMemo(() => new IKDebugger({
    maxIterations,
    tolerance,
    enableJointLimits: true
  }), [maxIterations, tolerance])

  const handleSolve = useCallback(() => {
    const joints: IKJoint[] = [
      {
        position: { ...basePosition },
        length: jansenParams.crankLength,
        minAngle: -180,
        maxAngle: 180
      },
      {
        position: {
          x: basePosition.x + jansenParams.crankLength,
          y: basePosition.y,
          z: basePosition.z
        },
        length: jansenParams.couplerLength,
        minAngle: -90,
        maxAngle: 90
      },
      {
        position: {
          x: basePosition.x + jansenParams.groundLink,
          y: basePosition.y,
          z: basePosition.z
        },
        length: jansenParams.rockerLength,
        minAngle: -60,
        maxAngle: 60
      },
      {
        position: {
          x: basePosition.x + jansenParams.groundLink + jansenParams.rockerLength,
          y: basePosition.y,
          z: basePosition.z
        },
        length: 0
      }
    ]

    let result: IKSolution & { history: any[] }
    
    if (enableDebug) {
      result = debugger.solveWithDebug({ joints, target: targetPosition, base: basePosition })
      setDebugHistory(result.history)
    } else {
      result = {
        ...solver.solve({ joints, target: targetPosition, base: basePosition }),
        history: []
      }
    }

    setSolution(result)
    setCurrentIteration(result.iterations)
    onIKSolution?.(result)
  }, [solver, debugger, targetPosition, basePosition, jansenParams, enableDebug, onIKSolution])

  const handlePlayAnimation = useCallback(() => {
    if (debugHistory.length === 0) {
      handleSolve()
      return
    }
    
    setIsAnimating(true)
    let i = 0
    const interval = setInterval(() => {
      if (i >= debugHistory.length) {
        clearInterval(interval)
        setIsAnimating(false)
        return
      }
      setCurrentIteration(debugHistory[i].iteration)
      i++
    }, 200)
  }, [debugHistory, handleSolve])

  const columns = [
    {
      title: '关节',
      dataIndex: 'joint',
      key: 'joint',
      render: (_: any, __: any, index: number) => {
        const names = ['曲柄支点', '曲柄销', '连杆销', '摇杆支点', '足端']
        return names[index] || `关节${index}`
      }
    },
    {
      title: 'X (mm)',
      dataIndex: 'x',
      key: 'x',
      render: (x: number) => x.toFixed(2)
    },
    {
      title: 'Y (mm)',
      dataIndex: 'y',
      key: 'y',
      render: (y: number) => y.toFixed(2)
    },
    {
      title: 'Z (mm)',
      dataIndex: 'z',
      key: 'z',
      render: (z: number) => z.toFixed(2)
    },
    {
      title: '角度 (°)',
      dataIndex: 'angle',
      key: 'angle',
      render: (angle: number) => angle.toFixed(1)
    }
  ]

  const historyColumns = [
    {
      title: '迭代',
      dataIndex: 'iteration',
      key: 'iteration'
    },
    {
      title: '误差 (mm)',
      dataIndex: 'distance',
      key: 'distance',
      render: (d: number) => d.toFixed(3)
    },
    {
      title: '收敛',
      key: 'converged',
      render: (_: any, record: any) => (
        <Tag color={record.distance < tolerance ? 'green' : 'orange'}>
          {record.distance < tolerance ? '是' : '否'}
        </Tag>
      )
    }
  ]

  const errorMetrics = enableDebug && debugHistory.length > 0 ? debugger.getErrorMetrics() : null

  React.useEffect(() => {
    if (autoSolve) {
      handleSolve()
    }
  }, [targetPosition, basePosition, jansenParams, autoSolve, handleSolve])

  const tableData = solution ? solution.joints.map((joint, index) => ({
    key: index,
    joint: index,
    x: joint.x,
    y: joint.y,
    z: joint.z,
    angle: solution.angles[index] || 0
  })) : []

  return (
    <Card
      title={
        <Space>
          <BugOutlined />
          <span>IK解算器调试面板</span>
        </Space>
      }
      size="small"
      className="ik-debug-panel"
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space wrap>
          <Space>
            <Text>启用调试:</Text>
            <Switch checked={enableDebug} onChange={setEnableDebug} />
          </Space>
          <Space>
            <Text>自动求解:</Text>
            <Switch checked={autoSolve} onChange={setAutoSolve} />
          </Space>
        </Space>

        <Form form={form} layout="inline" size="small">
          <Form.Item label="目标X">
            <InputNumber
              value={targetPosition.x}
              onChange={(v) => setTargetPosition(p => ({ ...p, x: v || 0 }))}
              step={10}
              style={{ width: 100 }}
            />
          </Form.Item>
          <Form.Item label="目标Y">
            <InputNumber
              value={targetPosition.y}
              onChange={(v) => setTargetPosition(p => ({ ...p, y: v || 0 }))}
              step={10}
              style={{ width: 100 }}
            />
          </Form.Item>
          <Form.Item label="最大迭代">
            <InputNumber
              value={maxIterations}
              onChange={setMaxIterations}
              min={1}
              max={100}
              style={{ width: 80 }}
            />
          </Form.Item>
          <Form.Item label="容差">
            <InputNumber
              value={tolerance}
              onChange={setTolerance}
              step={0.01}
              min={0.01}
              max={10}
              style={{ width: 80 }}
            />
          </Form.Item>
        </Form>

        <Space>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleSolve}
            disabled={isAnimating}
          >
            求解
          </Button>
          {enableDebug && (
            <Button
              icon={<ReloadOutlined />}
              onClick={handlePlayAnimation}
              disabled={isAnimating || debugHistory.length === 0}
            >
              播放迭代过程
            </Button>
          )}
        </Space>

        {solution && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              <Tag color={solution.converged ? 'green' : 'red'}>
                收敛: {solution.converged ? '是' : '否'}
              </Tag>
              <Tag color="blue">
                迭代次数: {solution.iterations}
              </Tag>
              <Tag color="orange">
                最终误差: {solution.distanceToTarget.toFixed(3)} mm
              </Tag>
              {errorMetrics && (
                <Tag color="purple">
                  误差改善: {errorMetrics.improvement.toFixed(1)}%
                </Tag>
              )}
            </div>

            <Divider orientation="left" plain>关节位置</Divider>
            <Table
              size="small"
              dataSource={tableData}
              columns={columns}
              pagination={false}
            />

            {enableDebug && debugHistory.length > 0 && (
              <>
                <Divider orientation="left" plain>收敛过程</Divider>
                <Table
                  size="small"
                  dataSource={debugHistory.map((h, i) => ({ key: i, ...h }))}
                  columns={historyColumns}
                  pagination={{ pageSize: 5 }}
                  scroll={{ y: 150 }}
                />
              </>
            )}
          </Space>
        )}
      </Space>
    </Card>
  )
}

export const IKVisualization: React.FC<{
  solution: IKSolution | null
  targetPosition: Point3D
  basePosition: Point3D
  showDebug?: boolean
}> = ({ solution, targetPosition, basePosition, showDebug = false }) => {
  const lineRef = React.useRef<THREE.Line>(null)

  useFrame(() => {
    if (!solution || !lineRef.current) return

    const points = solution.joints.map(
      j => new THREE.Vector3(j.x / 1000, j.y / 1000, j.z / 1000)
    )

    const geometry = lineRef.current.geometry as THREE.BufferGeometry
    geometry.setFromPoints(points)
    geometry.computeBoundingSphere()
  })

  if (!solution) return null

  return (
    <group>
      <line ref={lineRef}>
        <bufferGeometry />
        <lineBasicMaterial color="#B8860B" linewidth={3} />
      </line>

      {solution.joints.map((joint, index) => (
        <mesh
          key={index}
          position={[joint.x / 1000, joint.y / 1000, joint.z / 1000]}
        >
          <sphereGeometry args={[index === 0 || index === solution.joints.length - 1 ? 0.01 : 0.006]} />
          <meshBasicMaterial
            color={
              index === 0
                ? '#00FF00'
                : index === solution.joints.length - 1
                ? '#FF0000'
                : '#FFD700'
            }
          />
        </mesh>
      ))}

      <mesh position={[targetPosition.x / 1000, targetPosition.y / 1000, targetPosition.z / 1000]}>
        <sphereGeometry args={[0.012]} />
        <meshBasicMaterial color="#00FFFF" wireframe />
      </mesh>

      <mesh position={[basePosition.x / 1000, basePosition.y / 1000, basePosition.z / 1000]}>
        <sphereGeometry args={[0.012]} />
        <meshBasicMaterial color="#FF00FF" wireframe />
      </mesh>

      {showDebug && (
        <line
          points={[
            new THREE.Vector3(
              solution.joints[solution.joints.length - 1].x / 1000,
              solution.joints[solution.joints.length - 1].y / 1000,
              solution.joints[solution.joints.length - 1].z / 1000
            ),
            new THREE.Vector3(targetPosition.x / 1000, targetPosition.y / 1000, targetPosition.z / 1000)
          ]}
        >
          <bufferGeometry />
          <lineBasicMaterial
            color={solution.converged ? '#00FF00' : '#FF0000'}
            dashed
            dashSize={0.02}
            gapSize={0.01}
          />
        </line>
      )}
    </group>
  )
}

export default IKDebugPanel

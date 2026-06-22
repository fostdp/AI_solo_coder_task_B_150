import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Card,
  Row,
  Col,
  Button,
  Statistic,
  Tag,
  Space,
  Progress,
  Slider,
  Alert,
  Tooltip,
} from 'antd'
import {
  CarOutlined,
  ThunderboltOutlined,
  SafetyOutlined,
  WarningOutlined,
  ReloadOutlined,
  StopOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CompassOutlined,
  DashboardOutlined,
  RotateLeftOutlined,
} from '@ant-design/icons'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import type { DrivingState, DrivingControlInput, GamepadState } from '@/types'
import { drivingApi } from '@/utils/api'
import { useAppStore } from '@/store/useAppStore'
import { WoodOxBody } from './WoodOxBody'

const MAX_SPEED = 1.5
const DEADZONE = 0.1

function applyDeadzone(value: number, threshold = DEADZONE): number {
  if (Math.abs(value) < threshold) return 0
  const normalized = (Math.abs(value) - threshold) / (1 - threshold)
  return value >= 0 ? normalized : -normalized
}

function getInclinationColor(inclination: number): string {
  const abs = Math.abs(inclination)
  if (abs <= 5) return '#52c41a'
  if (abs <= 15) return '#faad14'
  return '#ff4d4f'
}

function getStabilityColor(margin: number): string {
  if (margin >= 60) return '#52c41a'
  if (margin >= 30) return '#faad14'
  return '#ff4d4f'
}

function SimpleDrivingScene({ crankAngle, bodyInclination }: { crankAngle: number; bodyInclination: number }) {
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[300, 400, 200]} intensity={0.8} castShadow />
      <WoodOxBody bodyInclination={bodyInclination} position={[0, 0, 0]} scale={0.8} />
      <Grid
        args={[1000, 1000]}
        position={[0, -5, 0]}
        cellSize={50}
        cellThickness={0.5}
        cellColor="#6B7280"
        sectionSize={200}
        sectionThickness={1}
        sectionColor="#9CA3AF"
        fadeDistance={800}
        fadeStrength={1}
        followCamera={false}
      />
      <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={150}
        maxDistance={800}
        target={[0, 80, 0]}
      />
    </>
  )
}

export function VirtualDriving() {
  const {
    drivingState,
    setDrivingState,
    drivingWsConnected,
    setDrivingWsConnected,
    lastControlInput,
    setLastControlInput,
    gamepadState,
    setGamepadState,
    setCrankAngle,
    setBodyInclination,
    selectedDevice,
  } = useAppStore()

  const [accelSlider, setAccelSlider] = useState(0)
  const [steerSlider, setSteerSlider] = useState(0)
  const [brakeSlider, setBrakeSlider] = useState(0)
  const [keyboardState, setKeyboardState] = useState({
    accelerate: false,
    decelerate: false,
    left: false,
    right: false,
    brake: false,
  })
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const [showAlert, setShowAlert] = useState(false)
  const [alertMessage, setAlertMessage] = useState('')

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const lastControlSentRef = useRef(0)

  const showWarning = useCallback((msg: string) => {
    setAlertMessage(msg)
    setShowAlert(true)
    setTimeout(() => setShowAlert(false), 3000)
  }, [])

  const sendControl = useCallback(
    (acceleration: number, steering: number, brake: number) => {
      const now = Date.now()
      if (now - lastControlSentRef.current < 50) return
      lastControlSentRef.current = now

      const input: DrivingControlInput = {
        device_id: selectedDevice,
        acceleration,
        steering,
        brake,
      }

      setLastControlInput(input)

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'control',
            payload: input,
          })
        )
      } else {
        drivingApi.sendControl(input).catch(() => {})
      }
    },
    [selectedDevice, setLastControlInput]
  )

  const handleReset = useCallback(async () => {
    try {
      await drivingApi.reset(selectedDevice)
      setAccelSlider(0)
      setSteerSlider(0)
      setBrakeSlider(0)
      showWarning('驾驶状态已重置')
    } catch {
      showWarning('重置失败，请重试')
    }
  }, [selectedDevice, showWarning])

  const handleEmergencyStop = useCallback(() => {
    sendControl(0, 0, 1)
    setAccelSlider(0)
    setSteerSlider(0)
    setBrakeSlider(1)
    showWarning('紧急制动已触发')
  }, [sendControl, showWarning])

  const connectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/driving/ws/${selectedDevice}`

    try {
      wsRef.current = new WebSocket(wsUrl)

      wsRef.current.onopen = () => {
        console.log('驾驶WebSocket连接已建立')
        setDrivingWsConnected(true)
        setReconnectAttempts(0)
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'state') {
            const state = message.payload as DrivingState
            setDrivingState(state)
            setCrankAngle(state.crank_angle)
            setBodyInclination(state.body_inclination)
          }
        } catch (error) {
          console.error('解析驾驶状态消息失败:', error)
        }
      }

      wsRef.current.onerror = () => {
        setDrivingWsConnected(false)
      }

      wsRef.current.onclose = () => {
        setDrivingWsConnected(false)
        const attempts = reconnectAttempts + 1
        setReconnectAttempts(attempts)
        const delay = Math.min(1000 * Math.pow(1.5, attempts - 1), 30000)

        if (reconnectTimerRef.current === null) {
          reconnectTimerRef.current = window.setTimeout(() => {
            reconnectTimerRef.current = null
            connectWebSocket()
          }, delay)
        }
      }
    } catch (error) {
      console.error('创建驾驶WebSocket连接失败:', error)
      setDrivingWsConnected(false)
    }
  }, [selectedDevice, reconnectAttempts, setDrivingWsConnected, setDrivingState, setCrankAngle, setBodyInclination])

  const toggleConnection = useCallback(() => {
    if (drivingWsConnected) {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      wsRef.current?.close()
      wsRef.current = null
      setDrivingWsConnected(false)
      setReconnectAttempts(0)
    } else {
      connectWebSocket()
    }
  }, [drivingWsConnected, connectWebSocket, setDrivingWsConnected])

  useEffect(() => {
    const handleGamepadConnected = (e: GamepadEvent) => {
      setGamepadState({
        connected: true,
        id: e.gamepad.id,
      })
      showWarning(`游戏手柄已连接: ${e.gamepad.id}`)
    }

    const handleGamepadDisconnected = () => {
      setGamepadState({
        connected: false,
        id: '',
        axisX: 0,
        axisY: 0,
        axisZ: 0,
        axisRz: 0,
        buttonA: false,
        buttonB: false,
        buttonX: false,
        buttonY: false,
        buttonLeft: false,
        buttonRight: false,
        buttonStart: false,
        buttonSelect: false,
      })
      showWarning('游戏手柄已断开')
    }

    window.addEventListener('gamepadconnected', handleGamepadConnected)
    window.addEventListener('gamepaddisconnected', handleGamepadDisconnected)

    return () => {
      window.removeEventListener('gamepadconnected', handleGamepadConnected)
      window.removeEventListener('gamepaddisconnected', handleGamepadDisconnected)
    }
  }, [setGamepadState, showWarning])

  useEffect(() => {
    const prevButtonState = { buttonA: false, buttonB: false, buttonStart: false }

    const pollGamepad = () => {
      const gamepads = navigator.getGamepads()
      const gamepad = gamepads.find((g) => g !== null)

      if (gamepad) {
        const leftStickX = applyDeadzone(gamepad.axes[0] ?? 0)
        const leftStickY = applyDeadzone(gamepad.axes[1] ?? 0)
        const rightTriggerAxis = gamepad.axes[5] ?? 0
        const rightTriggerButton = gamepad.buttons[7]?.value ?? 0
        const brakeValue = Math.max(
          rightTriggerAxis > 0 ? (rightTriggerAxis + 1) / 2 : 0,
          rightTriggerButton
        )

        const buttonA = gamepad.buttons[0]?.pressed ?? false
        const buttonB = gamepad.buttons[1]?.pressed ?? false
        const buttonStart = gamepad.buttons[9]?.pressed ?? false

        setGamepadState({
          connected: true,
          id: gamepad.id,
          axisX: leftStickX,
          axisY: leftStickY,
          axisZ: gamepad.axes[2] ?? 0,
          axisRz: gamepad.axes[3] ?? 0,
          buttonA,
          buttonB,
          buttonX: gamepad.buttons[2]?.pressed ?? false,
          buttonY: gamepad.buttons[3]?.pressed ?? false,
          buttonLeft: gamepad.buttons[4]?.pressed ?? false,
          buttonRight: gamepad.buttons[5]?.pressed ?? false,
          buttonStart,
          buttonSelect: gamepad.buttons[8]?.pressed ?? false,
        })

        const accelInput = -leftStickY
        const steerInput = leftStickX
        sendControl(accelInput, steerInput, brakeValue)

        if (buttonA && !prevButtonState.buttonA) {
          handleReset()
        }
        if (buttonB && !prevButtonState.buttonB) {
          handleEmergencyStop()
        }
        if (buttonStart && !prevButtonState.buttonStart) {
          toggleConnection()
        }

        prevButtonState.buttonA = buttonA
        prevButtonState.buttonB = buttonB
        prevButtonState.buttonStart = buttonStart
      }

      animationFrameRef.current = requestAnimationFrame(pollGamepad)
    }

    animationFrameRef.current = requestAnimationFrame(pollGamepad)

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [setGamepadState, sendControl, handleReset, handleEmergencyStop, toggleConnection])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.repeat) return
      switch (e.key.toLowerCase()) {
        case 'w':
        case 'arrowup':
          setKeyboardState((s) => ({ ...s, accelerate: true }))
          break
        case 's':
        case 'arrowdown':
          setKeyboardState((s) => ({ ...s, decelerate: true }))
          break
        case 'a':
        case 'arrowleft':
          setKeyboardState((s) => ({ ...s, left: true }))
          break
        case 'd':
        case 'arrowright':
          setKeyboardState((s) => ({ ...s, right: true }))
          break
        case ' ':
          e.preventDefault()
          setKeyboardState((s) => ({ ...s, brake: true }))
          break
        case 'r':
          handleReset()
          break
      }
    }

    const handleKeyUp = (e: KeyboardEvent) => {
      switch (e.key.toLowerCase()) {
        case 'w':
        case 'arrowup':
          setKeyboardState((s) => ({ ...s, accelerate: false }))
          break
        case 's':
        case 'arrowdown':
          setKeyboardState((s) => ({ ...s, decelerate: false }))
          break
        case 'a':
        case 'arrowleft':
          setKeyboardState((s) => ({ ...s, left: false }))
          break
        case 'd':
        case 'arrowright':
          setKeyboardState((s) => ({ ...s, right: false }))
          break
        case ' ':
          setKeyboardState((s) => ({ ...s, brake: false }))
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [handleReset])

  useEffect(() => {
    const hasKeyboardInput =
      keyboardState.accelerate ||
      keyboardState.decelerate ||
      keyboardState.left ||
      keyboardState.right ||
      keyboardState.brake

    if (hasKeyboardInput) {
      const accel = keyboardState.accelerate ? 1 : keyboardState.decelerate ? -1 : 0
      const steer = keyboardState.left ? -1 : keyboardState.right ? 1 : 0
      const brake = keyboardState.brake ? 1 : 0
      sendControl(accel, steer, brake)
    }
  }, [keyboardState, sendControl])

  useEffect(() => {
    connectWebSocket()

    return () => {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connectWebSocket])

  const walkingSpeed = drivingState?.walking_speed ?? 0
  const crankAngle = drivingState?.crank_angle ?? 0
  const bodyInclination = drivingState?.body_inclination ?? 0
  const stabilityMargin = drivingState?.stability_margin ?? 0
  const turnRate = drivingState?.turn_rate ?? 0
  const heading = drivingState?.heading ?? 0
  const positionX = drivingState?.position_x ?? 0
  const positionY = drivingState?.position_y ?? 0
  const totalDistance = drivingState?.total_distance ?? 0
  const isMoving = drivingState?.is_moving ?? false
  const isBraking = drivingState?.is_braking ?? false

  const speedPercent = Math.min(100, (Math.abs(walkingSpeed) / MAX_SPEED) * 100)
  const crankPercent = ((crankAngle % 360) + 360) % 360
  const stabilityPercent = Math.min(100, (stabilityMargin / 100) * 100)
  const turnPercent = Math.min(100, Math.abs(turnRate) * 100)
  const displayCrankAngle = ((crankAngle % 360) + 360) % 360

  return (
    <div className="space-y-4">
      {showAlert && (
        <Alert
          message={alertMessage}
          type="warning"
          showIcon
          closable
          onClose={() => setShowAlert(false)}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            title={
              <Space>
                <CarOutlined className="text-amber-600" />
                <span>虚拟驾驶舱</span>
                <Tag color={gamepadState.connected ? 'success' : 'error'}>
                  {gamepadState.connected ? '● 手柄已连接' : '○ 手柄未连接'}
                </Tag>
                <Tag color={drivingWsConnected ? 'success' : 'error'}>
                  {drivingWsConnected ? '● 驾驶连接' : '○ 连接断开'}
                </Tag>
              </Space>
            }
            extra={
              <Space>
                <Tooltip title={drivingWsConnected ? '断开连接' : '连接服务器'}>
                  <Button onClick={toggleConnection} size="small">
                    {drivingWsConnected ? '断开' : '连接'}
                  </Button>
                </Tooltip>
                {reconnectAttempts > 0 && (
                  <Tag color="orange">重连: {reconnectAttempts}</Tag>
                )}
              </Space>
            }
          >
            <div style={{ height: 320 }} className="rounded-lg overflow-hidden bg-amber-50">
              <Canvas
                shadows
                camera={{ position: [300, 250, 300], fov: 50 }}
                gl={{ antialias: true }}
              >
                <color attach="background" args={['#F5F0E6']} />
                <fog attach="fog" args={['#F5F0E6', 400, 1000]} />
                <SimpleDrivingScene
                  crankAngle={crankAngle}
                  bodyInclination={bodyInclination}
                />
              </Canvas>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card size="small">
              <Row gutter={[8, 8]}>
                <Col span={12}>
                  <Statistic
                    title="位置 X"
                    value={positionX}
                    precision={0}
                    suffix="mm"
                    valueStyle={{ fontSize: 16, color: '#1890ff' }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="位置 Y"
                    value={positionY}
                    precision={0}
                    suffix="mm"
                    valueStyle={{ fontSize: 16, color: '#1890ff' }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="总行驶距离"
                    value={totalDistance}
                    precision={2}
                    suffix="m"
                    prefix={<DashboardOutlined />}
                    valueStyle={{ fontSize: 16, color: '#722ed1' }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="状态"
                    value={isBraking ? '制动中' : isMoving ? '行驶中' : '停止'}
                    valueStyle={{
                      fontSize: 16,
                      color: isBraking ? '#ff4d4f' : isMoving ? '#52c41a' : '#8c8c8c',
                    }}
                  />
                </Col>
              </Row>
            </Card>

            <Card title={<span><ThunderboltOutlined className="text-blue-500" /> 行走速度</span>} size="small">
              <Progress
                type="dashboard"
                percent={Math.round(speedPercent)}
                format={() => `${walkingSpeed.toFixed(2)} m/s`}
                strokeColor={{
                  '0%': '#52c41a',
                  '50%': '#1890ff',
                  '100%': '#faad14',
                }}
              />
            </Card>

            <Card title={<span><RotateLeftOutlined className="text-amber-500" /> 曲柄角度</span>} size="small">
              <Progress
                type="dashboard"
                percent={Math.round((crankPercent / 360) * 100)}
                format={() => `${displayCrankAngle.toFixed(1)}°`}
                strokeColor="#d48806"
              />
            </Card>

            <Card title={<span><WarningOutlined className="text-orange-500" /> 机身倾角</span>} size="small">
              <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ textAlign: 'center' }}>
                  <span
                    style={{
                      fontSize: 28,
                      fontWeight: 'bold',
                      color: getInclinationColor(bodyInclination),
                    }}
                  >
                    {bodyInclination >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}{' '}
                    {Math.abs(bodyInclination).toFixed(1)}°
                  </span>
                </div>
                <Progress
                  percent={Math.min(100, (Math.abs(bodyInclination) / 30) * 100)}
                  strokeColor={getInclinationColor(bodyInclination)}
                  showInfo={false}
                />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>±5° 安全</span>
                  <span>±15° 警告</span>
                  <span>±30° 危险</span>
                </div>
              </Space>
            </Card>

            <Card title={<span><SafetyOutlined className="text-green-500" /> 稳定裕度</span>} size="small">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Progress
                  percent={Math.round(stabilityPercent)}
                  strokeColor={getStabilityColor(stabilityMargin)}
                  format={() => `${stabilityMargin.toFixed(0)} mm`}
                />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>0</span>
                  <span>50</span>
                  <span>100mm</span>
                </div>
              </Space>
            </Card>

            <Card title={<span><CompassOutlined className="text-cyan-500" /> 航向与转向</span>} size="small">
              <Row gutter={[8, 8]}>
                <Col span={12}>
                  <div className="text-center">
                    <div
                      style={{
                        width: 60,
                        height: 60,
                        borderRadius: '50%',
                        border: '2px solid #08979c',
                        margin: '0 auto',
                        position: 'relative',
                        backgroundColor: '#e6fffb',
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          top: '50%',
                          left: '50%',
                          width: 2,
                          height: 24,
                          backgroundColor: '#cf1322',
                          transformOrigin: 'bottom center',
                          transform: `translateX(-50%) translateY(-100%) rotate(${heading}deg)`,
                        }}
                      />
                      <div
                        style={{
                          position: 'absolute',
                          top: -6,
                          left: '50%',
                          transform: 'translateX(-50%)',
                          fontSize: 10,
                          color: '#cf1322',
                          fontWeight: 'bold',
                        }}
                      >
                        N
                      </div>
                    </div>
                    <div className="text-sm mt-1 text-gray-600">
                      {heading.toFixed(0)}°
                    </div>
                  </div>
                </Col>
                <Col span={12}>
                  <div className="text-center">
                    <div className="text-xs text-gray-500 mb-1">转向速率</div>
                    <Progress
                      type="dashboard"
                      percent={Math.round(turnPercent)}
                      format={() => `${turnRate.toFixed(2)}`}
                      strokeColor={turnRate > 0 ? '#1890ff' : '#722ed1'}
                      width={60}
                    />
                  </div>
                </Col>
              </Row>
            </Card>
          </Space>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="虚拟控制面板" size="small">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div>
                <div className="flex justify-between mb-1">
                  <span>
                    <ArrowUpOutlined className="text-green-500" /> 加速 /
                    <ArrowDownOutlined className="text-red-500" /> 减速
                  </span>
                  <span className="font-mono">{accelSlider.toFixed(2)}</span>
                </div>
                <Slider
                  min={-1}
                  max={1}
                  step={0.01}
                  value={accelSlider}
                  onChange={(v) => {
                    const val = v as number
                    setAccelSlider(val)
                    sendControl(val, steerSlider, brakeSlider)
                  }}
                  tooltip={{ formatter: (v) => `${v?.toFixed(2)}` }}
                  marks={{ '-1': '-1', 0: '0', 1: '1' }}
                />
              </div>

              <div>
                <div className="flex justify-between mb-1">
                  <span>
                    <ArrowLeftOutlined className="text-blue-500" /> 转向
                    <ArrowRightOutlined className="text-purple-500" />
                  </span>
                  <span className="font-mono">{steerSlider.toFixed(2)}</span>
                </div>
                <Slider
                  min={-1}
                  max={1}
                  step={0.01}
                  value={steerSlider}
                  onChange={(v) => {
                    const val = v as number
                    setSteerSlider(val)
                    sendControl(accelSlider, val, brakeSlider)
                  }}
                  tooltip={{ formatter: (v) => `${v?.toFixed(2)}` }}
                  marks={{ '-1': '左', 0: '中', 1: '右' }}
                />
              </div>

              <div>
                <div className="flex justify-between mb-1">
                  <span>
                    <StopOutlined className="text-red-500" /> 制动
                  </span>
                  <span className="font-mono">{brakeSlider.toFixed(2)}</span>
                </div>
                <Slider
                  min={0}
                  max={1}
                  step={0.01}
                  value={brakeSlider}
                  onChange={(v) => {
                    const val = v as number
                    setBrakeSlider(val)
                    sendControl(accelSlider, steerSlider, val)
                  }}
                  tooltip={{ formatter: (v) => `${v?.toFixed(2)}` }}
                  marks={{ 0: '释放', 0.5: '半刹', 1: '全刹' }}
                />
              </div>

              <Row gutter={[8, 8]}>
                <Col span={12}>
                  <Button
                    danger
                    type="primary"
                    block
                    size="large"
                    icon={<StopOutlined />}
                    onClick={handleEmergencyStop}
                  >
                    紧急制动
                  </Button>
                </Col>
                <Col span={12}>
                  <Button
                    block
                    size="large"
                    icon={<ReloadOutlined />}
                    onClick={handleReset}
                  >
                    重置驾驶
                  </Button>
                </Col>
              </Row>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="控制方式说明" size="small">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Alert
                type="info"
                showIcon
                message="键盘控制"
                description={
                  <div className="space-y-1 text-sm">
                    <div><Tag color="blue">W / ↑</Tag> 加速前进</div>
                    <div><Tag color="blue">S / ↓</Tag> 减速后退</div>
                    <div><Tag color="blue">A / ←</Tag> 向左转向</div>
                    <div><Tag color="blue">D / →</Tag> 向右转向</div>
                    <div><Tag color="red">空格</Tag> 制动</div>
                    <div><Tag color="default">R</Tag> 重置状态</div>
                  </div>
                }
              />

              <Alert
                type="info"
                showIcon
                message="游戏手柄控制"
                description={
                  <div className="space-y-1 text-sm">
                    <div><Tag color="green">左摇杆 Y</Tag> 加速/减速（上推前进）</div>
                    <div><Tag color="green">左摇杆 X</Tag> 左右转向</div>
                    <div><Tag color="green">RT 扳机</Tag> 制动（0~1 线性）</div>
                    <div><Tag color="geekblue">A 键</Tag> 重置驾驶状态</div>
                    <div><Tag color="red">B 键</Tag> 紧急制动</div>
                    <div><Tag color="default">Start 键</Tag> 连接/断开服务器</div>
                  </div>
                }
              />

              {lastControlInput && (
                <Alert
                  type="success"
                  showIcon
                  message="最后控制输入"
                  description={
                    <div className="text-xs font-mono space-y-1">
                      <div>加速度: {lastControlInput.acceleration.toFixed(3)}</div>
                      <div>转向: {lastControlInput.steering.toFixed(3)}</div>
                      <div>制动: {lastControlInput.brake.toFixed(3)}</div>
                    </div>
                  }
                />
              )}

              {gamepadState.connected && (
                <div className="p-3 bg-gray-50 rounded">
                  <div className="text-sm font-medium mb-2">手柄实时状态</div>
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div>X轴: {gamepadState.axisX.toFixed(2)}</div>
                    <div>Y轴: {gamepadState.axisY.toFixed(2)}</div>
                    <div>
                      A: <Tag color={gamepadState.buttonA ? 'green' : 'default'}>{gamepadState.buttonA ? '按' : '松'}</Tag>
                    </div>
                    <div>
                      B: <Tag color={gamepadState.buttonB ? 'red' : 'default'}>{gamepadState.buttonB ? '按' : '松'}</Tag>
                    </div>
                    <div>
                      Start: <Tag color={gamepadState.buttonStart ? 'blue' : 'default'}>{gamepadState.buttonStart ? '按' : '松'}</Tag>
                    </div>
                  </div>
                </div>
              )}
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default VirtualDriving

import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, Row, Col, Statistic, Tag, Button, Select, Slider, Modal, Progress } from 'antd'
import { CarOutlined, SettingOutlined, VibrateOutlined, WarningOutlined } from '@ant-design/icons'
import { drivingApi } from '@/utils/api'
import { useAppStore } from '@/store/useAppStore'
import type { DrivingState, GamepadState } from '@/types'

type ResponseCurveType = 'linear' | 'quadratic' | 'cubic'
type GamepadButtonKey = 'buttonA' | 'buttonB' | 'buttonX' | 'buttonY'
type ActionType = 'accelerate' | 'brake' | 'reset' | 'emergencyStop' | 'boost' | 'horn'

interface GamepadMapping {
  accelerate: GamepadButtonKey | null
  brake: GamepadButtonKey | null
  reset: GamepadButtonKey | null
  emergencyStop: GamepadButtonKey | null
  boost: GamepadButtonKey | null
  horn: GamepadButtonKey | null
}

interface CalibrationData {
  centerX: number
  centerY: number
  centerZ: number
  centerRz: number
  maxX: number
  maxY: number
  maxZ: number
  maxRz: number
  calibrated: boolean
}

const keyMap: Record<string, { axis: 'acceleration' | 'steering' | 'brake'; value: number }> = {
  ArrowUp: { axis: 'acceleration', value: 1 },
  ArrowDown: { axis: 'acceleration', value: -1 },
  ArrowLeft: { axis: 'steering', value: -1 },
  ArrowRight: { axis: 'steering', value: 1 },
  Space: { axis: 'brake', value: 1 },
}

export function VirtualDriving() {
  const { selectedDevice, jansenParams, drivingState, setDrivingState, drivingWsConnected, setDrivingWsConnected, lastControlInput, setLastControlInput, gamepadState, setGamepadState } = useAppStore()
  const wsRef = useRef<WebSocket | null>(null)
  const keysRef = useRef<Set<string>>(new Set())
  const prevButtonRef = useRef<{ reset: boolean; emergencyStop: boolean }>({ reset: false, emergencyStop: false })
  const [controlMode, setControlMode] = useState<'keyboard' | 'gamepad' | 'touch'>('keyboard')
  const [showSettings, setShowSettings] = useState(false)
  const [deadzone, setDeadzone] = useState(0.1)
  const [responseCurve, setResponseCurve] = useState<ResponseCurveType>('quadratic')
  const [sensitivity, setSensitivity] = useState(1.0)
  const [gamepadMapping, setGamepadMapping] = useState<GamepadMapping>({
    accelerate: null,
    brake: 'buttonA',
    reset: 'buttonB',
    emergencyStop: null,
    boost: 'buttonX',
    horn: 'buttonY',
  })
  const [calibration, setCalibration] = useState<CalibrationData>({
    centerX: 0,
    centerY: 0,
    centerZ: 0,
    centerRz: 0,
    maxX: 1,
    maxY: 1,
    maxZ: 1,
    maxRz: 1,
    calibrated: false,
  })
  const [calibrating, setCalibrating] = useState(false)
  const [hapticBrake, setHapticBrake] = useState(false)
  const [hapticStabilityWarning, setHapticStabilityWarning] = useState(false)

  const applyDeadzone = useCallback((value: number, threshold: number): number => {
    if (Math.abs(value) < threshold) return 0
    const sign = value > 0 ? 1 : -1
    return sign * ((Math.abs(value) - threshold) / (1 - threshold))
  }, [])

  const applyResponseCurve = useCallback((value: number, curve: ResponseCurveType): number => {
    const sign = value > 0 ? 1 : -1
    const abs = Math.abs(value)
    switch (curve) {
      case 'quadratic':
        return sign * abs * abs
      case 'cubic':
        return sign * abs * abs * abs
      case 'linear':
      default:
        return value
    }
  }, [])

  const applySensitivity = useCallback((value: number, sens: number): number => {
    const result = value * sens
    return Math.max(-1, Math.min(1, result))
  }, [])

  const processAxis = useCallback((rawValue: number): number => {
    const deadzoned = applyDeadzone(rawValue, deadzone)
    const curved = applyResponseCurve(deadzoned, responseCurve)
    const scaled = applySensitivity(curved, sensitivity)
    return scaled
  }, [deadzone, responseCurve, sensitivity, applyDeadzone, applyResponseCurve, applySensitivity])

  const getMappedButton = useCallback((action: ActionType): boolean => {
    if (!gamepadState) return false
    const buttonKey = gamepadMapping[action]
    if (!buttonKey) return false
    return gamepadState[buttonKey] ?? false
  }, [gamepadState, gamepadMapping])

  const calibrateCenter = useCallback(() => {
    if (!gamepadState) return
    setCalibration(prev => ({
      ...prev,
      centerX: gamepadState.axisX,
      centerY: gamepadState.axisY,
      centerZ: gamepadState.axisZ,
      centerRz: gamepadState.axisRz,
      calibrated: true,
    }))
  }, [gamepadState])

  const startCalibration = useCallback(() => {
    setCalibrating(true)
    setCalibration({
      centerX: 0,
      centerY: 0,
      centerZ: 0,
      centerRz: 0,
      maxX: 0,
      maxY: 0,
      maxZ: 0,
      maxRz: 0,
      calibrated: false,
    })
  }, [])

  const finishCalibration = useCallback(() => {
    setCalibrating(false)
  }, [])

  const resetCalibration = useCallback(() => {
    setCalibration({
      centerX: 0,
      centerY: 0,
      centerZ: 0,
      centerRz: 0,
      maxX: 1,
      maxY: 1,
      maxZ: 1,
      maxRz: 1,
      calibrated: false,
    })
    setCalibrating(false)
  }, [])

  const buttonOptions = [
    { value: 'buttonA', label: '按钮 A (0)' },
    { value: 'buttonB', label: '按钮 B (1)' },
    { value: 'buttonX', label: '按钮 X (2)' },
    { value: 'buttonY', label: '按钮 Y (3)' },
  ]

  const sendControl = useCallback(async (control: { acceleration: number; steering: number; brake: number }) => {
    try {
      await drivingApi.sendControl({
        device_id: selectedDevice,
        ...control,
      })
      setLastControlInput(control)
    } catch (error) {
      console.error('发送控制指令失败:', error)
    }
  }, [selectedDevice, setLastControlInput])

  const pollState = useCallback(async () => {
    try {
      const res = await drivingApi.getState(selectedDevice)
      setDrivingState(res.data as DrivingState)
    } catch (error) {
      console.error('获取驾驶状态失败:', error)
    }
  }, [selectedDevice, setDrivingState])

  useEffect(() => {
    const interval = setInterval(pollState, 200)
    return () => clearInterval(interval)
  }, [pollState])

  useEffect(() => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/api/driving/ws/${selectedDevice}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.onopen = () => setDrivingWsConnected(true)
    ws.onclose = () => setDrivingWsConnected(false)
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setDrivingState(data as DrivingState)
      } catch { /* ignore parse errors */ }
    }
    return () => { ws.close(); wsRef.current = null }
  }, [selectedDevice, setDrivingWsConnected, setDrivingState])

  useEffect(() => {
    const pollGamepad = () => {
      const gamepads = navigator.getGamepads()
      if (gamepads[0]) {
        const gp = gamepads[0]
        const state: GamepadState = {
          connected: true,
          id: gp.id,
          axisX: gp.axes[0] ?? 0,
          axisY: gp.axes[1] ?? 0,
          axisZ: gp.axes[2] ?? 0,
          axisRz: gp.axes[3] ?? 0,
          buttonA: gp.buttons[0]?.pressed ?? false,
          buttonB: gp.buttons[1]?.pressed ?? false,
          buttonX: gp.buttons[2]?.pressed ?? false,
          buttonY: gp.buttons[3]?.pressed ?? false,
          buttonLeft: gp.buttons[14]?.pressed ?? false,
          buttonRight: gp.buttons[15]?.pressed ?? false,
          buttonStart: gp.buttons[9]?.pressed ?? false,
          buttonSelect: gp.buttons[8]?.pressed ?? false,
        }
        setGamepadState(state)

        if (calibrating) {
          setCalibration(prev => ({
            ...prev,
            maxX: Math.max(prev.maxX, Math.abs(state.axisX)),
            maxY: Math.max(prev.maxY, Math.abs(state.axisY)),
            maxZ: Math.max(prev.maxZ, Math.abs(state.axisZ)),
            maxRz: Math.max(prev.maxRz, Math.abs(state.axisRz)),
          }))
        }
      }
      requestAnimationFrame(pollGamepad)
    }
    const rafId = requestAnimationFrame(pollGamepad)
    return () => cancelAnimationFrame(rafId)
  }, [setGamepadState, calibrating])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (keyMap[e.code]) {
        e.preventDefault()
        keysRef.current.add(e.code)
      }
    }
    const handleKeyUp = (e: KeyboardEvent) => {
      keysRef.current.delete(e.code)
    }
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [])

  useEffect(() => {
    if (controlMode !== 'keyboard') return
    const interval = setInterval(() => {
      let acceleration = 0
      let steering = 0
      let brake = 0
      keysRef.current.forEach((key) => {
        const mapping = keyMap[key]
        if (mapping) {
          if (mapping.axis === 'acceleration') acceleration += mapping.value
          if (mapping.axis === 'steering') steering += mapping.value
          if (mapping.axis === 'brake') brake += mapping.value
        }
      })
      acceleration = Math.max(-1, Math.min(1, acceleration))
      steering = Math.max(-1, Math.min(1, steering))
      brake = Math.max(0, Math.min(1, brake))
      sendControl({ acceleration, steering, brake })
    }, 100)
    return () => clearInterval(interval)
  }, [controlMode, sendControl])

  useEffect(() => {
    if (controlMode !== 'gamepad' || !gamepadState) return
    const interval = setInterval(() => {
      if (!gamepadState) return

      let axisX = gamepadState.axisX
      let axisY = gamepadState.axisY

      if (calibration.calibrated) {
        axisX = (axisX - calibration.centerX) / (calibration.maxX || 1)
        axisY = (axisY - calibration.centerY) / (calibration.maxY || 1)
        axisX = Math.max(-1, Math.min(1, axisX))
        axisY = Math.max(-1, Math.min(1, axisY))
      }

      const steering = processAxis(axisX)
      const acceleration = processAxis(-axisY)

      const brakePressed = getMappedButton('brake')
      const brake = brakePressed ? 1 : 0

      const acceleratePressed = getMappedButton('accelerate')
      const finalAcceleration = acceleratePressed ? Math.max(acceleration, 1) : acceleration

      sendControl({ acceleration: finalAcceleration, steering, brake })

      if (brake > 0.7) {
        setHapticBrake(true)
      } else {
        setHapticBrake(false)
      }
    }, 100)
    return () => clearInterval(interval)
  }, [controlMode, gamepadState, sendControl, processAxis, getMappedButton, calibration])

  useEffect(() => {
    if (!gamepadState) return
    const resetPressed = getMappedButton('reset')
    const emergencyStopPressed = getMappedButton('emergencyStop')

    if (resetPressed && !prevButtonRef.current.reset) {
      handleReset()
    }
    if (emergencyStopPressed && !prevButtonRef.current.emergencyStop) {
      sendControl({ acceleration: 0, steering: 0, brake: 1 })
    }

    prevButtonRef.current = {
      reset: resetPressed,
      emergencyStop: emergencyStopPressed,
    }
  }, [gamepadState, getMappedButton, handleReset, sendControl])

  useEffect(() => {
    if (drivingState && drivingState.stability_margin < 0.2) {
      setHapticStabilityWarning(true)
    } else {
      setHapticStabilityWarning(false)
    }
  }, [drivingState])

  const handleReset = async () => {
    try {
      await drivingApi.reset(selectedDevice)
      pollState()
    } catch (error) {
      console.error('重置驾驶状态失败:', error)
    }
  }

  const handleTouchControl = (acceleration: number, steering: number, brake: number) => {
    sendControl({ acceleration, steering, brake })
  }

  return (
    <div className="space-y-4">
      <Card title={<span><CarOutlined className="mr-2" />虚拟驾驶体验</span>}>
        <Row gutter={16} align="middle" className="mb-4">
          <Col>
            <span className="mr-2">控制模式:</span>
            <Select value={controlMode} onChange={setControlMode} style={{ width: 140 }} options={[
              { value: 'keyboard', label: '键盘控制' },
              { value: 'gamepad', label: '手柄控制' },
              { value: 'touch', label: '触屏控制' },
            ]} />
          </Col>
          <Col>
            <Tag color={drivingWsConnected ? 'green' : 'red'}>{drivingWsConnected ? 'WS已连接' : 'WS断开'}</Tag>
          </Col>
          <Col>
            <Button onClick={handleReset}>重置</Button>
          </Col>
          <Col>
            <Button icon={<SettingOutlined />} onClick={() => setShowSettings(true)}>手柄设置</Button>
          </Col>
          {hapticBrake && (
            <Col>
              <Tag color="orange" icon={<VibrateOutlined />}>制动振动</Tag>
            </Col>
          )}
          {hapticStabilityWarning && (
            <Col>
              <Tag color="red" icon={<WarningOutlined />}>稳定警告</Tag>
            </Col>
          )}
        </Row>

        <Row gutter={16}>
          <Col span={6}><Statistic title="曲柄转速" value={drivingState?.crank_speed ?? 0} suffix="°/s" /></Col>
          <Col span={6}><Statistic title="行走速度" value={drivingState?.walking_speed ?? 0} suffix="mm/s" /></Col>
          <Col span={6}><Statistic title="航向角" value={drivingState?.heading ?? 0} suffix="°" /></Col>
          <Col span={6}><Statistic title="稳定裕度" value={drivingState?.stability_margin ?? 0} /></Col>
        </Row>

        <Row gutter={16} className="mt-4">
          <Col span={6}><Statistic title="机身倾角" value={drivingState?.body_inclination ?? 0} suffix="°" /></Col>
          <Col span={6}><Statistic title="转向率" value={drivingState?.turn_rate ?? 0} suffix="°/s" /></Col>
          <Col span={6}><Statistic title="总距离" value={drivingState?.total_distance ?? 0} suffix="mm" /></Col>
          <Col span={6}>
            <Tag color={drivingState?.is_moving ? 'blue' : 'default'}>{drivingState?.is_moving ? '运动中' : '静止'}</Tag>
            <Tag color={drivingState?.is_braking ? 'red' : 'default'}>{drivingState?.is_braking ? '制动中' : ''}</Tag>
          </Col>
        </Row>
      </Card>

      {controlMode === 'touch' && (
        <Card title="触屏控制">
          <Row gutter={16} justify="center">
            <Col><Button size="large" onMouseDown={() => handleTouchControl(1, 0, 0)} onMouseUp={() => handleTouchControl(0, 0, 0)}>前进</Button></Col>
            <Col><Button size="large" onMouseDown={() => handleTouchControl(-1, 0, 0)} onMouseUp={() => handleTouchControl(0, 0, 0)}>后退</Button></Col>
            <Col><Button size="large" onMouseDown={() => handleTouchControl(0, -1, 0)} onMouseUp={() => handleTouchControl(0, 0, 0)}>左转</Button></Col>
            <Col><Button size="large" onMouseDown={() => handleTouchControl(0, 1, 0)} onMouseUp={() => handleTouchControl(0, 0, 0)}>右转</Button></Col>
            <Col><Button size="large" danger onMouseDown={() => handleTouchControl(0, 0, 1)} onMouseUp={() => handleTouchControl(0, 0, 0)}>制动</Button></Col>
          </Row>
        </Card>
      )}

      {controlMode === 'keyboard' && (
        <Card title="键盘操作说明">
          <p>↑ 加速 | ↓ 减速 | ← 左转 | → 右转 | 空格 制动</p>
        </Card>
      )}

      {controlMode === 'gamepad' && (
        <Card title="手柄状态" extra={<Button size="small" icon={<SettingOutlined />} onClick={() => setShowSettings(true)}>设置</Button>}>
          {gamepadState ? (
            <div className="space-y-4">
              <Row gutter={16}>
                <Col span={8}><Statistic title="左摇杆 X (原始)" value={gamepadState.axisX} precision={2} /></Col>
                <Col span={8}><Statistic title="左摇杆 Y (原始)" value={gamepadState.axisY} precision={2} /></Col>
                <Col span={8}><Tag color={gamepadState.connected ? 'green' : 'red'}>{gamepadState.connected ? '已连接' : '未连接'}</Tag></Col>
              </Row>
              <Row gutter={16} className="mt-2">
                <Col span={12}>
                  <div className="mb-1 text-sm text-gray-500">转向输出 (处理后)</div>
                  <Progress percent={Math.abs(processAxis(gamepadState.axisX)) * 100} status="normal" showInfo={false} />
                  <div className="text-xs text-gray-400 mt-1">{processAxis(gamepadState.axisX).toFixed(3)}</div>
                </Col>
                <Col span={12}>
                  <div className="mb-1 text-sm text-gray-500">加速输出 (处理后)</div>
                  <Progress percent={Math.abs(processAxis(-gamepadState.axisY)) * 100} status="normal" showInfo={false} />
                  <div className="text-xs text-gray-400 mt-1">{processAxis(-gamepadState.axisY).toFixed(3)}</div>
                </Col>
              </Row>
              <Row gutter={16} className="mt-2">
                <Col span={6}>
                  <Tag color={gamepadState.buttonA ? 'green' : 'default'}>A {gamepadMapping.brake === 'buttonA' ? '(制动)' : gamepadMapping.reset === 'buttonA' ? '(重置)' : ''}</Tag>
                </Col>
                <Col span={6}>
                  <Tag color={gamepadState.buttonB ? 'green' : 'default'}>B {gamepadMapping.reset === 'buttonB' ? '(重置)' : gamepadMapping.emergencyStop === 'buttonB' ? '(急停)' : ''}</Tag>
                </Col>
                <Col span={6}>
                  <Tag color={gamepadState.buttonX ? 'green' : 'default'}>X {gamepadMapping.boost === 'buttonX' ? '(加速)' : ''}</Tag>
                </Col>
                <Col span={6}>
                  <Tag color={gamepadState.buttonY ? 'green' : 'default'}>Y {gamepadMapping.horn === 'buttonY' ? '(喇叭)' : ''}</Tag>
                </Col>
              </Row>
              <Row gutter={16} className="mt-2">
                <Col span={12}>
                  <span className="text-sm text-gray-500">死区: </span>
                  <Tag color="blue">{deadzone}</Tag>
                </Col>
                <Col span={12}>
                  <span className="text-sm text-gray-500">响应曲线: </span>
                  <Tag color="purple">{responseCurve === 'linear' ? '线性' : responseCurve === 'quadratic' ? '二次方' : '三次方'}</Tag>
                </Col>
              </Row>
            </div>
          ) : (
            <p>未检测到手柄，请连接手柄设备</p>
          )}
        </Card>
      )}

      <Modal
        title="手柄设置"
        open={showSettings}
        onCancel={() => setShowSettings(false)}
        footer={[
          <Button key="close" onClick={() => setShowSettings(false)}>关闭</Button>,
        ]}
        width={600}
      >
        <div className="space-y-6">
          <div>
            <h4 className="font-semibold mb-2">死区设置</h4>
            <p className="text-sm text-gray-500 mb-2">死区阈值: {deadzone.toFixed(2)}</p>
            <Slider
              min={0}
              max={0.5}
              step={0.01}
              value={deadzone}
              onChange={setDeadzone}
            />
          </div>

          <div>
            <h4 className="font-semibold mb-2">响应曲线</h4>
            <Select
              value={responseCurve}
              onChange={(val) => setResponseCurve(val as ResponseCurveType)}
              style={{ width: '100%' }}
              options={[
                { value: 'linear', label: '线性' },
                { value: 'quadratic', label: '二次方 (默认)' },
                { value: 'cubic', label: '三次方' },
              ]}
            />
            <p className="text-xs text-gray-400 mt-1">
              二次方和三次方曲线在中心位置更精确，适合精细控制
            </p>
          </div>

          <div>
            <h4 className="font-semibold mb-2">灵敏度</h4>
            <p className="text-sm text-gray-500 mb-2">灵敏度系数: {sensitivity.toFixed(1)}</p>
            <Slider
              min={0.2}
              max={2.0}
              step={0.1}
              value={sensitivity}
              onChange={setSensitivity}
            />
          </div>

          <div>
            <h4 className="font-semibold mb-3">按钮映射</h4>
            <Row gutter={16} className="space-y-2">
              <Col span={12}>
                <label className="text-sm block mb-1">重置按钮</label>
                <Select
                  value={gamepadMapping.reset}
                  onChange={(val) => setGamepadMapping(prev => ({ ...prev, reset: val as GamepadButtonKey | null }))}
                  style={{ width: '100%' }}
                  allowClear
                  options={buttonOptions}
                />
              </Col>
              <Col span={12}>
                <label className="text-sm block mb-1">紧急停止</label>
                <Select
                  value={gamepadMapping.emergencyStop}
                  onChange={(val) => setGamepadMapping(prev => ({ ...prev, emergencyStop: val as GamepadButtonKey | null }))}
                  style={{ width: '100%' }}
                  allowClear
                  options={buttonOptions}
                />
              </Col>
              <Col span={12}>
                <label className="text-sm block mb-1">制动按钮</label>
                <Select
                  value={gamepadMapping.brake}
                  onChange={(val) => setGamepadMapping(prev => ({ ...prev, brake: val as GamepadButtonKey | null }))}
                  style={{ width: '100%' }}
                  allowClear
                  options={buttonOptions}
                />
              </Col>
              <Col span={12}>
                <label className="text-sm block mb-1">加速按钮</label>
                <Select
                  value={gamepadMapping.accelerate}
                  onChange={(val) => setGamepadMapping(prev => ({ ...prev, accelerate: val as GamepadButtonKey | null }))}
                  style={{ width: '100%' }}
                  allowClear
                  options={buttonOptions}
                />
              </Col>
              <Col span={12}>
                <label className="text-sm block mb-1">加速(Boost)</label>
                <Select
                  value={gamepadMapping.boost}
                  onChange={(val) => setGamepadMapping(prev => ({ ...prev, boost: val as GamepadButtonKey | null }))}
                  style={{ width: '100%' }}
                  allowClear
                  options={buttonOptions}
                />
              </Col>
              <Col span={12}>
                <label className="text-sm block mb-1">喇叭</label>
                <Select
                  value={gamepadMapping.horn}
                  onChange={(val) => setGamepadMapping(prev => ({ ...prev, horn: val as GamepadButtonKey | null }))}
                  style={{ width: '100%' }}
                  allowClear
                  options={buttonOptions}
                />
              </Col>
            </Row>
          </div>

          <div>
            <h4 className="font-semibold mb-2">摇杆校准</h4>
            <p className="text-sm text-gray-500 mb-2">
              {calibration.calibrated ? '已校准' : calibrating ? '校准中...' : '未校准'}
            </p>
            <Row gutter={8}>
              <Col><Button size="small" onClick={calibrateCenter} disabled={!gamepadState}>校准中心</Button></Col>
              <Col><Button size="small" onClick={startCalibration} disabled={!gamepadState || calibrating}>开始最大偏转检测</Button></Col>
              <Col><Button size="small" onClick={finishCalibration} disabled={!calibrating}>完成</Button></Col>
              <Col><Button size="small" danger onClick={resetCalibration}>重置校准</Button></Col>
            </Row>
            {calibrating && (
              <div className="mt-2 text-xs text-gray-400">
                请将摇杆推向各个方向的最大位置...
                <br />
                当前最大: X={calibration.maxX.toFixed(2)}, Y={calibration.maxY.toFixed(2)}
              </div>
            )}
          </div>

          <div>
            <h4 className="font-semibold mb-2">输入测试</h4>
            {gamepadState ? (
              <div className="space-y-2">
                <Row gutter={16}>
                  <Col span={12}>
                    <div className="text-sm">X轴 (原始): {gamepadState.axisX.toFixed(3)}</div>
                    <div className="text-sm text-green-600">X轴 (处理后): {processAxis(gamepadState.axisX).toFixed(3)}</div>
                  </Col>
                  <Col span={12}>
                    <div className="text-sm">Y轴 (原始): {gamepadState.axisY.toFixed(3)}</div>
                    <div className="text-sm text-green-600">Y轴 (处理后): {processAxis(gamepadState.axisY).toFixed(3)}</div>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={6}><Tag color={gamepadState.buttonA ? 'green' : 'default'}>A</Tag></Col>
                  <Col span={6}><Tag color={gamepadState.buttonB ? 'green' : 'default'}>B</Tag></Col>
                  <Col span={6}><Tag color={gamepadState.buttonX ? 'green' : 'default'}>X</Tag></Col>
                  <Col span={6}><Tag color={gamepadState.buttonY ? 'green' : 'default'}>Y</Tag></Col>
                </Row>
              </div>
            ) : (
              <p className="text-sm text-gray-400">未连接手柄</p>
            )}
          </div>

          <div>
            <h4 className="font-semibold mb-2">振动反馈提示</h4>
            <div className="text-sm text-gray-500 space-y-1">
              <p><VibrateOutlined className="mr-1 text-orange-500" />重制动时显示制动振动提示</p>
              <p><WarningOutlined className="mr-1 text-red-500" />稳定裕度过低时显示警告提示</p>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}

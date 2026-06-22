import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, Row, Col, Statistic, Tag, Button, Select } from 'antd'
import { CarOutlined } from '@ant-design/icons'
import { drivingApi } from '@/utils/api'
import { useAppStore } from '@/store/useAppStore'
import type { DrivingState, GamepadState } from '@/types'

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
  const [controlMode, setControlMode] = useState<'keyboard' | 'gamepad' | 'touch'>('keyboard')

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
      }
      requestAnimationFrame(pollGamepad)
    }
    const rafId = requestAnimationFrame(pollGamepad)
    return () => cancelAnimationFrame(rafId)
  }, [setGamepadState])

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
      sendControl({
        acceleration: -gamepadState.axisY,
        steering: gamepadState.axisX,
        brake: gamepadState.buttonA ? 1 : 0,
      })
    }, 100)
    return () => clearInterval(interval)
  }, [controlMode, gamepadState, sendControl])

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
        <Card title="手柄状态">
          {gamepadState ? (
            <Row gutter={16}>
              <Col span={8}><Statistic title="左摇杆 X" value={gamepadState.axisX} precision={2} /></Col>
              <Col span={8}><Statistic title="左摇杆 Y" value={gamepadState.axisY} precision={2} /></Col>
              <Col span={8}><Tag color={gamepadState.connected ? 'green' : 'red'}>{gamepadState.connected ? '已连接' : '未连接'} - {gamepadState.id}</Tag></Col>
            </Row>
          ) : (
            <p>未检测到手柄，请连接手柄设备</p>
          )}
        </Card>
      )}
    </div>
  )
}

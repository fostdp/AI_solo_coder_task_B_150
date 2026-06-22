import { Card, Slider, Switch, Button, Space, Row, Col, InputNumber, Divider } from 'antd'
import { PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, SettingOutlined } from '@ant-design/icons'
import { useAppStore } from '@/store/useAppStore'
import { simulationApi, analysisApi } from '@/utils/api'
import { useState } from 'react'

export function ControlPanel() {
  const {
    crankAngle,
    setCrankAngle,
    bodyInclination,
    setBodyInclination,
    isPlaying,
    setIsPlaying,
    showTrajectory,
    setShowTrajectory,
    showLinkages,
    setShowLinkages,
    obstacleHeight,
    setObstacleHeight,
    simulationSpeed,
    setSimulationSpeed,
    jansenParams,
    setJansenParams,
  } = useAppStore()

  const [loading, setLoading] = useState(false)

  const handleComputeGait = async () => {
    try {
      setLoading(true)
      await simulationApi.computeGait('woodox_001', jansenParams, crankAngle, bodyInclination)
    } catch (error) {
      console.error('步态计算失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAssessObstacle = async () => {
    try {
      setLoading(true)
      await analysisApi.simulateObstacle(obstacleHeight, 200, 30, bodyInclination, jansenParams)
    } catch (error) {
      console.error('越障评估失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setCrankAngle(0)
    setBodyInclination(0)
    setIsPlaying(false)
    setObstacleHeight(0)
    setJansenParams({
      crank_length: 150,
      rocker_length: 250,
      coupler_length: 300,
      ground_link: 200,
      crank_speed: 30,
      body_mass: 50,
      leg_mass: 10,
    })
  }

  return (
    <div className="space-y-4">
      <Card title="动画控制" size="small">
        <Space className="mb-4">
          <Button
            type={isPlaying ? 'default' : 'primary'}
            icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => setIsPlaying(!isPlaying)}
          >
            {isPlaying ? '暂停' : '播放'}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </Space>

        <div className="mb-4">
          <div className="flex justify-between mb-1">
            <span>曲柄转角</span>
            <span>{crankAngle.toFixed(1)}°</span>
          </div>
          <Slider
            min={0}
            max={360}
            step={0.1}
            value={crankAngle}
            onChange={(v) => setCrankAngle(v as number)}
            disabled={isPlaying}
          />
        </div>

        <div className="mb-4">
          <div className="flex justify-between mb-1">
            <span>机身倾角</span>
            <span>{bodyInclination.toFixed(1)}°</span>
          </div>
          <Slider
            min={-30}
            max={30}
            step={0.1}
            value={bodyInclination}
            onChange={(v) => setBodyInclination(v as number)}
          />
        </div>

        <div className="mb-4">
          <div className="flex justify-between mb-1">
            <span>仿真速度</span>
            <span>{simulationSpeed.toFixed(1)}x</span>
          </div>
          <Slider
            min={0.1}
            max={5}
            step={0.1}
            value={simulationSpeed}
            onChange={(v) => setSimulationSpeed(v as number)}
          />
        </div>
      </Card>

      <Card title="显示选项" size="small">
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span>显示足端轨迹</span>
            <Switch checked={showTrajectory} onChange={setShowTrajectory} />
          </div>
          <div className="flex justify-between items-center">
            <span>显示连杆机构</span>
            <Switch checked={showLinkages} onChange={setShowLinkages} />
          </div>
        </div>
      </Card>

      <Card title="越障设置" size="small">
        <div className="mb-4">
          <div className="flex justify-between mb-1">
            <span>障碍高度</span>
            <span>{obstacleHeight.toFixed(0)} mm</span>
          </div>
          <Slider
            min={0}
            max={200}
            step={1}
            value={obstacleHeight}
            onChange={(v) => setObstacleHeight(v as number)}
          />
        </div>
        <Button type="primary" block onClick={handleAssessObstacle} loading={loading}>
          评估越障能力
        </Button>
      </Card>

      <Card title={<span><SettingOutlined /> Jansen连杆参数</span>} size="small">
        <Row gutter={[8, 8]}>
          <Col span={12}>
            <div className="text-sm mb-1">曲柄长度 (mm)</div>
            <InputNumber
              min={50}
              max={300}
              value={jansenParams.crank_length}
              onChange={(v) => setJansenParams({ crank_length: v ?? 150 })}
              style={{ width: '100%' }}
              size="small"
            />
          </Col>
          <Col span={12}>
            <div className="text-sm mb-1">摇杆长度 (mm)</div>
            <InputNumber
              min={100}
              max={500}
              value={jansenParams.rocker_length}
              onChange={(v) => setJansenParams({ rocker_length: v ?? 250 })}
              style={{ width: '100%' }}
              size="small"
            />
          </Col>
          <Col span={12}>
            <div className="text-sm mb-1">连杆长度 (mm)</div>
            <InputNumber
              min={150}
              max={600}
              value={jansenParams.coupler_length}
              onChange={(v) => setJansenParams({ coupler_length: v ?? 300 })}
              style={{ width: '100%' }}
              size="small"
            />
          </Col>
          <Col span={12}>
            <div className="text-sm mb-1">机架长度 (mm)</div>
            <InputNumber
              min={100}
              max={400}
              value={jansenParams.ground_link}
              onChange={(v) => setJansenParams({ ground_link: v ?? 200 })}
              style={{ width: '100%' }}
              size="small"
            />
          </Col>
        </Row>
        <Divider className="my-3" />
        <Button type="primary" block onClick={handleComputeGait} loading={loading}>
          计算步态参数
        </Button>
      </Card>
    </div>
  )
}

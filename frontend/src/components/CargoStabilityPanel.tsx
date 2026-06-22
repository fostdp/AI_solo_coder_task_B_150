import { useEffect, useRef, useState, useCallback } from 'react'
import {
  Card, Row, Col, Slider, Button, Statistic, Tag, Tabs, Space, Alert, Tooltip, Spin, Empty
} from 'antd'
import {
  SafetyOutlined, WarningOutlined, ThunderboltOutlined, ExperimentOutlined,
  ReloadOutlined, AimOutlined
} from '@ant-design/icons'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip,
  ResponsiveContainer, Legend, ComposedChart, Bar
} from 'recharts'
import { useAppStore } from '@/store/useAppStore'
import { cargoApi } from '@/utils/api'
import type {
  CargoStabilityGridResult, CargoStabilityPoint, CargoHeightPoint, CargoMassPoint
} from '@/types'

function getMarginColor(avg_margin: number): string {
  if (avg_margin < 10) return '#ff4d4f'
  if (avg_margin < 30) return '#faad14'
  return '#52c41a'
}

function getMarginLabel(avg_margin: number): string {
  if (avg_margin < 10) return '危险'
  if (avg_margin < 30) return '警告'
  return '安全'
}

export function CargoStabilityPanel() {
  const {
    cargoGridResult, setCargoGridResult,
    cargoPayloadMass, setCargoPayloadMass,
    cargoPosition, setCargoPosition,
    jansenParams
  } = useAppStore()

  const [bodyInclination, setBodyInclination] = useState<number>(0)
  const [gridResolution, setGridResolution] = useState<number>(15)
  const [loadingGrid, setLoadingGrid] = useState<boolean>(false)
  const [loadingHeight, setLoadingHeight] = useState<boolean>(false)
  const [loadingMass, setLoadingMass] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [heightData, setHeightData] = useState<CargoHeightPoint[]>([])
  const [massData, setMassData] = useState<CargoMassPoint[]>([])

  const canvasRef = useRef<HTMLCanvasElement>(null)

  const drawHeatmap = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !cargoGridResult || cargoGridResult.grid.length === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height
    const padding = 50

    ctx.clearRect(0, 0, width, height)

    const grid = cargoGridResult.grid
    const xs = grid.map(g => g.x)
    const zs = grid.map(g => g.z)
    const xMin = Math.min(...xs)
    const xMax = Math.max(...xs)
    const zMin = Math.min(...zs)
    const zMax = Math.max(...zs)

    const plotWidth = width - padding * 2
    const plotHeight = height - padding * 2

    const res = Math.sqrt(grid.length)
    const cellWidth = plotWidth / res
    const cellHeight = plotHeight / res

    const toCanvasX = (x: number) => padding + ((x - xMin) / (xMax - xMin)) * plotWidth
    const toCanvasZ = (z: number) => padding + (1 - (z - zMin) / (zMax - zMin)) * plotHeight

    for (let i = 0; i < res; i++) {
      for (let j = 0; j < res; j++) {
        const idx = i * res + j
        if (idx >= grid.length) continue
        const point = grid[idx]
        const color = getMarginColor(point.avg_margin)

        const cx = padding + i * cellWidth
        const cz = padding + j * cellHeight
        ctx.fillStyle = color
        ctx.fillRect(cx, cz, cellWidth + 1, cellHeight + 1)
      }
    }

    ctx.strokeStyle = 'rgba(255,255,255,0.8)'
    ctx.lineWidth = 2
    ctx.beginPath()
    cargoGridResult.safe_zone_boundary.forEach((p, idx) => {
      const cx = toCanvasX(p.x)
      const cz = toCanvasZ(p.z)
      if (idx === 0) ctx.moveTo(cx, cz)
      else ctx.lineTo(cx, cz)
    })
    ctx.stroke()

    ctx.fillStyle = '#ffffff'
    cargoGridResult.safe_zone_boundary.forEach(p => {
      const cx = toCanvasX(p.x)
      const cz = toCanvasZ(p.z)
      ctx.beginPath()
      ctx.arc(cx, cz, 2, 0, Math.PI * 2)
      ctx.fill()
    })

    cargoGridResult.dangerous_zones.forEach(p => {
      const cx = toCanvasX(p.x)
      const cz = toCanvasZ(p.z)
      ctx.strokeStyle = '#000000'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(cx - 6, cz - 6)
      ctx.lineTo(cx + 6, cz + 6)
      ctx.moveTo(cx + 6, cz - 6)
      ctx.lineTo(cx - 6, cz + 6)
      ctx.stroke()
    })

    const optX = toCanvasX(cargoGridResult.optimal_position.x)
    const optZ = toCanvasZ(cargoGridResult.optimal_position.z)

    ctx.save()
    ctx.translate(optX, optZ)
    ctx.fillStyle = '#1890ff'
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 2
    const spikes = 5
    const outerR = 14
    const innerR = 6
    ctx.beginPath()
    for (let i = 0; i < spikes * 2; i++) {
      const r = i % 2 === 0 ? outerR : innerR
      const angle = (i * Math.PI) / spikes - Math.PI / 2
      const px = Math.cos(angle) * r
      const py = Math.sin(angle) * r
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    }
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
    ctx.restore()

    ctx.fillStyle = '#333'
    ctx.font = '12px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('X (mm)', width / 2, height - 15)

    ctx.save()
    ctx.translate(15, height / 2)
    ctx.rotate(-Math.PI / 2)
    ctx.fillText('Z (mm)', 0, 0)
    ctx.restore()

    ctx.textAlign = 'right'
    ctx.fillStyle = '#52c41a'
    ctx.fillText('> 30mm 安全', width - 10, 20)
    ctx.fillStyle = '#faad14'
    ctx.fillText('10-30mm 警告', width - 10, 38)
    ctx.fillStyle = '#ff4d4f'
    ctx.fillText('< 10mm 危险', width - 10, 56)
  }, [cargoGridResult])

  const handleAnalyzeGrid = async () => {
    try {
      setLoadingGrid(true)
      setError(null)
      const res = await cargoApi.getStabilityGrid({
        parameters: jansenParams,
        payload_mass: cargoPayloadMass,
        x_min: -400,
        x_max: 400,
        z_min: -150,
        z_max: 150,
        grid_resolution: gridResolution,
        body_inclination: bodyInclination,
      })
      setCargoGridResult(res.data as CargoStabilityGridResult)
      setCargoPosition((res.data as CargoStabilityGridResult).optimal_position)
    } catch (err: any) {
      setError(err?.response?.data?.detail || '热力图分析失败')
    } finally {
      setLoadingGrid(false)
    }
  }

  const handleAnalyzeHeight = async () => {
    try {
      setLoadingHeight(true)
      setError(null)
      const res = await cargoApi.getHeightEffect({
        parameters: jansenParams,
        payload_mass: cargoPayloadMass,
        cargo_x: cargoPosition.x,
        cargo_z: cargoPosition.z,
        height_min: 100,
        height_max: 800,
        num_steps: 15,
      })
      setHeightData(res.data.height_analysis as CargoHeightPoint[])
    } catch (err: any) {
      setError(err?.response?.data?.detail || '高度影响分析失败')
    } finally {
      setLoadingHeight(false)
    }
  }

  const handleAnalyzeMass = async () => {
    try {
      setLoadingMass(true)
      setError(null)
      const res = await cargoApi.getMassEffect({
        parameters: jansenParams,
        cargo_x: cargoPosition.x,
        cargo_z: cargoPosition.z,
        mass_min: 0,
        mass_max: 500,
        num_steps: 15,
        body_inclination: bodyInclination,
      })
      setMassData(res.data.mass_analysis as CargoMassPoint[])
    } catch (err: any) {
      setError(err?.response?.data?.detail || '质量影响分析失败')
    } finally {
      setLoadingMass(false)
    }
  }

  useEffect(() => {
    const fetchDefault = async () => {
      try {
        setLoadingGrid(true)
        const res = await cargoApi.getStabilityGrid({
          parameters: jansenParams,
          payload_mass: 150,
          x_min: -400,
          x_max: 400,
          z_min: -150,
          z_max: 150,
          grid_resolution: 15,
          body_inclination: 0,
        })
        setCargoGridResult(res.data as CargoStabilityGridResult)
        setCargoPosition((res.data as CargoStabilityGridResult).optimal_position)
      } catch (err: any) {
        setError(err?.response?.data?.detail || '初始化数据加载失败')
      } finally {
        setLoadingGrid(false)
      }
    }
    fetchDefault()
  }, [jansenParams, setCargoGridResult, setCargoPosition])

  useEffect(() => {
    drawHeatmap()
  }, [drawHeatmap])

  const stats = (() => {
    if (!cargoGridResult || cargoGridResult.grid.length === 0) return null
    const margins = cargoGridResult.grid.map(g => g.avg_margin)
    const minMargins = cargoGridResult.grid.map(g => g.min_margin)
    return {
      minMargin: Math.min(...minMargins),
      avgMargin: margins.reduce((a, b) => a + b, 0) / margins.length,
      dangerousCount: cargoGridResult.dangerous_zones.length,
    }
  })()

  const heightChartData = heightData.map(d => ({
    height: d.height,
    min_margin: Number(d.min_margin.toFixed(2)),
    avg_margin: Number(d.avg_margin.toFixed(2)),
    tipping_risk: Number(d.tipping_risk.toFixed(3)),
  }))

  const massChartData = massData.map(d => ({
    mass: d.mass,
    min_margin: Number(d.min_margin.toFixed(2)),
    max_safe_inclination: Number(d.max_safe_inclination.toFixed(2)),
    tipping_risk: Number(d.tipping_risk.toFixed(3)),
  }))

  const tabItems = [
    {
      key: '1',
      label: (
        <span className="flex items-center gap-1">
          <ExperimentOutlined /> 位置热力图
        </span>
      ),
      children: (
        <div className="space-y-4">
          {error && (
            <Alert
              type="error"
              message={error}
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}
          <Card title="分析参数" size="small">
            <Row gutter={[16, 16]}>
              <Col xs={24} md={8}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>载重质量</span>
                  <span className="font-mono">{cargoPayloadMass} kg</span>
                </div>
                <Slider
                  min={0}
                  max={500}
                  step={10}
                  value={cargoPayloadMass}
                  onChange={(v) => setCargoPayloadMass(v as number)}
                />
              </Col>
              <Col xs={24} md={8}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>机身倾角</span>
                  <span className="font-mono">{bodyInclination}°</span>
                </div>
                <Slider
                  min={0}
                  max={30}
                  step={1}
                  value={bodyInclination}
                  onChange={(v) => setBodyInclination(v as number)}
                />
              </Col>
              <Col xs={24} md={8}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>网格分辨率</span>
                  <span className="font-mono">{gridResolution} × {gridResolution}</span>
                </div>
                <Slider
                  min={5}
                  max={25}
                  step={2}
                  value={gridResolution}
                  onChange={(v) => setGridResolution(v as number)}
                />
              </Col>
            </Row>
            <div className="mt-4">
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={handleAnalyzeGrid}
                loading={loadingGrid}
              >
                分析稳定性热力图
              </Button>
            </div>
          </Card>

          <Card title="位置稳定性热力图" size="small">
            <Spin spinning={loadingGrid}>
              {cargoGridResult && cargoGridResult.grid.length > 0 ? (
                <div className="flex justify-center">
                  <canvas
                    ref={canvasRef}
                    width={600}
                    height={400}
                    style={{ maxWidth: '100%', height: 'auto', border: '1px solid #eee' }}
                  />
                </div>
              ) : (
                <Empty description="暂无数据，请点击分析按钮" />
              )}
            </Spin>
          </Card>

          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} lg={6}>
              <Card loading={loadingGrid || !stats}>
                <Statistic
                  title="最优位置坐标"
                  valueStyle={{ color: '#1890ff' }}
                  prefix={<AimOutlined />}
                  value={cargoGridResult ? `(${cargoGridResult.optimal_position.x.toFixed(0)}, ${cargoGridResult.optimal_position.z.toFixed(0)})` : '—'}
                  suffix="mm"
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card loading={loadingGrid || !stats}>
                <Statistic
                  title="最小稳定裕度"
                  value={stats?.minMargin ?? 0}
                  precision={1}
                  suffix="mm"
                  prefix={<WarningOutlined />}
                  valueStyle={{
                    color: (stats?.minMargin ?? 0) < 10 ? '#ff4d4f' : (stats?.minMargin ?? 0) < 30 ? '#faad14' : '#52c41a'
                  }}
                />
                <div className="mt-2">
                  <Tag color={getMarginColor(stats?.minMargin ?? 0)}>
                    {getMarginLabel(stats?.minMargin ?? 0)}
                  </Tag>
                </div>
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card loading={loadingGrid || !stats}>
                <Statistic
                  title="平均稳定裕度"
                  value={stats?.avgMargin ?? 0}
                  precision={1}
                  suffix="mm"
                  prefix={<SafetyOutlined />}
                  valueStyle={{
                    color: (stats?.avgMargin ?? 0) < 10 ? '#ff4d4f' : (stats?.avgMargin ?? 0) < 30 ? '#faad14' : '#52c41a'
                  }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card loading={loadingGrid || !stats}>
                <Statistic
                  title="危险区域数量"
                  value={stats?.dangerousCount ?? 0}
                  prefix={<ThunderboltOutlined />}
                  valueStyle={{ color: (stats?.dangerousCount ?? 0) > 0 ? '#ff4d4f' : '#52c41a' }}
                />
                <div className="mt-2">
                  <Tag color={(stats?.dangerousCount ?? 0) > 0 ? 'red' : 'green'}>
                    {(stats?.dangerousCount ?? 0) > 0 ? '存在风险' : '全部安全'}
                  </Tag>
                </div>
              </Card>
            </Col>
          </Row>
        </div>
      ),
    },
    {
      key: '2',
      label: (
        <span className="flex items-center gap-1">
          <SafetyOutlined /> 高度影响
        </span>
      ),
      children: (
        <div className="space-y-4">
          {error && (
            <Alert
              type="error"
              message={error}
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}
          <Card
            title="高度影响分析"
            size="small"
            extra={
              <Space>
                <Tag color="blue">载重: {cargoPayloadMass}kg</Tag>
                <Tag color="purple">位置: ({cargoPosition.x.toFixed(0)}, {cargoPosition.z.toFixed(0)})mm</Tag>
                <Button
                  type="primary"
                  icon={<ReloadOutlined />}
                  onClick={handleAnalyzeHeight}
                  loading={loadingHeight}
                >
                  分析高度影响
                </Button>
              </Space>
            }
          >
            <Spin spinning={loadingHeight}>
              {heightData.length > 0 ? (
                <div style={{ width: '100%', height: 380 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={heightChartData} margin={{ top: 20, right: 60, left: 20, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="height"
                        label={{ value: '货箱高度 (mm)', position: 'insideBottom', offset: -10 }}
                      />
                      <YAxis
                        yAxisId="left"
                        label={{ value: '稳定裕度 (mm)', angle: -90, position: 'insideLeft' }}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        domain={[0, 1]}
                        label={{ value: '倾翻风险', angle: 90, position: 'insideRight' }}
                      />
                      <ReTooltip
                        formatter={(value: any, name: string) => {
                          if (name === 'tipping_risk') return [Number(value).toFixed(3), '倾翻风险']
                          if (name === 'min_margin') return [Number(value).toFixed(2) + ' mm', '最小裕度']
                          if (name === 'avg_margin') return [Number(value).toFixed(2) + ' mm', '平均裕度']
                          return [value, name]
                        }}
                        labelFormatter={(label) => `高度: ${label} mm`}
                      />
                      <Legend />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="min_margin"
                        name="最小裕度"
                        stroke="#ff4d4f"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 5 }}
                      />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="avg_margin"
                        name="平均裕度"
                        stroke="#52c41a"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 5 }}
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="tipping_risk"
                        name="倾翻风险"
                        stroke="#722ed1"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        dot={{ r: 3 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Empty description="点击分析按钮查看货箱高度对稳定性的影响" />
              )}
            </Spin>
          </Card>
        </div>
      ),
    },
    {
      key: '3',
      label: (
        <span className="flex items-center gap-1">
          <WarningOutlined /> 质量影响
        </span>
      ),
      children: (
        <div className="space-y-4">
          {error && (
            <Alert
              type="error"
              message={error}
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}
          <Card
            title="质量影响分析"
            size="small"
            extra={
              <Space>
                <Tag color="purple">位置: ({cargoPosition.x.toFixed(0)}, {cargoPosition.z.toFixed(0)})mm</Tag>
                <Tag color="orange">倾角: {bodyInclination}°</Tag>
                <Button
                  type="primary"
                  icon={<ReloadOutlined />}
                  onClick={handleAnalyzeMass}
                  loading={loadingMass}
                >
                  分析质量影响
                </Button>
              </Space>
            }
          >
            <Spin spinning={loadingMass}>
              {massData.length > 0 ? (
                <div style={{ width: '100%', height: 380 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={massChartData} margin={{ top: 20, right: 60, left: 20, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="mass"
                        label={{ value: '载重质量 (kg)', position: 'insideBottom', offset: -10 }}
                      />
                      <YAxis
                        yAxisId="left"
                        label={{ value: '稳定裕度 / 倾角', angle: -90, position: 'insideLeft' }}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        domain={[0, 1]}
                        label={{ value: '倾翻风险', angle: 90, position: 'insideRight' }}
                      />
                      <ReTooltip
                        formatter={(value: any, name: string) => {
                          if (name === 'tipping_risk') return [Number(value).toFixed(3), '倾翻风险']
                          if (name === 'min_margin') return [Number(value).toFixed(2) + ' mm', '最小裕度']
                          if (name === 'max_safe_inclination') return [Number(value).toFixed(2) + '°', '最大安全倾角']
                          return [value, name]
                        }}
                        labelFormatter={(label) => `载重: ${label} kg`}
                      />
                      <Legend />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="min_margin"
                        name="最小裕度"
                        stroke="#ff4d4f"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 5 }}
                      />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="max_safe_inclination"
                        name="最大安全倾角"
                        stroke="#1890ff"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 5 }}
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="tipping_risk"
                        name="倾翻风险"
                        stroke="#722ed1"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        dot={{ r: 3 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Empty description="点击分析按钮查看载重质量对稳定性的影响" />
              )}
            </Spin>
          </Card>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <Card title="货箱装载稳定性分析" size="small">
        <Tabs defaultActiveKey="1" items={tabItems} />
      </Card>
    </div>
  )
}

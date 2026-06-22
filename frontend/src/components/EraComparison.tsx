import { useEffect, useState, useMemo } from 'react'
import {
  Card,
  Row,
  Col,
  Table,
  Statistic,
  Tag,
  Tabs,
  Timeline,
  Progress,
  Space,
  Spin,
  Alert,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts'
import { useAppStore } from '@/store/useAppStore'
import { comparisonApi } from '@/utils/api'
import type {
  EraMetrics,
  EraRadarAxis,
  EraTimelineEvent,
  EraComparisonResult,
  EraKey,
} from '@/types'

const ERA_COLORS: Record<EraKey, string> = {
  WoodenOx: '#E74C3C',
  Spot: '#3498DB',
  Cheetah: '#2ECC71',
  ANYmal: '#F39C12',
}

const ERA_LABELS: Record<EraKey, string> = {
  WoodenOx: '木牛流马',
  Spot: 'Spot',
  Cheetah: 'Cheetah',
  ANYmal: 'ANYmal',
}

const METRIC_LABELS: Record<keyof EraMetrics, { label: string; unit?: string }> = {
  mechanical_complexity: { label: '机械复杂度' },
  max_obstacle_height: { label: '最大越障高度', unit: 'mm' },
  max_slope_angle: { label: '最大爬坡角度', unit: '°' },
  speed: { label: '行走速度', unit: 'm/s' },
  payload_ratio: { label: '载重比' },
  autonomy_hours: { label: '续航时间', unit: 'h' },
  terrain_types_supported: { label: '支持地形种类' },
  noise_level_db: { label: '噪音水平', unit: 'dB' },
  cost_estimate_relative: { label: '成本估算(相对)' },
  control_method: { label: '控制方式' },
  power_source: { label: '动力来源' },
  sensing_capability: { label: '感知能力' },
  self_recovery: { label: '自恢复能力' },
  historical_significance: { label: '历史意义' },
  innovation_index: { label: '创新指数' },
}

const BAR_METRIC_KEYS = [
  'mechanical_complexity',
  'max_obstacle_height',
  'max_slope_angle',
  'speed',
] as const

const ERA_KEYS: EraKey[] = ['WoodenOx', 'Spot', 'Cheetah', 'ANYmal']

interface MechanismDetail {
  name: string
  era: string
  linkage_type: string
  actuation: string
  control: string
  gait_generation: string
  energy_efficiency: string
  adaptability: string
  key_innovation: string
  computed_stride_length_mm?: number
  computed_foot_clearance_mm?: number
  computed_support_phase_pct?: number
}

export function EraComparison() {
  const { jansenParams } = useAppStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [allMetrics, setAllMetrics] = useState<EraComparisonResult | null>(null)
  const [radarData, setRadarData] = useState<Record<EraKey, EraRadarAxis[]> | null>(null)
  const [timelineEvents, setTimelineEvents] = useState<EraTimelineEvent[]>([])
  const [mechanismData, setMechanismData] = useState<Record<EraKey, MechanismDetail> | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const [metricsRes, radarRes, timelineRes, mechanismRes] = await Promise.all([
          comparisonApi.getEraAllMetrics(jansenParams),
          comparisonApi.getEraRadar(jansenParams),
          comparisonApi.getEraTimeline(),
          comparisonApi.getEraMechanism(jansenParams),
        ])
        setAllMetrics(metricsRes.data)
        setRadarData(radarRes.data)
        setTimelineEvents(timelineRes.data.events)
        setMechanismData(mechanismRes.data)
      } catch (err) {
        console.error('获取跨时代对比数据失败:', err)
        setError('获取跨时代对比数据失败，请稍后重试')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [jansenParams])

  const radarChartData = useMemo(() => {
    if (!radarData) return []
    const axes = radarData.WoodenOx?.map((r) => r.axis) || []
    return axes.map((axis) => {
      const row: Record<string, string | number> = { axis }
      ERA_KEYS.forEach((era) => {
        const found = radarData[era]?.find((r) => r.axis === axis)
        if (found) {
          row[ERA_LABELS[era]] = Math.round(found.normalized * 100)
        }
      })
      return row
    })
  }, [radarData])

  const barChartData = useMemo(() => {
    if (!allMetrics) return []
    return BAR_METRIC_KEYS.map((key) => {
      const row: Record<string, string | number> = {
        metric: METRIC_LABELS[key].label,
      }
      ERA_KEYS.forEach((era) => {
        const val = allMetrics[era]?.[key]
        if (typeof val === 'number') {
          row[ERA_LABELS[era]] = val
        }
      })
      return row
    })
  }, [allMetrics])

  const tableColumns: ColumnsType<{ metric: string; key: string } & Record<EraKey, string | number | boolean>> = [
    {
      title: '指标',
      dataIndex: 'metric',
      key: 'metric',
      width: 160,
      fixed: 'left',
      render: (text) => <strong>{text}</strong>,
    },
    ...ERA_KEYS.map((era) => ({
      title: (
        <Space>
          <Tag color={ERA_COLORS[era]}>{ERA_LABELS[era]}</Tag>
        </Space>
      ),
      dataIndex: era,
      key: era,
      render: (value: string | number | boolean, record: { key: string }) => {
        if (typeof value === 'boolean') {
          return value ? <Tag color="success">支持</Tag> : <Tag color="default">不支持</Tag>
        }
        if (record.key === 'control_method' || record.key === 'power_source') {
          return <span>{value as string}</span>
        }
        const unit = METRIC_LABELS[record.key as keyof EraMetrics]?.unit
        return typeof value === 'number'
          ? `${value.toFixed(2)}${unit ? ` ${unit}` : ''}`
          : String(value)
      },
    })),
  ]

  const tableData = useMemo(() => {
    if (!allMetrics) return []
    const metricKeys = Object.keys(METRIC_LABELS) as Array<keyof EraMetrics>
    return metricKeys.map((key) => {
      const row: { metric: string; key: string } & Record<EraKey, string | number | boolean> = {
        metric: METRIC_LABELS[key].label,
        key: key as string,
        WoodenOx: allMetrics.WoodenOx?.[key] ?? '-',
        Spot: allMetrics.Spot?.[key] ?? '-',
        Cheetah: allMetrics.Cheetah?.[key] ?? '-',
        ANYmal: allMetrics.ANYmal?.[key] ?? '-',
      }
      return row
    })
  }, [allMetrics])

  const lineChartData = useMemo(() => {
    return timelineEvents.map((evt) => ({
      year: evt.year,
      event: evt.event,
      innovation: ERA_KEYS.reduce((acc, era) => {
        if (allMetrics?.[era]) {
          acc[ERA_LABELS[era]] = allMetrics[era].innovation_index
        }
        return acc
      }, {} as Record<string, number>),
    }))
  }, [timelineEvents, allMetrics])

  const renderMetricsTab = () => (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        {ERA_KEYS.map((era) => (
          <Col xs={12} sm={6} key={era}>
            <Card>
              <Statistic
                title={
                  <Space>
                    <Tag color={ERA_COLORS[era]}>{ERA_LABELS[era]}</Tag>
                  </Space>
                }
                value={allMetrics?.[era]?.innovation_index ?? 0}
                precision={1}
                suffix="/ 10"
                valueStyle={{ color: ERA_COLORS[era] }}
              />
              <div className="mt-2 text-xs text-gray-500">
                创新指数
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Card title="综合能力雷达图">
        <ResponsiveContainer width="100%" height={400}>
          <RadarChart data={radarChartData}>
            <PolarGrid />
            <PolarAngleAxis dataKey="axis" />
            <PolarRadiusAxis angle={30} domain={[0, 100]} />
            {ERA_KEYS.map((era) => (
              <Radar
                key={era}
                name={ERA_LABELS[era]}
                dataKey={ERA_LABELS[era]}
                stroke={ERA_COLORS[era]}
                fill={ERA_COLORS[era]}
                fillOpacity={0.2}
              />
            ))}
            <Legend />
            <Tooltip />
          </RadarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="关键指标对比">
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={barChartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="metric" />
            <YAxis />
            <Tooltip />
            <Legend />
            {ERA_KEYS.map((era) => (
              <Bar
                key={era}
                dataKey={ERA_LABELS[era]}
                fill={ERA_COLORS[era]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="详细指标对比表">
        <Table
          columns={tableColumns as ColumnsType<any>}
          dataSource={tableData}
          pagination={false}
          scroll={{ x: 800 }}
          size="small"
        />
      </Card>
    </Space>
  )

  const renderTimelineTab = () => (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="四足机器人发展历程">
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={14}>
            <Timeline
              mode="left"
              items={timelineEvents.map((evt) => {
                const eraKey = (evt.era === 'BigDog' ? 'Spot' : evt.era) as EraKey
                const color = ERA_COLORS[eraKey] ?? '#999'
                return {
                  color,
                  label: `${evt.year} 年`,
                  children: (
                    <div>
                      <Space>
                        <Tag color={color}>{evt.event}</Tag>
                        <Tag color="blue">{evt.era}</Tag>
                      </Space>
                      <p className="mt-2 text-gray-600">{evt.description}</p>
                    </div>
                  ),
                }
              })}
            />
          </Col>
          <Col xs={24} lg={10}>
            <Card title="创新指数趋势" size="small">
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={lineChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="year" />
                  <YAxis domain={[0, 10]} />
                  <Tooltip />
                  <Legend />
                  {ERA_KEYS.map((era) => (
                    <Line
                      key={era}
                      type="monotone"
                      dataKey={`innovation.${ERA_LABELS[era]}`}
                      stroke={ERA_COLORS[era]}
                      strokeWidth={2}
                      dot={{ fill: ERA_COLORS[era] }}
                      name={ERA_LABELS[era]}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        </Row>
      </Card>
    </Space>
  )

  const adaptabilityScore = (adaptability: string): number => {
    if (adaptability.includes('极高')) return 95
    if (adaptability.includes('高')) return 80
    if (adaptability.includes('中')) return 60
    if (adaptability.includes('低')) return 30
    return 50
  }

  const energyScore = (eff: string): number => {
    if (eff.includes('极高')) return 95
    if (eff.includes('高')) return 80
    if (eff.includes('中')) return 60
    if (eff.includes('低')) return 30
    return 50
  }

  const renderMechanismTab = () => (
    <Row gutter={[16, 16]}>
      {ERA_KEYS.map((era) => {
        const data = mechanismData?.[era]
        if (!data) return null
        const adaptScore = adaptabilityScore(data.adaptability)
        const effScore = energyScore(data.energy_efficiency)
        return (
          <Col xs={24} lg={12} key={era}>
            <Card
              title={
                <Space>
                  <Tag color={ERA_COLORS[era]}>{data.name}</Tag>
                  <Tag>{data.era}</Tag>
                </Space>
              }
              extra={
                <Tag color={ERA_COLORS[era]}>{ERA_LABELS[era]}</Tag>
              }
            >
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Row gutter={[16, 16]}>
                  <Col span={12}>
                    <div className="text-sm">
                      <div className="text-gray-500">连杆类型</div>
                      <div className="font-medium">{data.linkage_type}</div>
                    </div>
                  </Col>
                  <Col span={12}>
                    <div className="text-sm">
                      <div className="text-gray-500">驱动方式</div>
                      <div className="font-medium">{data.actuation}</div>
                    </div>
                  </Col>
                  <Col span={12}>
                    <div className="text-sm">
                      <div className="text-gray-500">控制方式</div>
                      <div className="font-medium">{data.control}</div>
                    </div>
                  </Col>
                  <Col span={12}>
                    <div className="text-sm">
                      <div className="text-gray-500">步态生成</div>
                      <div className="font-medium">{data.gait_generation}</div>
                    </div>
                  </Col>
                </Row>

                {era === 'WoodenOx' && data.computed_stride_length_mm !== undefined && (
                  <Card size="small" title="步态计算参数" type="inner" style={{ borderColor: ERA_COLORS[era] }}>
                    <Row gutter={[16, 16]}>
                      <Col span={8}>
                        <Statistic
                          title="步长"
                          value={data.computed_stride_length_mm}
                          precision={1}
                          suffix="mm"
                          valueStyle={{ color: ERA_COLORS[era], fontSize: 18 }}
                        />
                      </Col>
                      <Col span={8}>
                        <Statistic
                          title="足端间隙"
                          value={data.computed_foot_clearance_mm}
                          precision={1}
                          suffix="mm"
                          valueStyle={{ color: ERA_COLORS[era], fontSize: 18 }}
                        />
                      </Col>
                      <Col span={8}>
                        <Statistic
                          title="支撑相占比"
                          value={data.computed_support_phase_pct}
                          precision={1}
                          suffix="%"
                          valueStyle={{ color: ERA_COLORS[era], fontSize: 18 }}
                        />
                      </Col>
                    </Row>
                  </Card>
                )}

                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <div>
                    <div className="text-sm text-gray-500 mb-1">能源效率</div>
                    <Progress
                      percent={effScore}
                      strokeColor={ERA_COLORS[era]}
                      format={(p) => `${p}% - ${data.energy_efficiency}`}
                    />
                  </div>
                  <div>
                    <div className="text-sm text-gray-500 mb-1">环境适应能力</div>
                    <Progress
                      percent={adaptScore}
                      strokeColor={ERA_COLORS[era]}
                      format={(p) => `${p}% - ${data.adaptability}`}
                    />
                  </div>
                </Space>

                <div className="p-3 bg-gray-50 rounded">
                  <div className="text-sm text-gray-500 mb-1">核心创新</div>
                  <div className="text-sm font-medium" style={{ color: ERA_COLORS[era] }}>
                    {data.key_innovation}
                  </div>
                </div>
              </Space>
            </Card>
          </Col>
        )
      })}
    </Row>
  )

  if (error) {
    return (
      <Alert
        type="error"
        message="数据加载失败"
        description={error}
        showIcon
      />
    )
  }

  return (
    <Spin spinning={loading} tip="加载中...">
      <Card
        title={
          <Space>
            <Tag color="red">木牛流马</Tag>
            <span>vs</span>
            <Tag color="blue">Spot</Tag>
            <Tag color="green">Cheetah</Tag>
            <Tag color="orange">ANYmal</Tag>
            <span className="text-gray-500 text-sm font-normal">跨时代四足机器人对比</span>
          </Space>
        }
      >
        <Tabs
          defaultActiveKey="metrics"
          items={[
            {
              key: 'metrics',
              label: '指标对比',
              children: renderMetricsTab(),
            },
            {
              key: 'timeline',
              label: '发展时间线',
              children: renderTimelineTab(),
            },
            {
              key: 'mechanism',
              label: '机构原理',
              children: renderMechanismTab(),
            },
          ]}
        />
      </Card>
    </Spin>
  )
}

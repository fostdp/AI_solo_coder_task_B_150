import { useEffect, useState, useMemo } from 'react'
import {
  Card, Row, Col, Select, Table, Statistic, Tag, Tabs, Spin, Alert, Empty, Descriptions
} from 'antd'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import type { TransportRadarData, TransportComparisonResult, TerrainTypeKey, TransportMetrics } from '@/types'
import { comparisonApi } from '@/utils/api'
import { useAppStore } from '@/store/useAppStore'

type TransportKey = 'wooden_ox' | 'wheelbarrow' | 'horse_carriage'

interface TerrainComparisonResponse {
  terrain_type: string
  terrain_properties: Record<string, number>
  transport_comparison: TransportComparisonResult
  terrain_specific_analysis: Record<TransportKey, TerrainSpecificAnalysis>
  ranking: Record<string, Array<{ transport: string; value: number }>>
}

interface TerrainSpecificAnalysis {
  advantage: string
  disadvantage: string
  clearance_strategy: string
  suitability_score: number
}

interface TransportProfile {
  name: string
  name_en: string
  era: string
  inventor: string
  mechanism_type: string
  propulsion: string
  structural_params: Record<string, number>
  performance: Record<string, number>
  advantages: string[]
  disadvantages: string[]
}

const terrainOptions: Array<{ value: TerrainTypeKey; label: string }> = [
  { value: 'flat', label: '平地' },
  { value: 'gentle_slope', label: '缓坡' },
  { value: 'steep_slope', label: '陡坡' },
  { value: 'rocky', label: '岩石地形' },
  { value: 'muddy', label: '泥泞地形' },
  { value: 'stairs', label: '楼梯' },
  { value: 'obstacle', label: '障碍物' },
]

const transportLabels: Record<TransportKey, { name: string; color: string }> = {
  wooden_ox: { name: '木牛流马', color: '#E74C3C' },
  wheelbarrow: { name: '独轮车', color: '#3498DB' },
  horse_carriage: { name: '马车', color: '#2ECC71' },
}

const summaryLabels: Record<string, string> = {
  best_obstacle_clearing: '越障能力',
  best_slope_climbing: '爬坡能力',
  best_stability: '稳定性',
  best_payload: '载重能力',
  best_speed: '速度表现',
  best_energy_efficiency: '能源效率',
  best_terrain_adaptability: '地形适应性',
}

interface MetricConfig {
  key: keyof TransportMetrics
  label: string
  unit: string
}

const metricConfigs: MetricConfig[] = [
  { key: 'max_obstacle_height', label: '最大越障高度', unit: 'mm' },
  { key: 'max_slope_angle', label: '最大爬坡角度', unit: '°' },
  { key: 'pass_probability', label: '通过概率', unit: '%' },
  { key: 'stability_on_slope', label: '斜坡稳定性', unit: '%' },
  { key: 'energy_efficiency', label: '能源效率', unit: '%' },
  { key: 'payload_capacity', label: '载重能力', unit: 'kg' },
  { key: 'speed_on_flat', label: '平地速度', unit: 'm/s' },
  { key: 'speed_on_slope', label: '斜坡速度', unit: 'm/s' },
  { key: 'terrain_adaptability', label: '地形适应性', unit: '%' },
]

function formatValue(value: number, key: keyof TransportMetrics): number {
  if (key === 'pass_probability' || key === 'energy_efficiency') {
    return Number((value * 100).toFixed(1))
  }
  return Number(value.toFixed(2))
}

export function TransportComparison() {
  const { jansenParams } = useAppStore()
  const [terrainType, setTerrainType] = useState<TerrainTypeKey>('flat')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [comparisonData, setComparisonData] = useState<TerrainComparisonResponse | null>(null)
  const [radarData, setRadarData] = useState<TransportRadarData | null>(null)
  const [profiles, setProfiles] = useState<Record<TransportKey, TransportProfile> | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [compRes, radarRes, profilesRes] = await Promise.all([
        comparisonApi.compareTransportByTerrain(terrainType),
        comparisonApi.getTransportRadar(terrainType),
        comparisonApi.getTransportProfiles(jansenParams),
      ])
      setComparisonData(compRes.data as TerrainComparisonResponse)
      setRadarData(radarRes.data as TransportRadarData)
      setProfiles(profilesRes.data as Record<TransportKey, TransportProfile>)
    } catch (err) {
      setError(err instanceof Error ? err.message : '数据加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [terrainType])

  const radarChartData = useMemo(() => {
    if (!radarData) return []
    const axes = radarData.axes
    return axes.map((axis, idx) => {
      const row: Record<string, string | number> = { axis: axis.label }
      radarData.datasets.forEach((ds) => {
        row[ds.name] = Number((ds.values[idx] * 100).toFixed(1))
      })
      return row
    })
  }, [radarData])

  const barChartData = useMemo(() => {
    if (!comparisonData) return []
    const tc = comparisonData.transport_comparison
    return metricConfigs.map((mc) => {
      const row: Record<string, string | number> = { metric: mc.label }
      ;(['wooden_ox', 'wheelbarrow', 'horse_carriage'] as TransportKey[]).forEach((key) => {
        row[transportLabels[key].name] = formatValue(tc[key][mc.key], mc.key)
      })
      return row
    })
  }, [comparisonData])

  const tableData = useMemo(() => {
    if (!comparisonData) return []
    const tc = comparisonData.transport_comparison
    return metricConfigs.map((mc) => {
      const row: Record<string, string | number> = {
        key: mc.key,
        metric: mc.label,
        unit: mc.unit,
      }
      ;(['wooden_ox', 'wheelbarrow', 'horse_carriage'] as TransportKey[]).forEach((tk) => {
        row[tk] = formatValue(tc[tk][mc.key], mc.key)
      })
      return row
    })
  }, [comparisonData])

  const transportKeys: TransportKey[] = ['wooden_ox', 'wheelbarrow', 'horse_carriage']

  if (error) {
    return (
      <Alert
        type="error"
        message="加载失败"
        description={error}
        showIcon
        closable
        onClose={() => setError(null)}
      />
    )
  }

  return (
    <div className="space-y-4">
      <Card
        title="古代运输工具对比分析"
        extra={
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">地形类型:</span>
            <Select
              value={terrainType}
              onChange={setTerrainType}
              style={{ width: 160 }}
              options={terrainOptions}
              loading={loading}
            />
          </div>
        }
      >
        <Spin spinning={loading} tip="加载中...">
          {!comparisonData && !loading ? (
            <Empty />
          ) : (
            <div className="space-y-4">
              <Tabs
                defaultActiveKey="charts"
                items={[
                  {
                    key: 'charts',
                    label: '图表对比',
                    children: (
                      <div className="space-y-4">
                        <Row gutter={[16, 16]}>
                          <Col xs={24} lg={12}>
                            <Card title="能力雷达图" size="small">
                              <ResponsiveContainer width="100%" height={400}>
                                <RadarChart data={radarChartData}>
                                  <PolarGrid />
                                  <PolarAngleAxis dataKey="axis" />
                                  <PolarRadiusAxis angle={30} domain={[0, 100]} />
                                  {radarData?.datasets.map((ds) => (
                                    <Radar
                                      key={ds.transport}
                                      name={ds.name}
                                      dataKey={ds.name}
                                      stroke={ds.color}
                                      fill={ds.color}
                                      fillOpacity={0.3}
                                    />
                                  ))}
                                  <Legend />
                                </RadarChart>
                              </ResponsiveContainer>
                            </Card>
                          </Col>
                          <Col xs={24} lg={12}>
                            <Card title="指标对比柱状图" size="small">
                              <ResponsiveContainer width="100%" height={400}>
                                <BarChart data={barChartData} layout="vertical">
                                  <CartesianGrid strokeDasharray="3 3" />
                                  <XAxis type="number" />
                                  <YAxis dataKey="metric" type="category" width={100} />
                                  <Tooltip />
                                  <Legend />
                                  {transportKeys.map((tk) => (
                                    <Bar
                                      key={tk}
                                      dataKey={transportLabels[tk].name}
                                      fill={transportLabels[tk].color}
                                    />
                                  ))}
                                </BarChart>
                              </ResponsiveContainer>
                            </Card>
                          </Col>
                        </Row>
                      </div>
                    ),
                  },
                  {
                    key: 'table',
                    label: '详细数据表',
                    children: (
                      <Card size="small">
                        <Table
                          dataSource={tableData}
                          columns={[
                            { title: '指标', dataIndex: 'metric', key: 'metric', width: 150, fixed: 'left' as const },
                            { title: '单位', dataIndex: 'unit', key: 'unit', width: 80 },
                            ...transportKeys.map((tk) => ({
                              title: (
                                <span>
                                  <Tag color={transportLabels[tk].color}>{transportLabels[tk].name}</Tag>
                                </span>
                              ),
                              dataIndex: tk,
                              key: tk,
                              render: (val: number, record: any) => {
                                const metricKey = record.key as keyof TransportMetrics
                                const mc = metricConfigs.find((m) => m.key === metricKey)
                                if (!mc || !comparisonData) return val
                                const values = transportKeys.map((k) => ({
                                  key: k,
                                  value: comparisonData.transport_comparison[k][mc.key],
                                }))
                                const maxVal = Math.max(...values.map((v) => v.value))
                                const isMax = comparisonData.transport_comparison[tk][mc.key] === maxVal
                                return (
                                  <span className={isMax ? 'font-bold text-green-600' : ''}>
                                    {val}
                                    {isMax && <Tag color="green" className="ml-2">最优</Tag>}
                                  </span>
                                )
                              },
                            })),
                          ]}
                          pagination={false}
                          scroll={{ x: 800 }}
                          size="small"
                        />
                      </Card>
                    ),
                  },
                  {
                    key: 'best',
                    label: '最佳表现',
                    children: (
                      <Card size="small">
                        <Row gutter={[16, 16]}>
                          {comparisonData &&
                            Object.entries(comparisonData.transport_comparison.comparison_summary).map(
                              ([key, winner]) => {
                                const winnerKey = winner as TransportKey
                                const label = summaryLabels[key] || key
                                const info = transportLabels[winnerKey]
                                return (
                                  <Col xs={12} sm={8} md={6} key={key}>
                                    <Card size="small" className="text-center">
                                      <Statistic
                                        title={label}
                                        value={info.name}
                                        valueStyle={{ color: info.color, fontSize: 16 }}
                                        prefix={<Tag color={info.color}>最佳</Tag>}
                                      />
                                    </Card>
                                  </Col>
                                )
                              }
                            )}
                        </Row>
                      </Card>
                    ),
                  },
                  {
                    key: 'profiles',
                    label: '运输工具档案',
                    children: (
                      <div className="space-y-4">
                        <Row gutter={[16, 16]}>
                          {transportKeys.map((tk) => {
                            const profile = profiles?.[tk]
                            const info = transportLabels[tk]
                            if (!profile) return null
                            return (
                              <Col xs={24} lg={8} key={tk}>
                                <Card
                                  title={
                                    <span>
                                      <Tag color={info.color}>{profile.name}</Tag>
                                      <span className="text-xs text-gray-500 ml-2">{profile.name_en}</span>
                                    </span>
                                  }
                                  size="small"
                                >
                                  <Descriptions column={1} size="small" className="mb-3">
                                    <Descriptions.Item label="时代">{profile.era}</Descriptions.Item>
                                    <Descriptions.Item label="发明者">{profile.inventor}</Descriptions.Item>
                                    <Descriptions.Item label="机构类型">
                                      {profile.mechanism_type}
                                    </Descriptions.Item>
                                    <Descriptions.Item label="动力方式">{profile.propulsion}</Descriptions.Item>
                                  </Descriptions>
                                  <div className="mb-3">
                                    <div className="text-sm font-semibold mb-1">结构参数</div>
                                    <Descriptions column={1} size="small" bordered>
                                      {Object.entries(profile.structural_params).map(([k, v]) => (
                                        <Descriptions.Item key={k} label={k}>
                                          {typeof v === 'number' ? v.toFixed(1) : v}
                                        </Descriptions.Item>
                                      ))}
                                    </Descriptions>
                                  </div>
                                  <div className="mb-2">
                                    <div className="text-sm font-semibold mb-1 text-green-600">优势</div>
                                    {profile.advantages.map((a, i) => (
                                      <Tag key={i} color="green" className="mb-1">
                                        {a}
                                      </Tag>
                                    ))}
                                  </div>
                                  <div>
                                    <div className="text-sm font-semibold mb-1 text-red-500">劣势</div>
                                    {profile.disadvantages.map((d, i) => (
                                      <Tag key={i} color="red" className="mb-1">
                                        {d}
                                      </Tag>
                                    ))}
                                  </div>
                                </Card>
                              </Col>
                            )
                          })}
                        </Row>
                      </div>
                    ),
                  },
                ]}
              />
            </div>
          )}
        </Spin>
      </Card>
    </div>
  )
}

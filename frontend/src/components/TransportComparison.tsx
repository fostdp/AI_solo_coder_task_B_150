import { useState, useEffect } from 'react'
import { Card, Row, Col, Select, Table, Tag, Statistic } from 'antd'
import { SwapOutlined } from '@ant-design/icons'
import { comparisonApi } from '@/utils/api'
import type { TransportComparisonResult, TransportRadarData, TerrainTypeKey } from '@/types'

const terrainOptions: { value: TerrainTypeKey; label: string }[] = [
  { value: 'flat', label: '平地' },
  { value: 'gentle_slope', label: '缓坡' },
  { value: 'steep_slope', label: '陡坡' },
  { value: 'rocky', label: '碎石' },
  { value: 'muddy', label: '泥泞' },
  { value: 'stairs', label: '台阶' },
  { value: 'obstacle', label: '障碍' },
]

export function TransportComparison() {
  const [terrain, setTerrain] = useState<TerrainTypeKey>('flat')
  const [comparison, setComparison] = useState<TransportComparisonResult | null>(null)
  const [radarData, setRadarData] = useState<TransportRadarData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [compRes, radarRes] = await Promise.all([
          comparisonApi.compareTransportByTerrain(terrain),
          comparisonApi.getTransportRadar(terrain),
        ])
        setComparison(compRes.data)
        setRadarData(radarRes.data)
      } catch (error) {
        console.error('获取运输工具对比数据失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [terrain])

  const columns = [
    { title: '指标', dataIndex: 'metric', key: 'metric', width: 160 },
    { title: '木牛流马', dataIndex: 'wooden_ox', key: 'wooden_ox', render: (v: number) => <Tag color="blue">{v}</Tag> },
    { title: '独轮车', dataIndex: 'wheelbarrow', key: 'wheelbarrow', render: (v: number) => <Tag color="green">{v}</Tag> },
    { title: '马车', dataIndex: 'horse_carriage', key: 'horse_carriage', render: (v: number) => <Tag color="orange">{v}</Tag> },
  ]

  const getTableData = () => {
    if (!comparison) return []
    const keys = ['max_obstacle_height', 'max_slope_angle', 'pass_probability', 'stability_on_slope', 'energy_efficiency', 'payload_capacity', 'speed_on_flat', 'speed_on_slope', 'terrain_adaptability'] as const
    const labels: Record<string, string> = {
      max_obstacle_height: '最大越障高度 (mm)',
      max_slope_angle: '最大爬坡角 (°)',
      pass_probability: '通过概率',
      stability_on_slope: '坡道稳定性',
      energy_efficiency: '能量效率',
      payload_capacity: '载重能力 (kg)',
      speed_on_flat: '平地速度 (mm/s)',
      speed_on_slope: '坡道速度 (mm/s)',
      terrain_adaptability: '地形适应性',
    }
    return keys.map((key, i) => ({
      key: i,
      metric: labels[key],
      wooden_ox: (comparison.wooden_ox as any)[key],
      wheelbarrow: (comparison.wheelbarrow as any)[key],
      horse_carriage: (comparison.horse_carriage as any)[key],
    }))
  }

  return (
    <div className="space-y-4">
      <Card title={<span><SwapOutlined className="mr-2" />古代运输工具越障能力对比</span>}>
        <Row gutter={16} align="middle" className="mb-4">
          <Col>
            <span className="mr-2">地形类型:</span>
            <Select value={terrain} onChange={setTerrain} options={terrainOptions} style={{ width: 160 }} />
          </Col>
        </Row>
        <Table
          columns={columns}
          dataSource={getTableData()}
          loading={loading}
          pagination={false}
          size="small"
          bordered
        />
      </Card>

      {radarData && (
        <Card title="雷达图数据概览">
          <Row gutter={16}>
            {radarData.datasets.map((ds) => (
              <Col span={8} key={ds.transport}>
                <Statistic title={ds.name} value={ds.values.reduce((a, b) => a + b, 0) / ds.values.length} precision={2} />
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {comparison?.comparison_summary && (
        <Card title="对比总结">
          {Object.entries(comparison.comparison_summary).map(([key, value]) => (
            <p key={key}><Tag color="blue">{key}</Tag> {value}</p>
          ))}
        </Card>
      )}
    </div>
  )
}

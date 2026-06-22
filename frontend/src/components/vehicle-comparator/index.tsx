import { useState, useEffect } from 'react'
import { Card, Row, Col, Select, Table, Tag, Statistic } from 'antd'
import { SwapOutlined } from '@ant-design/icons'
import { comparisonApi } from '@/utils/api'
import { terrainOptions, getTableData } from './utils'
import type { TransportComparisonResult, TransportRadarData, TerrainTypeKey } from './types'

export function VehicleComparator() {
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
          dataSource={getTableData(comparison)}
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

export { VehicleComparator as TransportComparison }
export type * from './types'

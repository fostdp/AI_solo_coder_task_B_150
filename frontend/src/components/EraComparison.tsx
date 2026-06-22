import { useState, useEffect } from 'react'
import { Card, Row, Col, Table, Tag, Statistic, Tabs } from 'antd'
import { ClockCircleOutlined } from '@ant-design/icons'
import { comparisonApi } from '@/utils/api'
import type { EraComparisonResult, EraTimelineEvent, EraKey } from '@/types'

const eraNames: Record<EraKey, string> = {
  WoodenOx: '木牛流马',
  Spot: 'Spot',
  Cheetah: 'Cheetah',
  ANYmal: 'ANYmal',
}

const eraColors: Record<EraKey, string> = {
  WoodenOx: 'blue',
  Spot: 'green',
  Cheetah: 'orange',
  ANYmal: 'purple',
}

export function EraComparison() {
  const [eraData, setEraData] = useState<EraComparisonResult | null>(null)
  const [timeline, setTimeline] = useState<EraTimelineEvent[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [eraRes, timelineRes] = await Promise.all([
          comparisonApi.getEraAllMetrics(),
          comparisonApi.getEraTimeline(),
        ])
        setEraData(eraRes.data)
        setTimeline(timelineRes.data)
      } catch (error) {
        console.error('获取跨时代对比数据失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const columns = [
    { title: '指标', dataIndex: 'metric', key: 'metric', width: 200 },
    ...((Object.keys(eraNames) as EraKey[]).map((era) => ({
      title: eraNames[era],
      dataIndex: era,
      key: era,
      render: (v: any) => typeof v === 'boolean' ? <Tag color={v ? 'green' : 'red'}>{v ? '是' : '否'}</Tag> : <Tag color={eraColors[era]}>{v}</Tag>,
    }))),
  ]

  const getTableData = () => {
    if (!eraData) return []
    const keys = ['mechanical_complexity', 'max_obstacle_height', 'max_slope_angle', 'speed', 'payload_ratio', 'autonomy_hours', 'terrain_types_supported', 'noise_level_db', 'cost_estimate_relative', 'control_method', 'power_source', 'sensing_capability', 'self_recovery', 'historical_significance', 'innovation_index'] as const
    const labels: Record<string, string> = {
      mechanical_complexity: '机械复杂度',
      max_obstacle_height: '最大越障高度 (mm)',
      max_slope_angle: '最大爬坡角 (°)',
      speed: '速度',
      payload_ratio: '载重比',
      autonomy_hours: '续航时间 (h)',
      terrain_types_supported: '支持地形数',
      noise_level_db: '噪声水平 (dB)',
      cost_estimate_relative: '相对成本',
      control_method: '控制方式',
      power_source: '动力来源',
      sensing_capability: '感知能力',
      self_recovery: '自恢复',
      historical_significance: '历史意义',
      innovation_index: '创新指数',
    }
    return keys.map((key, i) => ({
      key: i,
      metric: labels[key],
      WoodenOx: (eraData.WoodenOx as any)[key],
      Spot: (eraData.Spot as any)[key],
      Cheetah: (eraData.Cheetah as any)[key],
      ANYmal: (eraData.ANYmal as any)[key],
    }))
  }

  const timelineColumns = [
    { title: '年份', dataIndex: 'year', key: 'year', width: 100 },
    { title: '时代', dataIndex: 'era', key: 'era', render: (v: string) => <Tag>{v}</Tag> },
    { title: '事件', dataIndex: 'event', key: 'event' },
    { title: '描述', dataIndex: 'description', key: 'description' },
  ]

  return (
    <div className="space-y-4">
      <Card title={<span><ClockCircleOutlined className="mr-2" />跨时代对比（古代木牛流马 vs 现代四足机器人）</span>}>
        <Tabs items={[
          { key: 'metrics', label: '指标对比', children: (
            <Table columns={columns} dataSource={getTableData()} loading={loading} pagination={false} size="small" bordered />
          )},
          { key: 'overview', label: '概览', children: eraData ? (
            <Row gutter={16}>
              {(Object.keys(eraNames) as EraKey[]).map((era) => (
                <Col span={6} key={era}>
                  <Card size="small">
                    <Statistic title={eraNames[era]} value={(eraData[era] as any).innovation_index} suffix="/ 100" />
                    <div className="mt-2"><Tag color={eraColors[era]}>{(eraData[era] as any).power_source}</Tag></div>
                  </Card>
                </Col>
              ))}
            </Row>
          ) : null },
        ]} />
      </Card>

      {timeline.length > 0 && (
        <Card title="技术演进时间线">
          <Table columns={timelineColumns} dataSource={timeline.map((t, i) => ({ key: i, ...t }))} pagination={false} size="small" bordered />
        </Card>
      )}
    </div>
  )
}

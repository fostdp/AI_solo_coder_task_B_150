import { useState, useEffect } from 'react'
import { Card, Row, Col, Table, Tag, Statistic, Tabs } from 'antd'
import { ClockCircleOutlined } from '@ant-design/icons'
import { comparisonApi } from '@/utils/api'
import { eraNames, eraColors, getTableData } from './utils'
import type { EraComparisonResult, EraTimelineEvent, EraKey } from './types'

export function EraComparator() {
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
            <Table columns={columns} dataSource={getTableData(eraData)} loading={loading} pagination={false} size="small" bordered />
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

export { EraComparator as EraComparison }
export type * from './types'

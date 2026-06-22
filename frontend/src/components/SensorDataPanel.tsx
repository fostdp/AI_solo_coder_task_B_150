import { useEffect, useState } from 'react'
import { Card, Statistic, Row, Col, Progress, Tag } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, ThunderboltOutlined, SafetyOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useAppStore } from '@/store/useAppStore'
import { sensorApi } from '@/utils/api'
import type { SensorData } from '@/types'
import dayjs from 'dayjs'

export function SensorDataPanel() {
  const { sensorData, sensorHistory, selectedDevice, setSensorData, setSensorHistory } = useAppStore()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [realtimeRes, historyRes] = await Promise.all([
          sensorApi.getRealtime(selectedDevice),
          sensorApi.getHistory(selectedDevice, undefined, undefined, 100),
        ])
        setSensorData(realtimeRes.data)
        setSensorHistory(historyRes.data)
      } catch (error) {
        console.error('获取传感器数据失败:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [selectedDevice, setSensorData, setSensorHistory])

  const chartOption = {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: ['曲柄转角', '腿足位移', '机身倾角', '地面起伏'],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: sensorHistory.slice(-20).map((d) => dayjs(d.timestamp).format('HH:mm:ss')),
    },
    yAxis: [
      {
        type: 'value',
        name: '角度(°)',
        position: 'left',
      },
      {
        type: 'value',
        name: '位移(mm)',
        position: 'right',
      },
    ],
    series: [
      {
        name: '曲柄转角',
        type: 'line',
        yAxisIndex: 0,
        smooth: true,
        data: sensorHistory.slice(-20).map((d) => d.crank_angle),
        lineStyle: { color: '#1890ff' },
      },
      {
        name: '腿足位移',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: sensorHistory.slice(-20).map((d) => d.leg_displacement),
        lineStyle: { color: '#52c41a' },
      },
      {
        name: '机身倾角',
        type: 'line',
        yAxisIndex: 0,
        smooth: true,
        data: sensorHistory.slice(-20).map((d) => d.body_inclination),
        lineStyle: { color: '#faad14' },
      },
      {
        name: '地面起伏',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: sensorHistory.slice(-20).map((d) => d.ground_elevation),
        lineStyle: { color: '#722ed1' },
      },
    ],
  }

  const inclinationStatus = sensorData
    ? Math.abs(sensorData.body_inclination) > 15
      ? 'error'
      : Math.abs(sensorData.body_inclination) > 10
      ? 'warning'
      : 'success'
    : 'normal'

  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="曲柄转角"
              value={sensorData?.crank_angle ?? 0}
              precision={1}
              suffix="°"
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
            <div className="mt-2 text-sm text-gray-500">
              {dayjs(sensorData?.timestamp).format('YYYY-MM-DD HH:mm:ss')}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="腿足位移"
              value={sensorData?.leg_displacement ?? 0}
              precision={1}
              suffix="mm"
              valueStyle={{ color: '#52c41a' }}
            />
            <div className="mt-2">
              <Progress
                percent={Math.round(((sensorData?.leg_displacement ?? 0) / 500) * 100)}
                strokeColor="#52c41a"
                size="small"
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="机身倾角"
              value={sensorData?.body_inclination ?? 0}
              precision={1}
              suffix="°"
              prefix={
                (sensorData?.body_inclination ?? 0) >= 0 ? (
                  <ArrowUpOutlined style={{ color: '#faad14' }} />
                ) : (
                  <ArrowDownOutlined style={{ color: '#fa8c16' }} />
                )
              }
              valueStyle={{
                color: inclinationStatus === 'error' ? '#ff4d4f' : inclinationStatus === 'warning' ? '#faad14' : '#52c41a',
              }}
            />
            <div className="mt-2">
              <Tag color={inclinationStatus}>
                {inclinationStatus === 'error' ? '超限' : inclinationStatus === 'warning' ? '警告' : '正常'}
              </Tag>
              阈值: ±15°
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="地面起伏"
              value={sensorData?.ground_elevation ?? 0}
              precision={1}
              suffix="mm"
              prefix={<SafetyOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
            <div className="mt-2 text-sm text-gray-500">
              范围: {(sensorHistory.length > 0
                ? Math.round(Math.min(...sensorHistory.map((d) => d.ground_elevation)))
                : 0) + ' ~ ' + (sensorHistory.length > 0
                ? Math.round(Math.max(...sensorHistory.map((d) => d.ground_elevation)))
                : 0)} mm
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="传感器数据趋势" loading={loading}>
        <ReactECharts option={chartOption} style={{ height: 350 }} />
      </Card>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Card, List, Tag, Button, Empty, Badge, Modal, message } from 'antd'
import { WarningOutlined, CheckCircleOutlined, BellOutlined } from '@ant-design/icons'
import { useAppStore } from '@/store/useAppStore'
import { alertApi } from '@/utils/api'
import type { Alert } from '@/types'
import dayjs from 'dayjs'

const alertTypeLabels: Record<string, { label: string; color: string }> = {
  INCLINATION_EXCEEDED: { label: '倾角超限', color: 'red' },
  MECHANISM_JAMMED: { label: '机构卡死', color: 'orange' },
  SENSOR_FAULT: { label: '传感器故障', color: 'gold' },
}

const alertLevelLabels: Record<string, { label: string; color: string }> = {
  INFO: { label: '信息', color: 'blue' },
  WARNING: { label: '警告', color: 'gold' },
  CRITICAL: { label: '严重', color: 'red' },
}

export function AlertPanel() {
  const { alerts, setAlerts, acknowledgeAlert, selectedDevice, wsConnected } = useAppStore()
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<any>(null)

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        setLoading(true)
        const [currentRes, statsRes] = await Promise.all([
          alertApi.getCurrent(selectedDevice),
          alertApi.getStatistics(24),
        ])
        setAlerts(currentRes.data)
        setStats(statsRes.data)
      } catch (error) {
        console.error('获取告警数据失败:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchAlerts()
    const interval = setInterval(fetchAlerts, 10000)
    return () => clearInterval(interval)
  }, [selectedDevice, setAlerts])

  const handleAcknowledge = async (alert: Alert) => {
    Modal.confirm({
      title: '确认告警',
      content: `确认处理告警 "${alert.message}"？`,
      onOk: async () => {
        try {
          await alertApi.acknowledge(alert.id)
          acknowledgeAlert(alert.id)
          message.success('告警已确认')
        } catch (error) {
          message.error('确认失败')
        }
      },
    })
  }

  const activeAlerts = alerts.filter((a) => !a.acknowledged)
  const acknowledgedAlerts = alerts.filter((a) => a.acknowledged)

  return (
    <div className="space-y-4">
      <Card
        title={
          <span className="flex items-center gap-2">
            <BellOutlined />
            告警中心
            <Badge count={activeAlerts.length} size="small" style={{ marginLeft: 8 }} />
          </span>
        }
        size="small"
        extra={
          <span className={`text-sm ${wsConnected ? 'text-green-500' : 'text-red-500'}`}>
            {wsConnected ? '● 实时连接' : '● 连接断开'}
          </span>
        }
      >
        {stats && (
          <div className="grid grid-cols-3 gap-2 mb-4 text-center">
            <div className="p-2 bg-red-50 rounded">
              <div className="text-2xl font-bold text-red-500">{stats.total || 0}</div>
              <div className="text-xs text-gray-500">24h总告警</div>
            </div>
            <div className="p-2 bg-orange-50 rounded">
              <div className="text-2xl font-bold text-orange-500">{activeAlerts.length}</div>
              <div className="text-xs text-gray-500">待处理</div>
            </div>
            <div className="p-2 bg-green-50 rounded">
              <div className="text-2xl font-bold text-green-500">{stats.acknowledged_count || 0}</div>
              <div className="text-xs text-gray-500">已确认</div>
            </div>
          </div>
        )}
      </Card>

      <Card title="活动告警" size="small" loading={loading}>
        {activeAlerts.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span className="text-green-500">
                <CheckCircleOutlined /> 暂无活动告警
              </span>
            }
          />
        ) : (
          <List
            dataSource={activeAlerts}
            renderItem={(alert) => (
              <List.Item
                className="border-l-4 border-red-500 pl-3 mb-2 bg-red-50"
                actions={[
                  <Button size="small" type="primary" onClick={() => handleAcknowledge(alert)}>
                    确认
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  avatar={<WarningOutlined className="text-red-500 text-xl" />}
                  title={
                    <div className="flex gap-2 items-center">
                      <Tag color={alertTypeLabels[alert.type]?.color}>
                        {alertTypeLabels[alert.type]?.label}
                      </Tag>
                      <Tag color={alertLevelLabels[alert.level]?.color}>
                        {alertLevelLabels[alert.level]?.label}
                      </Tag>
                      <span className="text-xs text-gray-500">
                        {alert.device_id}
                      </span>
                    </div>
                  }
                  description={
                    <div>
                      <div>{alert.message}</div>
                      <div className="text-xs text-gray-400 mt-1">
                        {dayjs(alert.timestamp).format('YYYY-MM-DD HH:mm:ss')}
                      </div>
                      {alert.sensor_data && (
                        <div className="text-xs text-gray-500 mt-1">
                          倾角: {alert.sensor_data.body_inclination.toFixed(1)}° | 
                          曲柄: {alert.sensor_data.crank_angle.toFixed(1)}°
                        </div>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      <Card title="历史告警" size="small" loading={loading}>
        {acknowledgedAlerts.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史告警" />
        ) : (
          <List
            dataSource={acknowledgedAlerts.slice(0, 10)}
            renderItem={(alert) => (
              <List.Item className="mb-2 opacity-60">
                <List.Item.Meta
                  avatar={<CheckCircleOutlined className="text-green-500" />}
                  title={
                    <div className="flex gap-2 items-center">
                      <Tag color={alertTypeLabels[alert.type]?.color}>
                        {alertTypeLabels[alert.type]?.label}
                      </Tag>
                      <span className="text-xs text-gray-500">
                        {dayjs(alert.timestamp).format('MM-DD HH:mm')}
                      </span>
                    </div>
                  }
                  description={alert.message}
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  )
}

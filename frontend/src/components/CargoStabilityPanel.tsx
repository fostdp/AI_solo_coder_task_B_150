import { useState, useEffect } from 'react'
import { Card, Row, Col, Select, Table, Tag, Statistic, InputNumber, Button } from 'antd'
import { UnorderedListOutlined } from '@ant-design/icons'
import { cargoApi } from '@/utils/api'
import { useAppStore } from '@/store/useAppStore'
import type { CargoStabilityGridResult, CargoStabilityPoint, CargoHeightPoint, CargoMassPoint } from '@/types'

export function CargoStabilityPanel() {
  const { jansenParams, cargoPayloadMass, setCargoPayloadMass, cargoGridResult, setCargoGridResult } = useAppStore()
  const [loading, setLoading] = useState(false)
  const [heightData, setHeightData] = useState<CargoHeightPoint[]>([])
  const [massData, setMassData] = useState<CargoMassPoint[]>([])

  const fetchGrid = async () => {
    setLoading(true)
    try {
      const res = await cargoApi.getStabilityGrid({
        parameters: jansenParams,
        payload_mass: cargoPayloadMass,
      })
      setCargoGridResult(res.data as CargoStabilityGridResult)
    } catch (error) {
      console.error('获取货箱稳定性网格失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const fetchEffects = async () => {
      try {
        const [heightRes, massRes] = await Promise.all([
          cargoApi.getHeightEffect({ parameters: jansenParams, payload_mass: cargoPayloadMass }),
          cargoApi.getMassEffect({ parameters: jansenParams }),
        ])
        setHeightData(heightRes.data)
        setMassData(massRes.data)
      } catch (error) {
        console.error('获取货箱效应数据失败:', error)
      }
    }
    fetchEffects()
  }, [jansenParams, cargoPayloadMass])

  const gridColumns = [
    { title: 'X (mm)', dataIndex: 'x', key: 'x' },
    { title: 'Z (mm)', dataIndex: 'z', key: 'z' },
    { title: '最小裕度', dataIndex: 'min_margin', key: 'min_margin', render: (v: number) => v?.toFixed(2) },
    { title: '平均裕度', dataIndex: 'avg_margin', key: 'avg_margin', render: (v: number) => v?.toFixed(2) },
    { title: '倾覆风险', dataIndex: 'tipping_risk', key: 'tipping_risk', render: (v: number) => <Tag color={v > 0.7 ? 'red' : v > 0.3 ? 'orange' : 'green'}>{v?.toFixed(2)}</Tag> },
    { title: '稳定', dataIndex: 'is_stable', key: 'is_stable', render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '是' : '否'}</Tag> },
  ]

  return (
    <div className="space-y-4">
      <Card title={<span><UnorderedListOutlined className="mr-2" />货箱装载位置稳定性分析</span>}>
        <Row gutter={16} align="middle" className="mb-4">
          <Col>
            <span className="mr-2">载重 (kg):</span>
            <InputNumber min={0} max={1000} value={cargoPayloadMass} onChange={(v) => setCargoPayloadMass(v ?? 150)} />
          </Col>
          <Col>
            <Button type="primary" onClick={fetchGrid} loading={loading}>分析稳定性</Button>
          </Col>
        </Row>
      </Card>

      {cargoGridResult && (
        <>
          <Card title="最优装载位置">
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="最优 X" value={cargoGridResult.optimal_position.x} suffix="mm" />
              </Col>
              <Col span={8}>
                <Statistic title="最优 Z" value={cargoGridResult.optimal_position.z} suffix="mm" />
              </Col>
              <Col span={8}>
                <Statistic title="危险区域数" value={cargoGridResult.dangerous_zones?.length ?? 0} />
              </Col>
            </Row>
          </Card>

          <Card title="稳定性网格">
            <Table
              columns={gridColumns}
              dataSource={cargoGridResult.grid?.map((p: CargoStabilityPoint, i: number) => ({ key: i, ...p })) ?? []}
              pagination={{ pageSize: 10 }}
              size="small"
              bordered
              scroll={{ y: 300 }}
            />
          </Card>

          {cargoGridResult.dangerous_zones?.length > 0 && (
            <Card title="危险区域">
              {cargoGridResult.dangerous_zones.map((zone, i) => (
                <p key={i}><Tag color="red">危险</Tag> X={zone.x}, Z={zone.z}: {zone.reason}</p>
              ))}
            </Card>
          )}
        </>
      )}

      {heightData.length > 0 && (
        <Card title="高度效应">
          <Table
            columns={[
              { title: '高度 (mm)', dataIndex: 'height', key: 'height' },
              { title: '最小裕度', dataIndex: 'min_margin', key: 'min_margin', render: (v: number) => v?.toFixed(2) },
              { title: '倾覆风险', dataIndex: 'tipping_risk', key: 'tipping_risk', render: (v: number) => <Tag color={v > 0.7 ? 'red' : 'green'}>{v?.toFixed(2)}</Tag> },
            ]}
            dataSource={heightData.map((d, i) => ({ key: i, ...d }))}
            pagination={false}
            size="small"
            bordered
          />
        </Card>
      )}

      {massData.length > 0 && (
        <Card title="质量效应">
          <Table
            columns={[
              { title: '质量 (kg)', dataIndex: 'mass', key: 'mass' },
              { title: '最小裕度', dataIndex: 'min_margin', key: 'min_margin', render: (v: number) => v?.toFixed(2) },
              { title: '倾覆风险', dataIndex: 'tipping_risk', key: 'tipping_risk', render: (v: number) => <Tag color={v > 0.7 ? 'red' : 'green'}>{v?.toFixed(2)}</Tag> },
              { title: '最大安全倾角', dataIndex: 'max_safe_inclination', key: 'max_safe_inclination', render: (v: number) => `${v?.toFixed(1)}°` },
            ]}
            dataSource={massData.map((d, i) => ({ key: i, ...d }))}
            pagination={false}
            size="small"
            bordered
          />
        </Card>
      )}
    </div>
  )
}

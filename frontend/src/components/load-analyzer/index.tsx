import { useState, useEffect } from 'react'
import { Card, Row, Col, Select, Table, Tag, Statistic, InputNumber, Button } from 'antd'
import { UnorderedListOutlined } from '@ant-design/icons'
import { cargoApi } from '@/utils/api'
import { useAppStore } from '@/store/useAppStore'
import { gridColumns, heightEffectColumns, massEffectColumns, mapGridData, mapHeightData, mapMassData } from './utils'
import type { CargoStabilityGridResult, CargoHeightPoint, CargoMassPoint } from './types'

export function LoadAnalyzer() {
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
              dataSource={mapGridData(cargoGridResult.grid)}
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
            columns={heightEffectColumns}
            dataSource={mapHeightData(heightData)}
            pagination={false}
            size="small"
            bordered
          />
        </Card>
      )}

      {massData.length > 0 && (
        <Card title="质量效应">
          <Table
            columns={massEffectColumns}
            dataSource={mapMassData(massData)}
            pagination={false}
            size="small"
            bordered
          />
        </Card>
      )}
    </div>
  )
}

export { LoadAnalyzer as CargoStabilityPanel }
export type * from './types'

import { Tag } from 'antd'
import type { CargoStabilityPoint, CargoHeightPoint, CargoMassPoint, HeightEffectRow, MassEffectRow, GridColumn } from './types'

export function getTippingRiskColor(risk: number): string {
  if (risk > 0.7) return 'red'
  if (risk > 0.3) return 'orange'
  return 'green'
}

export function formatTippingRisk(risk: number): React.ReactNode {
  return <Tag color={getTippingRiskColor(risk)}>{risk?.toFixed(2)}</Tag>
}

export function formatBooleanStable(isStable: boolean): React.ReactNode {
  return <Tag color={isStable ? 'green' : 'red'}>{isStable ? '是' : '否'}</Tag>
}

export const gridColumns: GridColumn[] = [
  { title: 'X (mm)', dataIndex: 'x', key: 'x' },
  { title: 'Z (mm)', dataIndex: 'z', key: 'z' },
  { title: '最小裕度', dataIndex: 'min_margin', key: 'min_margin', render: (v: number) => v?.toFixed(2) },
  { title: '平均裕度', dataIndex: 'avg_margin', key: 'avg_margin', render: (v: number) => v?.toFixed(2) },
  { title: '倾覆风险', dataIndex: 'tipping_risk', key: 'tipping_risk', render: formatTippingRisk },
  { title: '稳定', dataIndex: 'is_stable', key: 'is_stable', render: formatBooleanStable },
]

export const heightEffectColumns: GridColumn[] = [
  { title: '高度 (mm)', dataIndex: 'height', key: 'height' },
  { title: '最小裕度', dataIndex: 'min_margin', key: 'min_margin', render: (v: number) => v?.toFixed(2) },
  { title: '倾覆风险', dataIndex: 'tipping_risk', key: 'tipping_risk', render: formatTippingRisk },
]

export const massEffectColumns: GridColumn[] = [
  { title: '质量 (kg)', dataIndex: 'mass', key: 'mass' },
  { title: '最小裕度', dataIndex: 'min_margin', key: 'min_margin', render: (v: number) => v?.toFixed(2) },
  { title: '倾覆风险', dataIndex: 'tipping_risk', key: 'tipping_risk', render: formatTippingRisk },
  { title: '最大安全倾角', dataIndex: 'max_safe_inclination', key: 'max_safe_inclination', render: (v: number) => `${v?.toFixed(1)}°` },
]

export function mapGridData(grid: CargoStabilityPoint[] | undefined): any[] {
  return grid?.map((p: CargoStabilityPoint, i: number) => ({ key: i, ...p })) ?? []
}

export function mapHeightData(heightData: CargoHeightPoint[]): HeightEffectRow[] {
  return heightData.map((d, i) => ({ key: i, ...d }))
}

export function mapMassData(massData: CargoMassPoint[]): MassEffectRow[] {
  return massData.map((d, i) => ({ key: i, ...d }))
}

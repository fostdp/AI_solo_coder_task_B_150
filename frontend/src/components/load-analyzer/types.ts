export type { CargoStabilityGridResult, CargoStabilityPoint, CargoHeightPoint, CargoMassPoint } from '@/types'

export interface GridColumn {
  title: string
  dataIndex: string
  key: string
  render?: (v: any) => React.ReactNode
  width?: number
}

export interface HeightEffectRow {
  key: number
  height: number
  min_margin: number
  tipping_risk: number
}

export interface MassEffectRow {
  key: number
  mass: number
  min_margin: number
  tipping_risk: number
  max_safe_inclination: number
}

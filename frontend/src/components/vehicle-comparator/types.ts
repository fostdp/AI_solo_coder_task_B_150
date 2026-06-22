export type { TransportComparisonResult, TransportRadarData, TerrainTypeKey } from '@/types'

export interface TerrainOption {
  value: TerrainTypeKey
  label: string
}

export interface TableRow {
  key: number
  metric: string
  wooden_ox: number
  wheelbarrow: number
  horse_carriage: number
}

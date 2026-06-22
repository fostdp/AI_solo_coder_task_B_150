import type { TransportComparisonResult, TerrainTypeKey, TerrainOption, TableRow } from './types'

export const terrainOptions: TerrainOption[] = [
  { value: 'flat', label: '平地' },
  { value: 'gentle_slope', label: '缓坡' },
  { value: 'steep_slope', label: '陡坡' },
  { value: 'rocky', label: '碎石' },
  { value: 'muddy', label: '泥泞' },
  { value: 'stairs', label: '台阶' },
  { value: 'obstacle', label: '障碍' },
]

const metricKeys = [
  'max_obstacle_height',
  'max_slope_angle',
  'pass_probability',
  'stability_on_slope',
  'energy_efficiency',
  'payload_capacity',
  'speed_on_flat',
  'speed_on_slope',
  'terrain_adaptability',
] as const

const metricLabels: Record<string, string> = {
  max_obstacle_height: '最大越障高度 (mm)',
  max_slope_angle: '最大爬坡角 (°)',
  pass_probability: '通过概率',
  stability_on_slope: '坡道稳定性',
  energy_efficiency: '能量效率',
  payload_capacity: '载重能力 (kg)',
  speed_on_flat: '平地速度 (mm/s)',
  speed_on_slope: '坡道速度 (mm/s)',
  terrain_adaptability: '地形适应性',
}

export function getTableData(comparison: TransportComparisonResult | null): TableRow[] {
  if (!comparison) return []
  return metricKeys.map((key, i) => ({
    key: i,
    metric: metricLabels[key],
    wooden_ox: (comparison.wooden_ox as any)[key],
    wheelbarrow: (comparison.wheelbarrow as any)[key],
    horse_carriage: (comparison.horse_carriage as any)[key],
  }))
}

import type { EraComparisonResult, EraKey, EraNameMap, EraColorMap, TableRow } from './types'

export const eraNames: EraNameMap = {
  WoodenOx: '木牛流马',
  Spot: 'Spot',
  Cheetah: 'Cheetah',
  ANYmal: 'ANYmal',
}

export const eraColors: EraColorMap = {
  WoodenOx: 'blue',
  Spot: 'green',
  Cheetah: 'orange',
  ANYmal: 'purple',
}

const metricKeys = [
  'mechanical_complexity',
  'max_obstacle_height',
  'max_slope_angle',
  'speed',
  'payload_ratio',
  'autonomy_hours',
  'terrain_types_supported',
  'noise_level_db',
  'cost_estimate_relative',
  'control_method',
  'power_source',
  'sensing_capability',
  'self_recovery',
  'historical_significance',
  'innovation_index',
] as const

const metricLabels: Record<string, string> = {
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

export function getTableData(eraData: EraComparisonResult | null): TableRow[] {
  if (!eraData) return []
  return metricKeys.map((key, i) => ({
    key: i,
    metric: metricLabels[key],
    WoodenOx: (eraData.WoodenOx as any)[key],
    Spot: (eraData.Spot as any)[key],
    Cheetah: (eraData.Cheetah as any)[key],
    ANYmal: (eraData.ANYmal as any)[key],
  }))
}

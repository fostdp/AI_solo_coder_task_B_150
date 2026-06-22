export interface Point3D {
  x: number
  y: number
  z: number
}

export interface Point2D {
  x: number
  y: number
}

export interface SensorData {
  timestamp: string
  device_id: string
  crank_angle: number
  leg_displacement: number
  body_inclination: number
  ground_elevation: number
}

export interface JansenParameters {
  crank_length: number
  rocker_length: number
  coupler_length: number
  ground_link: number
  crank_speed: number
  body_mass: number
  leg_mass: number
  payload_mass: number
  payload_offset_x: number
  payload_offset_y: number
  payload_offset_z: number
  friction_coefficient: number
  ground_stiffness: number
  damping_coefficient: number
  foot_radius: number
}

export interface GroundContactState {
  is_contact: boolean
  contact_depth: number
  normal_force: number
  tangential_force: number
  friction_force: number
  is_slipping: boolean
  slip_velocity: Point3D
  slip_distance: number
  contact_area: number
  pressure_distribution: number
}

export interface COMAdjustmentState {
  target_com: Point3D
  current_com: Point3D
  adjustment_offset: Point3D
  payload_mass: number
  body_inclination_compensation: number
  adjustment_factor: number
  is_adjusting: boolean
  adjustment_remaining: number
}

export interface LinkageState {
  crank_angle: number
  joints: Record<string, Point3D>
  foot_position: Point3D
  link_angles: Record<string, number>
  is_singular: boolean
  ground_contact?: GroundContactState
  com_adjustment?: COMAdjustmentState
}

export type TerrainType = 'ice' | 'mud' | 'wet_grass' | 'gravel' | 'normal' | 'dry_grass' | 'wood' | 'concrete' | 'rubber'

export interface GaitAnalysisResult {
  device_id: string
  timestamp: string
  stride_length: number
  cadence: number
  support_phase: number
  swing_phase: number
  stability_margin: number
  gait_symmetry: number
  com_trajectory: Point3D[]
  zmp_trajectory: Point2D[]
  foot_trajectory: Point3D[]
  parameters: JansenParameters
}

export interface TerrainPoint {
  x: number
  y: number
  elevation: number
}

export interface TerrainData {
  grid_size: number
  resolution: number
  points: TerrainPoint[]
}

export interface ObstacleAssessmentRequest {
  device_id: string
  terrain_data: TerrainData
  current_inclination: number
  current_speed: number
  parameters: JansenParameters
}

export interface ObstacleAssessmentResult {
  device_id: string
  timestamp: string
  max_obstacle_height: number
  max_slope_angle: number
  critical_inclination: number
  obstacle_pass_probability: number
  recommended_speed: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  terrain_analysis: Record<string, number>
  parameters: JansenParameters
}

export enum AlertType {
  INCLINATION_EXCEEDED = 'INCLINATION_EXCEEDED',
  MECHANISM_JAMMED = 'MECHANISM_JAMMED',
  SENSOR_FAULT = 'SENSOR_FAULT'
}

export enum AlertLevel {
  INFO = 'INFO',
  WARNING = 'WARNING',
  CRITICAL = 'CRITICAL'
}

export interface Alert {
  id: string
  timestamp: string
  type: AlertType
  level: AlertLevel
  message: string
  device_id: string
  sensor_data: SensorData
  acknowledged: boolean
}

export interface WebSocketMessage {
  type: string
  payload: Record<string, any>
}

export interface StabilityAnalysisResult {
  static_stability: number
  dynamic_stability: number
  critical_inclination: number
  stability_margin: number
  com_position: Point3D
  zmp_position: Point2D
  support_polygon: Point2D[]
  risk_assessment: string
}

export interface DerivedMetrics {
  angular_velocity: number
  leg_velocity: number
  inclination_rate: number
  ground_gradient: number
  energy_consumption: number
  power_efficiency: number
}

export interface DataQuality {
  score: number
  issues: string[]
  validity: Record<string, boolean>
}

export type TransportType = 'wooden_ox' | 'wheelbarrow' | 'horse_carriage'
export type TerrainTypeKey = 'flat' | 'gentle_slope' | 'steep_slope' | 'rocky' | 'muddy' | 'stairs' | 'obstacle'
export type EraKey = 'WoodenOx' | 'Spot' | 'Cheetah' | 'ANYmal'

export interface TransportMetrics {
  name: string; name_en: string; mechanism: string
  max_obstacle_height: number; max_slope_angle: number; pass_probability: number
  stability_on_slope: number; energy_efficiency: number; payload_capacity: number
  speed_on_flat: number; speed_on_slope: number; terrain_adaptability: number
}
export interface TransportComparisonResult {
  wooden_ox: TransportMetrics; wheelbarrow: TransportMetrics; horse_carriage: TransportMetrics
  comparison_summary: Record<string, string>
}
export interface RadarAxis { label: string; key: string }
export interface RadarDataset { transport: string; name: string; name_en: string; values: number[]; color: string }
export interface TransportRadarData { terrain_type: string; axes: RadarAxis[]; datasets: RadarDataset[]; raw_metrics: Record<string, TransportMetrics> }

export interface EraMetrics {
  mechanical_complexity: number; max_obstacle_height: number; max_slope_angle: number
  speed: number; payload_ratio: number; autonomy_hours: number; terrain_types_supported: number
  noise_level_db: number; cost_estimate_relative: number; control_method: string; power_source: string
  sensing_capability: number; self_recovery: boolean; historical_significance: number; innovation_index: number
}
export interface EraComparisonResult { WoodenOx: EraMetrics; Spot: EraMetrics; Cheetah: EraMetrics; ANYmal: EraMetrics }
export interface EraRadarAxis { axis: string; value: number; normalized: number }
export interface EraTimelineEvent { year: number; era: string; event: string; description: string }

export interface CargoStabilityPoint { x: number; z: number; min_margin: number; avg_margin: number; max_zmp_dev: number; tipping_risk: number; is_stable: boolean }
export interface CargoStabilityGridResult { grid: CargoStabilityPoint[]; optimal_position: { x: number; z: number }; dangerous_zones: Array<{ x: number; z: number; reason: string }>; safe_zone_boundary: Array<{ x: number; z: number }> }
export interface CargoHeightPoint { height: number; min_margin: number; avg_margin: number; tipping_risk: number }
export interface CargoMassPoint { mass: number; min_margin: number; avg_margin: number; tipping_risk: number; max_safe_inclination: number }

export interface DrivingControlInput { device_id: string; acceleration: number; steering: number; brake: number; speed_override?: number; inclination_override?: number }
export interface DrivingState { device_id: string; timestamp: string; crank_speed: number; crank_angle: number; walking_speed: number; body_inclination: number; turn_rate: number; heading: number; position_x: number; position_y: number; stability_margin: number; is_moving: boolean; is_braking: boolean; total_distance: number; leg_states: Record<string, any> }
export interface GamepadState { connected: boolean; id: string; axisX: number; axisY: number; axisZ: number; axisRz: number; buttonA: boolean; buttonB: boolean; buttonX: boolean; buttonY: boolean; buttonLeft: boolean; buttonRight: boolean; buttonStart: boolean; buttonSelect: boolean }

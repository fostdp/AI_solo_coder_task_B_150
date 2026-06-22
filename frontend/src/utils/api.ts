import axios from 'axios'
import type {
  SensorData, Alert, GaitAnalysisResult, ObstacleAssessmentResult,
  ObstacleAssessmentRequest, LinkageState, JansenParameters,
  StabilityAnalysisResult, GroundContactState, COMAdjustmentState,
  TerrainType, Point3D
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const sensorApi = {
  getRealtime: (deviceId: string) =>
    api.get<SensorData>('/sensors/realtime', { params: { device_id: deviceId } }),

  getHistory: (deviceId: string, startTime?: string, endTime?: string, limit = 1000) =>
    api.get<SensorData[]>('/sensors/history', {
      params: { device_id: deviceId, start_time: startTime, end_time: endTime, limit },
    }),

  ingest: (data: SensorData) =>
    api.post('/sensors/ingest', data),

  getStatistics: (deviceId: string, windowMinutes = 5) =>
    api.get('/sensors/statistics', { params: { device_id: deviceId, window_minutes: windowMinutes } }),

  getDerived: (deviceId: string, count = 10) =>
    api.get('/sensors/derived', { params: { device_id: deviceId, count } }),

  getQuality: (deviceId: string) =>
    api.get('/sensors/quality', { params: { device_id: deviceId } }),

  getTrend: (deviceId: string) =>
    api.get('/sensors/trend', { params: { device_id: deviceId } }),
}

export const simulationApi = {
  computeGait: (deviceId: string, parameters?: JansenParameters, crankAngle?: number, bodyInclination = 0) =>
    api.post<GaitAnalysisResult>('/simulation/gait', parameters, {
      params: { device_id: deviceId, crank_angle: crankAngle, body_inclination: bodyInclination },
    }),

  getLinkage: (crankAngle: number, params?: Partial<JansenParameters>) =>
    api.get<LinkageState>('/simulation/linkage', {
      params: { crank_angle: crankAngle, ...params },
    }),

  getFootTrajectory: (startAngle = 0, endAngle = 360, steps = 360, params?: Partial<JansenParameters>) =>
    api.get('/simulation/foot-trajectory', {
      params: { start_angle: startAngle, end_angle: endAngle, steps, ...params },
    }),

  getGaitPhase: (crankAngle: number, numPhases = 8) =>
    api.get('/simulation/gait-phase', {
      params: { crank_angle: crankAngle, num_phases: numPhases },
    }),

  computeSymmetry: (leftOffset = 180, params?: Partial<JansenParameters>) =>
    api.get('/simulation/gait-symmetry', {
      params: { left_crank_offset: leftOffset, ...params },
    }),

  predictStability: (currentInclination = 0, targetSpeed = 30, roughness = 0) =>
    api.get('/simulation/stability-prediction', {
      params: {
        current_inclination: currentInclination,
        target_speed: targetSpeed,
        terrain_roughness: roughness,
      },
    }),

  computeGroundContact: (request: {
    crank_angle: number
    ground_elevation?: number
    terrain_type?: TerrainType
    total_mass?: number
    num_support_legs?: number
    parameters: JansenParameters
  }) =>
    api.post<GroundContactState>('/simulation/ground-contact', request),

  computeCOMAdjustment: (request: {
    crank_angle: number
    body_inclination?: number
    payload_mass?: number
    payload_offset?: Point3D
    num_support_legs?: number
    parameters: JansenParameters
  }) =>
    api.post<LinkageState>('/simulation/com-adjustment', request),

  getFrictionCoefficients: () =>
    api.get<Record<TerrainType, number>>('/simulation/friction-coefficients'),

  getLinkageWithEffects: (params: {
    crank_angle: number
    ground_elevation?: number
    terrain_type?: TerrainType
    body_inclination?: number
    payload_mass?: number
    payload_offset_x?: number
    payload_offset_y?: number
    payload_offset_z?: number
    num_support_legs?: number
    parameters?: JansenParameters
  }) =>
    api.post<LinkageState>('/simulation/linkage-with-effects', null, { params }),
}

export const analysisApi = {
  assessObstacle: (request: ObstacleAssessmentRequest) =>
    api.post<ObstacleAssessmentResult>('/analysis/obstacle', request),

  analyzeStaticStability: (crankAngle: number, bodyInclination = 0, parameters?: JansenParameters) =>
    api.post<StabilityAnalysisResult>('/analysis/stability/static', parameters, {
      params: { crank_angle: crankAngle, body_inclination: bodyInclination },
    }),

  getCriticalInclination: (crankAngle: number, direction = 'pitch', parameters?: JansenParameters) =>
    api.get('/analysis/stability/critical-inclination', {
      params: { crank_angle: crankAngle, direction, parameters },
    }),

  simulateObstacle: (obstacleHeight: number, obstacleWidth = 200, approachSpeed = 30, bodyInclination = 0, parameters?: JansenParameters) =>
    api.post('/analysis/obstacle/simulate', parameters, {
      params: {
        obstacle_height: obstacleHeight, obstacle_width: obstacleWidth,
        approach_speed: approachSpeed, body_inclination: bodyInclination,
      },
    }),
}

export const alertApi = {
  getCurrent: (deviceId?: string) =>
    api.get<Alert[]>('/alerts/current', { params: { device_id: deviceId } }),

  getHistory: (params?: {
    start_time?: string
    end_time?: string
    alert_type?: string
    device_id?: string
    acknowledged?: boolean
    limit?: number
  }) =>
    api.get('/alerts/history', { params }),

  acknowledge: (alertId: string) =>
    api.put(`/alerts/${alertId}/acknowledge`),

  getStatistics: (hours = 24) =>
    api.get('/alerts/statistics', { params: { hours } }),

  testAlert: (deviceId: string, alertType: string, level = 'WARNING') =>
    api.post('/alerts/test', {
      params: { device_id: deviceId, alert_type: alertType, level },
    }),
}

export const comparisonApi = {
  compareTransportObstacle: (terrain_type: string, parameters?: JansenParameters) => api.post('/comparison/transport/obstacle-clearing', { terrain_type, parameters }),
  compareTransportByTerrain: (terrainType: string) => api.get('/comparison/transport/terrain', { params: { terrain_type: terrainType } }),
  getTransportProfiles: (parameters?: JansenParameters) => api.get('/comparison/transport/profiles', { params: parameters }),
  getTransportRadar: (terrainType: string = 'flat') => api.get('/comparison/transport/radar', { params: { terrain_type: terrainType } }),
  getEraAllMetrics: (parameters?: JansenParameters) => api.get('/comparison/era/all-metrics', { params: parameters }),
  getEraRadar: (parameters?: JansenParameters) => api.get('/comparison/era/radar', { params: parameters }),
  getEraTimeline: () => api.get('/comparison/era/timeline'),
  getEraMechanism: (parameters?: JansenParameters) => api.get('/comparison/era/mechanism', { params: parameters }),
}
export const cargoApi = {
  getStabilityGrid: (request: any) => api.post('/cargo/stability-grid', request),
  findOptimalPosition: (parameters: JansenParameters, payload_mass: number, body_inclination?: number) => api.post('/cargo/optimal-position', { parameters, payload_mass, body_inclination }),
  getHeightEffect: (request: any) => api.post('/cargo/height-effect', request),
  getMassEffect: (request: any) => api.post('/cargo/mass-effect', request),
}
export const drivingApi = {
  sendControl: (control: any) => api.post('/driving/control', control),
  getState: (deviceId: string) => api.get(`/driving/state/${deviceId}`),
  reset: (deviceId: string) => api.post(`/driving/reset/${deviceId}`),
  setParams: (deviceId: string, parameters: JansenParameters) => api.post(`/driving/params/${deviceId}`, parameters),
}

export const systemApi = {
  getInfo: () => api.get('/info'),
  getHealth: () => api.get('/health'),
}

export default api

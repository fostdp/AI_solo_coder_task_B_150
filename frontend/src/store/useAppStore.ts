import { create } from 'zustand'
import type { SensorData, Alert, JansenParameters, LinkageState, DrivingState, GamepadState, CargoStabilityGridResult } from '@/types'

interface AppState {
  selectedDevice: string
  setSelectedDevice: (device: string) => void

  sensorData: SensorData | null
  setSensorData: (data: SensorData | null) => void

  sensorHistory: SensorData[]
  setSensorHistory: (data: SensorData[]) => void
  addSensorData: (data: SensorData) => void

  alerts: Alert[]
  setAlerts: (alerts: Alert[]) => void
  addAlert: (alert: Alert) => void
  acknowledgeAlert: (alertId: string) => void

  jansenParams: JansenParameters
  setJansenParams: (params: Partial<JansenParameters>) => void

  linkageState: LinkageState | null
  setLinkageState: (state: LinkageState | null) => void

  crankAngle: number
  setCrankAngle: (angle: number) => void

  bodyInclination: number
  setBodyInclination: (angle: number) => void

  isPlaying: boolean
  setIsPlaying: (playing: boolean) => void

  showTrajectory: boolean
  setShowTrajectory: (show: boolean) => void

  showLinkages: boolean
  setShowLinkages: (show: boolean) => void

  obstacleHeight: number
  setObstacleHeight: (height: number) => void

  simulationSpeed: number
  setSimulationSpeed: (speed: number) => void

  wsConnected: boolean
  setWsConnected: (connected: boolean) => void

  drivingState: DrivingState | null
  setDrivingState: (state: DrivingState | null) => void

  drivingWsConnected: boolean
  setDrivingWsConnected: (connected: boolean) => void

  lastControlInput: { acceleration: number; steering: number; brake: number } | null
  setLastControlInput: (input: { acceleration: number; steering: number; brake: number } | null) => void

  gamepadState: GamepadState | null
  setGamepadState: (state: GamepadState | null) => void

  cargoGridResult: CargoStabilityGridResult | null
  setCargoGridResult: (result: CargoStabilityGridResult | null) => void

  cargoPayloadMass: number
  setCargoPayloadMass: (mass: number) => void

  cargoPosition: { x: number; z: number }
  setCargoPosition: (pos: { x: number; z: number }) => void
}

const defaultJansenParams: JansenParameters = {
  crank_length: 150,
  rocker_length: 250,
  coupler_length: 300,
  ground_link: 200,
  crank_speed: 30,
  body_mass: 50,
  leg_mass: 10,
}

export const useAppStore = create<AppState>((set, get) => ({
  selectedDevice: 'woodox_001',
  setSelectedDevice: (device) => set({ selectedDevice: device }),

  sensorData: null,
  setSensorData: (data) => set({ sensorData: data }),

  sensorHistory: [],
  setSensorHistory: (data) => set({ sensorHistory: data }),
  addSensorData: (data) =>
    set((state) => ({
      sensorHistory: [...state.sensorHistory.slice(-99), data],
    })),

  alerts: [],
  setAlerts: (alerts) => set({ alerts }),
  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts.slice(0, 49)],
    })),
  acknowledgeAlert: (alertId) =>
    set((state) => ({
      alerts: state.alerts.map((a) =>
        a.id === alertId ? { ...a, acknowledged: true } : a
      ),
    })),

  jansenParams: defaultJansenParams,
  setJansenParams: (params) =>
    set((state) => ({
      jansenParams: { ...state.jansenParams, ...params },
    })),

  linkageState: null,
  setLinkageState: (state) => set({ linkageState: state }),

  crankAngle: 0,
  setCrankAngle: (angle) => set({ crankAngle: angle }),

  bodyInclination: 0,
  setBodyInclination: (angle) => set({ bodyInclination: angle }),

  isPlaying: false,
  setIsPlaying: (playing) => set({ isPlaying: playing }),

  showTrajectory: true,
  setShowTrajectory: (show) => set({ showTrajectory: show }),

  showLinkages: true,
  setShowLinkages: (show) => set({ showLinkages: show })),

  obstacleHeight: 0,
  setObstacleHeight: (height) => set({ obstacleHeight: height }),

  simulationSpeed: 1,
  setSimulationSpeed: (speed) => set({ simulationSpeed: speed }),

  wsConnected: false,
  setWsConnected: (connected) => set({ wsConnected: connected }),

  drivingState: null,
  setDrivingState: (state) => set({ drivingState: state }),

  drivingWsConnected: false,
  setDrivingWsConnected: (connected) => set({ drivingWsConnected: connected }),

  lastControlInput: null,
  setLastControlInput: (input) => set({ lastControlInput: input }),

  gamepadState: null,
  setGamepadState: (state) => set({ gamepadState: state }),

  cargoGridResult: null,
  setCargoGridResult: (result) => set({ cargoGridResult: result }),

  cargoPayloadMass: 150,
  setCargoPayloadMass: (mass) => set({ cargoPayloadMass: mass }),

  cargoPosition: { x: 0, z: 0 },
  setCargoPosition: (pos) => set({ cargoPosition: pos }),
}))

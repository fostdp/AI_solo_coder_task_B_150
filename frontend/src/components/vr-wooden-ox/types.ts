export type { DrivingState, GamepadState } from '@/types'

export type ResponseCurveType = 'linear' | 'quadratic' | 'cubic'
export type GamepadButtonKey = 'buttonA' | 'buttonB' | 'buttonX' | 'buttonY'
export type ActionType = 'accelerate' | 'brake' | 'reset' | 'emergencyStop' | 'boost' | 'horn'

export interface GamepadMapping {
  accelerate: GamepadButtonKey | null
  brake: GamepadButtonKey | null
  reset: GamepadButtonKey | null
  emergencyStop: GamepadButtonKey | null
  boost: GamepadButtonKey | null
  horn: GamepadButtonKey | null
}

export interface CalibrationData {
  centerX: number
  centerY: number
  centerZ: number
  centerRz: number
  maxX: number
  maxY: number
  maxZ: number
  maxRz: number
  calibrated: boolean
}

export interface ButtonOption {
  value: string
  label: string
}

export interface KeyMapping {
  axis: 'acceleration' | 'steering' | 'brake'
  value: number
}

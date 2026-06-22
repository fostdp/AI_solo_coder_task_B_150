import type { ResponseCurveType } from './types'

export function applyDeadzone(value: number, threshold: number): number {
  if (Math.abs(value) < threshold) return 0
  const sign = value > 0 ? 1 : -1
  return sign * ((Math.abs(value) - threshold) / (1 - threshold))
}

export function applyResponseCurve(value: number, curve: ResponseCurveType): number {
  const sign = value > 0 ? 1 : -1
  const abs = Math.abs(value)
  switch (curve) {
    case 'quadratic':
      return sign * abs * abs
    case 'cubic':
      return sign * abs * abs * abs
    case 'linear':
    default:
      return value
  }
}

export function applySensitivity(value: number, sens: number): number {
  const result = value * sens
  return Math.max(-1, Math.min(1, result))
}

export function processAxis(
  rawValue: number,
  deadzone: number,
  responseCurve: ResponseCurveType,
  sensitivity: number
): number {
  const deadzoned = applyDeadzone(rawValue, deadzone)
  const curved = applyResponseCurve(deadzoned, responseCurve)
  const scaled = applySensitivity(curved, sensitivity)
  return scaled
}

export function calibrateAxis(
  rawValue: number,
  center: number,
  max: number
): number {
  const calibrated = (rawValue - center) / (max || 1)
  return Math.max(-1, Math.min(1, calibrated))
}

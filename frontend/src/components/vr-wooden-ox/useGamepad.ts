import { useEffect, useRef, useCallback } from 'react'
import type { GamepadState, CalibrationData } from './types'

interface UseGamepadOptions {
  setGamepadState: (state: GamepadState) => void
  calibrating: boolean
  setCalibration: React.Dispatch<React.SetStateAction<CalibrationData>>
}

export function useGamepad({ setGamepadState, calibrating, setCalibration }: UseGamepadOptions) {
  const rafIdRef = useRef<number | null>(null)

  const pollGamepad = useCallback(() => {
    const gamepads = navigator.getGamepads()
    if (gamepads[0]) {
      const gp = gamepads[0]
      const state: GamepadState = {
        connected: true,
        id: gp.id,
        axisX: gp.axes[0] ?? 0,
        axisY: gp.axes[1] ?? 0,
        axisZ: gp.axes[2] ?? 0,
        axisRz: gp.axes[3] ?? 0,
        buttonA: gp.buttons[0]?.pressed ?? false,
        buttonB: gp.buttons[1]?.pressed ?? false,
        buttonX: gp.buttons[2]?.pressed ?? false,
        buttonY: gp.buttons[3]?.pressed ?? false,
        buttonLeft: gp.buttons[14]?.pressed ?? false,
        buttonRight: gp.buttons[15]?.pressed ?? false,
        buttonStart: gp.buttons[9]?.pressed ?? false,
        buttonSelect: gp.buttons[8]?.pressed ?? false,
      }
      setGamepadState(state)

      if (calibrating) {
        setCalibration(prev => ({
          ...prev,
          maxX: Math.max(prev.maxX, Math.abs(state.axisX)),
          maxY: Math.max(prev.maxY, Math.abs(state.axisY)),
          maxZ: Math.max(prev.maxZ, Math.abs(state.axisZ)),
          maxRz: Math.max(prev.maxRz, Math.abs(state.axisRz)),
        }))
      }
    }
    rafIdRef.current = requestAnimationFrame(pollGamepad)
  }, [setGamepadState, calibrating, setCalibration])

  useEffect(() => {
    rafIdRef.current = requestAnimationFrame(pollGamepad)
    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current)
      }
    }
  }, [pollGamepad])
}

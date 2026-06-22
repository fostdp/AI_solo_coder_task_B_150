import { useEffect, useRef, useCallback } from 'react'
import { useAppStore } from '@/store/useAppStore'
import type { SensorData, Alert } from '@/types'

interface UseWebSocketOptions {
  deviceId: string
  onSensorData?: (data: SensorData) => void
  onAlert?: (alert: Alert) => void
  onConnectionChange?: (connected: boolean) => void
}

export function useWebSocket(options: UseWebSocketOptions) {
  const { deviceId, onSensorData, onAlert, onConnectionChange } = options

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const { addSensorData, addAlert, setWsConnected, setSensorData } = useAppStore()

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/alerts/ws?device_id=${deviceId}`

    try {
      wsRef.current = new WebSocket(wsUrl)

      wsRef.current.onopen = () => {
        console.log('WebSocket连接已建立')
        setWsConnected(true)
        onConnectionChange?.(true)

        wsRef.current?.send(
          JSON.stringify({ action: 'subscribe', device_id: deviceId })
        )
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)

          if (message.type === 'SENSOR_DATA') {
            const sensorData = message.payload as SensorData
            setSensorData(sensorData)
            addSensorData(sensorData)
            onSensorData?.(sensorData)
          } else if (message.type === 'ALERT') {
            const alert = message.payload as Alert
            addAlert(alert)
            onAlert?.(alert)
          } else if (message.type === 'SIMULATION_RESULT') {
            console.log('仿真结果:', message.payload)
          }
        } catch (error) {
          console.error('解析WebSocket消息失败:', error)
        }
      }

      wsRef.current.onerror = (error) => {
        console.error('WebSocket错误:', error)
        setWsConnected(false)
        onConnectionChange?.(false)
      }

      wsRef.current.onclose = () => {
        console.log('WebSocket连接已关闭')
        setWsConnected(false)
        onConnectionChange?.(false)

        if (reconnectTimerRef.current === null) {
          reconnectTimerRef.current = window.setTimeout(() => {
            console.log('尝试重新连接...')
            reconnectTimerRef.current = null
            connect()
          }, 5000)
        }
      }
    } catch (error) {
      console.error('创建WebSocket连接失败:', error)
    }
  }, [deviceId, setWsConnected, setSensorData, addSensorData, addAlert, onSensorData, onAlert, onConnectionChange])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }

    wsRef.current?.close()
    wsRef.current = null
    setWsConnected(false)
  }, [setWsConnected])

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    send,
    connect,
    disconnect,
  }
}

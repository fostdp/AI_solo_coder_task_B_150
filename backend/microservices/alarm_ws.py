import sys
import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
from enum import Enum

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config_loader import get_mechanism_config, get_nested_config
from app.core.database import influx_db
from app.core.message_bus import (
    message_bus, CHANNELS, Message,
    publish_alert_triggered, publish_alert_cleared
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('alarm_ws')


class AlertSeverity(str, Enum):
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


class AlertType(str, Enum):
    BODY_INCLINATION = 'body_inclination'
    MECHANICAL_STUCK = 'mechanical_stuck'
    STABILITY_LOW = 'stability_low'
    TERRAIN_DANGEROUS = 'terrain_dangerous'
    OBSTACLE_HIGH_RISK = 'obstacle_high_risk'
    SENSOR_DATA_QUALITY = 'sensor_data_quality'


class Alert:
    def __init__(self, alert_id: str, device_id: str, alert_type: AlertType,
                 severity: AlertSeverity, message: str, payload: Dict[str, Any]):
        self.alert_id = alert_id
        self.device_id = device_id
        self.alert_type = alert_type
        self.severity = severity
        self.message = message
        self.payload = payload
        self.triggered_at = datetime.utcnow()
        self.cleared_at: Optional[datetime] = None
        self.is_active = True
        self.suppressed = False


class AlarmWSService:
    def __init__(self):
        mech_config = get_mechanism_config()
        thresholds = get_nested_config(mech_config, 'alert_thresholds', default={})

        self.inclination_warning = thresholds.get('body_inclination_warning', 10.0)
        self.inclination_critical = thresholds.get('body_inclination_critical', 20.0)
        self.stability_margin_warning = thresholds.get('stability_margin_warning', 20.0)
        self.stability_margin_critical = thresholds.get('stability_margin_critical', 10.0)
        self.sensor_quality_min = thresholds.get('sensor_quality_min', 60.0)
        self.mechanical_stuck_windows = thresholds.get('mechanical_stuck_window_seconds', 30.0)
        self.mechanical_stuck_min_samples = thresholds.get('mechanical_stuck_min_samples', 5)

        self.running = False
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.connected_clients: Set = set()
        self.crank_history: Dict[str, List] = {}

    def register_client(self, client):
        self.connected_clients.add(client)
        logger.info(f"WebSocket客户端已连接，共{len(self.connected_clients)}个客户端")

    def unregister_client(self, client):
        self.connected_clients.discard(client)
        logger.info(f"WebSocket客户端已断开，剩余{len(self.connected_clients)}个客户端")

    async def broadcast_to_clients(self, message: Dict[str, Any]):
        dead_clients = set()
        for client in self.connected_clients:
            try:
                if hasattr(client, 'send_text'):
                    await client.send_text(json.dumps(message, ensure_ascii=False, default=str))
                elif hasattr(client, 'send'):
                    await client.send(json.dumps(message, ensure_ascii=False, default=str))
            except Exception:
                dead_clients.add(client)

        for dead in dead_clients:
            self.unregister_client(dead)

    async def on_sensor_validated(self, message: Message):
        try:
            payload = message.payload
            sensor_data = payload.get('sensor_data', {})
            device_id = sensor_data.get('device_id', 'unknown')
            device = device_id

            if abs(sensor_data.get('body_inclination', 0.0)) > self.inclination_warning:
                await self._trigger_alert(
                    device_id=device,
                    alert_type=AlertType.BODY_INCLINATION,
                    severity=AlertSeverity.CRITICAL if abs(sensor_data['body_inclination']) > self.inclination_critical else AlertSeverity.WARNING,
                    message=f"机身倾角异常: {sensor_data['body_inclination']:.1f}°",
                    payload=sensor_data
                )
            else:
                await self._clear_alert(device, AlertType.BODY_INCLINATION)

            if payload.get('quality_score', 100) < self.sensor_quality_min:
                await self._trigger_alert(
                    device_id=device,
                    alert_type=AlertType.SENSOR_DATA_QUALITY,
                    severity=AlertSeverity.WARNING,
                    message=f"传感器数据质量低: {payload.get('quality_score', 0):.0f}/100",
                    payload=payload
                )

            if device_id not in self.crank_history:
                self.crank_history[device_id] = []
            self.crank_history[device_id].append((
                datetime.utcnow(),
                sensor_data.get('crank_angle', 0)
            ))

            cutoff = datetime.utcnow() - timedelta(seconds=self.mechanical_stuck_windows)
            self.crank_history[device_id] = [
                (t, a) for t, a in self.crank_history[device_id] if t > cutoff
            ]

            if len(self.crank_history[device_id]) >= self.mechanical_stuck_min_samples:
                recent = self.crank_history[device_id][-self.mechanical_stuck_min_samples:]
                angles = [a for _, a in recent]
                if len(set([round(a, 1) for a in angles])) == 1:
                    await self._trigger_alert(
                        device_id=device,
                        alert_type=AlertType.MECHANICAL_STUCK,
                        severity=AlertSeverity.CRITICAL,
                        message=f"检测到机构可能卡死，曲柄角度{angles[0]:.1f}°无变化",
                        payload={'crank_angles': angles}
                    )
                else:
                    await self._clear_alert(device, AlertType.MECHANICAL_STUCK)

        except Exception as e:
            logger.error(f"处理传感器告警数据失败: {e}")

    async def on_gait_result(self, message: Message):
        try:
            payload = message.payload
            device_id = payload.get('device_id', 'unknown')
            margin = payload.get('stability_margin', 100.0)

            if margin < self.stability_margin_warning:
                await self._trigger_alert(
                    device_id=device_id,
                    alert_type=AlertType.STABILITY_LOW,
                    severity=AlertSeverity.CRITICAL if margin < self.stability_margin_critical else AlertSeverity.WARNING,
                    message=f"稳定裕度过低: {margin:.1f}mm",
                    payload=payload
                )
            else:
                await self._clear_alert(device_id, AlertType.STABILITY_LOW)
        except Exception as e:
            logger.error(f"处理步态告警失败: {e}")

    async def on_obstacle_result(self, message: Message):
        try:
            payload = message.payload
            device_id = payload.get('device_id', 'unknown')
            risk = payload.get('risk_level', 'low')
            prob = payload.get('obstacle_pass_probability', 1.0)

            if risk in ('high', 'critical') or prob < 0.5:
                await self._trigger_alert(
                    device_id=device_id,
                    alert_type=AlertType.OBSTACLE_HIGH_RISK,
                    severity=AlertSeverity.CRITICAL if risk == 'critical' or prob < 0.3 else AlertSeverity.WARNING,
                    message=f"越障风险高: risk={risk}, pass_prob={prob:.1%}",
                    payload=payload
                )
        except Exception as e:
            logger.error(f"处理越障告警失败: {e}")

    async def on_terrain_result(self, message: Message):
        try:
            payload = message.payload
            device_id = payload.get('device_id', 'unknown')
            score = payload.get('traversability_score', 100)
            terrain_type = payload.get('terrain_type', 'flat')

            if score < 50 or terrain_type in ('steep_slope', 'rocky'):
                await self._trigger_alert(
                    device_id=device_id,
                    alert_type=AlertType.TERRAIN_DANGEROUS,
                    severity=AlertSeverity.WARNING,
                    message=f"地形通过性差: type={terrain_type}, score={score:.0f}",
                    payload=payload
                )
            else:
                await self._clear_alert(device_id, AlertType.TERRAIN_DANGEROUS)
        except Exception as e:
            logger.error(f"处理地形告警失败: {e}")

    async def _trigger_alert(self, device_id: str, alert_type: AlertType,
                              severity: AlertSeverity, message: str,
                              payload: Dict[str, Any]):
        alert_key = f"{device_id}:{alert_type.value}"

        if alert_key in self.active_alerts:
            existing = self.active_alerts[alert_key]
            if existing.severity == severity and existing.message == message:
                return

        alert = Alert(
            alert_id=f"alert_{datetime.utcnow().timestamp()}_{alert_key}",
            device_id=device_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            payload=payload
        )

        self.active_alerts[alert_key] = alert
        self.alert_history.append(alert)
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

        alert_payload = {
            'alert_id': alert.alert_id,
            'device_id': alert.device_id,
            'alert_type': alert.alert_type.value,
            'severity': alert.severity.value,
            'message': alert.message,
            'payload': alert.payload,
            'triggered_at': alert.triggered_at.isoformat(),
            'is_active': True
        }

        await publish_alert_triggered(alert_payload, source='alarm_ws')
        await self.broadcast_to_clients({
            'type': 'alert_triggered',
            'data': alert_payload
        })

        try:
            await influx_db.write_alert_record(alert_payload)
        except Exception as e:
            logger.error(f"写入告警记录失败: {e}")

        logger.warning(f"告警触发: [{severity.value}] {device_id} - {message}")

    async def _clear_alert(self, device_id: str, alert_type: AlertType):
        alert_key = f"{device_id}:{alert_type.value}"
        if alert_key in self.active_alerts:
            alert = self.active_alerts.pop(alert_key)
            alert.is_active = False
            alert.cleared_at = datetime.utcnow()

            clear_payload = {
                'alert_id': alert.alert_id,
                'device_id': alert.device_id,
                'alert_type': alert.alert_type.value,
                'severity': alert.severity.value,
                'message': alert.message,
                'triggered_at': alert.triggered_at.isoformat(),
                'cleared_at': alert.cleared_at.isoformat(),
                'is_active': False
            }

            await publish_alert_cleared(clear_payload, source='alarm_ws')
            await self.broadcast_to_clients({
                'type': 'alert_cleared',
                'data': clear_payload
            })

            logger.info(f"告警清除: {device_id} - {alert_type.value}")

    def get_active_alerts(self, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        alerts = list(self.active_alerts.values())
        if device_id:
            alerts = [a for a in alerts if a.device_id == device_id]

        return [
            {
                'alert_id': a.alert_id,
                'device_id': a.device_id,
                'alert_type': a.alert_type.value,
                'severity': a.severity.value,
                'message': a.message,
                'payload': a.payload,
                'triggered_at': a.triggered_at.isoformat(),
                'is_active': True
            }
            for a in alerts
        ]

    def get_alert_history(self, device_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        alerts = list(self.alert_history)
        if device_id:
            alerts = [a for a in alerts if a.device_id == device_id]

        alerts = alerts[-limit:]
        return [
            {
                'alert_id': a.alert_id,
                'device_id': a.device_id,
                'alert_type': a.alert_type.value,
                'severity': a.severity.value,
                'message': a.message,
                'triggered_at': a.triggered_at.isoformat(),
                'cleared_at': a.cleared_at.isoformat() if a.cleared_at else None,
                'is_active': a.is_active
            }
            for a in alerts
        ]

    async def start(self):
        self.running = True
        message_bus.subscribe(CHANNELS['SENSOR_VALIDATED'], self.on_sensor_validated)
        message_bus.subscribe(CHANNELS['GAIT_RESULT'], self.on_gait_result)
        message_bus.subscribe(CHANNELS['OBSTACLE_RESULT'], self.on_obstacle_result)
        message_bus.subscribe(CHANNELS['TERRAIN_RESULT'], self.on_terrain_result)

        await message_bus.start_listening([
            CHANNELS['SENSOR_VALIDATED'],
            CHANNELS['GAIT_RESULT'],
            CHANNELS['OBSTACLE_RESULT'],
            CHANNELS['TERRAIN_RESULT'],
            CHANNELS['COMMAND']
        ])

        logger.info("AlarmWS服务已启动，订阅SENSOR/GAIT/OBSTACLE/TERRAIN频道")

    async def stop(self):
        self.running = False
        await message_bus.stop_listening()
        logger.info("AlarmWS服务已停止")


alarm_service: Optional[AlarmWSService] = None


async def init_alarm_service():
    global alarm_service
    alarm_service = AlarmWSService()
    return alarm_service


def get_alarm_service() -> AlarmWSService:
    global alarm_service
    if alarm_service is None:
        raise RuntimeError("Alarm service not initialized")
    return alarm_service


if __name__ == '__main__':
    async def main():
        service = AlarmWSService()
        await service.start()
        while True:
            await asyncio.sleep(1)

    asyncio.run(main())

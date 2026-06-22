import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Set
import logging
from collections import defaultdict

from app.models.schemas import SensorData, Alert, AlertType, AlertLevel
from app.core.config import settings
from app.core.database import influx_db
from app.core.websocket import ws_manager

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.suppressed_alerts: Set[str] = set()
        self.last_alert_time: Dict[str, datetime] = {}
        self.alert_cooldown = 60
        
        self.thresholds = {
            AlertType.INCLINATION_EXCEEDED: settings.alert_inclination_threshold,
            AlertType.MECHANISM_JAMMED: settings.alert_jammed_threshold
        }
        
        self.consecutive_readings = defaultdict(lambda: defaultdict(int))
        self.required_consecutive = 3

    async def check_alerts(self, data: SensorData) -> List[Alert]:
        triggered_alerts = []
        
        new_alerts = await self._check_thresholds(data)
        triggered_alerts.extend(new_alerts)
        
        new_alerts = await self._check_mechanism_jam(data)
        triggered_alerts.extend(new_alerts)
        
        new_alerts = await self._check_sensor_fault(data)
        triggered_alerts.extend(new_alerts)
        
        for alert in triggered_alerts:
            await self._process_alert(alert)
        
        await self._check_alert_clearing(data)
        
        return triggered_alerts

    async def _check_thresholds(self, data: SensorData) -> List[Alert]:
        alerts = []
        
        if abs(data.body_inclination) > self.thresholds[AlertType.INCLINATION_EXCEEDED]:
            self.consecutive_readings[data.device_id][AlertType.INCLINATION_EXCEEDED] += 1
            
            if self.consecutive_readings[data.device_id][AlertType.INCLINATION_EXCEEDED] >= self.required_consecutive:
                if self._can_alert(data.device_id, AlertType.INCLINATION_EXCEEDED):
                    alert = Alert(
                        id=str(uuid.uuid4()),
                        timestamp=data.timestamp,
                        type=AlertType.INCLINATION_EXCEEDED,
                        level=AlertLevel.CRITICAL,
                        message=f"机身倾角超限: 当前{data.body_inclination:.1f}°, 阈值{self.thresholds[AlertType.INCLINATION_EXCEEDED]}°",
                        device_id=data.device_id,
                        sensor_data=data
                    )
                    alerts.append(alert)
        else:
            self.consecutive_readings[data.device_id][AlertType.INCLINATION_EXCEEDED] = 0
        
        return alerts

    async def _check_mechanism_jam(self, data: SensorData) -> List[Alert]:
        alerts = []
        
        from app.services.data_processor import data_processor
        recent_data = data_processor.get_recent_data(data.device_id, count=10)
        
        if len(recent_data) >= 5:
            displacements = [d.leg_displacement for d in recent_data[-5:]]
            crank_angles = [d.crank_angle for d in recent_data[-5:]]
            
            disp_std = abs(max(displacements) - min(displacements))
            crank_std = abs(max(crank_angles) - min(crank_angles))
            
            if disp_std < self.thresholds[AlertType.MECHANISM_JAMMED] and crank_std > 10:
                self.consecutive_readings[data.device_id][AlertType.MECHANISM_JAMMED] += 1
                
                if self.consecutive_readings[data.device_id][AlertType.MECHANISM_JAMMED] >= self.required_consecutive:
                    if self._can_alert(data.device_id, AlertType.MECHANISM_JAMMED):
                        alert = Alert(
                            id=str(uuid.uuid4()),
                            timestamp=data.timestamp,
                            type=AlertType.MECHANISM_JAMMED,
                            level=AlertLevel.CRITICAL,
                            message=f"机构可能卡死: 腿部位移变化{disp_std:.1f}mm, 低于阈值{self.thresholds[AlertType.MECHANISM_JAMMED]}mm",
                            device_id=data.device_id,
                            sensor_data=data
                        )
                        alerts.append(alert)
            else:
                self.consecutive_readings[data.device_id][AlertType.MECHANISM_JAMMED] = 0
        
        return alerts

    async def _check_sensor_fault(self, data: SensorData) -> List[Alert]:
        alerts = []
        
        from app.services.data_processor import data_processor
        quality = data_processor._assess_data_quality(data)
        
        if quality['score'] < 50:
            if self._can_alert(data.device_id, AlertType.SENSOR_FAULT):
                issues_str = "; ".join(quality['issues'])
                alert = Alert(
                    id=str(uuid.uuid4()),
                    timestamp=data.timestamp,
                    type=AlertType.SENSOR_FAULT,
                    level=AlertLevel.WARNING,
                    message=f"传感器数据质量问题: {issues_str}",
                    device_id=data.device_id,
                    sensor_data=data
                )
                alerts.append(alert)
        
        return alerts

    def _can_alert(self, device_id: str, alert_type: AlertType) -> bool:
        key = f"{device_id}:{alert_type.value}"
        
        if key in self.suppressed_alerts:
            return False
        
        if key in self.last_alert_time:
            time_since_last = (datetime.utcnow() - self.last_alert_time[key]).total_seconds()
            if time_since_last < self.alert_cooldown:
                return False
        
        return True

    async def _process_alert(self, alert: Alert):
        key = f"{alert.device_id}:{alert.type.value}"
        
        self.last_alert_time[key] = alert.timestamp
        self.active_alerts[alert.id] = alert
        
        self.alert_history.append(alert)
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        await influx_db.write_alert(alert)
        
        await ws_manager.broadcast_alert(alert)
        
        logger.warning(f"告警触发: {alert.type.value} - {alert.message}")

    async def _check_alert_clearing(self, data: SensorData):
        to_remove = []
        
        for alert_id, alert in self.active_alerts.items():
            if alert.device_id != data.device_id:
                continue
            
            is_cleared = False
            
            if alert.type == AlertType.INCLINATION_EXCEEDED:
                if abs(data.body_inclination) < self.thresholds[AlertType.INCLINATION_EXCEEDED] * 0.8:
                    is_cleared = True
            
            elif alert.type == AlertType.MECHANISM_JAMMED:
                from app.services.data_processor import data_processor
                recent_data = data_processor.get_recent_data(data.device_id, count=5)
                if len(recent_data) >= 3:
                    displacements = [d.leg_displacement for d in recent_data]
                    if abs(max(displacements) - min(displacements)) > self.thresholds[AlertType.MECHANISM_JAMMED] * 2:
                        is_cleared = True
            
            elif alert.type == AlertType.SENSOR_FAULT:
                from app.services.data_processor import data_processor
                quality = data_processor._assess_data_quality(data)
                if quality['score'] > 70:
                    is_cleared = True
            
            if is_cleared:
                to_remove.append(alert_id)
                logger.info(f"告警已清除: {alert.type.value} for device {alert.device_id}")
        
        for alert_id in to_remove:
            del self.active_alerts[alert_id]

    async def acknowledge_alert(self, alert_id: str) -> bool:
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            
            alert = self.active_alerts[alert_id]
            key = f"{alert.device_id}:{alert.type.value}"
            self.suppressed_alerts.add(key)
            
            return True
        return False

    async def unsuppress_alerts(self, device_id: Optional[str] = None):
        if device_id:
            to_remove = [k for k in self.suppressed_alerts if k.startswith(f"{device_id}:")]
            for k in to_remove:
                self.suppressed_alerts.discard(k)
        else:
            self.suppressed_alerts.clear()

    def get_active_alerts(self, device_id: Optional[str] = None) -> List[Alert]:
        alerts = list(self.active_alerts.values())
        if device_id:
            alerts = [a for a in alerts if a.device_id == device_id]
        return alerts

    def get_alert_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        alert_type: Optional[AlertType] = None,
        device_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Alert]:
        alerts = self.alert_history
        
        if start_time:
            alerts = [a for a in alerts if a.timestamp >= start_time]
        if end_time:
            alerts = [a for a in alerts if a.timestamp <= end_time]
        if alert_type:
            alerts = [a for a in alerts if a.type == alert_type]
        if device_id:
            alerts = [a for a in alerts if a.device_id == device_id]
        
        return alerts[-limit:]

    def get_alert_statistics(self, hours: int = 24) -> Dict:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_alerts = [a for a in self.alert_history if a.timestamp >= cutoff]
        
        stats = {
            'total': len(recent_alerts),
            'by_type': defaultdict(int),
            'by_level': defaultdict(int),
            'by_device': defaultdict(int),
            'active_count': len(self.active_alerts),
            'acknowledged_count': len([a for a in recent_alerts if a.acknowledged])
        }
        
        for alert in recent_alerts:
            stats['by_type'][alert.type.value] += 1
            stats['by_level'][alert.level.value] += 1
            stats['by_device'][alert.device_id] += 1
        
        return stats

    def update_threshold(self, alert_type: AlertType, threshold: float):
        if alert_type in self.thresholds:
            self.thresholds[alert_type] = threshold
            logger.info(f"告警阈值已更新: {alert_type.value} = {threshold}")

    def set_alert_cooldown(self, cooldown_seconds: int):
        self.alert_cooldown = max(10, cooldown_seconds)
        logger.info(f"告警冷却时间已设置: {self.alert_cooldown}s")


alert_service = AlertService()

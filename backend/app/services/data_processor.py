import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
from collections import deque

from app.models.schemas import SensorData
from app.core.database import influx_db, redis_db
from app.core.websocket import ws_manager

logger = logging.getLogger(__name__)


class DataProcessor:
    def __init__(self):
        self.data_buffers: Dict[str, deque] = {}
        self.buffer_size = 100
        self.last_processed: Dict[str, datetime] = {}

    async def process_sensor_data(self, data: SensorData) -> Dict:
        device_id = data.device_id
        
        if device_id not in self.data_buffers:
            self.data_buffers[device_id] = deque(maxlen=self.buffer_size)
        
        self.data_buffers[device_id].append(data)
        self.last_processed[device_id] = data.timestamp
        
        await influx_db.write_sensor_data(data)
        
        processed = self._process_data(data)
        
        await ws_manager.broadcast_sensor_data(data)
        
        cache_key = f"sensor:latest:{device_id}"
        await redis_db.set_cache(
            cache_key,
            {
                'timestamp': data.timestamp.isoformat(),
                'crank_angle': data.crank_angle,
                'leg_displacement': data.leg_displacement,
                'body_inclination': data.body_inclination,
                'ground_elevation': data.ground_elevation
            },
            expire=120
        )
        
        return processed

    def _process_data(self, data: SensorData) -> Dict:
        processed = {
            'raw_data': data.model_dump(),
            'derived_metrics': self._calculate_derived_metrics(data),
            'quality': self._assess_data_quality(data),
            'anomalies': self._detect_anomalies(data)
        }
        
        if len(self.data_buffers[data.device_id]) >= 10:
            processed['trend'] = self._calculate_trend(data.device_id)
        
        return processed

    def _calculate_derived_metrics(self, data: SensorData) -> Dict:
        metrics = {}
        
        metrics['crank_speed'] = self._calculate_crank_speed(data)
        metrics['leg_velocity'] = self._calculate_leg_velocity(data)
        metrics['inclination_rate'] = self._calculate_inclination_rate(data)
        metrics['ground_slope'] = self._calculate_ground_slope(data)
        metrics['energy_efficiency'] = self._calculate_energy_efficiency(data)
        
        return metrics

    def _calculate_crank_speed(self, data: SensorData) -> Optional[float]:
        buffer = self.data_buffers.get(data.device_id, deque())
        if len(buffer) < 2:
            return None
        
        prev_data = buffer[-2]
        delta_angle = data.crank_angle - prev_data.crank_angle
        delta_time = (data.timestamp - prev_data.timestamp).total_seconds()
        
        if delta_time <= 0:
            return None
        
        if delta_angle < -180:
            delta_angle += 360
        elif delta_angle > 180:
            delta_angle -= 360
        
        return float(delta_angle / delta_time)

    def _calculate_leg_velocity(self, data: SensorData) -> Optional[float]:
        buffer = self.data_buffers.get(data.device_id, deque())
        if len(buffer) < 2:
            return None
        
        prev_data = buffer[-2]
        delta_disp = data.leg_displacement - prev_data.leg_displacement
        delta_time = (data.timestamp - prev_data.timestamp).total_seconds()
        
        if delta_time <= 0:
            return None
        
        return float(delta_disp / delta_time)

    def _calculate_inclination_rate(self, data: SensorData) -> Optional[float]:
        buffer = self.data_buffers.get(data.device_id, deque())
        if len(buffer) < 5:
            return None
        
        inclinations = [d.body_inclination for d in list(buffer)[-5:]]
        times = [(d.timestamp - data.timestamp).total_seconds() for d in list(buffer)[-5:]]
        
        if len(times) < 2:
            return None
        
        coeffs = np.polyfit(times, inclinations, 1)
        return float(coeffs[0])

    def _calculate_ground_slope(self, data: SensorData) -> Optional[float]:
        buffer = self.data_buffers.get(data.device_id, deque())
        if len(buffer) < 5:
            return None
        
        elevations = [d.ground_elevation for d in list(buffer)[-10:]]
        
        if len(elevations) < 2:
            return None
        
        x = np.arange(len(elevations))
        coeffs = np.polyfit(x, elevations, 1)
        return float(coeffs[0])

    def _calculate_energy_efficiency(self, data: SensorData) -> float:
        crank_speed = self._calculate_crank_speed(data) or 30.0
        base_efficiency = 0.7
        
        inclination_penalty = 1.0 - abs(data.body_inclination) / 30.0
        speed_penalty = 1.0 - abs(crank_speed - 30.0) / 60.0
        
        efficiency = base_efficiency * max(0.3, inclination_penalty) * max(0.5, speed_penalty)
        return float(max(0.1, min(1.0, efficiency)))

    def _assess_data_quality(self, data: SensorData) -> Dict:
        quality_score = 100.0
        issues = []
        
        if data.crank_angle < 0 or data.crank_angle > 360:
            quality_score -= 30
            issues.append('曲柄转角超出正常范围')
        
        if abs(data.body_inclination) > 30:
            quality_score -= 20
            issues.append('机身倾角异常')
        
        buffer = self.data_buffers.get(data.device_id, deque())
        if len(buffer) > 5:
            recent_angles = [d.crank_angle for d in list(buffer)[-5:]]
            if len(set(recent_angles)) == 1:
                quality_score -= 20
                issues.append('传感器数据可能冻结')
            
            std_dev = np.std([d.leg_displacement for d in list(buffer)[-10:]])
            if std_dev < 0.1:
                quality_score -= 15
                issues.append('腿部位移变化异常小')
        
        quality_level = 'excellent'
        if quality_score < 60:
            quality_level = 'poor'
        elif quality_score < 80:
            quality_level = 'fair'
        
        return {
            'score': float(quality_score),
            'level': quality_level,
            'issues': issues
        }

    def _detect_anomalies(self, data: SensorData) -> List[Dict]:
        anomalies = []
        
        if abs(data.body_inclination) > 15:
            anomalies.append({
                'type': 'HIGH_INCLINATION',
                'severity': 'critical',
                'value': data.body_inclination,
                'threshold': 15.0,
                'message': f'机身倾角过高: {data.body_inclination:.1f}°'
            })
        
        buffer = self.data_buffers.get(data.device_id, deque())
        if len(buffer) >= 10:
            crank_angles = [d.crank_angle for d in list(buffer)[-10:]]
            expected_change = 30.0 * 60 / 60
            
            for i in range(1, len(crank_angles)):
                change = abs(crank_angles[i] - crank_angles[i-1])
                if change > expected_change * 3:
                    anomalies.append({
                        'type': 'SUDDEN_CHANGE',
                        'severity': 'warning',
                        'value': change,
                        'message': f'曲柄转角突变: {change:.1f}°'
                    })
                    break
            
            if len(set([round(d.leg_displacement, 2) for d in list(buffer)[-5:]])) == 1:
                anomalies.append({
                    'type': 'MECHANISM_JAM',
                    'severity': 'critical',
                    'message': '腿部位移无变化，可能机构卡死'
                })
        
        return anomalies

    def _calculate_trend(self, device_id: str) -> Dict:
        buffer = self.data_buffers.get(device_id, deque())
        if len(buffer) < 10:
            return {}
        
        recent_data = list(buffer)[-50:]
        
        trends = {}
        
        x = np.arange(len(recent_data))
        
        for field in ['crank_angle', 'leg_displacement', 'body_inclination', 'ground_elevation']:
            values = [getattr(d, field) for d in recent_data]
            coeffs = np.polyfit(x, values, 1)
            trends[field] = {
                'slope': float(coeffs[0]),
                'intercept': float(coeffs[1]),
                'direction': 'increasing' if coeffs[0] > 0 else 'decreasing' if coeffs[0] < 0 else 'stable'
            }
        
        return trends

    def get_statistics(self, device_id: str, window_minutes: int = 5) -> Optional[Dict]:
        buffer = self.data_buffers.get(device_id, deque())
        if not buffer:
            return None
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
        window_data = [d for d in buffer if d.timestamp >= cutoff_time]
        
        if not window_data:
            return None
        
        stats = {}
        
        for field in ['crank_angle', 'leg_displacement', 'body_inclination', 'ground_elevation']:
            values = [getattr(d, field) for d in window_data]
            stats[field] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'median': float(np.median(values))
            }
        
        return {
            'window_minutes': window_minutes,
            'sample_count': len(window_data),
            'statistics': stats
        }

    def get_recent_data(self, device_id: str, count: int = 50) -> List[SensorData]:
        buffer = self.data_buffers.get(device_id, deque())
        return list(buffer)[-count:]

    def clear_buffer(self, device_id: Optional[str] = None):
        if device_id:
            if device_id in self.data_buffers:
                self.data_buffers[device_id].clear()
        else:
            self.data_buffers.clear()


data_processor = DataProcessor()

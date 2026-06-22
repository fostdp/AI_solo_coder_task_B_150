import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models.schemas import SensorData
from app.services.modbus_client import ModbusRTUClient
from app.core.database import influx_db, redis_db
from app.core.config_loader import get_terrain_config
from app.core.message_bus import (
    message_bus, CHANNELS, publish_sensor_validated
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('modbus_receiver')


class ModbusReceiverService:
    def __init__(self, device_id: str = 'woodox_001', poll_interval: float = 60.0):
        self.device_id = device_id
        self.poll_interval = poll_interval
        self.modbus_client = ModbusRTUClient()
        self.data_buffers: Dict[str, deque] = {}
        self.buffer_size = 100
        self.running = False

        terrain_config = get_terrain_config()
        dq = terrain_config.get('data_quality', {})
        self.crank_valid_range = dq.get('crank_angle_valid_range', [0, 360])
        self.inclination_abnormal = dq.get('inclination_abnormal_threshold', 30.0)
        self.freeze_samples = dq.get('freeze_detection_samples', 5)
        self.low_variation_std = dq.get('low_variation_std', 0.1)

    async def validate_sensor_data(self, data: SensorData) -> Dict[str, Any]:
        issues = []
        quality_score = 100.0

        if data.crank_angle < self.crank_valid_range[0] or data.crank_angle > self.crank_valid_range[1]:
            quality_score -= 30
            issues.append('曲柄转角超出正常范围')

        if abs(data.body_inclination) > self.inclination_abnormal:
            quality_score -= 20
            issues.append('机身倾角异常')

        buf = self.data_buffers.get(data.device_id, deque())
        if len(buf) >= self.freeze_samples:
            recent = list(buf)[-self.freeze_samples:]
            crank_angles = [d.crank_angle for d in recent]
            if len(set([round(a, 2) for a in crank_angles])) == 1:
                quality_score -= 20
                issues.append('传感器数据可能冻结')

            import numpy as np
            disp_std = np.std([d.leg_displacement for d in recent])
            if disp_std < self.low_variation_std:
                quality_score -= 15
                issues.append('腿部位移变化异常小')

        if quality_score < 60:
            quality_level = 'poor'
        elif quality_score < 80:
            quality_level = 'fair'
        else:
            quality_level = 'excellent'

        derived = self._calculate_derived_metrics(data)

        return {
            'valid': quality_score >= 50,
            'quality_score': quality_score,
            'quality_level': quality_level,
            'issues': issues,
            'derived_metrics': derived,
            'sensor_data': {
                'timestamp': data.timestamp.isoformat(),
                'device_id': data.device_id,
                'crank_angle': data.crank_angle,
                'leg_displacement': data.leg_displacement,
                'body_inclination': data.body_inclination,
                'ground_elevation': data.ground_elevation
            }
        }

    def _calculate_derived_metrics(self, data: SensorData) -> Dict[str, Any]:
        metrics = {}
        buf = self.data_buffers.get(data.device_id, deque())

        if len(buf) >= 2:
            prev = buf[-2]
            dt = (data.timestamp - prev.timestamp).total_seconds()
            if dt > 0:
                delta_angle = data.crank_angle - prev.crank_angle
                if delta_angle < -180:
                    delta_angle += 360
                elif delta_angle > 180:
                    delta_angle -= 360
                metrics['crank_speed'] = delta_angle / dt
                metrics['leg_velocity'] = (data.leg_displacement - prev.leg_displacement) / dt

        return metrics

    async def process_single_reading(self, data: SensorData):
        if data.device_id not in self.data_buffers:
            self.data_buffers[data.device_id] = deque(maxlen=self.buffer_size)
        self.data_buffers[data.device_id].append(data)

        validation = await self.validate_sensor_data(data)

        try:
            await influx_db.write_sensor_data(data)
        except Exception as e:
            logger.error(f"写入InfluxDB失败: {e}")

        try:
            cache_key = f"sensor:latest:{data.device_id}"
            await redis_db.set_cache(cache_key, validation['sensor_data'], expire=120)
        except Exception as e:
            logger.error(f"写入Redis缓存失败: {e}")

        if validation['valid']:
            await publish_sensor_validated(validation, source='modbus_receiver')
            logger.info(f"数据校验通过: device={data.device_id}, crank={data.crank_angle:.1f}°, quality={validation['quality_level']}")
        else:
            logger.warning(f"数据质量不合格: device={data.device_id}, score={validation['quality_score']}, issues={validation['issues']}")

    async def ingest_external_data(self, data: SensorData) -> Dict[str, Any]:
        if data.device_id not in self.data_buffers:
            self.data_buffers[data.device_id] = deque(maxlen=self.buffer_size)
        self.data_buffers[data.device_id].append(data)

        validation = await self.validate_sensor_data(data)

        try:
            await influx_db.write_sensor_data(data)
        except Exception as e:
            logger.error(f"写入InfluxDB失败: {e}")

        if validation['valid']:
            await publish_sensor_validated(validation, source='http_api')

        return validation

    async def start_polling(self):
        self.running = True
        logger.info(f"启动Modbus数据采集: device={self.device_id}, interval={self.poll_interval}s")

        if not self.modbus_client.connect():
            logger.error("Modbus连接失败，将使用模拟数据模式")

        while self.running:
            try:
                data = self.modbus_client.read_sensor_data(self.device_id)
                if data:
                    await self.process_single_reading(data)
                else:
                    logger.debug("Modbus读取失败，跳过本轮")

                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("数据采集已取消")
                break
            except Exception as e:
                logger.error(f"数据采集异常: {e}")
                await asyncio.sleep(self.poll_interval)

    async def stop(self):
        self.running = False
        self.modbus_client.disconnect()
        logger.info("ModbusReceiver已停止")


receiver_service: Optional[ModbusReceiverService] = None


async def init_receiver_service(device_id: str = 'woodox_001', poll_interval: float = 60.0):
    global receiver_service
    receiver_service = ModbusReceiverService(device_id=device_id, poll_interval=poll_interval)
    return receiver_service


def get_receiver_service() -> ModbusReceiverService:
    global receiver_service
    if receiver_service is None:
        raise RuntimeError("Receiver service not initialized")
    return receiver_service


if __name__ == '__main__':
    async def main():
        service = ModbusReceiverService(device_id='woodox_001', poll_interval=5.0)
        await message_bus.start_listening([CHANNELS['COMMAND']])
        await service.start_polling()

    asyncio.run(main())

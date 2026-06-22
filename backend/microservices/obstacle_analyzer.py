import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models.schemas import (
    JansenParameters, ObstacleAssessmentRequest, TerrainData, ObstacleAssessmentResult
)
from app.analysis.terrain_recognition import TerrainRecognizer
from app.analysis.stability_analysis import StabilityAnalyzer
from app.analysis.obstacle_analysis import ObstacleAnalyzer
from app.core.config_loader import get_mechanism_config, get_terrain_config, get_nested_config
from app.core.database import influx_db
from app.core.message_bus import (
    message_bus, CHANNELS, Message,
    publish_terrain_result, publish_obstacle_result
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('obstacle_analyzer')


class ObstacleAnalyzerService:
    def __init__(self):
        mech_config = get_mechanism_config()
        terrain_config = get_terrain_config()
        jl = get_nested_config(mech_config, 'jansen_linkage', default={})

        self.params = JansenParameters(
            crank_length=jl.get('crank_length', 150.0),
            rocker_length=jl.get('rocker_length', 250.0),
            coupler_length=jl.get('coupler_length', 300.0),
            ground_link=jl.get('ground_link', 200.0),
            crank_speed=jl.get('crank_speed', 30.0),
        )

        self.terrain_recognizer = TerrainRecognizer()
        self.stability_analyzer = StabilityAnalyzer(self.params)
        self.obstacle_analyzer = ObstacleAnalyzer(self.params)
        self.running = False

        obs_config = get_nested_config(terrain_config, 'obstacle_assessment', default={})
        self.clearance_safety_margin = obs_config.get('clearance_safety_margin', 0.7)
        self.low_risk_threshold = obs_config.get('low_risk_threshold', 0.8)

        self._results_cache: Dict[str, Dict[str, Any]] = {}

    async def on_sensor_validated(self, message: Message):
        try:
            payload = message.payload
            sensor_data = payload.get('sensor_data', {})
            device_id = sensor_data.get('device_id', 'unknown')

            terrain_analysis = await self.analyze_terrain_from_sensor(
                device_id=device_id,
                ground_elevation=sensor_data.get('ground_elevation', 0.0),
                body_inclination=sensor_data.get('body_inclination', 0.0)
            )

            cache_key = f"{device_id}:latest"
            self._results_cache[cache_key] = {
                'terrain': terrain_analysis,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"处理传感器数据失败: {e}")

    async def analyze_terrain_from_sensor(
        self,
        device_id: str,
        ground_elevation: float,
        body_inclination: float
    ) -> Dict[str, Any]:
        try:
            terrain_points = []
            for i in range(20):
                for j in range(20):
                    elev = ground_elevation * (0.5 + 0.5 * (i + j) / 40)
                    terrain_points.append({
                        'x': i * 100.0,
                        'y': j * 100.0,
                        'elevation': elev
                    })

            simple_terrain = {
                'terrain_type': 'flat' if abs(body_inclination) < 3 else ('gentle_slope' if abs(body_inclination) < 10 else 'steep_slope'),
                'roughness': abs(body_inclination) * 2,
                'slope_max': abs(body_inclination),
                'elevation_stats': {
                    'min': ground_elevation - 10,
                    'max': ground_elevation + 10,
                    'mean': ground_elevation
                },
                'obstacles': [],
                'traversability_score': max(20, 100 - abs(body_inclination) * 5)
            }

            await publish_terrain_result({
                'device_id': device_id,
                'timestamp': datetime.utcnow().isoformat(),
                **simple_terrain
            })

            logger.info(f"地形分析完成: device={device_id}, type={simple_terrain['terrain_type']}, score={simple_terrain['traversability_score']:.1f}%")

            return simple_terrain

        except Exception as e:
            logger.error(f"地形分析失败: {e}")
            raise

    async def assess_obstacle(
        self,
        request: ObstacleAssessmentRequest
    ) -> Dict[str, Any]:
        try:
            self.obstacle_analyzer = ObstacleAnalyzer(request.parameters)
            self.stability_analyzer = StabilityAnalyzer(request.parameters)

            result = self.obstacle_analyzer.assess_obstacle_clearing(request)

            result_dict = {
                'device_id': result.device_id,
                'timestamp': result.timestamp.isoformat(),
                'max_obstacle_height': result.max_obstacle_height,
                'max_slope_angle': result.max_slope_angle,
                'critical_inclination': result.critical_inclination,
                'obstacle_pass_probability': result.obstacle_pass_probability,
                'recommended_speed': result.recommended_speed,
                'risk_level': result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level),
                'terrain_analysis': result.terrain_analysis
            }

            try:
                await influx_db.write_obstacle_assessment(result)
            except Exception as e:
                logger.error(f"写入越障评估失败: {e}")

            await publish_obstacle_result(result_dict)

            logger.info(
                f"越障评估完成: device={request.device_id}, "
                f"max_h={result.max_obstacle_height:.1f}mm, "
                f"prob={result.obstacle_pass_probability:.1%}, "
                f"risk={result.risk_level}"
            )

            return result_dict

        except Exception as e:
            logger.error(f"越障评估失败: {e}")
            raise

    async def simulate_obstacle_traversal(
        self,
        obstacle_height: float,
        obstacle_width: float,
        approach_speed: float,
        body_inclination: float,
        params: Optional[JansenParameters] = None
    ) -> Dict[str, Any]:
        try:
            analyzer = ObstacleAnalyzer(params or self.params)
            result = analyzer.simulate_obstacle_traversal(
                obstacle_height=obstacle_height,
                obstacle_width=obstacle_width,
                approach_speed=approach_speed,
                body_inclination=body_inclination
            )

            logger.info(
                f"越障仿真完成: h={obstacle_height}mm, "
                f"success={result['successful']}, "
                f"clearance={result['minimum_clearance']:.1f}mm"
            )

            return result

        except Exception as e:
            logger.error(f"越障仿真失败: {e}")
            raise

    async def analyze_terrain_data(self, terrain_data: TerrainData) -> Dict[str, Any]:
        try:
            result = self.terrain_recognizer.analyze_terrain(terrain_data)
            await publish_terrain_result(result)
            return result
        except Exception as e:
            logger.error(f"地形数据分析失败: {e}")
            raise

    def get_cached_result(self, device_id: str) -> Optional[Dict[str, Any]]:
        return self._results_cache.get(f"{device_id}:latest")

    async def start(self):
        self.running = True
        message_bus.subscribe(CHANNELS['SENSOR_VALIDATED'], self.on_sensor_validated)
        await message_bus.start_listening([CHANNELS['SENSOR_VALIDATED'], CHANNELS['COMMAND']])
        logger.info("ObstacleAnalyzer服务已启动，订阅SENSOR_VALIDATED频道")

    async def stop(self):
        self.running = False
        await message_bus.stop_listening()
        logger.info("ObstacleAnalyzer服务已停止")


obstacle_service: Optional[ObstacleAnalyzerService] = None


async def init_obstacle_service():
    global obstacle_service
    obstacle_service = ObstacleAnalyzerService()
    return obstacle_service


def get_obstacle_service() -> ObstacleAnalyzerService:
    global obstacle_service
    if obstacle_service is None:
        raise RuntimeError("Obstacle service not initialized")
    return obstacle_service


if __name__ == '__main__':
    async def main():
        service = ObstacleAnalyzerService()
        await service.start()
        while True:
            await asyncio.sleep(1)

    asyncio.run(main())

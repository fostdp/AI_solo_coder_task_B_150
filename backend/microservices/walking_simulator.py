import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models.schemas import JansenParameters, GaitAnalysisResult, Point3D
from app.simulation.jansen_linkage import JansenLinkageSolver
from app.simulation.multibody_dynamics import MultibodyDynamics
from app.simulation.gait_engine import GaitEngine
from app.core.config_loader import get_mechanism_config, get_nested_config
from app.core.database import influx_db
from app.core.message_bus import (
    message_bus, CHANNELS, Message,
    publish_gait_result, publish_dynamics_result
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('walking_simulator')


class WalkingSimulatorService:
    def __init__(self):
        mech_config = get_mechanism_config()
        jl = get_nested_config(mech_config, 'jansen_linkage', default={})

        self.params = JansenParameters(
            crank_length=jl.get('crank_length', 150.0),
            rocker_length=jl.get('rocker_length', 250.0),
            coupler_length=jl.get('coupler_length', 300.0),
            ground_link=jl.get('ground_link', 200.0),
            crank_speed=jl.get('crank_speed', 30.0),
            ground_stiffness=get_nested_config(mech_config, 'ground_contact', 'ground_stiffness', default=10000.0),
            damping_coefficient=get_nested_config(mech_config, 'ground_contact', 'damping_coefficient', default=100.0),
            foot_radius=get_nested_config(mech_config, 'dimensions', 'foot_radius', default=15.0),
            friction_coefficient=get_nested_config(mech_config, 'ground_contact', 'friction_coefficients', 'normal', default=0.6),
        )

        self.linkage_solver = JansenLinkageSolver(self.params)
        self.dynamics = MultibodyDynamics(self.params)
        self.gait_engine = GaitEngine(self.params)
        self.running = False

        com_config = get_nested_config(mech_config, 'com_adjustment', default={})
        self.max_adjustment_speed = com_config.get('max_adjustment_speed', 50.0)
        self.adjustment_gain = com_config.get('adjustment_gain', 0.5)

        self._results_cache: Dict[str, Dict[str, Any]] = {}

    async def on_sensor_validated(self, message: Message):
        try:
            payload = message.payload
            sensor_data = payload.get('sensor_data', {})
            device_id = sensor_data.get('device_id', 'unknown')

            gait_result = await self.compute_gait_analysis(
                device_id=device_id,
                crank_angle=sensor_data.get('crank_angle', 0.0),
                body_inclination=sensor_data.get('body_inclination', 0.0),
                payload_mass=payload.get('payload_mass', 0.0),
                terrain_type=payload.get('terrain_type', 'normal')
            )

            dynamics_result = await self.compute_dynamics(
                device_id=device_id,
                crank_angle=sensor_data.get('crank_angle', 0.0),
                body_inclination=sensor_data.get('body_inclination', 0.0),
                payload_mass=payload.get('payload_mass', 0.0)
            )

            cache_key = f"{device_id}:latest"
            self._results_cache[cache_key] = {
                'gait': gait_result,
                'dynamics': dynamics_result,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"处理传感器数据失败: {e}")

    async def compute_gait_analysis(
        self,
        device_id: str,
        crank_angle: float,
        body_inclination: float = 0.0,
        payload_mass: float = 0.0,
        terrain_type: str = 'normal'
    ) -> Dict[str, Any]:
        try:
            self.params.payload_mass = payload_mass
            self.params.friction_coefficient = self.linkage_solver.get_terrain_friction_coefficient(terrain_type)
            self.linkage_solver = JansenLinkageSolver(self.params)
            self.gait_engine = GaitEngine(self.params)

            gait_result = self.gait_engine.compute_gait_analysis(
                device_id=device_id,
                crank_angle=crank_angle,
                body_inclination=body_inclination
            )

            result_dict = {
                'device_id': gait_result.device_id,
                'timestamp': gait_result.timestamp.isoformat(),
                'stride_length': gait_result.stride_length,
                'cadence': gait_result.cadence,
                'walking_speed': gait_result.walking_speed,
                'support_phase': gait_result.support_phase,
                'swing_phase': gait_result.swing_phase,
                'gait_symmetry': gait_result.gait_symmetry,
                'stability_margin': gait_result.stability_margin,
                'gait_phase': gait_result.gait_phase,
                'phase_name': gait_result.phase_name,
                'is_support_phase': gait_result.is_support_phase,
                'com_trajectory': [p.model_dump() for p in gait_result.com_trajectory],
                'zmp_trajectory': [p.model_dump() for p in gait_result.zmp_trajectory],
            }

            try:
                await influx_db.write_gait_result(gait_result)
            except Exception as e:
                logger.error(f"写入步态结果失败: {e}")

            await publish_gait_result(result_dict)
            logger.info(f"步态分析完成: device={device_id}, phase={gait_result.phase_name}, stability={gait_result.stability_margin:.1f}mm")

            return result_dict

        except Exception as e:
            logger.error(f"步态分析失败: {e}")
            raise

    async def compute_dynamics(
        self,
        device_id: str,
        crank_angle: float,
        body_inclination: float = 0.0,
        payload_mass: float = 0.0,
        num_support_legs: int = 2
    ) -> Dict[str, Any]:
        try:
            self.params.payload_mass = payload_mass
            self.dynamics = MultibodyDynamics(self.params)

            joints = self.linkage_solver.solve_linkage(crank_angle)
            com_positions = self.dynamics.calculate_link_centers_of_mass(
                joints,
                payload_mass=payload_mass,
                payload_offset=Point3D(x=self.params.payload_offset_x, y=self.params.payload_offset_y, z=self.params.payload_offset_z)
            )
            total_com = self.dynamics.calculate_total_center_of_mass(com_positions, body_inclination)

            support_polygon = self.dynamics.calculate_support_polygon(joints, num_legs=num_support_legs)
            forces = self.dynamics.calculate_joint_forces(joints, com_positions, body_inclination)
            zmp = self.dynamics.calculate_zero_moment_point(total_com, forces, joints, body_inclination)
            stability_margin = self.dynamics.calculate_stability_margin(zmp, support_polygon)
            torques = self.dynamics.calculate_joint_torques(crank_angle, body_inclination, 0.0)

            linkage_state = self.linkage_solver.get_linkage_state(
                crank_angle=crank_angle,
                total_mass=35.0 + payload_mass,
                num_support_legs=num_support_legs
            )
            adjusted_state = self.dynamics.update_linkage_state_with_com(
                linkage_state=linkage_state,
                body_inclination=body_inclination,
                num_support_legs=num_support_legs
            )

            result_dict = {
                'device_id': device_id,
                'timestamp': datetime.utcnow().isoformat(),
                'center_of_mass': {
                    'x': total_com.x,
                    'y': total_com.y,
                    'z': total_com.z
                },
                'zmp': {
                    'x': zmp.x,
                    'y': zmp.y
                },
                'stability_margin': stability_margin,
                'joint_torques': torques,
                'ground_contact': adjusted_state.ground_contact.model_dump() if adjusted_state.ground_contact else None,
                'com_adjustment': adjusted_state.com_adjustment.model_dump() if adjusted_state.com_adjustment else None
            }

            await publish_dynamics_result(result_dict)
            logger.info(f"动力学计算完成: device={device_id}, COM=({total_com.x:.1f},{total_com.y:.1f}), margin={stability_margin:.1f}mm")

            return result_dict

        except Exception as e:
            logger.error(f"动力学计算失败: {e}")
            raise

    def get_cached_result(self, device_id: str) -> Optional[Dict[str, Any]]:
        return self._results_cache.get(f"{device_id}:latest")

    def get_linkage_state(self, crank_angle: float, params: Optional[JansenParameters] = None) -> Dict[str, Any]:
        solver = JansenLinkageSolver(params or self.params)
        joints = solver.solve_linkage(crank_angle)
        return {name: {'x': p.x, 'y': p.y, 'z': p.z} for name, p in joints.items()}

    def get_foot_trajectory(self, start_angle: float = 0, end_angle: float = 360, samples: int = 720, params: Optional[JansenParameters] = None):
        solver = JansenLinkageSolver(params or self.params)
        trajectory = solver.generate_foot_trajectory(start_angle, end_angle, samples)
        return [{'x': p.x, 'y': p.y, 'z': p.z} for p in trajectory]

    async def start(self):
        self.running = True
        message_bus.subscribe(CHANNELS['SENSOR_VALIDATED'], self.on_sensor_validated)
        await message_bus.start_listening([CHANNELS['SENSOR_VALIDATED'], CHANNELS['COMMAND']])
        logger.info("WalkingSimulator服务已启动，订阅SENSOR_VALIDATED频道")

    async def stop(self):
        self.running = False
        await message_bus.stop_listening()
        logger.info("WalkingSimulator服务已停止")


walking_service: Optional[WalkingSimulatorService] = None


async def init_walking_service():
    global walking_service
    walking_service = WalkingSimulatorService()
    return walking_service


def get_walking_service() -> WalkingSimulatorService:
    global walking_service
    if walking_service is None:
        raise RuntimeError("Walking service not initialized")
    return walking_service


if __name__ == '__main__':
    async def main():
        service = WalkingSimulatorService()
        await service.start()
        while True:
            await asyncio.sleep(1)

    asyncio.run(main())

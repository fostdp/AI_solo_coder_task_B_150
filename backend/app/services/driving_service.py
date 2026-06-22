import numpy as np
from typing import Dict, Optional
from datetime import datetime
import asyncio
from collections import defaultdict

from app.models.schemas import (
    DrivingControlInput, DrivingState, JansenParameters, Point3D, Point2D
)
from app.simulation.jansen_linkage import JansenLinkageSolver
from app.simulation.multibody_dynamics import MultibodyDynamics


class VirtualDrivingService:
    _instance = None

    def __init__(self):
        self._devices: Dict[str, dict] = {}
        self._subscribers: Dict[str, list] = defaultdict(list)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_device(self, device_id: str) -> dict:
        if device_id not in self._devices:
            params = JansenParameters()
            self._devices[device_id] = {
                'params': params,
                'state': DrivingState(
                    device_id=device_id,
                    crank_speed=params.crank_speed,
                    crank_angle=0,
                    walking_speed=0,
                    body_inclination=0,
                    turn_rate=0,
                    heading=0,
                    position_x=0,
                    position_y=0,
                    stability_margin=1.0,
                    is_moving=False,
                    is_braking=False,
                    total_distance=0,
                    leg_states={},
                    timestamp=datetime.utcnow(),
                ),
                'linkage_solver': JansenLinkageSolver(params),
                'dynamics': MultibodyDynamics(params),
                'target_speed': 0,
                'target_inclination': 0,
            }
        return self._devices[device_id]

    def set_device_parameters(self, device_id: str, params: JansenParameters):
        device = self._ensure_device(device_id)
        device['params'] = params
        device['linkage_solver'] = JansenLinkageSolver(params)
        device['dynamics'] = MultibodyDynamics(params)

    def apply_control(self, device_id: str, control: DrivingControlInput) -> DrivingState:
        device = self._ensure_device(device_id)
        state = device['state']

        base_speed = device['params'].crank_speed

        if control.speed_override is not None:
            target_speed = control.speed_override
        else:
            acceleration = control.acceleration if control.acceleration is not None else 0
            brake_factor = max(0, 1 - (control.brake or 0))
            target_speed = base_speed * (1 + acceleration * 1.5) * brake_factor

        if control.inclination_override is not None:
            target_inclination = control.inclination_override
        else:
            steering = control.steering if control.steering is not None else 0
            target_inclination = state.body_inclination + steering * 5
            target_inclination = max(-30, min(30, target_inclination))

        turn_rate = (control.steering or 0) * 45

        device['target_speed'] = target_speed
        device['target_inclination'] = target_inclination
        state.crank_speed = target_speed
        state.body_inclination = target_inclination
        state.turn_rate = turn_rate
        state.is_braking = (control.brake or 0) > 0.1

        self._broadcast_state(device_id, state)
        return state

    def update_physics(self, device_id: str, dt: float = 0.016) -> DrivingState:
        device = self._ensure_device(device_id)
        state = device['state']
        params = device['params']
        solver = device['linkage_solver']
        dynamics = device['dynamics']

        crank_speed = device['target_speed'] if device['target_speed'] > 0 else params.crank_speed
        state.crank_speed = crank_speed
        state.crank_angle = (state.crank_angle + crank_speed * dt) % 360

        gait_params = solver.calculate_gait_parameters(state.crank_angle)
        stride = gait_params['stride_length']
        walking_speed = stride * crank_speed / 360.0
        state.walking_speed = walking_speed

        heading_rad = np.radians(state.heading)
        dx = walking_speed * np.cos(heading_rad) * dt
        dy = walking_speed * np.sin(heading_rad) * dt
        state.position_x = state.position_x + dx
        state.position_y = state.position_y + dy
        state.total_distance = state.total_distance + np.sqrt(dx**2 + dy**2)
        state.is_moving = walking_speed > 0.1

        steering = 0
        if device['target_inclination'] != state.body_inclination:
            steering = (device['target_inclination'] - state.body_inclination) * 0.1

        state.heading = (state.heading + steering * 45 * dt) % 360
        state.body_inclination = device['target_inclination']

        joints = solver.solve_linkage(state.crank_angle)
        com_positions = dynamics.calculate_link_centers_of_mass(joints)
        total_com = dynamics.calculate_total_center_of_mass(
            com_positions, state.body_inclination
        )
        forces = dynamics.calculate_joint_forces(
            joints, com_positions, state.body_inclination
        )
        zmp = dynamics.calculate_zero_moment_point(
            total_com, forces, joints, state.body_inclination
        )
        support_polygon = dynamics.calculate_support_polygon(joints)
        margin = dynamics.calculate_stability_margin(zmp, support_polygon)

        state.stability_margin = self._compute_stability(device_id)
        state.timestamp = datetime.utcnow()

        self._broadcast_state(device_id, state)
        return state

    def _compute_stability(self, device_id: str) -> float:
        device = self._ensure_device(device_id)
        state = device['state']
        solver = device['linkage_solver']
        dynamics = device['dynamics']

        joints = solver.solve_linkage(state.crank_angle)
        com_positions = dynamics.calculate_link_centers_of_mass(joints)
        total_com = dynamics.calculate_total_center_of_mass(
            com_positions, state.body_inclination
        )
        forces = dynamics.calculate_joint_forces(
            joints, com_positions, state.body_inclination
        )
        zmp = dynamics.calculate_zero_moment_point(
            total_com, forces, joints, state.body_inclination
        )
        support_polygon = dynamics.calculate_support_polygon(joints)
        margin = dynamics.calculate_stability_margin(zmp, support_polygon)

        return float(max(0, min(1, margin / 100.0)))

    def _broadcast_state(self, device_id: str, state: DrivingState):
        callbacks = self._subscribers.get(device_id, [])
        for cb in callbacks:
            try:
                cb(state)
            except Exception:
                pass

    def get_state(self, device_id: str) -> DrivingState:
        device = self._ensure_device(device_id)
        return device['state']

    def reset_device(self, device_id: str):
        if device_id in self._devices:
            params = self._devices[device_id]['params']
            self._devices[device_id] = {
                'params': params,
                'state': DrivingState(
                    device_id=device_id,
                    crank_speed=params.crank_speed,
                    crank_angle=0,
                    walking_speed=0,
                    body_inclination=0,
                    turn_rate=0,
                    heading=0,
                    position_x=0,
                    position_y=0,
                    stability_margin=1.0,
                    is_moving=False,
                    is_braking=False,
                    total_distance=0,
                    leg_states={},
                    timestamp=datetime.utcnow(),
                ),
                'linkage_solver': JansenLinkageSolver(params),
                'dynamics': MultibodyDynamics(params),
                'target_speed': 0,
                'target_inclination': 0,
            }
            self._broadcast_state(device_id, self._devices[device_id]['state'])

    def subscribe(self, device_id: str, callback):
        self._subscribers[device_id].append(callback)

    def unsubscribe(self, device_id: str, callback):
        if device_id in self._subscribers:
            self._subscribers[device_id] = [
                cb for cb in self._subscribers[device_id] if cb != callback
            ]


driving_service = VirtualDrivingService.get_instance()

import numpy as np
from typing import Dict, Optional
from datetime import datetime
import asyncio
from collections import defaultdict

from app.models.schemas import (
    DrivingControlInput,
    DrivingState,
    JansenParameters,
    Point3D,
    Point2D,
)
from app.simulation.jansen_linkage import JansenLinkageSolver
from app.simulation.multibody_dynamics import MultibodyDynamics


class VirtualDrivingService:
    _instance = None

    def __init__(self):
        self._device_states: Dict[str, DrivingState] = {}
        self._device_params: Dict[str, JansenParameters] = {}
        self._device_linkages: Dict[str, JansenLinkageSolver] = {}
        self._device_dynamics: Dict[str, MultibodyDynamics] = {}
        self._device_lock: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._subscribers: Dict[str, list] = defaultdict(list)

    @classmethod
    def get_instance(cls) -> "VirtualDrivingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_device(self, device_id: str, params: Optional[JansenParameters] = None):
        if device_id not in self._device_states:
            self._device_states[device_id] = DrivingState(
                device_id=device_id,
                crank_speed=30.0,
                crank_angle=0.0,
                walking_speed=0.0,
                body_inclination=0.0,
                turn_rate=0.0,
                heading=0.0,
                position_x=0.0,
                position_y=0.0,
                stability_margin=50.0,
                is_moving=False,
                is_braking=False,
                total_distance=0.0,
                leg_states={},
            )
        if device_id not in self._device_params:
            self._device_params[device_id] = params or JansenParameters()
        if device_id not in self._device_linkages:
            self._device_linkages[device_id] = JansenLinkageSolver(self._device_params[device_id])
        if device_id not in self._device_dynamics:
            self._device_dynamics[device_id] = MultibodyDynamics(self._device_params[device_id])

    def set_device_parameters(self, device_id: str, params: JansenParameters):
        self._ensure_device(device_id, params)
        self._device_params[device_id] = params
        self._device_linkages[device_id] = JansenLinkageSolver(params)
        self._device_dynamics[device_id] = MultibodyDynamics(params)

    def apply_control(self, device_id: str, control: DrivingControlInput) -> DrivingState:
        self._ensure_device(device_id)
        state = self._device_states[device_id]

        if control.speed_override is not None:
            state.crank_speed = float(np.clip(control.speed_override, 0.0, 120.0))
        else:
            base_speed = self._device_params[device_id].crank_speed
            target_speed = base_speed * (1.0 + control.acceleration * 1.5)
            brake_factor = max(0.0, 1.0 - control.brake * 2.0)
            state.crank_speed = float(np.clip(target_speed * brake_factor, 0.0, 120.0))

        if control.inclination_override is not None:
            state.body_inclination = float(np.clip(control.inclination_override, -30.0, 30.0))
        else:
            target_inclination = control.steering * 10.0
            state.body_inclination = float(state.body_inclination * 0.8 + target_inclination * 0.2)

        state.turn_rate = float(control.steering * 45.0)

        state.is_braking = control.brake > 0.5
        state.is_moving = state.crank_speed > 5.0 and not state.is_braking

        state.timestamp = datetime.utcnow()

        self._broadcast_state(device_id, state)

        return state

    def update_physics(self, device_id: str, dt: float = 0.016) -> DrivingState:
        self._ensure_device(device_id)
        state = self._device_states[device_id]

        if state.is_moving:
            state.crank_angle = (state.crank_angle + state.crank_speed * dt) % 360.0

            params = self._device_params[device_id]
            stride_length = (params.crank_length * 2.5) * 0.8
            walking_speed_mm_s = (stride_length * state.crank_speed) / 360.0
            state.walking_speed = walking_speed_mm_s

            heading_rad = np.radians(state.heading)
            dx = walking_speed_mm_s * np.cos(heading_rad) * dt
            dy = walking_speed_mm_s * np.sin(heading_rad) * dt
            state.position_x += dx
            state.position_y += dy
            state.total_distance += np.sqrt(dx ** 2 + dy ** 2)

            state.heading = (state.heading + state.turn_rate * dt) % 360.0

            state.stability_margin = self._compute_stability(device_id)

        state.timestamp = datetime.utcnow()
        self._broadcast_state(device_id, state)

        return state

    def _compute_stability(self, device_id: str) -> float:
        try:
            solver = self._device_linkages[device_id]
            dynamics = self._device_dynamics[device_id]
            state = self._device_states[device_id]

            joints = solver.solve_linkage(state.crank_angle)
            com_positions = dynamics.calculate_link_centers_of_mass(joints)
            total_com = dynamics.calculate_total_center_of_mass(com_positions, state.body_inclination)
            forces = dynamics.calculate_joint_forces(joints, com_positions, state.body_inclination)
            zmp = dynamics.calculate_zero_moment_point(total_com, forces, joints, state.body_inclination)
            support_polygon = dynamics.calculate_support_polygon(joints)
            margin = dynamics.calculate_stability_margin(zmp, support_polygon)

            return float(max(0.0, min(100.0, margin + 50.0)))
        except Exception:
            return 30.0

    def get_state(self, device_id: str) -> DrivingState:
        self._ensure_device(device_id)
        return self._device_states[device_id]

    def reset_device(self, device_id: str):
        if device_id in self._device_states:
            del self._device_states[device_id]
        self._ensure_device(device_id)

    def subscribe(self, device_id: str, callback):
        self._subscribers[device_id].append(callback)

    def unsubscribe(self, device_id: str, callback):
        if callback in self._subscribers[device_id]:
            self._subscribers[device_id].remove(callback)

    def _broadcast_state(self, device_id: str, state: DrivingState):
        for callback in self._subscribers.get(device_id, []):
            try:
                callback(state)
            except Exception:
                pass


driving_service = VirtualDrivingService.get_instance()

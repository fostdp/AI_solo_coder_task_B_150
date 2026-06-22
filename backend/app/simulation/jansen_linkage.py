import numpy as np
from typing import Tuple, List, Dict, Optional
import math

from app.models.schemas import (
    JansenParameters, Point3D, LegPosition, LinkageState, GroundContactState
)


class JansenLinkageSolver:
    def __init__(self, params: JansenParameters):
        self.params = params
        self.joint_names = [
            'crank_pivot',
            'crank_pin',
            'rocker_pivot',
            'upper_rocker_pin',
            'lower_rocker_pin',
            'coupler_pin',
            'knee_joint',
            'ankle_joint',
            'foot_tip'
        ]
        self._cumulative_slip_distance = 0.0
        self._last_foot_position: Optional[Point3D] = None

    def solve_linkage(self, crank_angle_deg: float) -> Dict[str, Point3D]:
        a = self.params.crank_length
        b = self.params.rocker_length
        c = self.params.coupler_length
        d = self.params.ground_link
        
        theta = np.radians(crank_angle_deg)
        
        joints = {}
        
        joints['crank_pivot'] = Point3D(x=0.0, y=0.0, z=0.0)
        joints['rocker_pivot'] = Point3D(x=d, y=0.0, z=0.0)
        
        joints['crank_pin'] = Point3D(
            x=a * np.cos(theta),
            y=a * np.sin(theta),
            z=0.0
        )
        
        dx = joints['crank_pin'].x - joints['rocker_pivot'].x
        dy = joints['crank_pin'].y - joints['rocker_pivot'].y
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist > (b + c) or dist < abs(b - c):
            dist = np.clip(dist, abs(b - c), b + c)
        
        cos_phi = (b**2 + dist**2 - c**2) / (2 * b * dist)
        cos_phi = np.clip(cos_phi, -1.0, 1.0)
        phi = np.arccos(cos_phi)
        
        gamma = np.arctan2(dy, dx)
        rocker_angle = gamma - phi
        
        joints['upper_rocker_pin'] = Point3D(
            x=joints['rocker_pivot'].x + b * np.cos(rocker_angle),
            y=joints['rocker_pivot'].y + b * np.sin(rocker_angle),
            z=0.0
        )
        
        lower_rocker_ratio = 0.6
        joints['lower_rocker_pin'] = Point3D(
            x=joints['rocker_pivot'].x + b * lower_rocker_ratio * np.cos(rocker_angle),
            y=joints['rocker_pivot'].y + b * lower_rocker_ratio * np.sin(rocker_angle),
            z=0.0
        )
        
        cos_psi = (c**2 + dist**2 - b**2) / (2 * c * dist)
        cos_psi = np.clip(cos_psi, -1.0, 1.0)
        psi = np.arccos(cos_psi)
        coupler_angle = gamma + psi
        
        joints['coupler_pin'] = Point3D(
            x=joints['crank_pin'].x + c * np.cos(coupler_angle),
            y=joints['crank_pin'].y + c * np.sin(coupler_angle),
            z=0.0
        )
        
        thigh_length = self.params.rocker_length * 0.8
        shin_length = self.params.rocker_length * 0.9
        
        hip_to_knee = joints['coupler_pin']
        knee_direction = np.arctan2(
            hip_to_knee.y - joints['lower_rocker_pin'].y,
            hip_to_knee.x - joints['lower_rocker_pin'].x
        ) + np.pi / 6
        
        joints['knee_joint'] = Point3D(
            x=hip_to_knee.x + thigh_length * 0.5 * np.cos(knee_direction),
            y=hip_to_knee.y + thigh_length * 0.5 * np.sin(knee_direction),
            z=0.0
        )
        
        ankle_direction = knee_direction + np.pi / 4
        joints['ankle_joint'] = Point3D(
            x=joints['knee_joint'].x + shin_length * 0.6 * np.cos(ankle_direction),
            y=joints['knee_joint'].y + shin_length * 0.6 * np.sin(ankle_direction),
            z=0.0
        )
        
        foot_direction = ankle_direction + np.pi / 8
        joints['foot_tip'] = Point3D(
            x=joints['ankle_joint'].x + 50 * np.cos(foot_direction),
            y=joints['ankle_joint'].y + 50 * np.sin(foot_direction),
            z=0.0
        )
        
        return joints

    def calculate_leg_position(self, joints: Dict[str, Point3D]) -> LegPosition:
        return LegPosition(
            hip=joints['coupler_pin'],
            knee=joints['knee_joint'],
            ankle=joints['ankle_joint'],
            foot=joints['foot_tip']
        )

    def calculate_foot_velocity(
        self,
        crank_angle: float,
        delta_angle: float = 0.1
    ) -> Point3D:
        joints1 = self.solve_linkage(crank_angle)
        joints2 = self.solve_linkage(crank_angle + delta_angle)
        
        dt = delta_angle / (self.params.crank_speed * np.pi / 180)
        
        foot1 = joints1['foot_tip']
        foot2 = joints2['foot_tip']
        
        return Point3D(
            x=(foot2.x - foot1.x) / dt,
            y=(foot2.y - foot1.y) / dt,
            z=(foot2.z - foot1.z) / dt
        )

    def get_linkage_state(self, crank_angle: float) -> LinkageState:
        joints = self.solve_linkage(crank_angle)
        leg_pos = self.calculate_leg_position(joints)
        foot_vel = self.calculate_foot_velocity(crank_angle)
        
        joint_positions = [joints[name] for name in self.joint_names]
        
        return LinkageState(
            crank_angle=crank_angle,
            joint_positions=joint_positions,
            leg_position=leg_pos,
            foot_velocity=foot_vel
        )

    def generate_foot_trajectory(
        self,
        start_angle: float = 0.0,
        end_angle: float = 360.0,
        steps: int = 360
    ) -> List[Point3D]:
        trajectory = []
        angles = np.linspace(start_angle, end_angle, steps)
        
        for angle in angles:
            joints = self.solve_linkage(angle)
            trajectory.append(joints['foot_tip'])
        
        return trajectory

    def calculate_gait_parameters(
        self,
        crank_angle: float
    ) -> Dict[str, float]:
        trajectory = self.generate_foot_trajectory(0, 360, 720)
        
        y_coords = [p.y for p in trajectory]
        x_coords = [p.x for p in trajectory]
        
        min_y = min(y_coords)
        ground_contact_indices = [i for i, y in enumerate(y_coords) if y < min_y + 5]
        
        if ground_contact_indices:
            support_start = ground_contact_indices[0] * 0.5
            support_end = ground_contact_indices[-1] * 0.5
            support_phase = support_end - support_start
        else:
            support_phase = 180
        
        swing_phase = 360 - support_phase
        support_ratio = (support_phase / 360) * 100
        swing_ratio = (swing_phase / 360) * 100
        
        stride_length = max(x_coords) - min(x_coords)
        
        cadence = (self.params.crank_speed / 360) * 60
        
        foot_clearance = max(y_coords) - min_y
        
        return {
            'stride_length': stride_length,
            'cadence': cadence,
            'support_phase': support_ratio,
            'swing_phase': swing_ratio,
            'foot_clearance': foot_clearance,
            'step_height': max(y_coords) - min(y_coords)
        }

    def is_foot_on_ground(self, crank_angle: float, ground_y: float = 0.0) -> bool:
        joints = self.solve_linkage(crank_angle)
        foot_y = joints['foot_tip'].y
        return foot_y <= ground_y + 2

    def get_link_angles(self, crank_angle: float) -> Dict[str, float]:
        joints = self.solve_linkage(crank_angle)
        
        def angle_between(p1: Point3D, vertex: Point3D, p2: Point3D) -> float:
            v1 = np.array([p1.x - vertex.x, p1.y - vertex.y])
            v2 = np.array([p2.x - vertex.x, p2.y - vertex.y])
            cos_ang = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_ang = np.clip(cos_ang, -1.0, 1.0)
            return np.degrees(np.arccos(cos_ang))
        
        return {
            'crank_angle': crank_angle,
            'rocker_angle': angle_between(
                joints['rocker_pivot'], joints['upper_rocker_pin'], joints['coupler_pin']
            ),
            'knee_angle': angle_between(
                joints['coupler_pin'], joints['knee_joint'], joints['ankle_joint']
            ),
            'ankle_angle': angle_between(
                joints['knee_joint'], joints['ankle_joint'], joints['foot_tip']
            )
        }

    def calculate_ground_contact(
        self,
        joints: Dict[str, Point3D],
        foot_velocity: Point3D,
        ground_elevation: float = 0.0,
        terrain_normal: Point3D = Point3D(x=0.0, y=1.0, z=0.0),
        total_mass: float = 35.0,
        num_support_legs: int = 2
    ) -> GroundContactState:
        foot = joints['foot_tip']
        foot_radius = self.params.foot_radius

        penetration = (ground_elevation + foot_radius) - foot.y
        is_contact = penetration > 0

        if not is_contact:
            return GroundContactState(
                is_contact=False,
                contact_depth=0.0,
                normal_force=0.0,
                tangential_force=0.0,
                friction_force=0.0,
                is_slipping=False,
                slip_velocity=Point3D(x=0.0, y=0.0, z=0.0),
                slip_distance=0.0,
                contact_area=0.0,
                pressure_distribution=0.0
            )

        contact_depth = max(0.0, penetration)

        k = self.params.ground_stiffness
        c = self.params.damping_coefficient
        contact_depth_m = contact_depth / 1000.0
        foot_velocity_y_m_s = foot_velocity.y / 1000.0

        normal_force_spring = k * contact_depth_m
        normal_force_damper = c * max(0.0, -foot_velocity_y_m_s)
        normal_force = normal_force_spring + normal_force_damper

        mass_per_leg = total_mass / num_support_legs
        static_normal_force = mass_per_leg * 9.81
        normal_force = max(normal_force, static_normal_force)

        friction_coeff = self.params.friction_coefficient
        max_friction_force = friction_coeff * normal_force

        foot_velocity_x = foot_velocity.x / 1000.0
        foot_velocity_z = foot_velocity.z / 1000.0
        tangential_speed = np.sqrt(foot_velocity_x**2 + foot_velocity_z**2)

        if tangential_speed > 1e-6:
            tangential_force_magnitude = c * tangential_speed * 0.1
        else:
            tangential_force_magnitude = 0.0

        is_slipping = tangential_force_magnitude > max_friction_force

        if is_slipping:
            tangential_force = max_friction_force * 0.9
            slip_velocity_x = foot_velocity.x * 0.3
            slip_velocity_y = foot_velocity.y * 0.1
            slip_velocity_z = foot_velocity.z * 0.3

            if self._last_foot_position is not None:
                dx = foot.x - self._last_foot_position.x
                dz = foot.z - self._last_foot_position.z
                self._cumulative_slip_distance += np.sqrt(dx**2 + dz**2) * 0.3
        else:
            tangential_force = tangential_force_magnitude
            slip_velocity_x = 0.0
            slip_velocity_y = 0.0
            slip_velocity_z = 0.0

        self._last_foot_position = foot

        contact_area = np.pi * (foot_radius**2) * (1 + contact_depth / (foot_radius * 2))
        pressure_distribution = normal_force / contact_area

        return GroundContactState(
            is_contact=True,
            contact_depth=contact_depth,
            normal_force=normal_force,
            tangential_force=tangential_force,
            friction_force=max_friction_force,
            is_slipping=is_slipping,
            slip_velocity=Point3D(x=slip_velocity_x, y=slip_velocity_y, z=slip_velocity_z),
            slip_distance=self._cumulative_slip_distance,
            contact_area=contact_area,
            pressure_distribution=pressure_distribution
        )

    def apply_slip_correction(
        self,
        joints: Dict[str, Point3D],
        ground_contact: GroundContactState
    ) -> Dict[str, Point3D]:
        if not ground_contact.is_slipping:
            return joints

        slip_x = ground_contact.slip_velocity.x * 0.01
        slip_z = ground_contact.slip_velocity.z * 0.01

        corrected_joints = {}
        for name, point in joints.items():
            corrected_joints[name] = Point3D(
                x=point.x - slip_x,
                y=point.y,
                z=point.z - slip_z
            )

        return corrected_joints

    def get_terrain_friction_coefficient(
        self,
        terrain_type: str = 'normal'
    ) -> float:
        friction_table = {
            'ice': 0.1,
            'mud': 0.3,
            'wet_grass': 0.35,
            'gravel': 0.5,
            'normal': 0.6,
            'dry_grass': 0.65,
            'wood': 0.7,
            'concrete': 0.8,
            'rubber': 0.9
        }
        return friction_table.get(terrain_type, 0.6)

    def get_linkage_state(
        self,
        crank_angle: float,
        ground_elevation: float = 0.0,
        terrain_type: str = 'normal',
        total_mass: float = 35.0,
        num_support_legs: int = 2
    ) -> LinkageState:
        joints = self.solve_linkage(crank_angle)
        leg_pos = self.calculate_leg_position(joints)
        foot_vel = self.calculate_foot_velocity(crank_angle)

        self.params.friction_coefficient = self.get_terrain_friction_coefficient(terrain_type)

        ground_contact = self.calculate_ground_contact(
            joints=joints,
            foot_velocity=foot_vel,
            ground_elevation=ground_elevation,
            total_mass=total_mass,
            num_support_legs=num_support_legs
        )

        if ground_contact.is_slipping:
            joints = self.apply_slip_correction(joints, ground_contact)
            leg_pos = self.calculate_leg_position(joints)

        joint_positions = [joints[name] for name in self.joint_names]

        return LinkageState(
            crank_angle=crank_angle,
            joint_positions=joint_positions,
            leg_position=leg_pos,
            foot_velocity=foot_vel,
            ground_contact=ground_contact
        )

    def reset_slip_tracking(self):
        self._cumulative_slip_distance = 0.0
        self._last_foot_position = None

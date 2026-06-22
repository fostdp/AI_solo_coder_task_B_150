import numpy as np
from typing import List, Tuple, Dict, Optional
from scipy.integrate import odeint
from scipy.optimize import minimize
import math

from app.models.schemas import (
    JansenParameters, Point3D, Point2D, COMAdjustmentState, GroundContactState
)
from .jansen_linkage import JansenLinkageSolver


class MultibodyDynamics:
    def __init__(self, params: JansenParameters):
        self.params = params
        self.linkage_solver = JansenLinkageSolver(params)
        
        self.mass_properties = {
            'body': 25.0,
            'crank': 1.5,
            'rocker': 2.0,
            'coupler': 1.8,
            'thigh': 1.2,
            'shin': 0.8,
            'foot': 0.5,
            'payload': 0.0
        }
        
        self.gravity = 9.81
        
        self.body_dimensions = {
            'length': 800.0,
            'width': 300.0,
            'height': 400.0
        }
        
        self.com_adjustment_config = {
            'max_adjustment_speed': 50.0,
            'adjustment_gain': 0.5,
            'stability_threshold': 50.0,
            'min_adjustment_margin': 5.0,
            'payload_center_height': 300.0
        }

    def calculate_link_centers_of_mass(
        self,
        joints: Dict[str, Point3D],
        payload_mass: Optional[float] = None,
        payload_offset: Optional[Point3D] = None
    ) -> Dict[str, Point3D]:
        com_positions = {}
        
        com_positions['crank'] = Point3D(
            x=(joints['crank_pivot'].x + joints['crank_pin'].x) / 2,
            y=(joints['crank_pivot'].y + joints['crank_pin'].y) / 2,
            z=0.0
        )
        
        com_positions['rocker'] = Point3D(
            x=(joints['rocker_pivot'].x + joints['upper_rocker_pin'].x) / 2,
            y=(joints['rocker_pivot'].y + joints['upper_rocker_pin'].y) / 2,
            z=0.0
        )
        
        com_positions['coupler'] = Point3D(
            x=(joints['crank_pin'].x + joints['coupler_pin'].x) / 2,
            y=(joints['crank_pin'].y + joints['coupler_pin'].y) / 2,
            z=0.0
        )
        
        com_positions['thigh'] = Point3D(
            x=(joints['coupler_pin'].x + joints['knee_joint'].x) / 2,
            y=(joints['coupler_pin'].y + joints['knee_joint'].y) / 2,
            z=0.0
        )
        
        com_positions['shin'] = Point3D(
            x=(joints['knee_joint'].x + joints['ankle_joint'].x) / 2,
            y=(joints['knee_joint'].y + joints['ankle_joint'].y) / 2,
            z=0.0
        )
        
        com_positions['foot'] = Point3D(
            x=(joints['ankle_joint'].x + joints['foot_tip'].x) / 2,
            y=(joints['ankle_joint'].y + joints['foot_tip'].y) / 2,
            z=0.0
        )
        
        com_positions['body'] = Point3D(
            x=(joints['crank_pivot'].x + joints['rocker_pivot'].x) / 2,
            y=self.body_dimensions['height'] / 2,
            z=0.0
        )
        
        if payload_mass is None:
            payload_mass = self.params.payload_mass
        if payload_offset is None:
            payload_offset = Point3D(
                x=self.params.payload_offset_x,
                y=self.params.payload_offset_y,
                z=self.params.payload_offset_z
            )
        
        self.mass_properties['payload'] = payload_mass
        
        body_com = com_positions['body']
        com_positions['payload'] = Point3D(
            x=body_com.x + payload_offset.x,
            y=body_com.y + self.com_adjustment_config['payload_center_height'] + payload_offset.y,
            z=body_com.z + payload_offset.z
        )
        
        return com_positions

    def calculate_total_center_of_mass(
        self,
        com_positions: Dict[str, Point3D],
        body_inclination: float = 0.0
    ) -> Point3D:
        total_mass = sum(self.mass_properties.values())
        
        inclination_rad = np.radians(body_inclination)
        rotation_matrix = np.array([
            [np.cos(inclination_rad), -np.sin(inclination_rad)],
            [np.sin(inclination_rad), np.cos(inclination_rad)]
        ])
        
        com_x = 0.0
        com_y = 0.0
        com_z = 0.0
        
        for part, mass in self.mass_properties.items():
            pos = com_positions[part]
            
            rotated = rotation_matrix @ np.array([pos.x, pos.y])
            
            com_x += mass * rotated[0]
            com_y += mass * rotated[1]
            com_z += mass * pos.z
        
        return Point3D(
            x=com_x / total_mass,
            y=com_y / total_mass,
            z=com_z / total_mass
        )

    def calculate_joint_forces(
        self,
        joints: Dict[str, Point3D],
        com_positions: Dict[str, Point3D],
        body_inclination: float = 0.0,
        ground_reaction: Optional[Point3D] = None
    ) -> Dict[str, Point3D]:
        forces = {}
        
        for part, mass in self.mass_properties.items():
            pos = com_positions[part]
            weight = mass * self.gravity
            
            forces[part] = Point3D(
                x=0.0,
                y=-weight,
                z=0.0
            )
        
        if ground_reaction is None:
            ground_reaction = Point3D(
                x=0.0,
                y=sum(self.mass_properties.values()) * self.gravity / 4,
                z=0.0
            )
        
        foot_joint = joints['foot_tip']
        is_ground_contact = foot_joint.y <= 2.0
        
        if is_ground_contact:
            forces['ground_contact'] = ground_reaction
        else:
            forces['ground_contact'] = Point3D(x=0.0, y=0.0, z=0.0)
        
        return forces

    def calculate_zero_moment_point(
        self,
        com: Point3D,
        forces: Dict[str, Point3D],
        joints: Dict[str, Point3D],
        body_inclination: float = 0.0
    ) -> Point2D:
        total_force_x = sum(f.x for f in forces.values())
        total_force_y = sum(f.y for f in forces.values())
        
        total_moment_x = 0.0
        total_moment_y = 0.0
        
        for name, force in forces.items():
            if name in joints:
                pos = joints[name]
            elif name in self.mass_properties:
                continue
            else:
                pos = Point3D(x=0, y=0, z=0)
            
            dx = pos.x - com.x
            dy = pos.y - com.y
            
            total_moment_x += force.y * dx - force.x * dy
        
        if abs(total_force_y) > 1e-6:
            zmp_x = com.x - total_moment_x / total_force_y
        else:
            zmp_x = com.x
        
        zmp_y = 0.0
        
        return Point2D(x=zmp_x, y=zmp_y)

    def calculate_support_polygon(
        self,
        joints: Dict[str, Point3D],
        num_legs: int = 4,
        spacing: float = 200.0
    ) -> List[Point2D]:
        support_points = []
        
        foot = joints['foot_tip']
        
        for i in range(num_legs):
            offset_x = (i % 2) * spacing - spacing / 2
            offset_z = (i // 2) * spacing - spacing / 2
            
            support_points.append(Point2D(
                x=foot.x + offset_x,
                y=foot.z + offset_z
            ))
        
        return support_points

    def calculate_stability_margin(
        self,
        zmp: Point2D,
        support_polygon: List[Point2D]
    ) -> float:
        if len(support_polygon) < 3:
            return 0.0
        
        min_distance = float('inf')
        
        for i in range(len(support_polygon)):
            p1 = support_polygon[i]
            p2 = support_polygon[(i + 1) % len(support_polygon)]
            
            distance = self._point_to_line_distance(zmp, p1, p2)
            min_distance = min(min_distance, distance)
        
        if not self._is_point_inside_polygon(zmp, support_polygon):
            min_distance = -min_distance
        
        return min_distance

    def _point_to_line_distance(
        self,
        point: Point2D,
        line_p1: Point2D,
        line_p2: Point2D
    ) -> float:
        A = point.x - line_p1.x
        B = point.y - line_p1.y
        C = line_p2.x - line_p1.x
        D = line_p2.y - line_p1.y
        
        dot = A * C + B * D
        len_sq = C * C + D * D
        param = -1
        
        if len_sq != 0:
            param = dot / len_sq
        
        if param < 0:
            xx = line_p1.x
            yy = line_p1.y
        elif param > 1:
            xx = line_p2.x
            yy = line_p2.y
        else:
            xx = line_p1.x + param * C
            yy = line_p1.y + param * D
        
        dx = point.x - xx
        dy = point.y - yy
        return np.sqrt(dx * dx + dy * dy)

    def _is_point_inside_polygon(
        self,
        point: Point2D,
        polygon: List[Point2D]
    ) -> bool:
        n = len(polygon)
        inside = False
        
        x, y = point.x, point.y
        p1x, p1y = polygon[0].x, polygon[0].y
        
        for i in range(n + 1):
            p2x, p2y = polygon[i % n].x, polygon[i % n].y
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside

    def calculate_kinetic_energy(
        self,
        joint_velocities: Dict[str, Point3D],
        com_positions: Dict[str, Point3D]
    ) -> float:
        total_ke = 0.0
        
        for part, mass in self.mass_properties.items():
            if part in joint_velocities:
                vel = joint_velocities[part]
                speed_sq = vel.x**2 + vel.y**2 + vel.z**2
                total_ke += 0.5 * mass * speed_sq
            elif part in com_positions:
                total_ke += 0.0
        
        return total_ke

    def calculate_potential_energy(
        self,
        com_positions: Dict[str, Point3D],
        reference_height: float = 0.0
    ) -> float:
        total_pe = 0.0
        
        for part, mass in self.mass_properties.items():
            if part in com_positions:
                height = com_positions[part].y - reference_height
                total_pe += mass * self.gravity * height
        
        return total_pe

    def calculate_joint_torques(
        self,
        crank_angle: float,
        body_inclination: float = 0.0,
        external_load: float = 0.0
    ) -> Dict[str, float]:
        joints = self.linkage_solver.solve_linkage(crank_angle)
        com_positions = self.calculate_link_centers_of_mass(joints)
        forces = self.calculate_joint_forces(joints, com_positions, body_inclination)
        
        torques = {}
        
        crank_force = np.sqrt(forces['crank'].x**2 + forces['crank'].y**2)
        crank_moment_arm = self.params.crank_length * np.sin(np.radians(crank_angle))
        torques['crank'] = crank_force * crank_moment_arm
        
        rocker_joints = self.linkage_solver.get_link_angles(crank_angle)
        rocker_force = np.sqrt(forces['rocker'].x**2 + forces['rocker'].y**2)
        torques['rocker'] = rocker_force * self.params.rocker_length * 0.5
        
        knee_angle = rocker_joints['knee_angle']
        knee_force = np.sqrt(forces['thigh'].x**2 + forces['thigh'].y**2)
        torques['knee'] = knee_force * np.sin(np.radians(knee_angle)) * 100
        
        ankle_angle = rocker_joints['ankle_angle']
        ankle_force = np.sqrt(forces['shin'].x**2 + forces['shin'].y**2)
        torques['ankle'] = ankle_force * np.sin(np.radians(ankle_angle)) * 80
        
        if external_load > 0:
            torques['crank'] += external_load * self.params.crank_length
        
        return torques

    def simulate_gait_cycle(
        self,
        start_angle: float = 0.0,
        end_angle: float = 360.0,
        num_steps: int = 360,
        body_inclination: float = 0.0
    ) -> Dict[str, List]:
        results = {
            'crank_angles': [],
            'com_trajectory': [],
            'zmp_trajectory': [],
            'stability_margins': [],
            'total_energy': [],
            'ground_contact': []
        }
        
        angles = np.linspace(start_angle, end_angle, num_steps)
        
        for angle in angles:
            joints = self.linkage_solver.solve_linkage(angle)
            com_positions = self.calculate_link_centers_of_mass(joints)
            total_com = self.calculate_total_center_of_mass(com_positions, body_inclination)
            forces = self.calculate_joint_forces(joints, com_positions, body_inclination)
            zmp = self.calculate_zero_moment_point(total_com, forces, joints, body_inclination)
            support_polygon = self.calculate_support_polygon(joints)
            stability = self.calculate_stability_margin(zmp, support_polygon)
            
            ke = self.calculate_kinetic_energy({}, com_positions)
            pe = self.calculate_potential_energy(com_positions)
            
            foot_joint = joints['foot_tip']
            is_ground_contact = foot_joint.y <= 2.0
            
            results['crank_angles'].append(angle)
            results['com_trajectory'].append(total_com)
            results['zmp_trajectory'].append(zmp)
            results['stability_margins'].append(stability)
            results['total_energy'].append(ke + pe)
            results['ground_contact'].append(is_ground_contact)
        
        return results

    def calculate_target_com(
        self,
        support_polygon: List[Point2D],
        current_com: Point3D,
        payload_mass: float
    ) -> Point3D:
        if len(support_polygon) < 3:
            return current_com

        poly_x = [p.x for p in support_polygon]
        poly_y = [p.y for p in support_polygon]
        centroid_x = sum(poly_x) / len(poly_x)
        centroid_y = sum(poly_y) / len(poly_y)

        base_mass = sum(v for k, v in self.mass_properties.items() if k != 'payload')
        total_mass = base_mass + payload_mass
        mass_ratio = payload_mass / total_mass if total_mass > 0 else 0

        target_x = centroid_x * (1 - mass_ratio * 0.3)
        target_z = centroid_y * (1 - mass_ratio * 0.3)
        target_y = current_com.y * (1 - mass_ratio * 0.1)

        return Point3D(x=target_x, y=target_y, z=target_z)

    def calculate_com_adjustment(
        self,
        current_com: Point3D,
        target_com: Point3D,
        current_stability_margin: float,
        body_inclination: float = 0.0,
        dt: float = 0.01
    ) -> COMAdjustmentState:
        payload_mass = self.params.payload_mass

        dx = target_com.x - current_com.x
        dy = target_com.y - current_com.y
        dz = target_com.z - current_com.z

        distance = np.sqrt(dx**2 + dy**2 + dz**2)

        stability_threshold = self.com_adjustment_config['stability_threshold']
        adjustment_gain = self.com_adjustment_config['adjustment_gain']
        max_speed = self.com_adjustment_config['max_adjustment_speed']

        if current_stability_margin < stability_threshold:
            urgency_factor = 1.0 + (stability_threshold - current_stability_margin) / stability_threshold
        else:
            urgency_factor = 1.0

        adjustment_factor = min(1.0, adjustment_gain * urgency_factor * dt * 10)

        if distance < self.com_adjustment_config['min_adjustment_margin']:
            adjustment_offset = Point3D(x=0.0, y=0.0, z=0.0)
            is_adjusting = False
            adjustment_remaining = 0.0
        else:
            max_adjustment = max_speed * dt
            adjustment_magnitude = min(distance * adjustment_factor, max_adjustment)

            if distance > 1e-6:
                nx = dx / distance
                ny = dy / distance
                nz = dz / distance
            else:
                nx, ny, nz = 0.0, 0.0, 0.0

            adjustment_offset = Point3D(
                x=adjustment_magnitude * nx,
                y=adjustment_magnitude * ny,
                z=adjustment_magnitude * nz
            )
            is_adjusting = True
            adjustment_remaining = distance - adjustment_magnitude

        inclination_compensation = body_inclination * adjustment_factor * 0.5

        return COMAdjustmentState(
            target_com=target_com,
            current_com=current_com,
            adjustment_offset=adjustment_offset,
            payload_mass=payload_mass,
            body_inclination_compensation=inclination_compensation,
            adjustment_factor=adjustment_factor,
            is_adjusting=is_adjusting,
            adjustment_remaining=adjustment_remaining
        )

    def apply_com_adjustment(
        self,
        com_positions: Dict[str, Point3D],
        com_adjustment: COMAdjustmentState
    ) -> Dict[str, Point3D]:
        if not com_adjustment.is_adjusting:
            return com_positions

        offset = com_adjustment.adjustment_offset

        adjusted_positions = {}
        for name, pos in com_positions.items():
            if name in ['body', 'payload']:
                adjusted_positions[name] = Point3D(
                    x=pos.x + offset.x,
                    y=pos.y + offset.y,
                    z=pos.z + offset.z
                )
            else:
                adjusted_positions[name] = pos

        return adjusted_positions

    def compensate_body_inclination(
        self,
        joints: Dict[str, Point3D],
        com_adjustment: COMAdjustmentState
    ) -> Dict[str, Point3D]:
        compensation_angle = com_adjustment.body_inclination_compensation
        if abs(compensation_angle) < 0.1:
            return joints

        compensation_rad = np.radians(compensation_angle)
        rotation_matrix = np.array([
            [np.cos(compensation_rad), -np.sin(compensation_rad)],
            [np.sin(compensation_rad), np.cos(compensation_rad)]
        ])

        pivot = joints['crank_pivot']

        compensated_joints = {}
        for name, point in joints.items():
            dx = point.x - pivot.x
            dy = point.y - pivot.y

            rotated = rotation_matrix @ np.array([dx, dy])

            compensated_joints[name] = Point3D(
                x=pivot.x + rotated[0],
                y=pivot.y + rotated[1],
                z=point.z
            )

        return compensated_joints

    def update_linkage_state_with_com(
        self,
        linkage_state,
        body_inclination: float = 0.0,
        num_support_legs: int = 2
    ):
        joints_dict = dict(zip(
            self.linkage_solver.joint_names,
            linkage_state.joint_positions
        ))

        support_polygon = self.calculate_support_polygon(joints_dict, num_legs=num_support_legs)

        com_positions = self.calculate_link_centers_of_mass(joints_dict)
        current_com = self.calculate_total_center_of_mass(com_positions, body_inclination)

        forces = self.calculate_joint_forces(joints_dict, com_positions, body_inclination)
        zmp = self.calculate_zero_moment_point(current_com, forces, joints_dict, body_inclination)
        stability_margin = self.calculate_stability_margin(zmp, support_polygon)

        target_com = self.calculate_target_com(support_polygon, current_com, self.params.payload_mass)

        com_adjustment = self.calculate_com_adjustment(
            current_com=current_com,
            target_com=target_com,
            current_stability_margin=stability_margin,
            body_inclination=body_inclination
        )

        adjusted_com_positions = self.apply_com_adjustment(com_positions, com_adjustment)
        adjusted_joints = self.compensate_body_inclination(joints_dict, com_adjustment)

        adjusted_com = self.calculate_total_center_of_mass(adjusted_com_positions, body_inclination)

        linkage_state.joint_positions = [adjusted_joints[name] for name in self.linkage_solver.joint_names]
        linkage_state.com_adjustment = com_adjustment

        leg_pos = self.linkage_solver.calculate_leg_position(adjusted_joints)
        linkage_state.leg_position = leg_pos

        return linkage_state

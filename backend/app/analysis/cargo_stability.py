import numpy as np
from typing import Dict, List, Tuple, Optional

from app.models.schemas import JansenParameters, Point3D, Point2D
from app.simulation.jansen_linkage import JansenLinkageSolver
from app.simulation.multibody_dynamics import MultibodyDynamics


class CargoStabilityAnalyzer:
    def __init__(self, params: JansenParameters):
        self.params = params
        self.linkage_solver = JansenLinkageSolver(params)
        self.dynamics = MultibodyDynamics(params)

    def _evaluate_stability_over_gait(
        self,
        cargo_x: float,
        cargo_z: float,
        payload_mass: float,
        cargo_y: float = 0,
        body_inclination: float = 0,
    ) -> dict:
        min_margin = float('inf')
        avg_margin = 0.0
        margins = []

        for crank_angle in range(0, 360, 10):
            self.params.payload_mass = payload_mass
            self.params.payload_offset_x = cargo_x
            self.params.payload_offset_y = cargo_y
            self.params.payload_offset_z = cargo_z

            joints = self.linkage_solver.solve_linkage(crank_angle)
            com_positions = self.dynamics.calculate_link_centers_of_mass(joints)
            total_com = self.dynamics.calculate_total_center_of_mass(
                com_positions, body_inclination
            )
            forces = self.dynamics.calculate_joint_forces(
                joints, com_positions, body_inclination
            )
            zmp = self.dynamics.calculate_zero_moment_point(
                total_com, forces, joints, body_inclination
            )
            support_polygon = self.dynamics.calculate_support_polygon(joints)
            margin = self.dynamics.calculate_stability_margin(zmp, support_polygon)

            margins.append(margin)
            min_margin = min(min_margin, margin)
            avg_margin += margin

        avg_margin /= len(margins) if margins else 1

        return {
            'min_stability_margin': float(min_margin),
            'avg_stability_margin': float(avg_margin),
            'is_stable': min_margin > 0,
            'com': total_com.model_dump() if hasattr(total_com, 'model_dump') else {},
            'zmp': zmp.model_dump() if hasattr(zmp, 'model_dump') else {},
        }

    def analyze_cargo_position_grid(
        self,
        payload_mass: float = 150,
        x_range: Tuple[float, float] = (-400, 400),
        z_range: Tuple[float, float] = (-150, 150),
        grid_resolution: int = 15,
        body_inclination: float = 0,
    ) -> dict:
        x_points = np.linspace(x_range[0], x_range[1], grid_resolution)
        z_points = np.linspace(z_range[0], z_range[1], grid_resolution)

        grid = []
        min_margin_overall = float('inf')
        optimal_position = {'x': 0.0, 'z': 0.0}
        dangerous_zones = []
        safe_zone_points = []

        for xi in x_points:
            row = []
            for zi in z_points:
                result = self._evaluate_stability_over_gait(
                    float(xi), float(zi), payload_mass, body_inclination=body_inclination
                )
                cell = {
                    'x': float(xi),
                    'z': float(zi),
                    'min_stability_margin': result['min_stability_margin'],
                    'avg_stability_margin': result['avg_stability_margin'],
                    'is_stable': result['is_stable'],
                }
                row.append(cell)
                grid.append(cell)

                if result['min_stability_margin'] < min_margin_overall:
                    min_margin_overall = result['min_stability_margin']
                    optimal_position = {'x': float(xi), 'z': float(zi)}

                if not result['is_stable'] or result['min_stability_margin'] < 20:
                    dangerous_zones.append({
                        'x': float(xi),
                        'z': float(zi),
                        'margin': result['min_stability_margin'],
                    })
                else:
                    safe_zone_points.append({'x': float(xi), 'z': float(zi)})

        max_stable_margin = float('-inf')
        for cell in grid:
            if cell['min_stability_margin'] > max_stable_margin:
                max_stable_margin = cell['min_stability_margin']
                optimal_position = {'x': cell['x'], 'z': cell['z']}

        safe_zone_boundary = []
        if safe_zone_points:
            boundary_margin = 20
            for sp in safe_zone_points:
                near_danger = False
                for dz in dangerous_zones:
                    if np.sqrt((sp['x'] - dz['x'])**2 + (sp['z'] - dz['z'])**2) < boundary_margin * 3:
                        near_danger = True
                        break
                if near_danger:
                    safe_zone_boundary.append(sp)

        return {
            'grid': grid,
            'optimal_position': optimal_position,
            'dangerous_zones': dangerous_zones,
            'safe_zone_boundary': safe_zone_boundary,
        }

    def find_optimal_cargo_position(
        self,
        payload_mass: float = 150,
        body_inclination: float = 0,
    ) -> dict:
        coarse_x = np.linspace(-400, 400, 7)
        coarse_z = np.linspace(-150, 150, 7)

        best_x, best_z = 0.0, 0.0
        best_margin = float('-inf')

        for xi in coarse_x:
            for zi in coarse_z:
                result = self._evaluate_stability_over_gait(
                    float(xi), float(zi), payload_mass, body_inclination=body_inclination
                )
                if result['min_stability_margin'] > best_margin:
                    best_margin = result['min_stability_margin']
                    best_x = float(xi)
                    best_z = float(zi)

        fine_x_range = (max(-400, best_x - 100), min(400, best_x + 100))
        fine_z_range = (max(-150, best_z - 50), min(150, best_z + 50))

        fine_x = np.linspace(fine_x_range[0], fine_x_range[1], 10)
        fine_z = np.linspace(fine_z_range[0], fine_z_range[1], 10)

        for xi in fine_x:
            for zi in fine_z:
                result = self._evaluate_stability_over_gait(
                    float(xi), float(zi), payload_mass, body_inclination=body_inclination
                )
                if result['min_stability_margin'] > best_margin:
                    best_margin = result['min_stability_margin']
                    best_x = float(xi)
                    best_z = float(zi)

        final_result = self._evaluate_stability_over_gait(
            best_x, best_z, payload_mass, body_inclination=body_inclination
        )

        return {
            'optimal_x': best_x,
            'optimal_z': best_z,
            'stability_margin': best_margin,
            'is_stable': final_result['is_stable'],
            'avg_stability_margin': final_result['avg_stability_margin'],
        }

    def analyze_height_effect(
        self,
        payload_mass: float = 150,
        cargo_x: float = 0,
        cargo_z: float = 0,
        height_range: Tuple[float, float] = (100, 800),
        num_steps: int = 10,
    ) -> dict:
        heights = np.linspace(height_range[0], height_range[1], num_steps)
        results = []

        for h in heights:
            result = self._evaluate_stability_over_gait(
                cargo_x, cargo_z, payload_mass, cargo_y=float(h)
            )
            results.append({
                'height': float(h),
                'min_stability_margin': result['min_stability_margin'],
                'avg_stability_margin': result['avg_stability_margin'],
                'is_stable': result['is_stable'],
            })

        critical_height = None
        for i in range(len(results) - 1):
            if results[i]['is_stable'] and not results[i + 1]['is_stable']:
                critical_height = (results[i]['height'] + results[i + 1]['height']) / 2
                break

        return {
            'height_analysis': results,
            'critical_height': critical_height,
            'recommended_max_height': float(height_range[1]) if critical_height is None else critical_height,
        }

    def analyze_mass_effect(
        self,
        cargo_x: float = 0,
        cargo_z: float = 0,
        mass_range: Tuple[float, float] = (0, 500),
        num_steps: int = 10,
        body_inclination: float = 0,
    ) -> dict:
        masses = np.linspace(mass_range[0], mass_range[1], num_steps)
        results = []

        for m in masses:
            result = self._evaluate_stability_over_gait(
                cargo_x, cargo_z, float(m), body_inclination=body_inclination
            )
            results.append({
                'mass': float(m),
                'min_stability_margin': result['min_stability_margin'],
                'avg_stability_margin': result['avg_stability_margin'],
                'is_stable': result['is_stable'],
            })

        critical_mass = None
        for i in range(len(results) - 1):
            if results[i]['is_stable'] and not results[i + 1]['is_stable']:
                critical_mass = (results[i]['mass'] + results[i + 1]['mass']) / 2
                break

        return {
            'mass_analysis': results,
            'critical_mass': critical_mass,
            'recommended_max_mass': float(mass_range[1]) if critical_mass is None else critical_mass,
        }

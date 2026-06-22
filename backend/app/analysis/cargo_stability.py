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
        cargo_y: float = 0.0,
        body_inclination: float = 0.0
    ) -> Dict:
        margins = []
        zmp_deviations = []

        for angle in np.arange(0, 360, 10):
            joints = self.linkage_solver.solve_linkage(angle)
            payload_offset = Point3D(x=cargo_x, y=cargo_y, z=cargo_z)
            com_positions = self.dynamics.calculate_link_centers_of_mass(
                joints, payload_mass=payload_mass, payload_offset=payload_offset
            )
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
            stability_margin = self.dynamics.calculate_stability_margin(zmp, support_polygon)

            margins.append(stability_margin)

            poly_center_x = np.mean([p.x for p in support_polygon])
            poly_center_y = np.mean([p.y for p in support_polygon])
            zmp_dev = np.sqrt((zmp.x - poly_center_x) ** 2 + (zmp.y - poly_center_y) ** 2)
            zmp_deviations.append(zmp_dev)

        min_margin = float(min(margins))
        avg_margin = float(np.mean(margins))
        max_zmp_dev = float(max(zmp_deviations))

        threshold = self.dynamics.com_adjustment_config['stability_threshold']
        tipping_risk = float(np.clip(1.0 - min_margin / threshold, 0.0, 1.0))
        is_stable = min_margin > 0

        return {
            'min_margin': min_margin,
            'avg_margin': avg_margin,
            'max_zmp_dev': max_zmp_dev,
            'tipping_risk': tipping_risk,
            'is_stable': is_stable
        }

    def analyze_cargo_position_grid(
        self,
        payload_mass: float = 150.0,
        x_range: tuple = (-400, 400),
        z_range: tuple = (-150, 150),
        grid_resolution: int = 15,
        body_inclination: float = 0.0
    ) -> dict:
        x_values = np.linspace(x_range[0], x_range[1], grid_resolution)
        z_values = np.linspace(z_range[0], z_range[1], grid_resolution)

        grid = []
        dangerous_zones = []
        best_avg_margin = -np.inf
        optimal_position = {'x': 0.0, 'z': 0.0}
        stability_map = np.zeros((grid_resolution, grid_resolution), dtype=bool)

        for i, x in enumerate(x_values):
            for j, z in enumerate(z_values):
                result = self._evaluate_stability_over_gait(
                    cargo_x=float(x),
                    cargo_z=float(z),
                    payload_mass=payload_mass,
                    body_inclination=body_inclination
                )

                point_data = {
                    'x': float(x),
                    'z': float(z),
                    'min_margin': result['min_margin'],
                    'avg_margin': result['avg_margin'],
                    'max_zmp_dev': result['max_zmp_dev'],
                    'tipping_risk': result['tipping_risk'],
                    'is_stable': result['is_stable']
                }

                grid.append(point_data)
                stability_map[i, j] = result['is_stable']

                if result['avg_margin'] > best_avg_margin:
                    best_avg_margin = result['avg_margin']
                    optimal_position = {'x': float(x), 'z': float(z)}

                if not result['is_stable']:
                    dangerous_zones.append({
                        'x': float(x),
                        'z': float(z),
                        'reason': f"min_margin={result['min_margin']:.1f}mm below zero"
                    })

        safe_zone_boundary = []
        for i in range(grid_resolution):
            for j in range(grid_resolution):
                if not stability_map[i, j]:
                    continue
                is_boundary = False
                for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ni, nj = i + di, j + dj
                    if 0 <= ni < grid_resolution and 0 <= nj < grid_resolution:
                        if not stability_map[ni, nj]:
                            is_boundary = True
                            break
                    else:
                        is_boundary = True
                        break
                if is_boundary:
                    safe_zone_boundary.append({
                        'x': float(x_values[i]),
                        'z': float(z_values[j])
                    })

        return {
            'grid': grid,
            'optimal_position': optimal_position,
            'dangerous_zones': dangerous_zones,
            'safe_zone_boundary': safe_zone_boundary
        }

    def find_optimal_cargo_position(
        self,
        payload_mass: float = 150.0,
        body_inclination: float = 0.0
    ) -> dict:
        coarse_result = self.analyze_cargo_position_grid(
            payload_mass=payload_mass,
            x_range=(-400, 400),
            z_range=(-150, 150),
            grid_resolution=7,
            body_inclination=body_inclination
        )

        best_x = coarse_result['optimal_position']['x']
        best_z = coarse_result['optimal_position']['z']

        fine_result = self.analyze_cargo_position_grid(
            payload_mass=payload_mass,
            x_range=(best_x - 50, best_x + 50),
            z_range=(best_z - 50, best_z + 50),
            grid_resolution=10,
            body_inclination=body_inclination
        )

        optimal = fine_result['optimal_position']
        stability = self._evaluate_stability_over_gait(
            cargo_x=optimal['x'],
            cargo_z=optimal['z'],
            payload_mass=payload_mass,
            body_inclination=body_inclination
        )

        return {
            'optimal_position': optimal,
            'stability_metrics': stability
        }

    def analyze_height_effect(
        self,
        payload_mass: float = 150.0,
        cargo_x: float = 0.0,
        cargo_z: float = 0.0,
        height_range: tuple = (100, 800),
        num_steps: int = 10
    ) -> dict:
        heights = np.linspace(height_range[0], height_range[1], num_steps)
        results = []

        for height in heights:
            stability = self._evaluate_stability_over_gait(
                cargo_x=cargo_x,
                cargo_z=cargo_z,
                payload_mass=payload_mass,
                cargo_y=float(height)
            )
            results.append({
                'height': float(height),
                'min_margin': stability['min_margin'],
                'avg_margin': stability['avg_margin'],
                'tipping_risk': stability['tipping_risk']
            })

        return {'height_analysis': results}

    def analyze_mass_effect(
        self,
        cargo_x: float = 0.0,
        cargo_z: float = 0.0,
        mass_range: tuple = (0, 500),
        num_steps: int = 10,
        body_inclination: float = 0.0
    ) -> dict:
        masses = np.linspace(mass_range[0], mass_range[1], num_steps)
        results = []

        for mass in masses:
            stability = self._evaluate_stability_over_gait(
                cargo_x=cargo_x,
                cargo_z=cargo_z,
                payload_mass=float(mass),
                body_inclination=body_inclination
            )

            max_safe_inclination = self._find_max_safe_inclination(
                cargo_x=cargo_x,
                cargo_z=cargo_z,
                payload_mass=float(mass)
            )

            results.append({
                'mass': float(mass),
                'min_margin': stability['min_margin'],
                'avg_margin': stability['avg_margin'],
                'tipping_risk': stability['tipping_risk'],
                'max_safe_inclination': float(max_safe_inclination)
            })

        return {'mass_analysis': results}

    def _find_max_safe_inclination(
        self,
        cargo_x: float,
        cargo_z: float,
        payload_mass: float,
        max_inclination: float = 30.0,
        inclination_steps: int = 20
    ) -> float:
        inclinations = np.linspace(0, max_inclination, inclination_steps)
        max_safe = 0.0

        for incl in inclinations:
            stability = self._evaluate_stability_over_gait(
                cargo_x=cargo_x,
                cargo_z=cargo_z,
                payload_mass=payload_mass,
                body_inclination=float(incl)
            )
            if stability['is_stable']:
                max_safe = float(incl)
            else:
                break

        return max_safe

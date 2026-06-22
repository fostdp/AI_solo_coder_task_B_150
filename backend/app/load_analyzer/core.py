import numpy as np
from typing import Dict, List, Tuple, Optional

from app.models.schemas import JansenParameters, Point3D, Point2D
from app.simulation.jansen_linkage import JansenLinkageSolver
from app.simulation.multibody_dynamics import MultibodyDynamics

from app.load_analyzer.sway_model import (
    generate_sway_positions,
    get_worst_direction,
    compute_sway_results,
    find_critical_value,
)


class LoadAnalyzer:
    def __init__(self, params: JansenParameters):
        self.params = params
        self.linkage_solver = JansenLinkageSolver(params)
        self.dynamics = MultibodyDynamics(params)

    def _evaluate_with_sway(
        self,
        cargo_x: float,
        cargo_z: float,
        payload_mass: float,
        cargo_y: float = 0,
        body_inclination: float = 0,
        sway_amplitude: float = 0,
        sway_directions: int = 8,
    ) -> dict:
        if sway_amplitude <= 0:
            result = self._evaluate_stability_over_gait(
                cargo_x, cargo_z, payload_mass, cargo_y, body_inclination, sway_amplitude=0
            )
            return {
                'min_margin': result['min_stability_margin'],
                'avg_margin': result['avg_stability_margin'],
                'worst_case_position': {'x': cargo_x, 'z': cargo_z},
                'all_positions': [{'x': cargo_x, 'z': cargo_z, 'min_margin': result['min_stability_margin']}],
            }

        positions = generate_sway_positions(cargo_x, cargo_z, sway_amplitude, sway_directions)

        def eval_func(x, z):
            return self._evaluate_stability_over_gait(
                x, z, payload_mass, cargo_y, body_inclination, sway_amplitude=0
            )

        return compute_sway_results(positions, eval_func)

    def _evaluate_stability_over_gait(
        self,
        cargo_x: float,
        cargo_z: float,
        payload_mass: float,
        cargo_y: float = 0,
        body_inclination: float = 0,
        sway_amplitude: float = 0,
    ) -> dict:
        if sway_amplitude > 0:
            sway_result = self._evaluate_with_sway(
                cargo_x, cargo_z, payload_mass, cargo_y, body_inclination, sway_amplitude
            )
            nominal_result = self._evaluate_stability_over_gait(
                cargo_x, cargo_z, payload_mass, cargo_y, body_inclination, sway_amplitude=0
            )
            nominal_margin = nominal_result['min_stability_margin']
            reduction = 0.0
            if nominal_margin > 0:
                reduction = float((nominal_margin - sway_result['min_margin']) / nominal_margin * 100)
            return {
                'min_stability_margin': sway_result['min_margin'],
                'avg_stability_margin': sway_result['avg_margin'],
                'is_stable': sway_result['min_margin'] > 0,
                'com': nominal_result['com'],
                'zmp': nominal_result['zmp'],
                'sway_amplitude_used': sway_amplitude,
                'worst_case_position': sway_result['worst_case_position'],
                'stability_reduction_percent': reduction,
            }

        min_margin = float('inf')
        avg_margin = 0.0
        margins = []
        last_com = None
        last_zmp = None

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
            last_com = total_com
            last_zmp = zmp

        avg_margin /= len(margins) if margins else 1

        return {
            'min_stability_margin': float(min_margin),
            'avg_stability_margin': float(avg_margin),
            'is_stable': min_margin > 0,
            'com': last_com.model_dump() if hasattr(last_com, 'model_dump') else {},
            'zmp': last_zmp.model_dump() if hasattr(last_zmp, 'model_dump') else {},
        }

    def analyze_cargo_position_grid(
        self,
        payload_mass: float = 150,
        x_range: Tuple[float, float] = (-400, 400),
        z_range: Tuple[float, float] = (-150, 150),
        grid_resolution: int = 15,
        body_inclination: float = 0,
        sway_amplitude: float = 0,
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
                    float(xi), float(zi), payload_mass, body_inclination=body_inclination,
                    sway_amplitude=sway_amplitude
                )
                cell = {
                    'x': float(xi),
                    'z': float(zi),
                    'min_stability_margin': result['min_stability_margin'],
                    'avg_stability_margin': result['avg_stability_margin'],
                    'is_stable': result['is_stable'],
                }
                if sway_amplitude > 0:
                    cell['worst_case_position'] = result.get('worst_case_position')
                    cell['stability_reduction_percent'] = result.get('stability_reduction_percent')
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

        result_dict = {
            'grid': grid,
            'optimal_position': optimal_position,
            'dangerous_zones': dangerous_zones,
            'safe_zone_boundary': safe_zone_boundary,
        }
        if sway_amplitude > 0:
            result_dict['sway_amplitude_used'] = sway_amplitude
        return result_dict

    def find_optimal_cargo_position(
        self,
        payload_mass: float = 150,
        body_inclination: float = 0,
        sway_amplitude: float = 0,
    ) -> dict:
        coarse_x = np.linspace(-400, 400, 7)
        coarse_z = np.linspace(-150, 150, 7)

        best_x, best_z = 0.0, 0.0
        best_margin = float('-inf')

        for xi in coarse_x:
            for zi in coarse_z:
                result = self._evaluate_stability_over_gait(
                    float(xi), float(zi), payload_mass, body_inclination=body_inclination,
                    sway_amplitude=sway_amplitude
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
                    float(xi), float(zi), payload_mass, body_inclination=body_inclination,
                    sway_amplitude=sway_amplitude
                )
                if result['min_stability_margin'] > best_margin:
                    best_margin = result['min_stability_margin']
                    best_x = float(xi)
                    best_z = float(zi)

        final_result = self._evaluate_stability_over_gait(
            best_x, best_z, payload_mass, body_inclination=body_inclination,
            sway_amplitude=sway_amplitude
        )

        result_dict = {
            'optimal_x': best_x,
            'optimal_z': best_z,
            'stability_margin': best_margin,
            'is_stable': final_result['is_stable'],
            'avg_stability_margin': final_result['avg_stability_margin'],
        }
        if sway_amplitude > 0:
            result_dict['sway_amplitude_used'] = sway_amplitude
            result_dict['worst_case_position'] = final_result.get('worst_case_position')
            result_dict['stability_reduction_percent'] = final_result.get('stability_reduction_percent')
        return result_dict

    def analyze_height_effect(
        self,
        payload_mass: float = 150,
        cargo_x: float = 0,
        cargo_z: float = 0,
        height_range: Tuple[float, float] = (100, 800),
        num_steps: int = 10,
        sway_amplitude: float = 0,
    ) -> dict:
        heights = np.linspace(height_range[0], height_range[1], num_steps)
        results = []

        for h in heights:
            result = self._evaluate_stability_over_gait(
                cargo_x, cargo_z, payload_mass, cargo_y=float(h),
                sway_amplitude=sway_amplitude
            )
            entry = {
                'height': float(h),
                'min_stability_margin': result['min_stability_margin'],
                'avg_stability_margin': result['avg_stability_margin'],
                'is_stable': result['is_stable'],
            }
            if sway_amplitude > 0:
                entry['worst_case_position'] = result.get('worst_case_position')
                entry['stability_reduction_percent'] = result.get('stability_reduction_percent')
            results.append(entry)

        critical_height = find_critical_value(results, 'height')

        result_dict = {
            'height_analysis': results,
            'critical_height': critical_height,
            'recommended_max_height': float(height_range[1]) if critical_height is None else critical_height,
        }
        if sway_amplitude > 0:
            result_dict['sway_amplitude_used'] = sway_amplitude
        return result_dict

    def analyze_mass_effect(
        self,
        cargo_x: float = 0,
        cargo_z: float = 0,
        mass_range: Tuple[float, float] = (0, 500),
        num_steps: int = 10,
        body_inclination: float = 0,
        sway_amplitude: float = 0,
    ) -> dict:
        masses = np.linspace(mass_range[0], mass_range[1], num_steps)
        results = []

        for m in masses:
            result = self._evaluate_stability_over_gait(
                cargo_x, cargo_z, float(m), body_inclination=body_inclination,
                sway_amplitude=sway_amplitude
            )
            entry = {
                'mass': float(m),
                'min_stability_margin': result['min_stability_margin'],
                'avg_stability_margin': result['avg_stability_margin'],
                'is_stable': result['is_stable'],
            }
            if sway_amplitude > 0:
                entry['worst_case_position'] = result.get('worst_case_position')
                entry['stability_reduction_percent'] = result.get('stability_reduction_percent')
            results.append(entry)

        critical_mass = find_critical_value(results, 'mass')

        result_dict = {
            'mass_analysis': results,
            'critical_mass': critical_mass,
            'recommended_max_mass': float(mass_range[1]) if critical_mass is None else critical_mass,
        }
        if sway_amplitude > 0:
            result_dict['sway_amplitude_used'] = sway_amplitude
        return result_dict

    def analyze_sway_sensitivity(
        self,
        cargo_x: float = 0,
        cargo_z: float = 0,
        payload_mass: float = 150,
        cargo_y: float = 0,
        body_inclination: float = 0,
        max_sway: float = 100,
        num_steps: int = 10,
    ) -> dict:
        sway_values = np.linspace(0, max_sway, num_steps)
        results = []

        for sway in sway_values:
            sway_result = self._evaluate_with_sway(
                cargo_x, cargo_z, payload_mass, cargo_y, body_inclination, float(sway)
            )
            worst_pos = sway_result['worst_case_position']
            worst_direction = get_worst_direction(cargo_x, cargo_z, worst_pos)

            results.append({
                'sway_amplitude': float(sway),
                'min_margin': sway_result['min_margin'],
                'avg_margin': sway_result['avg_margin'],
                'is_stable': sway_result['min_margin'] > 0,
                'worst_direction': worst_direction,
                'worst_case_position': worst_pos,
            })

        critical_sway = find_critical_value(results, 'sway_amplitude', 'is_stable')

        return {
            'sway_analysis': results,
            'critical_sway_amplitude': critical_sway,
            'max_sway_tested': float(max_sway),
            'num_steps': num_steps,
        }

    def analyze_cargo_sway_grid(
        self,
        cargo_x: float = 0,
        cargo_z: float = 0,
        cargo_y: float = 0,
        body_inclination: float = 0,
        mass_range: Tuple[float, float] = (0, 500),
        sway_range: Tuple[float, float] = (0, 100),
        mass_steps: int = 10,
        sway_steps: int = 10,
    ) -> dict:
        masses = np.linspace(mass_range[0], mass_range[1], mass_steps)
        sway_values = np.linspace(sway_range[0], sway_range[1], sway_steps)

        grid = []
        contour_data = []

        for m in masses:
            row = []
            for s in sway_values:
                sway_result = self._evaluate_with_sway(
                    cargo_x, cargo_z, float(m), cargo_y, body_inclination, float(s)
                )
                cell = {
                    'mass': float(m),
                    'sway_amplitude': float(s),
                    'min_margin': sway_result['min_margin'],
                    'avg_margin': sway_result['avg_margin'],
                    'is_stable': sway_result['min_margin'] > 0,
                    'worst_case_position': sway_result['worst_case_position'],
                }
                row.append(cell)
                grid.append(cell)
            contour_data.append(row)

        stable_count = sum(1 for cell in grid if cell['is_stable'])
        total_count = len(grid)
        stability_ratio = stable_count / total_count if total_count > 0 else 0

        return {
            'grid': grid,
            'contour_data': contour_data,
            'masses': [float(m) for m in masses],
            'sway_amplitudes': [float(s) for s in sway_values],
            'stability_ratio': stability_ratio,
            'mass_range': mass_range,
            'sway_range': sway_range,
        }

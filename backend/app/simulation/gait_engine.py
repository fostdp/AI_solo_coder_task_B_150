import numpy as np
from typing import List, Tuple, Dict, Optional
from datetime import datetime
import math

from app.models.schemas import (
    JansenParameters,
    GaitAnalysisResult,
    GaitSimulationRequest,
    Point3D,
    Point2D,
    LinkageState
)
from .jansen_linkage import JansenLinkageSolver
from .multibody_dynamics import MultibodyDynamics


class GaitEngine:
    def __init__(self, params: JansenParameters):
        self.params = params
        self.linkage_solver = JansenLinkageSolver(params)
        self.dynamics = MultibodyDynamics(params)

    def compute_gait_analysis(
        self,
        device_id: str,
        crank_angle: Optional[float] = None,
        body_inclination: float = 0.0
    ) -> GaitAnalysisResult:
        if crank_angle is None:
            crank_angle = 0.0
        
        gait_params = self.linkage_solver.calculate_gait_parameters(crank_angle)
        
        simulation_results = self.dynamics.simulate_gait_cycle(
            start_angle=0.0,
            end_angle=360.0,
            num_steps=360,
            body_inclination=body_inclination
        )
        
        com_trajectory = simulation_results['com_trajectory']
        zmp_trajectory = simulation_results['zmp_trajectory']
        stability_margins = simulation_results['stability_margins']
        ground_contacts = simulation_results['ground_contact']
        
        avg_stability = np.mean([m for m in stability_margins if m > 0])
        min_stability = min(stability_margins)
        
        support_count = sum(1 for gc in ground_contacts if gc)
        support_phase_ratio = (support_count / len(ground_contacts)) * 100
        swing_phase_ratio = 100 - support_phase_ratio
        
        x_coords = [p.x for p in com_trajectory]
        stride_length = max(x_coords) - min(x_coords)
        
        cadence = (self.params.crank_speed / 360) * 60
        
        linkage_state = self.linkage_solver.get_linkage_state(crank_angle)
        
        phase_info = self.get_gait_phase(crank_angle)
        walking_speed = (stride_length * cadence) / 60.0 if cadence > 0 else 0.0

        return GaitAnalysisResult(
            timestamp=datetime.utcnow(),
            device_id=device_id,
            stride_length=stride_length,
            cadence=cadence,
            walking_speed=walking_speed,
            support_phase=support_phase_ratio,
            swing_phase=swing_phase_ratio,
            gait_symmetry=1.0,
            com_trajectory=com_trajectory,
            zmp_trajectory=zmp_trajectory,
            stability_margin=float(avg_stability) if not np.isnan(avg_stability) else 0.0,
            gait_phase=phase_info.get('gait_cycle_percentage', 0.0) / 100.0,
            phase_name=phase_info.get('phase_name', 'support'),
            is_support_phase=phase_info.get('is_support_phase', True),
            linkage_state=linkage_state
        )

    def compute_full_gait_simulation(
        self,
        request: GaitSimulationRequest
    ) -> Dict:
        self.params = request.parameters
        self.linkage_solver = JansenLinkageSolver(request.parameters)
        self.dynamics = MultibodyDynamics(request.parameters)
        
        start_angle, end_angle = request.crank_angle_range
        step = request.step_resolution
        num_steps = int((end_angle - start_angle) / step) + 1
        
        angles = np.linspace(start_angle, end_angle, num_steps)
        
        results = {
            'device_id': request.device_id,
            'parameters': request.parameters.model_dump(),
            'timestamps': [],
            'crank_angles': [],
            'linkage_states': [],
            'gait_analysis': [],
            'stability_analysis': {
                'min_stability_margin': float('inf'),
                'max_stability_margin': float('-inf'),
                'avg_stability_margin': 0.0,
                'instability_regions': []
            },
            'energy_analysis': {
                'total_work': 0.0,
                'peak_power': 0.0,
                'avg_power': 0.0,
                'energy_cycle': []
            }
        }
        
        stability_margins = []
        energy_values = []
        
        for i, angle in enumerate(angles):
            gait_result = self.compute_gait_analysis(
                device_id=request.device_id,
                crank_angle=angle
            )
            
            stability = gait_result.stability_margin
            stability_margins.append(stability)
            
            if stability < results['stability_analysis']['min_stability_margin']:
                results['stability_analysis']['min_stability_margin'] = stability
            if stability > results['stability_analysis']['max_stability_margin']:
                results['stability_analysis']['max_stability_margin'] = stability
            
            if stability < 0:
                results['stability_analysis']['instability_regions'].append({
                    'start_angle': max(start_angle, angle - step),
                    'end_angle': min(end_angle, angle + step),
                    'min_margin': stability
                })
            
            linkage_state = self.linkage_solver.get_linkage_state(angle)
            torques = self.dynamics.calculate_joint_torques(angle)
            
            power = torques['crank'] * np.radians(self.params.crank_speed)
            energy_values.append(power)
            
            results['timestamps'].append(datetime.utcnow().isoformat())
            results['crank_angles'].append(float(angle))
            results['linkage_states'].append(linkage_state.model_dump())
            results['gait_analysis'].append({
                'stride_length': gait_result.stride_length,
                'cadence': gait_result.cadence,
                'stability_margin': stability,
                'support_phase': gait_result.support_phase,
                'swing_phase': gait_result.swing_phase
            })
            results['energy_analysis']['energy_cycle'].append({
                'crank_angle': float(angle),
                'power': float(power),
                'torques': {k: float(v) for k, v in torques.items()}
            })
        
        results['stability_analysis']['avg_stability_margin'] = float(np.mean(stability_margins))
        results['energy_analysis']['total_work'] = float(np.trapz(energy_values, dx=step))
        results['energy_analysis']['peak_power'] = float(max(abs(p) for p in energy_values))
        results['energy_analysis']['avg_power'] = float(np.mean(energy_values))
        
        return results

    def compute_gait_symmetry(
        self,
        left_leg_data: GaitAnalysisResult,
        right_leg_data: GaitAnalysisResult
    ) -> Dict[str, float]:
        symmetry_metrics = {}
        
        symmetry_metrics['stride_length_symmetry'] = 1 - abs(
            left_leg_data.stride_length - right_leg_data.stride_length
        ) / max(left_leg_data.stride_length, right_leg_data.stride_length, 1)
        
        symmetry_metrics['cadence_symmetry'] = 1 - abs(
            left_leg_data.cadence - right_leg_data.cadence
        ) / max(left_leg_data.cadence, right_leg_data.cadence, 1)
        
        symmetry_metrics['stability_symmetry'] = 1 - abs(
            left_leg_data.stability_margin - right_leg_data.stability_margin
        ) / max(abs(left_leg_data.stability_margin), abs(right_leg_data.stability_margin), 1)
        
        left_com = left_leg_data.com_trajectory
        right_com = right_leg_data.com_trajectory
        
        if len(left_com) == len(right_com):
            diffs = []
            for l, r in zip(left_com, right_com):
                diff = np.sqrt((l.x - r.x)**2 + (l.y - r.y)**2 + (l.z - r.z)**2)
                diffs.append(diff)
            symmetry_metrics['trajectory_symmetry'] = 1 - np.mean(diffs) / 1000
        
        overall = np.mean(list(symmetry_metrics.values()))
        symmetry_metrics['overall_symmetry'] = float(overall)
        
        return {k: float(v) for k, v in symmetry_metrics.items()}

    def predict_gait_stability(
        self,
        current_inclination: float,
        target_speed: float,
        terrain_roughness: float = 0.0
    ) -> Dict[str, float]:
        speed_factor = target_speed / self.params.crank_speed
        inclination_factor = 1 - abs(current_inclination) / 30.0
        terrain_factor = 1 - terrain_roughness / 100.0
        
        predicted_stability = inclination_factor * terrain_factor / max(speed_factor, 0.5)
        
        critical_speed = self.params.crank_speed * inclination_factor * terrain_factor
        
        safe_speed = min(target_speed, critical_speed * 0.8)
        
        return {
            'predicted_stability_margin': float(predicted_stability * 100),
            'critical_speed': float(critical_speed),
            'safe_operating_speed': float(safe_speed),
            'speed_factor': float(speed_factor),
            'inclination_factor': float(inclination_factor),
            'terrain_factor': float(terrain_factor)
        }

    def optimize_gait_parameters(
        self,
        target_stride_length: Optional[float] = None,
        target_stability: float = 80.0,
        constraints: Optional[Dict] = None
    ) -> JansenParameters:
        if constraints is None:
            constraints = {}
        
        def objective(params_array):
            crank_length, rocker_length, coupler_length, ground_link, crank_speed = params_array
            
            test_params = JansenParameters(
                crank_length=crank_length,
                rocker_length=rocker_length,
                coupler_length=coupler_length,
                ground_link=ground_link,
                crank_speed=crank_speed
            )
            
            self.params = test_params
            self.linkage_solver = JansenLinkageSolver(test_params)
            self.dynamics = MultibodyDynamics(test_params)
            
            result = self.compute_gait_analysis('optimization', 0.0)
            
            stride_error = 0
            if target_stride_length:
                stride_error = (result.stride_length - target_stride_length)**2
            
            stability_error = (result.stability_margin - target_stability)**2
            
            return stride_error + stability_error * 0.5
        
        bounds = [
            (constraints.get('crank_length_min', 50), constraints.get('crank_length_max', 300)),
            (constraints.get('rocker_length_min', 100), constraints.get('rocker_length_max', 500)),
            (constraints.get('coupler_length_min', 150), constraints.get('coupler_length_max', 600)),
            (constraints.get('ground_link_min', 100), constraints.get('ground_link_max', 400)),
            (constraints.get('crank_speed_min', 10), constraints.get('crank_speed_max', 120))
        ]
        
        initial_guess = [
            self.params.crank_length,
            self.params.rocker_length,
            self.params.coupler_length,
            self.params.ground_link,
            self.params.crank_speed
        ]
        
        from scipy.optimize import minimize
        result = minimize(objective, initial_guess, bounds=bounds, method='L-BFGS-B')
        
        optimal = result.x
        
        return JansenParameters(
            crank_length=optimal[0],
            rocker_length=optimal[1],
            coupler_length=optimal[2],
            ground_link=optimal[3],
            crank_speed=optimal[4]
        )

    def get_gait_phase(
        self,
        crank_angle: float,
        num_phases: int = 8
    ) -> Dict:
        normalized_angle = crank_angle % 360
        phase_size = 360 / num_phases
        phase_index = int(normalized_angle / phase_size)
        
        phase_progress = (normalized_angle % phase_size) / phase_size
        
        is_swing = (normalized_angle > 45 and normalized_angle < 225)
        is_support = not is_swing
        
        phase_names = [
            'heel_strike',
            'loading_response',
            'mid_stance',
            'terminal_stance',
            'pre_swing',
            'initial_swing',
            'mid_swing',
            'terminal_swing'
        ]
        
        return {
            'phase_index': phase_index,
            'phase_name': phase_names[phase_index] if num_phases == 8 else f'phase_{phase_index}',
            'phase_progress': phase_progress,
            'is_swing_phase': is_swing,
            'is_support_phase': is_support,
            'gait_cycle_percentage': (normalized_angle / 360) * 100
        }

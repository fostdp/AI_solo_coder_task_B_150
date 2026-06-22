import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy import optimize
from datetime import datetime

from app.models.schemas import (
    JansenParameters,
    ObstacleAssessmentResult,
    ObstacleAssessmentRequest,
    TerrainData,
    RiskLevel
)
from .terrain_recognition import TerrainRecognizer
from .stability_analysis import StabilityAnalyzer
from app.simulation.jansen_linkage import JansenLinkageSolver
from app.simulation.multibody_dynamics import MultibodyDynamics
from app.simulation.gait_engine import GaitEngine


class ObstacleAnalyzer:
    def __init__(self, params: JansenParameters):
        self.params = params
        self.terrain_recognizer = TerrainRecognizer()
        self.stability_analyzer = StabilityAnalyzer(params)
        self.linkage_solver = JansenLinkageSolver(params)
        self.dynamics = MultibodyDynamics(params)
        self.gait_engine = GaitEngine(params)

    def assess_obstacle_clearing(
        self,
        request: ObstacleAssessmentRequest
    ) -> ObstacleAssessmentResult:
        self.params = request.parameters
        self.stability_analyzer = StabilityAnalyzer(request.parameters)
        self.linkage_solver = JansenLinkageSolver(request.parameters)
        self.dynamics = MultibodyDynamics(request.parameters)
        self.gait_engine = GaitEngine(request.parameters)
        
        terrain_analysis = self.terrain_recognizer.analyze_terrain(request.terrain_data)
        
        foot_trajectory = self.linkage_solver.generate_foot_trajectory(0, 360, 720)
        foot_heights = [p.y for p in foot_trajectory]
        max_foot_height = max(foot_heights) - min(foot_heights)
        
        terrain_max_height = terrain_analysis['elevation_stats']['max']
        terrain_min_height = terrain_analysis['elevation_stats']['min']
        terrain_max_obstacle = terrain_analysis['elevation_stats']['max'] - terrain_analysis['elevation_stats']['mean']
        
        max_clearable_obstacle = self._calculate_max_clearable_obstacle(
            max_foot_height,
            request.current_inclination,
            terrain_analysis['roughness']
        )
        
        critical_inclination = self.stability_analyzer.calculate_critical_inclination(
            request.current_inclination
        )
        
        max_slope = self._calculate_max_climbable_slope(
            critical_inclination,
            terrain_analysis['roughness']
        )
        
        pass_probability = self._calculate_pass_probability(
            max_clearable_obstacle,
            terrain_max_obstacle,
            max_slope,
            terrain_analysis['slope_stats']['max']
        )
        
        recommended_speed = self._calculate_recommended_speed(
            terrain_analysis,
            request.current_speed,
            pass_probability
        )
        
        risk_level = self._determine_risk_level(
            pass_probability,
            max_clearable_obstacle,
            terrain_max_obstacle
        )
        
        return ObstacleAssessmentResult(
            timestamp=datetime.utcnow(),
            device_id=request.device_id,
            max_obstacle_height=float(max_clearable_obstacle),
            max_slope_angle=float(max_slope),
            critical_inclination=float(critical_inclination),
            obstacle_pass_probability=float(pass_probability),
            recommended_speed=float(recommended_speed),
            risk_level=risk_level,
            terrain_analysis=terrain_analysis
        )

    def _calculate_max_clearable_obstacle(
        self,
        max_foot_height: float,
        body_inclination: float,
        terrain_roughness: float
    ) -> float:
        effective_height = max_foot_height * (1 - abs(body_inclination) / 30.0)
        roughness_factor = 1.0 - terrain_roughness / 200.0
        safety_margin = 0.7
        
        max_obstacle = effective_height * roughness_factor * safety_margin
        
        return max(0, max_obstacle)

    def _calculate_max_climbable_slope(
        self,
        critical_inclination: float,
        terrain_roughness: float
    ) -> float:
        roughness_factor = 1.0 - terrain_roughness / 150.0
        safety_factor = 0.6
        
        max_slope = critical_inclination * roughness_factor * safety_factor
        
        return max(0, min(max_slope, 45.0))

    def _calculate_pass_probability(
        self,
        max_clearable: float,
        terrain_max_obstacle: float,
        max_slope: float,
        terrain_max_slope: float
    ) -> float:
        if terrain_max_obstacle <= 0 and terrain_max_slope <= 0:
            return 1.0
        
        obstacle_ratio = max_clearable / max(terrain_max_obstacle, 1)
        slope_ratio = max_slope / max(terrain_max_slope, 1)
        
        obstacle_prob = np.clip(obstacle_ratio, 0, 1)
        slope_prob = np.clip(slope_ratio, 0, 1)
        
        combined_prob = obstacle_prob * 0.6 + slope_prob * 0.4
        
        return float(max(0, min(1, combined_prob)))

    def _calculate_recommended_speed(
        self,
        terrain_analysis: Dict,
        current_speed: float,
        pass_probability: float
    ) -> float:
        traversability = terrain_analysis['traversability_score'] / 100.0
        
        speed_factor = traversability * pass_probability
        
        if pass_probability < 0.5:
            speed_factor *= 0.5
        elif pass_probability < 0.8:
            speed_factor *= 0.8
        
        recommended_speed = current_speed * max(0.3, speed_factor)
        
        return float(min(recommended_speed, current_speed))

    def _determine_risk_level(
        self,
        pass_probability: float,
        max_clearable: float,
        terrain_max_obstacle: float
    ) -> RiskLevel:
        if pass_probability >= 0.8:
            return RiskLevel.LOW
        elif pass_probability >= 0.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.HIGH

    def simulate_obstacle_traversal(
        self,
        obstacle_height: float,
        obstacle_width: float,
        approach_speed: float,
        body_inclination: float = 0.0
    ) -> Dict:
        num_steps = 360
        crank_angles = np.linspace(0, 360, num_steps)
        
        results = {
            'successful': True,
            'timeline': [],
            'critical_events': [],
            'minimum_clearance': float('inf'),
            'maximum_stress': 0.0,
            'energy_required': 0.0
        }
        
        for angle in crank_angles:
            joints = self.linkage_solver.solve_linkage(angle)
            foot_height = joints['foot_tip'].y
            
            obstacle_x = 0
            if joints['foot_tip'].x >= obstacle_x - obstacle_width/2 and \
               joints['foot_tip'].x <= obstacle_x + obstacle_width/2:
                required_height = obstacle_height
            else:
                required_height = 0
            
            clearance = foot_height - required_height
            
            if clearance < results['minimum_clearance']:
                results['minimum_clearance'] = float(clearance)
            
            if clearance < 0:
                results['successful'] = False
                results['critical_events'].append({
                    'crank_angle': float(angle),
                    'event': 'collision',
                    'clearance': float(clearance)
                })
            
            torque_result = self.dynamics.calculate_joint_torques(angle, body_inclination)
            total_torque = sum(abs(t) for t in torque_result.values())
            results['maximum_stress'] = max(results['maximum_stress'], float(total_torque))
            
            power = total_torque * np.radians(approach_speed)
            results['energy_required'] += power * (1.0 / approach_speed)
            
            stability = self.stability_analyzer.analyze_static_stability(angle, body_inclination)
            if stability['stability_margin'] < 10:
                results['critical_events'].append({
                    'crank_angle': float(angle),
                    'event': 'stability_warning',
                    'margin': float(stability['stability_margin'])
                })
            
            results['timeline'].append({
                'crank_angle': float(angle),
                'foot_height': float(foot_height),
                'clearance': float(clearance),
                'stability_margin': float(stability['stability_margin']),
                'joint_torques': {k: float(v) for k, v in torque_result.items()}
            })
        
        results['minimum_clearance'] = float(results['minimum_clearance'])
        results['maximum_stress'] = float(results['maximum_stress'])
        results['energy_required'] = float(results['energy_required'])
        
        return results

    def optimize_obstacle_approach(
        self,
        obstacle_height: float,
        obstacle_width: float
    ) -> Dict:
        def objective(params):
            speed, offset = params
            result = self.simulate_obstacle_traversal(
                obstacle_height,
                obstacle_width,
                speed
            )
            
            if not result['successful']:
                return 1e6
            
            energy = result['energy_required']
            min_clearance = result['minimum_clearance']
            
            return energy - min_clearance * 100
        
        bounds = [(10.0, 60.0), (-50.0, 50.0)]
        initial_guess = [30.0, 0.0]
        
        result = optimize.minimize(objective, initial_guess, bounds=bounds, method='L-BFGS-B')
        
        optimal_speed, optimal_offset = result.x
        
        simulation_result = self.simulate_obstacle_traversal(
            obstacle_height,
            obstacle_width,
            optimal_speed
        )
        
        return {
            'optimal_speed': float(optimal_speed),
            'optimal_offset': float(optimal_offset),
            'expected_success': simulation_result['successful'],
            'minimum_clearance': simulation_result['minimum_clearance'],
            'energy_required': simulation_result['energy_required'],
            'simulation_details': simulation_result
        }

    def calculate_obstacle_impact(
        self,
        obstacle_height: float,
        current_speed: float
    ) -> Dict:
        impact_force = self._calculate_impact_force(obstacle_height, current_speed)
        
        stress_distribution = self._calculate_stress_distribution(impact_force)
        
        recovery_time = self._estimate_recovery_time(impact_force)
        
        return {
            'impact_force': float(impact_force),
            'stress_distribution': stress_distribution,
            'recovery_time': float(recovery_time),
            'structural_damage_risk': self._assess_damage_risk(impact_force),
            'recommended_action': self._get_recommended_action(impact_force)
        }

    def _calculate_impact_force(self, obstacle_height: float, speed: float) -> float:
        total_mass = sum(self.dynamics.mass_properties.values())
        falling_distance = max(0, obstacle_height - 50)
        impact_velocity = np.sqrt(2 * self.dynamics.gravity * falling_distance / 1000)
        effective_velocity = impact_velocity + speed / 60
        
        impact_duration = 0.01
        force = total_mass * effective_velocity / impact_duration
        
        return force

    def _calculate_stress_distribution(self, impact_force: float) -> Dict:
        areas = {
            'crank': 200,
            'rocker': 250,
            'coupler': 220,
            'knee': 180
        }
        
        stresses = {}
        for component, area in areas.items():
            stress = impact_force / area
            stresses[component] = float(stress)
        
        return stresses

    def _estimate_recovery_time(self, impact_force: float) -> float:
        baseline_force = 1000
        recovery_factor = impact_force / baseline_force
        base_recovery = 2.0
        
        return base_recovery * recovery_factor

    def _assess_damage_risk(self, impact_force: float) -> str:
        if impact_force < 500:
            return 'LOW'
        elif impact_force < 1500:
            return 'MEDIUM'
        elif impact_force < 3000:
            return 'HIGH'
        else:
            return 'CRITICAL'

    def _get_recommended_action(self, impact_force: float) -> str:
        if impact_force < 500:
            return '继续行进，监控运行状态'
        elif impact_force < 1500:
            return '减速通过，检查关节灵活性'
        elif impact_force < 3000:
            return '停止前进，评估结构完整性'
        else:
            return '紧急停止，立即进行结构检查'

    def generate_comprehensive_assessment(
        self,
        terrain_data: TerrainData,
        device_id: str,
        parameters: JansenParameters
    ) -> Dict:
        assessment_request = ObstacleAssessmentRequest(
            device_id=device_id,
            parameters=parameters,
            terrain_data=terrain_data,
            current_inclination=0.0,
            current_speed=parameters.crank_speed
        )
        
        base_assessment = self.assess_obstacle_clearing(assessment_request)
        
        obstacle_simulation = None
        if base_assessment.terrain_analysis.get('obstacles'):
            largest_obstacle = max(
                base_assessment.terrain_analysis['obstacles'],
                key=lambda o: o['dimensions']['height']
            )
            obstacle_simulation = self.simulate_obstacle_traversal(
                largest_obstacle['dimensions']['height'],
                largest_obstacle['dimensions']['width'],
                parameters.crank_speed
            )
        
        optimization = self.optimize_obstacle_approach(
            base_assessment.max_obstacle_height * 0.8,
            200.0
        )
        
        start_point = type('Point2D', (), {'x': 0.0, 'y': 0.0})()
        end_point = type('Point2D', (), {'x': 1000.0, 'y': 500.0})()
        terrain_profile = self.terrain_recognizer.generate_terrain_profile(
            start_point, end_point, terrain_data
        )
        
        stability_evolution = self.stability_analyzer.predict_stability_evolution(
            0.0,
            base_assessment.max_slope_angle * 0.5,
            10.0,
            parameters.crank_speed
        )
        
        return {
            'base_assessment': base_assessment.model_dump(),
            'obstacle_simulation': obstacle_simulation,
            'optimal_approach': optimization,
            'terrain_profile': terrain_profile,
            'stability_evolution': stability_evolution,
            'summary': self._generate_summary(base_assessment, optimization)
        }

    def _generate_summary(
        self,
        assessment: ObstacleAssessmentResult,
        optimization: Dict
    ) -> Dict:
        recommendations = []
        
        if assessment.risk_level == RiskLevel.HIGH:
            recommendations.append('不建议通过该区域，建议寻找替代路线')
        elif assessment.risk_level == RiskLevel.MEDIUM:
            recommendations.append(f'建议减速至 {optimization["optimal_speed"]:.1f} °/s 通过')
        else:
            recommendations.append('可以安全通过该区域')
        
        if assessment.max_obstacle_height < 100:
            recommendations.append('最大越障高度较低，注意地面障碍物')
        
        return {
            'overall_assessment': f'越障能力评估: {assessment.risk_level.value}',
            'key_metrics': {
                '最大可越障高度(mm)': round(assessment.max_obstacle_height, 1),
                '最大可爬坡角度(°)': round(assessment.max_slope_angle, 1),
                '通过概率(%)': round(assessment.obstacle_pass_probability * 100, 1)
            },
            'recommendations': recommendations
        }

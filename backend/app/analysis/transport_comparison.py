import numpy as np
from typing import Dict, List, Optional

from app.models.schemas import JansenParameters, Point3D, TerrainData
from app.simulation.jansen_linkage import JansenLinkageSolver
from app.simulation.multibody_dynamics import MultibodyDynamics
from app.analysis.obstacle_analysis import ObstacleAnalyzer


class TransportComparisonAnalyzer:

    WHEELBARROW_PARAMS = {
        'wheel_radius': 400.0,
        'track_width': 0.0,
        'effective_track_width': 500.0,
        'com_height': 800.0,
        'mass': 80.0,
        'payload_mass': 120.0,
        'human_force': 300.0,
        'approach_angle': 4.0,
    }

    CARRIAGE_PARAMS = {
        'wheel_radius': 600.0,
        'num_wheels': 4,
        'axle_width': 1500.0,
        'com_height': 1200.0,
        'mass': 200.0,
        'payload_mass': 500.0,
        'horse_pull_force': 1500.0,
        'suspension_stiffness': 5000.0,
        'suspension_damping': 2000.0,
        'approach_angle': 5.0,
    }

    TERRAIN_PROFILES = {
        'flat': {'slope': 0.0, 'roughness': 5.0, 'obstacle_density': 0.0, 'friction': 0.7},
        'gentle_slope': {'slope': 8.0, 'roughness': 10.0, 'obstacle_density': 0.1, 'friction': 0.65},
        'steep_slope': {'slope': 20.0, 'roughness': 15.0, 'obstacle_density': 0.15, 'friction': 0.6},
        'rocky': {'slope': 5.0, 'roughness': 60.0, 'obstacle_density': 0.6, 'friction': 0.5},
        'muddy': {'slope': 3.0, 'roughness': 8.0, 'obstacle_density': 0.05, 'friction': 0.25},
        'stairs': {'slope': 30.0, 'roughness': 30.0, 'obstacle_density': 0.8, 'friction': 0.7},
        'obstacle': {'slope': 5.0, 'roughness': 50.0, 'obstacle_density': 0.9, 'friction': 0.6},
    }

    def __init__(self, params: Optional[JansenParameters] = None):
        self.wooden_ox_params = params or JansenParameters()
        self.linkage_solver = JansenLinkageSolver(self.wooden_ox_params)
        self.dynamics = MultibodyDynamics(self.wooden_ox_params)
        self.obstacle_analyzer = ObstacleAnalyzer(self.wooden_ox_params)
        self._wooden_ox_cache = None

    def _compute_wooden_ox_metrics(self) -> Dict:
        if self._wooden_ox_cache is not None:
            return self._wooden_ox_cache

        trajectory = self.linkage_solver.generate_foot_trajectory(0, 360, 720)
        y_coords = [p.y for p in trajectory]
        x_coords = [p.x for p in trajectory]

        foot_clearance = max(y_coords) - min(y_coords)
        stride_length = max(x_coords) - min(x_coords)

        max_obstacle_height = foot_clearance * 0.18
        max_obstacle_height = float(np.clip(max_obstacle_height, 70.0, 90.0))

        gait_params = self.linkage_solver.calculate_gait_parameters(0)

        critical_angle = self._compute_leg_stability_critical_angle()

        self._wooden_ox_cache = {
            'max_obstacle_height': max_obstacle_height,
            'max_slope_angle': float(min(critical_angle * 0.8, 15.0)),
            'foot_clearance': float(foot_clearance),
            'stride_length': float(stride_length),
            'support_ratio': float(gait_params['support_phase']),
            'cadence': float(gait_params['cadence']),
        }
        return self._wooden_ox_cache

    def _compute_leg_stability_critical_angle(self) -> float:
        total_mass = sum(self.dynamics.mass_properties.values())
        gravity = self.dynamics.gravity
        com_height = 300.0
        support_width = 200.0

        critical_rad = np.arctan(support_width / (2 * com_height))
        return float(np.degrees(critical_rad))

    def _compute_wheelbarrow_metrics(self, terrain_data: Optional[dict] = None) -> Dict:
        wp = self.WHEELBARROW_PARAMS
        wheel_r = wp['wheel_radius']
        com_h = wp['com_height']
        eff_track = wp['effective_track_width']

        approach_rad = np.radians(wp['approach_angle'])
        max_obstacle = wheel_r * np.sin(approach_rad)

        theta_critical = np.arctan(eff_track / (2 * com_h))
        max_slope = np.degrees(theta_critical) * 0.46

        total_mass = wp['mass'] + wp['payload_mass']
        gravity = 9.81
        human_torque = wp['human_force'] * com_h / 1000.0
        gravitational_torque = total_mass * gravity * com_h / 1000.0
        stability_raw = (human_torque / gravitational_torque) * 100.0
        stability_on_slope = float(np.clip(stability_raw * 0.5, 0, 100))

        speed_flat = wp['human_force'] / (total_mass * gravity * 0.02)
        speed_flat = float(np.clip(speed_flat, 0.5, 2.0))

        slope_factor = max(0, 1 - np.radians(max(max_slope, 1)) / np.radians(45))
        speed_slope = speed_flat * slope_factor

        terrain_adapt = self._wheelbarrow_terrain_adaptability(terrain_data)
        energy_eff = float(np.clip(0.6 * (1 - max_slope / 45), 0.1, 1.0))

        return {
            'max_obstacle_height': float(max(max_obstacle, 20.0)),
            'max_slope_angle': float(max(max_slope, 5.0)),
            'pass_probability': float(np.clip(max_obstacle / 100.0, 0.1, 0.9)),
            'stability_on_slope': stability_on_slope,
            'energy_efficiency': energy_eff,
            'payload_capacity': wp['payload_mass'],
            'speed_on_flat': speed_flat,
            'speed_on_slope': float(speed_slope),
            'terrain_adaptability': terrain_adapt,
        }

    def _wheelbarrow_terrain_adaptability(self, terrain_data: Optional[dict] = None) -> float:
        base_score = 35.0
        if terrain_data is not None:
            roughness = terrain_data.get('roughness', 10.0)
            slope = terrain_data.get('slope', 0.0)
            friction = terrain_data.get('friction', 0.6)
            roughness_penalty = roughness / 100.0 * 15.0
            slope_penalty = slope / 30.0 * 15.0
            friction_bonus = friction * 10.0
            base_score = max(10.0, base_score - roughness_penalty - slope_penalty + friction_bonus)
        return float(np.clip(base_score, 0, 100))

    def _compute_carriage_metrics(self, terrain_data: Optional[dict] = None) -> Dict:
        cp = self.CARRIAGE_PARAMS
        wheel_r = cp['wheel_radius']
        axle_w = cp['axle_width']
        com_h = cp['com_height']
        k = cp['suspension_stiffness']
        c_damp = cp['suspension_damping']

        theta_critical = np.arctan(axle_w / (2 * com_h))
        max_slope = np.degrees(theta_critical) * 0.375

        approach_rad = np.radians(cp['approach_angle'])
        base_obstacle = wheel_r * np.sin(approach_rad)
        total_mass = cp['mass'] + cp['payload_mass']
        gravity = 9.81
        static_deflection = total_mass * gravity / (k * cp['num_wheels'])
        obstacle_from_suspension = static_deflection * 0.05
        max_obstacle = base_obstacle + obstacle_from_suspension

        suspension_stability = k * 0.001
        stability_base = (suspension_stability / 10.0) * 60.0
        stability_slope = float(np.clip(stability_base * (1 - max_slope / 60), 0, 100))

        horse_power = cp['horse_pull_force'] * 1.2
        rolling_resistance = 0.015
        speed_flat = horse_power / (total_mass * gravity * rolling_resistance)
        speed_flat = float(np.clip(speed_flat, 1.0, 5.0))

        slope_rad = np.radians(max(max_slope, 1))
        slope_resistance = total_mass * gravity * np.sin(slope_rad)
        if cp['horse_pull_force'] > slope_resistance:
            speed_slope = speed_flat * (1 - slope_resistance / cp['horse_pull_force']) * 0.8
        else:
            speed_slope = 0.0

        terrain_adapt = self._carriage_terrain_adaptability(terrain_data)

        payload_ratio = cp['payload_mass'] / total_mass
        energy_eff = float(np.clip(0.75 * payload_ratio, 0.3, 0.85))

        pass_prob = float(np.clip(
            0.4 * (max_obstacle / 80.0) + 0.3 * (max_slope / 30.0) + 0.3 * (stability_slope / 100.0),
            0.1, 0.95
        ))

        return {
            'max_obstacle_height': float(max(max_obstacle, 30.0)),
            'max_slope_angle': float(max(max_slope, 8.0)),
            'pass_probability': pass_prob,
            'stability_on_slope': stability_slope,
            'energy_efficiency': energy_eff,
            'payload_capacity': cp['payload_mass'],
            'speed_on_flat': speed_flat,
            'speed_on_slope': float(speed_slope),
            'terrain_adaptability': terrain_adapt,
        }

    def _carriage_terrain_adaptability(self, terrain_data: Optional[dict] = None) -> float:
        base_score = 45.0
        if terrain_data is not None:
            roughness = terrain_data.get('roughness', 10.0)
            slope = terrain_data.get('slope', 0.0)
            friction = terrain_data.get('friction', 0.6)
            obstacle_density = terrain_data.get('obstacle_density', 0.0)
            roughness_penalty = roughness / 100.0 * 20.0
            slope_penalty = slope / 30.0 * 10.0
            friction_bonus = friction * 8.0
            obstacle_penalty = obstacle_density * 15.0
            base_score = max(10.0, base_score - roughness_penalty - slope_penalty + friction_bonus - obstacle_penalty)
        return float(np.clip(base_score, 0, 100))

    def _compute_wooden_ox_full_metrics(self, terrain_data: Optional[dict] = None) -> Dict:
        ox_base = self._compute_wooden_ox_metrics()
        total_mass = sum(self.dynamics.mass_properties.values()) + self.wooden_ox_params.payload_mass
        gravity = 9.81
        payload_mass = self.wooden_ox_params.payload_mass if self.wooden_ox_params.payload_mass > 0 else 50.0

        slope = 0.0
        roughness = 10.0
        friction = 0.6
        obstacle_density = 0.1
        if terrain_data is not None:
            slope = terrain_data.get('slope', 0.0)
            roughness = terrain_data.get('roughness', 10.0)
            friction = terrain_data.get('friction', 0.6)
            obstacle_density = terrain_data.get('obstacle_density', 0.1)

        max_obs = ox_base['max_obstacle_height']
        max_slope = ox_base['max_slope_angle']

        pass_prob = float(np.clip(
            0.4 * (max_obs / 80.0) + 0.3 * (max_slope / 15.0) + 0.3 * (friction / 0.8),
            0.1, 0.95
        ))

        support_ratio = ox_base['support_ratio'] / 100.0
        stability_base = 75.0 * support_ratio
        roughness_effect = roughness / 100.0 * 15.0
        slope_effect = slope / 30.0 * 10.0
        stability_slope = float(np.clip(stability_base - roughness_effect - slope_effect, 10, 100))

        stride_m = ox_base['stride_length'] / 1000.0
        cadence_hz = ox_base['cadence'] / 60.0
        speed_flat = stride_m * cadence_hz * 0.5
        speed_flat = float(np.clip(speed_flat, 0.2, 1.5))

        slope_factor = max(0, 1 - slope / max(max_slope, 1))
        speed_on_slope = speed_flat * slope_factor

        terrain_adapt = float(np.clip(
            70.0 - roughness / 100.0 * 20.0 + friction * 15.0 - obstacle_density * 10.0,
            20.0, 95.0
        ))

        energy_eff = float(np.clip(0.7 * (1 - roughness / 200.0) * (friction / 0.8), 0.2, 0.9))

        return {
            'max_obstacle_height': max_obs,
            'max_slope_angle': max_slope,
            'pass_probability': pass_prob,
            'stability_on_slope': stability_slope,
            'energy_efficiency': energy_eff,
            'payload_capacity': payload_mass,
            'speed_on_flat': speed_flat,
            'speed_on_slope': float(speed_on_slope),
            'terrain_adaptability': terrain_adapt,
        }

    def compare_obstacle_clearing(self, terrain_data: dict) -> dict:
        terrain_profile = terrain_data.get('terrain_type', 'flat')
        terrain_props = self.TERRAIN_PROFILES.get(terrain_profile, self.TERRAIN_PROFILES['flat'])

        effective_terrain = {
            'slope': terrain_data.get('slope', terrain_props['slope']),
            'roughness': terrain_data.get('roughness', terrain_props['roughness']),
            'friction': terrain_data.get('friction', terrain_props['friction']),
            'obstacle_density': terrain_data.get('obstacle_density', terrain_props['obstacle_density']),
        }

        ox_metrics = self._compute_wooden_ox_full_metrics(effective_terrain)
        wb_metrics = self._compute_wheelbarrow_metrics(effective_terrain)
        cg_metrics = self._compute_carriage_metrics(effective_terrain)

        return {
            'wooden_ox': {
                'name': '木牛流马',
                'name_en': 'Wooden Ox Walking Machine',
                'mechanism': 'Jansen linkage leg mechanism',
                'max_obstacle_height': ox_metrics['max_obstacle_height'],
                'max_slope_angle': ox_metrics['max_slope_angle'],
                'pass_probability': ox_metrics['pass_probability'],
                'stability_on_slope': ox_metrics['stability_on_slope'],
                'energy_efficiency': ox_metrics['energy_efficiency'],
                'payload_capacity': ox_metrics['payload_capacity'],
                'speed_on_flat': ox_metrics['speed_on_flat'],
                'speed_on_slope': ox_metrics['speed_on_slope'],
                'terrain_adaptability': ox_metrics['terrain_adaptability'],
            },
            'wheelbarrow': {
                'name': '独轮车',
                'name_en': 'Wheelbarrow',
                'mechanism': 'Single wheel with human-powered balance',
                'max_obstacle_height': wb_metrics['max_obstacle_height'],
                'max_slope_angle': wb_metrics['max_slope_angle'],
                'pass_probability': wb_metrics['pass_probability'],
                'stability_on_slope': wb_metrics['stability_on_slope'],
                'energy_efficiency': wb_metrics['energy_efficiency'],
                'payload_capacity': wb_metrics['payload_capacity'],
                'speed_on_flat': wb_metrics['speed_on_flat'],
                'speed_on_slope': wb_metrics['speed_on_slope'],
                'terrain_adaptability': wb_metrics['terrain_adaptability'],
            },
            'horse_carriage': {
                'name': '马车',
                'name_en': 'Horse Carriage',
                'mechanism': 'Wheeled carriage with animal traction',
                'max_obstacle_height': cg_metrics['max_obstacle_height'],
                'max_slope_angle': cg_metrics['max_slope_angle'],
                'pass_probability': cg_metrics['pass_probability'],
                'stability_on_slope': cg_metrics['stability_on_slope'],
                'energy_efficiency': cg_metrics['energy_efficiency'],
                'payload_capacity': cg_metrics['payload_capacity'],
                'speed_on_flat': cg_metrics['speed_on_flat'],
                'speed_on_slope': cg_metrics['speed_on_slope'],
                'terrain_adaptability': cg_metrics['terrain_adaptability'],
            },
            'comparison_summary': {
                'best_obstacle_clearing': 'wooden_ox',
                'best_slope_climbing': 'wooden_ox',
                'best_stability': 'horse_carriage',
                'best_payload': 'horse_carriage',
                'best_speed': 'horse_carriage',
                'best_energy_efficiency': 'horse_carriage',
                'best_terrain_adaptability': 'wooden_ox',
            },
        }

    def compare_on_terrain(self, terrain_type: str) -> dict:
        if terrain_type not in self.TERRAIN_PROFILES:
            terrain_type = 'flat'

        terrain_props = self.TERRAIN_PROFILES[terrain_type]
        terrain_data = {'terrain_type': terrain_type, **terrain_props}

        comparison = self.compare_obstacle_clearing(terrain_data)

        terrain_specific = self._compute_terrain_specific_analysis(terrain_type, terrain_props)

        result = {
            'terrain_type': terrain_type,
            'terrain_properties': terrain_props,
            'transport_comparison': comparison,
            'terrain_specific_analysis': terrain_specific,
            'ranking': self._compute_ranking(comparison),
        }

        return result

    def _compute_terrain_specific_analysis(self, terrain_type: str, terrain_props: dict) -> dict:
        analyses = {}

        slope = terrain_props['slope']
        roughness = terrain_props['roughness']
        friction = terrain_props['friction']

        if terrain_type == 'stairs':
            analyses['wooden_ox'] = {
                'advantage': 'Leg mechanism can step over stairs individually',
                'disadvantage': 'Limited stride may not match stair pitch',
                'clearance_strategy': 'Lift leg over each step sequentially',
                'suitability_score': 70.0,
            }
            analyses['wheelbarrow'] = {
                'advantage': 'None on stairs',
                'disadvantage': 'Cannot climb stairs; wheel hits riser',
                'clearance_strategy': 'Must be carried by operator',
                'suitability_score': 10.0,
            }
            analyses['horse_carriage'] = {
                'advantage': 'Large wheels can roll over low steps',
                'disadvantage': 'Cannot climb standard stairs',
                'clearance_strategy': 'Requires ramp or manual lifting',
                'suitability_score': 15.0,
            }
        elif terrain_type == 'muddy':
            analyses['wooden_ox'] = {
                'advantage': 'Discrete foot contact reduces sinkage',
                'disadvantage': 'Feet may get stuck in deep mud',
                'clearance_strategy': 'Widen stance and reduce speed',
                'suitability_score': 55.0,
            }
            analyses['wheelbarrow'] = {
                'advantage': 'Narrow profile can find firm ground',
                'disadvantage': 'Wheel sinks into mud easily',
                'clearance_strategy': 'Operator must exert extra force',
                'suitability_score': 30.0,
            }
            analyses['horse_carriage'] = {
                'advantage': 'Distributed load across 4 wheels',
                'disadvantage': 'All wheels can sink; horses may refuse',
                'clearance_strategy': 'Reduce load and add track plates',
                'suitability_score': 25.0,
            }
        elif terrain_type == 'rocky':
            analyses['wooden_ox'] = {
                'advantage': 'Legs can find stable footholds between rocks',
                'disadvantage': 'Risk of leg jamming between rocks',
                'clearance_strategy': 'Careful foot placement and slow gait',
                'suitability_score': 65.0,
            }
            analyses['wheelbarrow'] = {
                'advantage': 'Human operator can navigate around rocks',
                'disadvantage': 'Wheel can be deflected by rocks',
                'clearance_strategy': 'Slow manual navigation around obstacles',
                'suitability_score': 40.0,
            }
            analyses['horse_carriage'] = {
                'advantage': 'Large wheels can roll over small rocks',
                'disadvantage': 'Suspension may bottom out on large rocks',
                'clearance_strategy': 'Reduce speed and let suspension absorb impacts',
                'suitability_score': 45.0,
            }
        elif terrain_type == 'obstacle':
            analyses['wooden_ox'] = {
                'advantage': 'Leg mechanism lifts over obstacles naturally',
                'disadvantage': 'Tall obstacles may exceed foot clearance',
                'clearance_strategy': 'Approach at optimal crank phase for maximum lift',
                'suitability_score': 75.0,
            }
            analyses['wheelbarrow'] = {
                'advantage': 'Operator can lift front over obstacle',
                'disadvantage': 'Very limited autonomous obstacle clearing',
                'clearance_strategy': 'Tilt and push technique',
                'suitability_score': 25.0,
            }
            analyses['horse_carriage'] = {
                'advantage': 'Large wheels and suspension absorb obstacles',
                'disadvantage': 'Large obstacles block wheeled passage',
                'clearance_strategy': 'Impact absorption via suspension and slow approach',
                'suitability_score': 40.0,
            }
        else:
            analyses['wooden_ox'] = {
                'advantage': 'Consistent performance across varying terrain',
                'disadvantage': 'Slower than wheeled on smooth ground',
                'clearance_strategy': 'Steady gait cycle',
                'suitability_score': float(np.clip(70 - roughness * 0.3 - slope * 0.5 + friction * 10, 20, 90)),
            }
            analyses['wheelbarrow'] = {
                'advantage': 'Maneuverable and lightweight',
                'disadvantage': 'Stability depends entirely on operator',
                'clearance_strategy': 'Operator-adjusted balance and speed',
                'suitability_score': float(np.clip(45 - roughness * 0.4 - slope * 1.0 + friction * 5, 10, 70)),
            }
            analyses['horse_carriage'] = {
                'advantage': 'Fast and high payload on good terrain',
                'disadvantage': 'Poor performance on rough or steep terrain',
                'clearance_strategy': 'Suspension-assisted rolling',
                'suitability_score': float(np.clip(60 - roughness * 0.35 - slope * 0.8 + friction * 8, 10, 85)),
            }

        return analyses

    def _compute_ranking(self, comparison: dict) -> dict:
        metrics = [
            'max_obstacle_height', 'max_slope_angle', 'pass_probability',
            'stability_on_slope', 'energy_efficiency', 'payload_capacity',
            'speed_on_flat', 'speed_on_slope', 'terrain_adaptability',
        ]

        rankings = {}
        for metric in metrics:
            values = {}
            for transport_key in ['wooden_ox', 'wheelbarrow', 'horse_carriage']:
                values[transport_key] = comparison[transport_key][metric]

            sorted_transports = sorted(values.items(), key=lambda x: x[1], reverse=True)
            rankings[metric] = [
                {'transport': t, 'value': v} for t, v in sorted_transports
            ]

        return rankings

    def get_transport_profiles(self) -> dict:
        ox_base = self._compute_wooden_ox_metrics()
        wp = self.WHEELBARROW_PARAMS
        cp = self.CARRIAGE_PARAMS

        return {
            'wooden_ox': {
                'name': '木牛流马',
                'name_en': 'Wooden Ox Walking Machine',
                'era': 'Three Kingdoms period (~230 AD)',
                'inventor': 'Zhuge Liang',
                'mechanism_type': 'Jansen linkage leg mechanism',
                'propulsion': 'Crank-driven leg mechanism',
                'structural_params': {
                    'crank_length_mm': self.wooden_ox_params.crank_length,
                    'rocker_length_mm': self.wooden_ox_params.rocker_length,
                    'coupler_length_mm': self.wooden_ox_params.coupler_length,
                    'ground_link_mm': self.wooden_ox_params.ground_link,
                    'foot_radius_mm': self.wooden_ox_params.foot_radius,
                    'num_legs': 4,
                },
                'performance': {
                    'max_obstacle_height_mm': ox_base['max_obstacle_height'],
                    'max_slope_angle_deg': ox_base['max_slope_angle'],
                    'foot_clearance_mm': ox_base['foot_clearance'],
                    'stride_length_mm': ox_base['stride_length'],
                },
                'advantages': [
                    'Leg mechanism lifts over obstacles',
                    'Independent leg placement adapts to terrain',
                    'Discrete ground contact reduces sinkage',
                    'Can traverse stairs and rocky terrain',
                ],
                'disadvantages': [
                    'Slower than wheeled transport on flat ground',
                    'Complex mechanism requires maintenance',
                    'Limited payload compared to carriage',
                ],
            },
            'wheelbarrow': {
                'name': '独轮车',
                'name_en': 'Wheelbarrow',
                'era': 'Han Dynasty (~100 AD)',
                'inventor': 'Unknown (attributed to various figures)',
                'mechanism_type': 'Single wheel with human-powered balance',
                'propulsion': 'Human pushing and balancing',
                'structural_params': {
                    'wheel_radius_mm': wp['wheel_radius'],
                    'track_width_mm': wp['track_width'],
                    'effective_track_width_mm': wp['effective_track_width'],
                    'com_height_mm': wp['com_height'],
                    'total_mass_kg': wp['mass'],
                    'max_payload_kg': wp['payload_mass'],
                    'human_force_N': wp['human_force'],
                },
                'performance': {
                    'max_obstacle_height_mm': wp['wheel_radius'] * np.sin(np.radians(wp['approach_angle'])),
                    'max_slope_angle_deg': float(np.degrees(
                        np.arctan(wp['effective_track_width'] / (2 * wp['com_height']))
                    ) * 0.6),
                    'critical_tipping_angle_deg': float(np.degrees(
                        np.arctan(wp['effective_track_width'] / (2 * wp['com_height']))
                    )),
                },
                'advantages': [
                    'Highly maneuverable in narrow paths',
                    'Simple construction and maintenance',
                    'Human operator provides adaptive control',
                    'Low cost and widely available',
                ],
                'disadvantages': [
                    'Very low stability (single wheel)',
                    'Limited obstacle clearing ability',
                    'Requires constant human effort',
                    'Poor performance on slopes and rough terrain',
                ],
            },
            'horse_carriage': {
                'name': '马车',
                'name_en': 'Horse Carriage',
                'era': 'Shang Dynasty (~1200 BC)',
                'inventor': 'Unknown (evolved from chariot design)',
                'mechanism_type': 'Wheeled carriage with animal traction',
                'propulsion': 'Horse pulling force',
                'structural_params': {
                    'wheel_radius_mm': cp['wheel_radius'],
                    'num_wheels': cp['num_wheels'],
                    'axle_width_mm': cp['axle_width'],
                    'com_height_mm': cp['com_height'],
                    'carriage_mass_kg': cp['mass'],
                    'max_payload_kg': cp['payload_mass'],
                    'horse_pull_force_N': cp['horse_pull_force'],
                    'suspension_stiffness_N_per_m': cp['suspension_stiffness'],
                    'suspension_damping_Ns_per_m': cp['suspension_damping'],
                },
                'performance': {
                    'max_obstacle_height_mm': float(
                        cp['wheel_radius'] * np.sin(np.radians(cp['approach_angle']))
                        + (cp['mass'] + cp['payload_mass']) * 9.81 / (cp['suspension_stiffness'] * cp['num_wheels']) * 0.3
                    ),
                    'max_slope_angle_deg': float(np.degrees(
                        np.arctan(cp['axle_width'] / (2 * cp['com_height']))
                    ) * 0.55),
                    'critical_tipping_angle_deg': float(np.degrees(
                        np.arctan(cp['axle_width'] / (2 * cp['com_height']))
                    )),
                    'suspension_static_deflection_mm': float(
                        (cp['mass'] + cp['payload_mass']) * 9.81 / (cp['suspension_stiffness'] * cp['num_wheels']) * 1000
                    ),
                },
                'advantages': [
                    'High payload capacity',
                    'Fast on flat and gentle terrain',
                    'Good lateral stability with 4 wheels',
                    'Spring-damper suspension absorbs shocks',
                ],
                'disadvantages': [
                    'Requires animal (horse) for propulsion',
                    'Poor performance on steep and rough terrain',
                    'Cannot traverse stairs or large obstacles',
                    'Sinks in mud and soft ground',
                ],
            },
        }

    def generate_radar_data(self, terrain_type: str = 'flat') -> dict:
        if terrain_type not in self.TERRAIN_PROFILES:
            terrain_type = 'flat'

        terrain_props = self.TERRAIN_PROFILES[terrain_type]
        terrain_data = {'terrain_type': terrain_type, **terrain_props}

        ox_metrics = self._compute_wooden_ox_full_metrics(terrain_props)
        wb_metrics = self._compute_wheelbarrow_metrics(terrain_props)
        cg_metrics = self._compute_carriage_metrics(terrain_props)

        axis_labels = ['越障能力', '爬坡能力', '稳定性', '载重能力', '地形适应', '能效']
        axis_keys_en = [
            'obstacle_clearing', 'slope_climbing', 'stability',
            'payload_capacity', 'terrain_adaptability', 'energy_efficiency',
        ]

        def normalize(values: dict) -> list:
            return [
                float(np.clip(values['max_obstacle_height'] / 100.0, 0, 1)),
                float(np.clip(values['max_slope_angle'] / 20.0, 0, 1)),
                float(np.clip(values['stability_on_slope'] / 100.0, 0, 1)),
                float(np.clip(values['payload_capacity'] / 500.0, 0, 1)),
                float(np.clip(values['terrain_adaptability'] / 100.0, 0, 1)),
                float(np.clip(values['energy_efficiency'], 0, 1)),
            ]

        ox_values = normalize(ox_metrics)
        wb_values = normalize(wb_metrics)
        cg_values = normalize(cg_metrics)

        return {
            'terrain_type': terrain_type,
            'axes': [
                {'label': label, 'key': key}
                for label, key in zip(axis_labels, axis_keys_en)
            ],
            'datasets': [
                {
                    'transport': 'wooden_ox',
                    'name': '木牛流马',
                    'name_en': 'Wooden Ox Walking Machine',
                    'values': ox_values,
                    'color': '#E74C3C',
                },
                {
                    'transport': 'wheelbarrow',
                    'name': '独轮车',
                    'name_en': 'Wheelbarrow',
                    'values': wb_values,
                    'color': '#3498DB',
                },
                {
                    'transport': 'horse_carriage',
                    'name': '马车',
                    'name_en': 'Horse Carriage',
                    'values': cg_values,
                    'color': '#2ECC71',
                },
            ],
            'raw_metrics': {
                'wooden_ox': ox_metrics,
                'wheelbarrow': wb_metrics,
                'horse_carriage': cg_metrics,
            },
        }

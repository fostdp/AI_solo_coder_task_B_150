import numpy as np
from typing import Dict, List, Optional

from app.models.schemas import JansenParameters, Point3D, TerrainData
from app.simulation.jansen_linkage import JansenLinkageSolver
from app.simulation.multibody_dynamics import MultibodyDynamics
from app.analysis.obstacle_analysis import ObstacleAnalyzer


class TransportComparisonAnalyzer:
    WHEELBARROW_PARAMS = {
        'wheel_radius': 350,
        'track_width': 0,
        'effective_track_width': 500,
        'com_height': 900,
        'mass': 40,
        'payload_mass': 200,
        'human_force': 500,
        'approach_angle': 3,
        'historical_source': '《三国志·蜀书·诸葛亮传》《后汉书》',
    }

    CARRIAGE_PARAMS = {
        'wheel_radius': 700,
        'num_wheels': 4,
        'axle_width': 1500,
        'com_height': 1500,
        'mass': 300,
        'payload_mass': 600,
        'horse_pull_force': 2000,
        'num_horses': 2,
        'suspension_stiffness': 5000,
        'suspension_damping': 2000,
        'approach_angle': 6,
        'historical_source': '《周礼·考工记》《史记·平准书》',
    }

    TERRAIN_PROFILES = {
        'flat': {'slope': 0, 'roughness': 0, 'obstacle_density': 0, 'friction': 0.8},
        'gentle_slope': {'slope': 10, 'roughness': 5, 'obstacle_density': 0, 'friction': 0.7},
        'steep_slope': {'slope': 25, 'roughness': 10, 'obstacle_density': 5, 'friction': 0.6},
        'rocky': {'slope': 15, 'roughness': 50, 'obstacle_density': 30, 'friction': 0.5},
        'muddy': {'slope': 5, 'roughness': 5, 'obstacle_density': 0, 'friction': 0.3},
        'stairs': {'slope': 30, 'roughness': 20, 'obstacle_density': 50, 'friction': 0.7},
        'obstacle': {'slope': 5, 'roughness': 30, 'obstacle_density': 60, 'friction': 0.6},
    }

    HISTORICAL_SOURCES = {
        '木牛流马': {
            'source': '《三国志·蜀书·后主传》《诸葛亮集·作木牛流马法》',
            'description': '诸葛亮创制的木制机械运输工具，用于蜀汉时期',
        },
        '独轮车': {
            'source': '《三国志·蜀书·诸葛亮传》《后汉书》',
            'description': '古代单轮人力运输工具，相传由诸葛亮发明或改进',
        },
        '马车': {
            'source': '《周礼·考工记》《史记·平准书》',
            'description': '古代畜力运输工具，商周时期已广泛使用',
        },
    }

    def __init__(self, params: Optional[JansenParameters] = None):
        self.params = params or JansenParameters()
        self.linkage_solver = JansenLinkageSolver(self.params)
        self.dynamics = MultibodyDynamics(self.params)
        self.obstacle_analyzer = ObstacleAnalyzer(self.params)

    def _compute_wooden_ox_metrics(self, terrain_profile: dict) -> dict:
        foot_trajectory = self.linkage_solver.generate_foot_trajectory(0, 360, 720)
        foot_heights = [p.y for p in foot_trajectory]
        foot_xs = [p.x for p in foot_trajectory]
        max_obstacle_height = (max(foot_heights) - min(foot_heights)) * 0.7
        stride_length = max(foot_xs) - min(foot_xs)

        gait_params = self.linkage_solver.calculate_gait_parameters(0)
        cadence = gait_params['cadence']
        walking_speed = stride_length * cadence / 60.0

        slope = terrain_profile.get('slope', 0)
        roughness = terrain_profile.get('roughness', 0)
        friction = terrain_profile.get('friction', 0.8)

        max_slope_angle = min(15.0 * friction / 0.6, 25.0)
        stability_on_slope = max(0, 1.0 - slope / 30.0) * friction
        pass_probability = max(0, min(1, (1 - roughness / 100.0) * stability_on_slope))
        speed_on_flat = walking_speed * 0.8
        speed_on_slope = speed_on_flat * max(0.2, 1 - slope / 20.0)
        payload_capacity = 150.0 * (1 - slope / 40.0)
        energy_efficiency = 0.6 * (1 - roughness / 150.0) * friction
        terrain_adaptability = min(1.0, (0.5 + 0.3 * friction + 0.2 * (1 - roughness / 100.0)))

        return {
            'max_obstacle_height': float(max_obstacle_height),
            'max_slope_angle': float(max_slope_angle),
            'pass_probability': float(pass_probability),
            'stability_on_slope': float(stability_on_slope),
            'energy_efficiency': float(energy_efficiency),
            'payload_capacity': float(payload_capacity),
            'speed_on_flat': float(speed_on_flat),
            'speed_on_slope': float(speed_on_slope),
            'terrain_adaptability': float(terrain_adaptability),
        }

    def _compute_wheelbarrow_metrics(self, terrain_profile: dict) -> dict:
        wp = self.WHEELBARROW_PARAMS
        wheel_r = wp['wheel_radius']
        track_w = wp['effective_track_width']
        com_h = wp['com_height']
        total_mass = wp['mass'] + wp['payload_mass']
        approach_angle = wp['approach_angle']

        approach_factor = 1.0 + np.radians(approach_angle) * 0.5
        max_obstacle_height = wheel_r * 0.6 * approach_factor
        theta_critical = np.arctan(track_w / (2 * com_h))
        max_slope_angle = np.degrees(theta_critical) * 0.8

        slope = terrain_profile.get('slope', 0)
        roughness = terrain_profile.get('roughness', 0)
        friction = terrain_profile.get('friction', 0.8)

        slope_rad = np.radians(slope)
        stability_on_slope = max(0, np.cos(slope_rad) - np.sin(slope_rad) * com_h / (track_w / 2))
        pass_probability = max(0, min(1, stability_on_slope * (1 - roughness / 80.0) * friction))

        speed_on_flat = (wp['human_force'] / total_mass) * 1000
        speed_on_slope = speed_on_flat * max(0.1, 1 - slope / 15.0)
        payload_capacity = wp['payload_mass'] * (1 - slope / 25.0)
        energy_efficiency = 0.4 * friction * (1 - roughness / 100.0)
        terrain_adaptability = min(1.0, 0.3 * friction + 0.2 * (1 - roughness / 80.0) + 0.2)

        return {
            'max_obstacle_height': float(max_obstacle_height),
            'max_slope_angle': float(max_slope_angle),
            'pass_probability': float(pass_probability),
            'stability_on_slope': float(stability_on_slope),
            'energy_efficiency': float(energy_efficiency),
            'payload_capacity': float(payload_capacity),
            'speed_on_flat': float(speed_on_flat),
            'speed_on_slope': float(speed_on_slope),
            'terrain_adaptability': float(terrain_adaptability),
        }

    def _compute_carriage_metrics(self, terrain_profile: dict) -> dict:
        cp = self.CARRIAGE_PARAMS
        wheel_r = cp['wheel_radius']
        com_h = cp['com_height']
        total_mass = cp['mass'] + cp['payload_mass']
        num_horses = cp['num_horses']
        total_pull_force = cp['horse_pull_force'] * num_horses

        max_obstacle_height = wheel_r * 0.3
        slope = terrain_profile.get('slope', 0)
        roughness = terrain_profile.get('roughness', 0)
        friction = terrain_profile.get('friction', 0.8)

        k = cp['suspension_stiffness']
        c = cp['suspension_damping']
        suspension_compression = total_mass * 9.81 / (k * cp['num_wheels'])
        effective_clearance = wheel_r - suspension_compression * 1000
        max_obstacle_height = min(max_obstacle_height, effective_clearance * 0.5)

        max_slope_angle = min(np.degrees(np.arctan(friction)) * 0.9, 20.0)
        stability_on_slope = max(0, 1 - slope / max(max_slope_angle, 1))
        pass_probability = max(0, min(1, stability_on_slope * (1 - roughness / 60.0) * friction))

        speed_on_flat = (total_pull_force / total_mass) * 800
        speed_on_slope = speed_on_flat * max(0.2, 1 - slope / 12.0)
        payload_capacity = cp['payload_mass'] * (1 - slope / 20.0)
        energy_efficiency = 0.5 * friction * (1 - roughness / 80.0)
        terrain_adaptability = min(1.0, 0.3 * friction + 0.3 * (1 - roughness / 70.0) + 0.15)

        return {
            'max_obstacle_height': float(max(max_obstacle_height, 0)),
            'max_slope_angle': float(max_slope_angle),
            'pass_probability': float(pass_probability),
            'stability_on_slope': float(stability_on_slope),
            'energy_efficiency': float(energy_efficiency),
            'payload_capacity': float(payload_capacity),
            'speed_on_flat': float(speed_on_flat),
            'speed_on_slope': float(speed_on_slope),
            'terrain_adaptability': float(terrain_adaptability),
        }

    def compare_obstacle_clearing(self, terrain_data: dict) -> dict:
        terrain_profile = {
            'slope': terrain_data.get('slope', 0),
            'roughness': terrain_data.get('roughness', 0),
            'obstacle_density': terrain_data.get('obstacle_density', 0),
            'friction': terrain_data.get('friction', 0.6),
        }

        return {
            '木牛流马': self._compute_wooden_ox_metrics(terrain_profile),
            '独轮车': self._compute_wheelbarrow_metrics(terrain_profile),
            '马车': self._compute_carriage_metrics(terrain_profile),
        }

    def compare_on_terrain(self, terrain_type: str) -> dict:
        terrain_profile = self.TERRAIN_PROFILES.get(terrain_type, self.TERRAIN_PROFILES['flat'])

        return {
            '木牛流马': self._compute_wooden_ox_metrics(terrain_profile),
            '独轮车': self._compute_wheelbarrow_metrics(terrain_profile),
            '马车': self._compute_carriage_metrics(terrain_profile),
        }

    def get_transport_profiles(self) -> dict:
        return {
            '木牛流马': {
                'type': 'legged',
                'mechanism': 'Jansen linkage',
                'historical_source': '《三国志·蜀书·后主传》《诸葛亮集·作木牛流马法》',
                'description': '诸葛亮创制的木制机械运输工具，用于蜀汉时期',
                'params': {
                    'crank_length': self.params.crank_length,
                    'rocker_length': self.params.rocker_length,
                    'coupler_length': self.params.coupler_length,
                    'ground_link': self.params.ground_link,
                },
            },
            '独轮车': {
                'type': 'wheeled',
                'mechanism': 'single_wheel',
                'historical_source': self.WHEELBARROW_PARAMS['historical_source'],
                'params': self.WHEELBARROW_PARAMS,
            },
            '马车': {
                'type': 'wheeled',
                'mechanism': 'multi_wheel_suspension',
                'historical_source': self.CARRIAGE_PARAMS['historical_source'],
                'params': self.CARRIAGE_PARAMS,
            },
        }

    def get_historical_sources(self) -> dict:
        return self.HISTORICAL_SOURCES

    def generate_radar_data(self, terrain_type: str = 'flat') -> dict:
        comparison = self.compare_on_terrain(terrain_type)

        axes = [
            'max_obstacle_height', 'max_slope_angle', 'pass_probability',
            'stability_on_slope', 'energy_efficiency', 'payload_capacity',
            'speed_on_flat', 'speed_on_slope', 'terrain_adaptability',
        ]

        max_values = {}
        for axis in axes:
            vals = [comparison[name][axis] for name in comparison]
            max_values[axis] = max(vals) if max(vals) > 0 else 1

        radar = {}
        for name in comparison:
            radar[name] = [comparison[name][axis] / max_values[axis] for axis in axes]

        return {
            'axes': axes,
            'max_values': max_values,
            'data': radar,
        }

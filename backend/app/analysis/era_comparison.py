import numpy as np
from typing import Dict, Optional

from app.models.schemas import JansenParameters, Point3D
from app.simulation.jansen_linkage import JansenLinkageSolver


class EraComparisonAnalyzer:
    ERAS = ["WoodenOx", "Spot", "Cheetah", "ANYmal"]

    STATIC_METRICS = {
        "WoodenOx": {
            'mechanical_complexity': 30,
            'max_obstacle_height': 100,
            'max_slope_angle': 15,
            'speed': 0.3,
            'payload_ratio': 0.6,
            'autonomy_hours': 0,
            'terrain_types_supported': 3,
            'noise_level_db': 40,
            'cost_estimate_relative': 1,
            'control_method': '纯机械',
            'power_source': '人力',
            'sensing_capability': 1,
            'self_recovery': False,
            'historical_significance': 10,
            'innovation_index': 9,
        },
        "Spot": {
            'mechanical_complexity': 200,
            'max_obstacle_height': 300,
            'max_slope_angle': 35,
            'speed': 1.6,
            'payload_ratio': 0.3,
            'autonomy_hours': 1.5,
            'terrain_types_supported': 8,
            'noise_level_db': 65,
            'cost_estimate_relative': 1000,
            'control_method': 'AI+液压',
            'power_source': '电池+液压',
            'sensing_capability': 9,
            'self_recovery': True,
            'historical_significance': 7,
            'innovation_index': 9,
        },
        "Cheetah": {
            'mechanical_complexity': 150,
            'max_obstacle_height': 250,
            'max_slope_angle': 30,
            'speed': 3.0,
            'payload_ratio': 0.2,
            'autonomy_hours': 2.0,
            'terrain_types_supported': 6,
            'noise_level_db': 55,
            'cost_estimate_relative': 800,
            'control_method': 'AI+电机',
            'power_source': '电池+电机',
            'sensing_capability': 8,
            'self_recovery': True,
            'historical_significance': 8,
            'innovation_index': 10,
        },
        "ANYmal": {
            'mechanical_complexity': 180,
            'max_obstacle_height': 200,
            'max_slope_angle': 25,
            'speed': 1.0,
            'payload_ratio': 0.25,
            'autonomy_hours': 4.0,
            'terrain_types_supported': 7,
            'noise_level_db': 50,
            'cost_estimate_relative': 600,
            'control_method': 'AI+电机',
            'power_source': '电池+电机',
            'sensing_capability': 9,
            'self_recovery': True,
            'historical_significance': 7,
            'innovation_index': 8,
        },
    }

    def compare_all_metrics(self, params: Optional[JansenParameters] = None) -> Dict:
        metrics = {}
        for era in self.ERAS:
            metrics[era] = dict(self.STATIC_METRICS[era])

        if params is not None:
            solver = JansenLinkageSolver(params)
            foot_trajectory = solver.generate_foot_trajectory(0, 360, 720)
            foot_heights = [p.y for p in foot_trajectory]
            max_foot_height = max(foot_heights) - min(foot_heights)
            obstacle_height = max_foot_height * 0.7

            gait_params = solver.calculate_gait_parameters(0)
            stride = gait_params['stride_length']
            cadence = gait_params['cadence']
            speed = stride * cadence / 60.0 / 1000.0

            max_slope = 15.0 * params.friction_coefficient / 0.6
            max_slope = min(max_slope, 25.0)

            metrics['WoodenOx']['max_obstacle_height'] = float(obstacle_height)
            metrics['WoodenOx']['max_slope_angle'] = float(max_slope)
            metrics['WoodenOx']['speed'] = float(min(speed, 1.0))

        return metrics

    def generate_era_radar(self, params: Optional[JansenParameters] = None) -> Dict:
        metrics = self.compare_all_metrics(params)

        radar_axes = [
            ('max_obstacle_height', '越障'),
            ('speed', '速度'),
            ('payload_ratio', '载重'),
            ('autonomy_hours', '自主性'),
            ('terrain_types_supported', '地形适应'),
            ('noise_level_db', '安静性'),
            ('sensing_capability', '感知'),
            ('innovation_index', '创新'),
        ]

        axis_keys = [k for k, _ in radar_axes]
        axis_labels = [v for _, v in radar_axes]

        max_values = {}
        for key in axis_keys:
            if key == 'noise_level_db':
                max_values[key] = max(metrics[era][key] for era in self.ERAS)
            else:
                max_values[key] = max(metrics[era][key] for era in self.ERAS)
            if max_values[key] == 0:
                max_values[key] = 1

        data = {}
        for era in self.ERAS:
            values = []
            for key in axis_keys:
                raw = metrics[era][key]
                if key == 'noise_level_db':
                    normalized = 1.0 - raw / max_values[key]
                else:
                    normalized = raw / max_values[key]
                values.append(float(normalized))
            data[era] = values

        return {
            'axes': axis_labels,
            'axis_keys': axis_keys,
            'max_values': max_values,
            'data': data,
        }

    def generate_timeline(self) -> Dict:
        events = [
            {'year': 230, 'era': 'WoodenOx', 'event': '木牛流马', 'description': '诸葛亮发明木牛流马，用于蜀汉北伐粮草运输'},
            {'year': 2005, 'era': 'BigDog', 'event': 'BigDog', 'description': 'Boston Dynamics发布BigDog四足机器人'},
            {'year': 2013, 'era': 'Spot', 'event': 'Spot', 'description': 'Boston Dynamics发布Spot四足机器人'},
            {'year': 2014, 'era': 'Cheetah', 'event': 'Cheetah', 'description': 'MIT Cheetah实现高速奔跑'},
            {'year': 2016, 'era': 'ANYmal', 'event': 'ANYmal', 'description': 'ETH Zurich发布ANYmal四足机器人'},
        ]
        return {'events': events}

    def compare_mechanism_principle(self, params: Optional[JansenParameters] = None) -> Dict:
        principles = {
            'WoodenOx': {
                'mechanism_type': '纯机械连杆',
                'drive_method': '人力曲柄驱动',
                'locomotion': 'Jansen连杆足端轨迹',
                'control_paradigm': '开环机械控制',
                'energy_chain': '人力→曲柄→连杆→足端',
                'adaptation_method': '固定轨迹，无自适应',
                'stability_method': '多足支撑，静态稳定',
            },
            'Spot': {
                'mechanism_type': '液压驱动关节',
                'drive_method': '液压作动器',
                'locomotion': '逆运动学足端规划',
                'control_paradigm': '模型预测控制(MPC)',
                'energy_chain': '电池→液压泵→作动器→关节',
                'adaptation_method': '力矩反馈+视觉感知',
                'stability_method': '动态平衡+ZMP控制',
            },
            'Cheetah': {
                'mechanism_type': '电机驱动关节',
                'drive_method': '无刷直流电机',
                'locomotion': '弹跳步态+接触检测',
                'control_paradigm': '分层控制+倒立摆模型',
                'energy_chain': '电池→电机→减速器→关节',
                'adaptation_method': '触觉反馈+跳跃规划',
                'stability_method': '动态奔跑+反应控制',
            },
            'ANYmal': {
                'mechanism_type': '串联弹性驱动(SEA)',
                'drive_method': '弹性驱动器',
                'locomotion': '自由步态规划',
                'control_paradigm': '全身控制(WBC)+强化学习',
                'energy_chain': '电池→SEA→关节',
                'adaptation_method': '深度感知+RL策略',
                'stability_method': '动态平衡+恢复控制',
            },
        }

        if params is not None:
            solver = JansenLinkageSolver(params)
            foot_trajectory = solver.generate_foot_trajectory(0, 360, 720)
            foot_heights = [p.y for p in foot_trajectory]
            foot_xs = [p.x for p in foot_trajectory]
            step_height = max(foot_heights) - min(foot_heights)
            stride_length = max(foot_xs) - min(foot_xs)

            principles['WoodenOx']['trajectory_data'] = {
                'step_height': float(step_height),
                'stride_length': float(stride_length),
                'crank_length': params.crank_length,
                'rocker_length': params.rocker_length,
                'coupler_length': params.coupler_length,
                'ground_link': params.ground_link,
            }

        return principles

import numpy as np
from typing import Dict, Optional

from app.models.schemas import JansenParameters, Point3D
from app.simulation.jansen_linkage import JansenLinkageSolver


class EraComparisonAnalyzer:

    ERAS = ["WoodenOx", "Spot", "Cheetah", "ANYmal"]

    STATIC_METRICS = {
        "WoodenOx": {
            "mechanical_complexity": 30,
            "max_slope_angle": 15.0,
            "speed": 0.3,
            "payload_ratio": 0.6,
            "autonomy_hours": 0.0,
            "terrain_types_supported": 3,
            "noise_level_db": 40,
            "cost_estimate_relative": 1,
            "control_method": "纯机械",
            "power_source": "人力",
            "sensing_capability": 1,
            "self_recovery": False,
            "historical_significance": 10,
            "innovation_index": 9,
        },
        "Spot": {
            "mechanical_complexity": 200,
            "max_obstacle_height": 300.0,
            "max_slope_angle": 35.0,
            "speed": 1.6,
            "payload_ratio": 0.3,
            "autonomy_hours": 1.5,
            "terrain_types_supported": 8,
            "noise_level_db": 65,
            "cost_estimate_relative": 1000,
            "control_method": "AI+液压",
            "power_source": "电池+液压",
            "sensing_capability": 9,
            "self_recovery": True,
            "historical_significance": 7,
            "innovation_index": 9,
        },
        "Cheetah": {
            "mechanical_complexity": 150,
            "max_obstacle_height": 250.0,
            "max_slope_angle": 30.0,
            "speed": 3.0,
            "payload_ratio": 0.2,
            "autonomy_hours": 2.0,
            "terrain_types_supported": 6,
            "noise_level_db": 55,
            "cost_estimate_relative": 800,
            "control_method": "AI+电机",
            "power_source": "电池+电机",
            "sensing_capability": 8,
            "self_recovery": True,
            "historical_significance": 8,
            "innovation_index": 10,
        },
        "ANYmal": {
            "mechanical_complexity": 180,
            "max_obstacle_height": 200.0,
            "max_slope_angle": 25.0,
            "speed": 1.0,
            "payload_ratio": 0.25,
            "autonomy_hours": 4.0,
            "terrain_types_supported": 7,
            "noise_level_db": 50,
            "cost_estimate_relative": 600,
            "control_method": "AI+电机",
            "power_source": "电池+电机",
            "sensing_capability": 9,
            "self_recovery": True,
            "historical_significance": 7,
            "innovation_index": 8,
        },
    }

    def _compute_wooden_ox_obstacle_height(
        self, params: JansenParameters
    ) -> float:
        solver = JansenLinkageSolver(params)
        trajectory = solver.generate_foot_trajectory(0, 360, 720)
        y_coords = [p.y for p in trajectory]
        foot_clearance = max(y_coords) - min(y_coords)
        return float(foot_clearance * 0.7)

    def _compute_wooden_ox_slope_angle(
        self, params: JansenParameters
    ) -> float:
        solver = JansenLinkageSolver(params)
        trajectory = solver.generate_foot_trajectory(0, 360, 720)
        x_coords = [p.x for p in trajectory]
        y_coords = [p.y for p in trajectory]
        stride_length = max(x_coords) - min(x_coords)
        foot_clearance = max(y_coords) - min(y_coords)
        if stride_length <= 0:
            return 15.0
        effective_angle = np.degrees(np.arctan(foot_clearance / stride_length))
        return float(min(effective_angle * 0.6, 25.0))

    def compare_all_metrics(
        self, params: Optional[JansenParameters] = None
    ) -> Dict:
        results = {}
        for era in self.ERAS:
            metrics = dict(self.STATIC_METRICS[era])
            if era == "WoodenOx" and params is not None:
                metrics["max_obstacle_height"] = self._compute_wooden_ox_obstacle_height(params)
                metrics["max_slope_angle"] = self._compute_wooden_ox_slope_angle(params)
            elif era == "WoodenOx":
                metrics["max_obstacle_height"] = 100.0
            results[era] = metrics
        return results

    def generate_era_radar(
        self, params: Optional[JansenParameters] = None
    ) -> Dict:
        all_metrics = self.compare_all_metrics(params)
        radar_axes = [
            ("越障", "max_obstacle_height", 300.0),
            ("速度", "speed", 3.0),
            ("载重", "payload_ratio", 0.6),
            ("自主性", "autonomy_hours", 4.0),
            ("地形适应", "terrain_types_supported", 8),
            ("安静性", "noise_level_db", 40.0, True),
            ("感知", "sensing_capability", 10.0),
            ("创新", "innovation_index", 10.0),
        ]

        radar_data = {}
        for era in self.ERAS:
            metrics = all_metrics[era]
            axis_values = []
            for axis_spec in radar_axes:
                if len(axis_spec) == 4:
                    name, key, max_val, invert = axis_spec
                    raw = metrics[key]
                    normalized = (max_val - raw) / max_val if max_val > 0 else 0.0
                else:
                    name, key, max_val = axis_spec
                    raw = metrics[key]
                    normalized = raw / max_val if max_val > 0 else 0.0
                axis_values.append({
                    "axis": name,
                    "value": float(raw),
                    "normalized": float(np.clip(normalized, 0.0, 1.0)),
                })
            radar_data[era] = axis_values
        return radar_data

    def generate_timeline(self) -> Dict:
        return {
            "events": [
                {"year": 230, "era": "WoodenOx", "event": "木牛流马", "description": "诸葛亮发明木牛流马，用于蜀汉军队粮草运输"},
                {"year": 2005, "era": "BigDog", "event": "BigDog", "description": "Boston Dynamics发布BigDog，四足机器人研究开端"},
                {"year": 2013, "era": "Spot", "event": "Spot", "description": "Boston Dynamics发布Spot，液压驱动四足机器人"},
                {"year": 2014, "era": "Cheetah", "event": "Cheetah", "description": "MIT Cheetah突破高速奔跑技术"},
                {"year": 2016, "era": "ANYmal", "event": "ANYmal", "description": "ETH Zurich发布ANYmal，专注工业巡检应用"},
            ]
        }

    def compare_mechanism_principle(
        self, params: Optional[JansenParameters] = None
    ) -> Dict:
        wooden_ox_detail = {
            "name": "木牛流马",
            "era": "~230 AD",
            "linkage_type": "Jansen linkage",
            "actuation": "被动行走，重力驱动步态",
            "control": "纯机械约束，无主动控制",
            "gait_generation": "连杆机构几何约束产生步态轨迹",
            "energy_efficiency": "极高（人力直接驱动，无转换损耗）",
            "adaptability": "低（固定轨迹，无法实时调整）",
            "key_innovation": "用平面连杆机构实现三维足端轨迹",
        }

        if params is not None:
            solver = JansenLinkageSolver(params)
            gait_params = solver.calculate_gait_parameters(0)
            wooden_ox_detail["computed_stride_length_mm"] = gait_params["stride_length"]
            wooden_ox_detail["computed_foot_clearance_mm"] = gait_params["foot_clearance"]
            wooden_ox_detail["computed_support_phase_pct"] = gait_params["support_phase"]

        return {
            "WoodenOx": wooden_ox_detail,
            "Spot": {
                "name": "Boston Dynamics Spot",
                "era": "2020s",
                "linkage_type": "液压执行器",
                "actuation": "液压驱动，模型预测控制",
                "control": "AI+液压，实时模型预测控制(MPC)",
                "gait_generation": "基于动力学模型的步态优化",
                "energy_efficiency": "中低（液压系统能量转换损耗较大）",
                "adaptability": "高（实时感知与步态调整）",
                "key_innovation": "液压系统的高力密度比与动态稳定性控制",
            },
            "Cheetah": {
                "name": "MIT Cheetah",
                "era": "2010s-2020s",
                "linkage_type": "高扭矩BLDC电机",
                "actuation": "高扭矩无刷直流电机，跳跃步态",
                "control": "AI+电机，高速动态运动控制",
                "gait_generation": "基于接触事件的步态切换与跳跃控制",
                "energy_efficiency": "中高（电机直驱，传动效率高）",
                "adaptability": "高（快速步态切换与地形适应）",
                "key_innovation": "电机高扭矩密度与仿生跳跃步态",
            },
            "ANYmal": {
                "name": "ETH ANYmal",
                "era": "2010s-2020s",
                "linkage_type": "串联弹性执行器",
                "actuation": "串联弹性执行器(SEA)，深度强化学习",
                "control": "AI+电机，深度强化学习控制策略",
                "gait_generation": "基于强化学习的端到端步态策略",
                "energy_efficiency": "中高（SEA储能回收，电机效率高）",
                "adaptability": "极高（强化学习策略泛化能力强）",
                "key_innovation": "深度强化学习实现复杂地形自主运动",
            },
        }

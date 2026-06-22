import pytest
import numpy as np
from app.analysis.cargo_stability import CargoStabilityAnalyzer
from app.models.schemas import JansenParameters


class TestCargoStabilityNormal:
    def test_grid_analysis_returns_grid_data(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(-200, 200), z_range=(-100, 100), grid_resolution=5
        )
        assert 'grid' in result
        assert 'optimal_position' in result
        assert 'dangerous_zones' in result
        assert 'safe_zone_boundary' in result
        assert len(result['grid']) == 25

    def test_optimal_position_has_coordinates(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(-200, 200), z_range=(-100, 100), grid_resolution=5
        )
        opt = result['optimal_position']
        assert 'x' in opt and 'z' in opt
        assert -200 <= opt['x'] <= 200
        assert -100 <= opt['z'] <= 100

    def test_grid_points_have_required_fields(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(-200, 200), z_range=(-100, 100), grid_resolution=3
        )
        for point in result['grid']:
            assert 'x' in point
            assert 'z' in point
            assert 'min_stability_margin' in point
            assert 'avg_stability_margin' in point
            assert 'is_stable' in point

    def test_center_position_more_stable_than_edge(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(-400, 400), z_range=(-150, 150), grid_resolution=7
        )
        center_points = [p for p in result['grid'] if abs(p['x']) < 50 and abs(p['z']) < 50]
        edge_points = [p for p in result['grid'] if abs(p['x']) > 300 or abs(p['z']) > 100]
        if center_points and edge_points:
            avg_center = np.mean([p['avg_stability_margin'] for p in center_points])
            avg_edge = np.mean([p['avg_stability_margin'] for p in edge_points])
            assert avg_center >= avg_edge, "中心位置应比边缘更稳定"

    def test_height_effect_returns_data(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_height_effect(
            payload_mass=150.0, height_range=(100, 800), num_steps=5
        )
        assert 'height_analysis' in result
        assert len(result['height_analysis']) == 5

    def test_higher_cargo_less_stable(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_height_effect(
            payload_mass=150.0, height_range=(100, 800), num_steps=8
        )
        analysis = result['height_analysis']
        low_margin = analysis[0]['avg_stability_margin']
        high_margin = analysis[-1]['avg_stability_margin']
        assert high_margin <= low_margin, "更高货箱应更低稳定裕度"

    def test_higher_cargo_lower_stability(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_height_effect(
            payload_mass=150.0, height_range=(100, 800), num_steps=8
        )
        analysis = result['height_analysis']
        low_is_stable = analysis[0]['is_stable']
        high_is_stable = analysis[-1]['is_stable']
        assert (not high_is_stable) or (high_is_stable == low_is_stable), "更高货箱稳定性应不高于低货箱"

    def test_mass_effect_returns_data(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_mass_effect(
            mass_range=(0, 500), num_steps=5
        )
        assert 'mass_analysis' in result
        assert len(result['mass_analysis']) == 5

    def test_heavier_cargo_less_stable(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_mass_effect(
            mass_range=(0, 500), num_steps=8
        )
        analysis = result['mass_analysis']
        light_margin = analysis[0]['avg_stability_margin']
        heavy_margin = analysis[-1]['avg_stability_margin']
        assert heavy_margin <= light_margin, "更重负载应更低稳定裕度"

    def test_optimal_position_search(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.find_optimal_cargo_position(payload_mass=150.0)
        assert 'optimal_x' in result
        assert 'optimal_z' in result
        assert 'stability_margin' in result
        assert result['avg_stability_margin'] is not None


class TestCargoStabilityBoundary:
    def test_zero_payload(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=0.0, x_range=(-200, 200), z_range=(-100, 100), grid_resolution=3
        )
        assert len(result['grid']) == 9

    def test_max_payload(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=1000.0, x_range=(-200, 200), z_range=(-100, 100), grid_resolution=3
        )
        for point in result['grid']:
            assert 'is_stable' in point

    def test_minimum_grid_resolution(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(-200, 200), z_range=(-100, 100), grid_resolution=3
        )
        assert len(result['grid']) == 9

    def test_single_point_grid(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(0, 0), z_range=(0, 0), grid_resolution=3
        )
        assert len(result['grid']) == 9

    def test_extreme_inclination(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(-200, 200), z_range=(-100, 100),
            grid_resolution=3, body_inclination=30.0
        )
        for point in result['grid']:
            assert 'min_stability_margin' in point

    def test_tipping_boundary_identified(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=500.0, x_range=(-400, 400), z_range=(-150, 150), grid_resolution=9
        )
        stable_points = [p for p in result['grid'] if p['is_stable']]
        unstable_points = [p for p in result['grid'] if not p['is_stable']]
        if stable_points and unstable_points:
            min_stable_margin = min(p['min_stability_margin'] for p in stable_points)
            max_unstable_margin = max(p['min_stability_margin'] for p in unstable_points)
            assert min_stable_margin >= 0
            assert max_unstable_margin < 0

    def test_height_at_zero(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_height_effect(
            payload_mass=150.0, height_range=(0, 100), num_steps=3
        )
        assert len(result['height_analysis']) == 3

    def test_dangerous_zones_populated_for_heavy_load(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=500.0, x_range=(-400, 400), z_range=(-150, 150), grid_resolution=7
        )
        assert len(result['dangerous_zones']) > 0, "重载下应存在危险区域"


class TestCargoStabilityAbnormal:
    def test_negative_x_range(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(-400, 400), z_range=(-150, 150), grid_resolution=3
        )
        assert len(result['grid']) > 0

    def test_very_large_range(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150.0, x_range=(-1000, 1000), z_range=(-500, 500), grid_resolution=3
        )
        assert len(result['grid']) == 9

    def test_mass_effect_zero_to_heavy(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_mass_effect(
            mass_range=(0, 1000), num_steps=3, body_inclination=15.0
        )
        assert len(result['mass_analysis']) == 3
        for point in result['mass_analysis']:
            assert 'is_stable' in point

    def test_height_effect_critical_height_detection(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_height_effect(
            payload_mass=300.0, height_range=(50, 1200), num_steps=10
        )
        if result['critical_height'] is not None:
            assert 50 < result['critical_height'] < 1200

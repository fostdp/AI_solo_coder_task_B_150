import pytest
import numpy as np
from app.analysis.transport_comparison import TransportComparisonAnalyzer
from app.models.schemas import JansenParameters

TRANSPORT_KEYS = ['木牛流马', '独轮车', '马车']


class TestTransportComparisonNormal:
    def test_compare_returns_all_three_transports(self, default_params, flat_terrain):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing(flat_terrain)
        for key in TRANSPORT_KEYS:
            assert key in result

    def test_wooden_ox_obstacle_height_positive(self, default_params, flat_terrain):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing(flat_terrain)
        ox_height = result['木牛流马']['max_obstacle_height']
        assert ox_height > 0, "木牛流马越障高度应大于0"
        assert ox_height < 500, "木牛流马越障高度应在合理范围"

    def test_wooden_ox_obstacle_higher_than_wheelbarrow(self, default_params, flat_terrain):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing(flat_terrain)
        ox_h = result['木牛流马']['max_obstacle_height']
        wb_h = result['独轮车']['max_obstacle_height']
        assert ox_h > wb_h, "木牛流马(腿式)越障高度应高于独轮车(轮式)"

    def test_carriage_payload_greater_than_wheelbarrow(self, default_params, flat_terrain):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing(flat_terrain)
        assert result['马车']['payload_capacity'] > result['独轮车']['payload_capacity']

    def test_carriage_speed_greater_than_wooden_ox(self, default_params, flat_terrain):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing(flat_terrain)
        assert result['马车']['speed_on_flat'] > result['木牛流马']['speed_on_flat']

    def test_all_metrics_in_range(self, default_params, flat_terrain):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing(flat_terrain)
        for key in TRANSPORT_KEYS:
            m = result[key]
            assert 0 <= m['pass_probability'] <= 1, f"{key} pass_probability out of range"
            assert 0 <= m['energy_efficiency'] <= 1, f"{key} energy_efficiency out of range"
            assert m['max_slope_angle'] > 0, f"{key} max_slope_angle must be positive"
            assert m['speed_on_flat'] > 0, f"{key} speed_on_flat must be positive"

    def test_compare_on_terrain_returns_all_transports(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        for terrain_type in ['flat', 'gentle_slope', 'steep_slope', 'rocky', 'muddy', 'stairs', 'obstacle']:
            result = analyzer.compare_on_terrain(terrain_type)
            for key in TRANSPORT_KEYS:
                assert key in result

    def test_radar_data_structure(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        radar = analyzer.generate_radar_data('flat')
        assert 'axes' in radar
        assert 'data' in radar
        assert len(radar['axes']) == 9
        for key in TRANSPORT_KEYS:
            assert key in radar['data']
            assert len(radar['data'][key]) == 9
            for v in radar['data'][key]:
                assert 0 <= v <= 1.0 + 1e-6

    def test_profiles_contain_chinese_names(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        profiles = analyzer.get_transport_profiles()
        for key in TRANSPORT_KEYS:
            assert key in profiles
            assert 'mechanism' in profiles[key]

    def test_rocky_terrain_reduces_adaptability(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        flat_result = analyzer.compare_on_terrain('flat')
        rocky_result = analyzer.compare_on_terrain('rocky')
        for key in TRANSPORT_KEYS:
            assert rocky_result[key]['terrain_adaptability'] <= flat_result[key]['terrain_adaptability'] + 0.01

    def test_steeper_slope_reduces_stability(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        flat_result = analyzer.compare_on_terrain('flat')
        steep_result = analyzer.compare_on_terrain('steep_slope')
        for key in TRANSPORT_KEYS:
            assert steep_result[key]['stability_on_slope'] <= flat_result[key]['stability_on_slope'] + 0.01


class TestTransportComparisonBoundary:
    def test_zero_obstacle_terrain(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing({'terrain_type': 'flat', 'slope': 0, 'roughness': 0, 'obstacle_density': 0, 'friction': 1.0})
        for key in TRANSPORT_KEYS:
            assert result[key]['max_obstacle_height'] > 0

    def test_extreme_terrain_all_metrics_finite(self, extreme_params):
        analyzer = TransportComparisonAnalyzer(extreme_params)
        result = analyzer.compare_obstacle_clearing({'terrain_type': 'obstacle', 'slope': 30, 'roughness': 200, 'obstacle_density': 1.0, 'friction': 0.05})
        for key in TRANSPORT_KEYS:
            m = result[key]
            assert np.isfinite(m['pass_probability'])
            assert np.isfinite(m['stability_on_slope'])
            assert np.isfinite(m['max_obstacle_height'])

    def test_very_small_crank_length(self):
        params = JansenParameters(crank_length=10, rocker_length=250, coupler_length=300, ground_link=200)
        analyzer = TransportComparisonAnalyzer(params)
        result = analyzer.compare_obstacle_clearing({'terrain_type': 'flat'})
        assert result['木牛流马']['max_obstacle_height'] >= 0

    def test_invalid_terrain_defaults_to_flat(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_on_terrain('nonexistent_terrain')
        for key in TRANSPORT_KEYS:
            assert key in result

    def test_heavy_payload_reduces_wooden_ox_obstacle(self, heavy_params, flat_terrain):
        light_analyzer = TransportComparisonAnalyzer(JansenParameters(payload_mass=10))
        heavy_analyzer = TransportComparisonAnalyzer(heavy_params)
        light_result = light_analyzer.compare_obstacle_clearing(flat_terrain)
        heavy_result = heavy_analyzer.compare_obstacle_clearing(flat_terrain)
        assert heavy_result['木牛流马']['max_obstacle_height'] <= light_result['木牛流马']['max_obstacle_height'] + 1

    def test_muddy_terrain_reduces_friction_effect(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        flat_result = analyzer.compare_on_terrain('flat')
        muddy_result = analyzer.compare_on_terrain('muddy')
        assert muddy_result['木牛流马']['pass_probability'] < flat_result['木牛流马']['pass_probability'] + 0.01


class TestTransportComparisonAbnormal:
    def test_missing_terrain_fields_uses_defaults(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing({'terrain_type': 'flat'})
        for key in TRANSPORT_KEYS:
            assert key in result

    def test_empty_terrain_data(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing({})
        for key in TRANSPORT_KEYS:
            assert key in result

    def test_negative_slope_handled(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing({'terrain_type': 'flat', 'slope': -5, 'roughness': 10, 'friction': 0.6, 'obstacle_density': 0})
        assert np.isfinite(result['木牛流马']['stability_on_slope'])

    def test_friction_above_one_handled(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing({'terrain_type': 'flat', 'slope': 0, 'roughness': 5, 'friction': 2.0, 'obstacle_density': 0})
        for key in TRANSPORT_KEYS:
            assert result[key]['pass_probability'] <= 1.0 + 0.01

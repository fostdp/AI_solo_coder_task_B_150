import pytest
import numpy as np
from app.analysis.era_comparison import EraComparisonAnalyzer
from app.models.schemas import JansenParameters


class TestEraComparisonNormal:
    def test_all_four_eras_present(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        for era in ['WoodenOx', 'Spot', 'Cheetah', 'ANYmal']:
            assert era in result

    def test_wooden_ox_slowest(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        ox_speed = result['WoodenOx']['speed']
        for era in ['Spot', 'Cheetah', 'ANYmal']:
            assert result[era]['speed'] > ox_speed, f"{era} should be faster than WoodenOx"

    def test_cheetah_fastest(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        speeds = {era: result[era]['speed'] for era in result}
        assert speeds['Cheetah'] >= speeds['Spot']
        assert speeds['Cheetah'] >= speeds['ANYmal']

    def test_wooden_ox_highest_payload_ratio(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        ox_ratio = result['WoodenOx']['payload_ratio']
        for era in ['Spot', 'Cheetah', 'ANYmal']:
            assert ox_ratio > result[era]['payload_ratio'], f"WoodenOx payload_ratio should exceed {era}"

    def test_wooden_ox_zero_autonomy(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['WoodenOx']['autonomy_hours'] == 0.0
        for era in ['Spot', 'Cheetah', 'ANYmal']:
            assert result[era]['autonomy_hours'] > 0

    def test_modern_robots_self_recovery(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['WoodenOx']['self_recovery'] is False
        assert result['Spot']['self_recovery'] is True
        assert result['Cheetah']['self_recovery'] is True
        assert result['ANYmal']['self_recovery'] is True

    def test_wooden_ox_quietest(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        ox_noise = result['WoodenOx']['noise_level_db']
        for era in ['Spot', 'Cheetah', 'ANYmal']:
            assert ox_noise < result[era]['noise_level_db']

    def test_radar_has_eight_axes(self):
        analyzer = EraComparisonAnalyzer()
        radar = analyzer.generate_era_radar()
        assert len(radar['axes']) == 8
        assert len(radar['axis_keys']) == 8

    def test_radar_data_has_all_eras(self):
        analyzer = EraComparisonAnalyzer()
        radar = analyzer.generate_era_radar()
        for era in ['WoodenOx', 'Spot', 'Cheetah', 'ANYmal']:
            assert era in radar['data']
            assert len(radar['data'][era]) == 8

    def test_radar_normalized_values_in_range(self):
        analyzer = EraComparisonAnalyzer()
        radar = analyzer.generate_era_radar()
        for era in radar['data']:
            for v in radar['data'][era]:
                assert 0 <= v <= 1.0 + 1e-6, f"{era} radar value out of range: {v}"

    def test_timeline_has_five_events(self):
        analyzer = EraComparisonAnalyzer()
        timeline = analyzer.generate_timeline()
        assert len(timeline['events']) == 5
        years = [e['year'] for e in timeline['events']]
        assert years == sorted(years), "Timeline should be chronologically ordered"

    def test_timeline_starts_at_230ad(self):
        analyzer = EraComparisonAnalyzer()
        timeline = analyzer.generate_timeline()
        assert timeline['events'][0]['year'] == 230
        assert '木牛流马' in timeline['events'][0]['event']

    def test_mechanism_comparison_has_all_eras(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_mechanism_principle()
        for era in ['WoodenOx', 'Spot', 'Cheetah', 'ANYmal']:
            assert era in result
            assert 'mechanism_type' in result[era]
            assert 'drive_method' in result[era]

    def test_wooden_ox_pure_mechanism_type(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_mechanism_principle()
        assert result['WoodenOx']['mechanism_type'] == '纯机械连杆'


class TestEraComparisonBoundary:
    def test_params_affect_wooden_ox_obstacle(self):
        analyzer = EraComparisonAnalyzer()
        result_no_params = analyzer.compare_all_metrics()
        default_obstacle = result_no_params['WoodenOx']['max_obstacle_height']

        params = JansenParameters(crank_length=300, rocker_length=500, coupler_length=600, ground_link=400)
        result_with_params = analyzer.compare_all_metrics(params)
        params_obstacle = result_with_params['WoodenOx']['max_obstacle_height']
        assert params_obstacle > 0

    def test_anymal_longest_autonomy(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['ANYmal']['autonomy_hours'] >= result['Spot']['autonomy_hours']
        assert result['ANYmal']['autonomy_hours'] >= result['Cheetah']['autonomy_hours']

    def test_spot_highest_obstacle_clearing(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['Spot']['max_obstacle_height'] >= result['WoodenOx']['max_obstacle_height']

    def test_wooden_ox_lowest_cost(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['WoodenOx']['cost_estimate_relative'] < result['Spot']['cost_estimate_relative']

    def test_all_sensing_capabilities_in_range(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        for era in result:
            assert 0 <= result[era]['sensing_capability'] <= 10

    def test_radar_quietness_inverted(self):
        analyzer = EraComparisonAnalyzer()
        radar = analyzer.generate_era_radar()
        quiet_idx = radar['axis_keys'].index('noise_level_db')
        ox_quiet = radar['data']['WoodenOx'][quiet_idx]
        spot_quiet = radar['data']['Spot'][quiet_idx]
        assert ox_quiet > spot_quiet, "WoodenOx should score higher on quietness (inverted)"


class TestEraComparisonAbnormal:
    def test_none_params_still_works(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics(None)
        assert 'WoodenOx' in result

    def test_default_params_object(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics(JansenParameters())
        assert 'WoodenOx' in result
        assert result['WoodenOx']['max_obstacle_height'] > 0

    def test_mechanism_with_params_adds_trajectory_data(self):
        params = JansenParameters()
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_mechanism_principle(params)
        assert 'trajectory_data' in result['WoodenOx']
        assert result['WoodenOx']['trajectory_data']['step_height'] > 0
        assert result['WoodenOx']['trajectory_data']['stride_length'] > 0

    def test_timeline_events_have_required_fields(self):
        analyzer = EraComparisonAnalyzer()
        timeline = analyzer.generate_timeline()
        for event in timeline['events']:
            assert 'year' in event
            assert 'era' in event
            assert 'event' in event
            assert 'description' in event

    def test_all_metrics_types_correct(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        for era in result:
            assert isinstance(result[era]['self_recovery'], bool)
            assert isinstance(result[era]['control_method'], str)
            assert isinstance(result[era]['speed'], (int, float))

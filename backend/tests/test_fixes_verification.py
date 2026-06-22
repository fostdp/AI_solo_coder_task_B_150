import pytest
import numpy as np
from app.analysis.transport_comparison import TransportComparisonAnalyzer
from app.analysis.era_comparison import EraComparisonAnalyzer
from app.analysis.cargo_stability import CargoStabilityAnalyzer
from app.services.driving_service import VirtualDrivingService
from app.models.schemas import JansenParameters


class TestHistoricalParametersFix:
    def test_wheelbarrow_radius_350mm(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        profiles = analyzer.get_transport_profiles()
        wb = profiles['独轮车']['params']
        assert wb['wheel_radius'] == 350, "独轮车半径应为350mm（直径70cm，符合史书记载）"

    def test_carriage_wheel_radius_700mm(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        profiles = analyzer.get_transport_profiles()
        cr = profiles['马车']['params']
        assert cr['wheel_radius'] == 700, "马车轮半径应为700mm（《考工记》记载轮高约三尺半）"

    def test_wheelbarrow_payload_200kg(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        result = analyzer.compare_obstacle_clearing({})
        assert result['独轮车']['payload_capacity'] >= 180, "独轮车载重应约200kg"

    def test_carriage_uses_two_horses(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        profiles = analyzer.get_transport_profiles()
        assert profiles['马车']['params']['num_horses'] == 2, "默认两匹马"

    def test_historical_sources_present(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        sources = analyzer.get_historical_sources()
        for key in ['木牛流马', '独轮车', '马车']:
            assert key in sources
            assert 'source' in sources[key]
            assert len(sources[key]['source']) > 0
            assert '《' in sources[key]['source'], "应包含文献引用"

    def test_sanguo_references_present(self, default_params):
        analyzer = TransportComparisonAnalyzer(default_params)
        sources = analyzer.get_historical_sources()
        assert '三国志' in sources['木牛流马']['source']
        assert '三国志' in sources['独轮车']['source']


class TestModernRobotStandardsFix:
    def test_spot_payload_14kg(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['Spot']['payload_kg'] == 14, "Spot有效载荷应为14kg（官方规格）"

    def test_spot_weight_32pt5kg(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['Spot']['weight_kg'] == 32.5, "Spot自重应为32.5kg（官方规格）"

    def test_cheetah_speed_6pt4_mps(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['Cheetah']['speed'] == 6.4, "MIT Cheetah 3最高速度应为6.4 m/s"

    def test_spot_noise_60dB(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['Spot']['noise_level_db'] == 60, "Spot噪音约60dB"

    def test_anymal_autonomy_4h(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['ANYmal']['autonomy_hours'] == 4.0, "ANYmal续航4小时"

    def test_all_modern_robots_12_dof(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        for era in ['Spot', 'Cheetah', 'ANYmal']:
            assert result[era]['degrees_of_freedom'] == 12, f"{era} 应为 4腿×3自由度=12"

    def test_wooden_ox_1_dof(self):
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics()
        assert result['WoodenOx']['degrees_of_freedom'] == 1, "木牛流马仅1自由度（曲柄驱动）"

    def test_standard_sources_present(self):
        analyzer = EraComparisonAnalyzer()
        sources = analyzer.get_standard_sources()
        for era in ['Spot', 'Cheetah', 'ANYmal', 'WoodenOx']:
            assert era in sources
            assert len(sources[era]) > 0


class TestCargoSwayFix:
    def test_zero_sway_identical_to_original(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result_zero = analyzer.analyze_cargo_position_grid(
            payload_mass=150, x_range=(-200, 200), z_range=(-100, 100),
            grid_resolution=3, sway_amplitude=0
        )
        result_none = analyzer.analyze_cargo_position_grid(
            payload_mass=150, x_range=(-200, 200), z_range=(-100, 100),
            grid_resolution=3
        )
        for i in range(len(result_zero['grid'])):
            assert result_zero['grid'][i]['min_stability_margin'] == pytest.approx(
                result_none['grid'][i]['min_stability_margin'], abs=1e-6
            ), "sway_amplitude=0 应与原版完全一致（向后兼容）"

    def test_sway_reduces_stability(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result_no_sway = analyzer.analyze_cargo_position_grid(
            payload_mass=200, x_range=(-200, 200), z_range=(-100, 100),
            grid_resolution=3, sway_amplitude=0
        )
        result_with_sway = analyzer.analyze_cargo_position_grid(
            payload_mass=200, x_range=(-200, 200), z_range=(-100, 100),
            grid_resolution=3, sway_amplitude=50
        )
        no_sway_min = min(p['min_stability_margin'] for p in result_no_sway['grid'])
        with_sway_min = min(p['min_stability_margin'] for p in result_with_sway['grid'])
        assert with_sway_min < no_sway_min, "考虑货物晃动后，最小稳定裕度应降低"

    def test_sway_amplitude_field_present(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=150, x_range=(-200, 200), z_range=(-100, 100),
            grid_resolution=3, sway_amplitude=30
        )
        assert 'sway_amplitude_used' in result
        assert result['sway_amplitude_used'] == 30

    def test_sway_sensitivity_returns_critical(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_sway_sensitivity(
            cargo_x=0, cargo_z=0, payload_mass=300, max_sway=200, num_steps=10
        )
        assert 'sway_analysis' in result
        assert len(result['sway_analysis']) == 10
        assert 'critical_sway_amplitude' in result

    def test_sway_sensitivity_monotonic(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_sway_sensitivity(
            cargo_x=0, cargo_z=0, payload_mass=200, max_sway=100, num_steps=8
        )
        margins = [r['min_margin'] for r in result['sway_analysis']]
        for i in range(len(margins) - 1):
            assert margins[i] >= margins[i + 1] - 0.1, "晃动幅度越大，稳定裕度应单调递减"

    def test_sway_grid_correct_size(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_cargo_sway_grid(
            mass_range=(50, 400), mass_steps=5,
            sway_range=(0, 100), sway_steps=6
        )
        assert len(result['masses']) == 5
        assert len(result['sway_amplitudes']) == 6
        assert len(result['grid']) == 30

    def test_worst_case_position_exists(self, default_params):
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_sway_sensitivity(
            cargo_x=0, cargo_z=0, payload_mass=150, max_sway=50, num_steps=3
        )
        for entry in result['sway_analysis']:
            if entry['sway_amplitude'] > 0:
                assert 'worst_case_position' in entry
                assert 'x' in entry['worst_case_position']
                assert 'z' in entry['worst_case_position']


class TestGamepadMappingFix:
    def test_driving_service_apply_control_bounds(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_gp_1')

        control_input = {'device_id': 'test_gp_1', 'acceleration': 1.0, 'steering': 1.0, 'brake': 0.0}
        from app.models.schemas import DrivingControlInput
        state = service.apply_control('test_gp_1', DrivingControlInput(**control_input))
        assert state.turn_rate == 45.0, "转向1.0 → 45°/s"

    def test_steering_deadzone_analog(self, default_params):
        from app.analysis.cargo_stability import CargoStabilityAnalyzer
        analyzer = CargoStabilityAnalyzer(default_params)
        result = analyzer.analyze_sway_sensitivity(
            cargo_x=0, cargo_z=0, payload_mass=150, max_sway=100, num_steps=5
        )
        assert result['sway_analysis'][0]['sway_amplitude'] == 0.0

    def test_zero_steering_turn_rate_zero(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_gp_2')
        from app.models.schemas import DrivingControlInput
        control = DrivingControlInput(device_id='test_gp_2', acceleration=0.5, steering=0.0, brake=0.0)
        state = service.apply_control('test_gp_2', control)
        assert state.turn_rate == 0.0, "转向=0 时 turn_rate 应为 0"

    def test_full_left_steering(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_gp_3')
        from app.models.schemas import DrivingControlInput
        control = DrivingControlInput(device_id='test_gp_3', acceleration=0.0, steering=-1.0, brake=0.0)
        state = service.apply_control('test_gp_3', control)
        assert state.turn_rate == -45.0

    def test_acceleration_sensitivity_curve(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_gp_4')
        base_speed = JansenParameters().crank_speed
        from app.models.schemas import DrivingControlInput

        half_control = DrivingControlInput(device_id='test_gp_4', acceleration=0.5, steering=0.0, brake=0.0)
        state_half = service.apply_control('test_gp_4', half_control)
        expected_half = base_speed * (1 + 0.5 * 1.5)
        assert state_half.crank_speed == pytest.approx(expected_half, abs=0.01)

        full_control = DrivingControlInput(device_id='test_gp_4', acceleration=1.0, steering=0.0, brake=0.0)
        state_full = service.apply_control('test_gp_4', full_control)
        expected_full = base_speed * 2.5
        assert state_full.crank_speed == pytest.approx(expected_full, abs=0.01)

        delta_full = expected_full - base_speed
        delta_half = expected_half - base_speed
        assert delta_half == pytest.approx(delta_full * 0.5, rel=0.01), "加速映射线性"

    def test_brake_override_acceleration(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_gp_5')
        base_speed = JansenParameters().crank_speed
        from app.models.schemas import DrivingControlInput

        control = DrivingControlInput(device_id='test_gp_5', acceleration=1.0, steering=0.0, brake=1.0)
        state = service.apply_control('test_gp_5', control)
        expected = base_speed * 2.5 * (1 - 1.0)
        assert state.crank_speed == pytest.approx(expected, abs=0.01), "满刹车应将速度乘以(1-brake)"

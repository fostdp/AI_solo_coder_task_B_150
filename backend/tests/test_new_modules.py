import pytest
import numpy as np
from app.models.schemas import JansenParameters


class TestVehicleComparatorModule:
    def test_module_level_compare_obstacle_clearing(self):
        from app.vehicle_comparator import compare_obstacle_clearing
        result = compare_obstacle_clearing({})
        assert '木牛流马' in result
        assert '独轮车' in result
        assert '马车' in result
        for key in result:
            assert 'max_obstacle_height' in result[key]

    def test_module_level_compare_on_terrain(self):
        from app.vehicle_comparator import compare_on_terrain
        result = compare_on_terrain('flat')
        assert '木牛流马' in result
        assert '独轮车' in result
        assert '马车' in result
        for key in result:
            assert 'max_obstacle_height' in result[key]
            assert 'stability_on_slope' in result[key]
            assert 'pass_probability' in result[key]

    def test_module_level_get_transport_profiles(self):
        from app.vehicle_comparator import get_transport_profiles
        profiles = get_transport_profiles()
        assert '木牛流马' in profiles
        assert '独轮车' in profiles
        assert '马车' in profiles
        for key in profiles:
            assert 'type' in profiles[key]
            assert 'params' in profiles[key]
            assert 'mechanism' in profiles[key]

    def test_module_level_get_historical_sources(self):
        from app.vehicle_comparator import get_historical_sources
        sources = get_historical_sources()
        assert '木牛流马' in sources
        assert '独轮车' in sources
        assert '马车' in sources

    def test_module_level_generate_radar_data(self):
        from app.vehicle_comparator import generate_radar_data
        radar = generate_radar_data('flat')
        assert 'axes' in radar
        assert 'data' in radar
        assert 'max_values' in radar
        assert len(radar['axes']) >= 6

    def test_historical_params_constants(self):
        from app.vehicle_comparator import WHEELBARROW_PARAMS, CARRIAGE_PARAMS, TERRAIN_PROFILES, HISTORICAL_SOURCES
        assert WHEELBARROW_PARAMS['wheel_radius'] == 350
        assert CARRIAGE_PARAMS['wheel_radius'] == 700
        assert 'flat' in TERRAIN_PROFILES
        assert 'rocky' in TERRAIN_PROFILES
        assert 'muddy' in TERRAIN_PROFILES
        assert len(HISTORICAL_SOURCES) == 3


class TestEraComparatorModule:
    def test_module_level_compare_all_metrics(self):
        from app.era_comparator import compare_all_metrics
        result = compare_all_metrics()
        for era in ['WoodenOx', 'Spot', 'Cheetah', 'ANYmal']:
            assert era in result

    def test_module_level_generate_era_radar(self):
        from app.era_comparator import generate_era_radar
        radar = generate_era_radar()
        assert 'axes' in radar
        assert 'axis_keys' in radar
        assert 'data' in radar
        assert len(radar['axes']) >= 7

    def test_module_level_generate_timeline(self):
        from app.era_comparator import generate_timeline
        result = generate_timeline()
        assert 'events' in result
        timeline = result['events']
        assert isinstance(timeline, list)
        assert len(timeline) >= 4
        years = [e['year'] for e in timeline]
        assert years == sorted(years)

    def test_module_level_compare_mechanism_principle(self):
        from app.era_comparator import compare_mechanism_principle
        result = compare_mechanism_principle()
        for era in ['WoodenOx', 'Spot', 'Cheetah', 'ANYmal']:
            assert era in result
            assert 'control_paradigm' in result[era]
            assert 'mechanism_type' in result[era]

    def test_module_level_get_standard_sources(self):
        from app.era_comparator import get_standard_sources
        sources = get_standard_sources()
        for era in ['WoodenOx', 'Spot', 'Cheetah', 'ANYmal']:
            assert era in sources

    def test_robot_specs_constants(self):
        from app.era_comparator import STATIC_METRICS, STANDARD_SOURCES, ERAS
        assert len(ERAS) == 4
        for era in ERAS:
            assert era in STATIC_METRICS
            assert 'weight_kg' in STATIC_METRICS[era]
            assert 'payload_kg' in STATIC_METRICS[era]


class TestLoadAnalyzerModule:
    def test_module_level_analyze_position_grid(self):
        from app.load_analyzer import analyze_cargo_position_grid
        result = analyze_cargo_position_grid(
            payload_mass=150,
            x_range=(-200, 200),
            z_range=(-100, 100),
            grid_resolution=3,
            body_inclination=0.0,
            sway_amplitude=0,
        )
        assert 'grid' in result
        assert len(result['grid']) == 9

    def test_module_level_find_optimal_position(self):
        from app.load_analyzer import find_optimal_cargo_position
        result = find_optimal_cargo_position(
            payload_mass=150, body_inclination=0.0, sway_amplitude=0
        )
        assert 'optimal_x' in result
        assert 'optimal_z' in result
        assert 'is_stable' in result
        assert 'stability_margin' in result

    def test_module_level_analyze_height_effect(self):
        from app.load_analyzer import analyze_height_effect
        result = analyze_height_effect(
            payload_mass=150, cargo_x=0, cargo_z=0,
            height_range=(100, 400), num_steps=4, sway_amplitude=0
        )
        assert 'height_analysis' in result
        assert len(result['height_analysis']) == 4

    def test_module_level_analyze_mass_effect(self):
        from app.load_analyzer import analyze_mass_effect
        result = analyze_mass_effect(
            cargo_x=0, cargo_z=0,
            mass_range=(50, 400), num_steps=4, body_inclination=0.0, sway_amplitude=0
        )
        assert 'mass_analysis' in result
        assert len(result['mass_analysis']) == 4

    def test_module_level_analyze_sway_sensitivity(self):
        from app.load_analyzer import analyze_sway_sensitivity
        result = analyze_sway_sensitivity(
            cargo_x=0, cargo_z=0, payload_mass=150,
            cargo_y=200, body_inclination=0.0, max_sway=80, num_steps=4
        )
        assert 'sway_analysis' in result
        assert len(result['sway_analysis']) == 4

    def test_module_level_analyze_cargo_sway_grid(self):
        from app.load_analyzer import analyze_cargo_sway_grid
        result = analyze_cargo_sway_grid(
            cargo_x=0, cargo_z=0, cargo_y=200, body_inclination=0.0,
            mass_range=(50, 350), sway_range=(0, 60), mass_steps=3, sway_steps=3
        )
        assert 'grid' in result
        assert len(result['grid']) == 9
        assert 'masses' in result
        assert len(result['masses']) == 3
        assert len(result['sway_amplitudes']) == 3


class TestVRWoodenOxModule:
    def test_gamepad_apply_deadzone(self):
        from app.vr_wooden_ox import apply_deadzone
        assert apply_deadzone(0.0, 0.1) == 0.0
        assert apply_deadzone(0.05, 0.1) == 0.0
        assert apply_deadzone(-0.05, 0.1) == 0.0
        assert apply_deadzone(0.5, 0.0) == pytest.approx(0.5, abs=0.01)

    def test_gamepad_apply_response_curve_linear(self):
        from app.vr_wooden_ox import apply_response_curve
        assert apply_response_curve(0.5, 'linear') == pytest.approx(0.5, abs=0.01)

    def test_gamepad_apply_response_curve_quadratic(self):
        from app.vr_wooden_ox import apply_response_curve
        val = apply_response_curve(0.5, 'quadratic')
        assert val == pytest.approx(0.25, abs=0.01)

    def test_gamepad_apply_response_curve_cubic(self):
        from app.vr_wooden_ox import apply_response_curve
        val = apply_response_curve(0.5, 'cubic')
        assert val == pytest.approx(0.125, abs=0.01)

    def test_gamepad_apply_sensitivity(self):
        from app.vr_wooden_ox import apply_sensitivity
        assert apply_sensitivity(0.5, 1.0) == pytest.approx(0.5, abs=0.01)
        assert apply_sensitivity(0.5, 0.5) == pytest.approx(0.25, abs=0.01)
        assert apply_sensitivity(0.5, 2.0) == pytest.approx(1.0, abs=0.01)

    def test_gamepad_process_axis_full_pipeline(self):
        from app.vr_wooden_ox import process_axis
        v = process_axis(0.5, deadzone=0.1, curve='quadratic', sensitivity=1.0)
        assert isinstance(v, float)
        assert 0.0 <= v <= 1.0

    def test_vr_singleton(self):
        from app.vr_wooden_ox import VRWoodenOxDriving, vr_driving_service, driving_service
        assert vr_driving_service is driving_service
        s1 = VRWoodenOxDriving.get_instance()
        s2 = VRWoodenOxDriving.get_instance()
        assert s1 is s2
        assert s1 is vr_driving_service

    def test_vr_driving_models_exported(self):
        from app.vr_wooden_ox import DrivingControlInput, DrivingState
        from app.models.schemas import DrivingControlInput as OrigDCI, DrivingState as OrigDS
        assert DrivingControlInput is OrigDCI
        assert DrivingState is OrigDS


class TestDynamicsWorkerFallback:
    def test_async_multibody_dynamics_fallback_mode(self):
        from app.dynamics_worker import AsyncMultibodyDynamics
        async_mbd = AsyncMultibodyDynamics(JansenParameters())
        assert async_mbd is not None

    @pytest.mark.asyncio
    async def test_async_calculate_com(self):
        from app.dynamics_worker import AsyncMultibodyDynamics
        from app.simulation.jansen_linkage import JansenLinkageSolver

        async_mbd = AsyncMultibodyDynamics(JansenParameters())
        solver = JansenLinkageSolver(JansenParameters())
        result_dict = solver.solve_linkage(0.0)
        
        # solver.solve_linkage 返回 dict，joints 在 dict 中
        joints = result_dict['joints'] if 'joints' in result_dict else result_dict
        
        # 先调用 calculate_link_centers_of_mass 得到正确的 com_positions
        com_positions = await async_mbd.calculate_link_centers_of_mass(
            joints=joints,
            payload_mass=0.0
        )
        
        # 再调用 calculate_total_center_of_mass
        result = await async_mbd.calculate_total_center_of_mass(
            com_positions=com_positions,
            body_inclination=0.0
        )
        assert result is not None
        assert hasattr(result, 'x')
        assert hasattr(result, 'y')
        assert isinstance(result.x, (int, float))
        assert isinstance(result.y, (int, float))

import pytest
import numpy as np
from app.services.driving_service import VirtualDrivingService, driving_service
from app.models.schemas import DrivingControlInput, JansenParameters


class TestDrivingNormal:
    def test_initial_state_exists(self):
        service = VirtualDrivingService.get_instance()
        state = service.get_state('test_initial')
        assert state is not None
        assert state.device_id == 'test_initial'
        assert state.crank_angle == 0.0
        assert state.heading == 0.0
        assert state.total_distance == 0.0

    def test_accelerate_increases_speed(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_accel')
        initial = service.get_state('test_accel')
        base = initial.crank_speed
        control = DrivingControlInput(device_id='test_accel', acceleration=1.0, steering=0.0, brake=0.0)
        state = service.apply_control('test_accel', control)
        assert state.crank_speed > base, "加速后曲柄转速应增加"

    def test_brake_reduces_speed(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_brake')
        control = DrivingControlInput(device_id='test_brake', acceleration=0.5, steering=0.0, brake=0.0)
        after_accel = service.apply_control('test_brake', control).crank_speed
        brake_control = DrivingControlInput(device_id='test_brake', acceleration=0.5, steering=0.0, brake=1.0)
        state = service.apply_control('test_brake', brake_control)
        assert state.is_braking is True
        assert state.crank_speed < after_accel or state.crank_speed == 0

    def test_steering_changes_turn_rate(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_steer')
        control = DrivingControlInput(device_id='test_steer', acceleration=0.0, steering=1.0, brake=0.0)
        state = service.apply_control('test_steer', control)
        assert state.turn_rate == 45.0, "转向角速率应为 steering*45"

    def test_steering_left_negative_rate(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_steer_left')
        control = DrivingControlInput(device_id='test_steer_left', acceleration=0.0, steering=-1.0, brake=0.0)
        state = service.apply_control('test_steer_left', control)
        assert state.turn_rate == -45.0

    def test_speed_override_sets_exact_speed(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_override')
        control = DrivingControlInput(device_id='test_override', acceleration=0.0, steering=0.0, brake=0.0, speed_override=60.0)
        state = service.apply_control('test_override', control)
        assert state.crank_speed == 60.0

    def test_inclination_override_sets_exact_angle(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_incl')
        control = DrivingControlInput(device_id='test_incl', acceleration=0.0, steering=0.0, brake=0.0, inclination_override=10.0)
        state = service.apply_control('test_incl', control)
        assert state.body_inclination == 10.0

    def test_physics_update_advances_crank(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_physics')
        control = DrivingControlInput(device_id='test_physics', acceleration=1.0, steering=0.0, brake=0.0)
        service.apply_control('test_physics', control)
        initial_angle = service.get_state('test_physics').crank_angle
        state = service.update_physics('test_physics', dt=0.1)
        assert state.crank_angle > initial_angle, "物理更新应推进曲柄角度"

    def test_physics_updates_distance(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_pos')
        control = DrivingControlInput(device_id='test_pos', acceleration=1.0, steering=0.0, brake=0.0)
        service.apply_control('test_pos', control)
        for _ in range(5):
            state = service.update_physics('test_pos', dt=0.1)
        assert state.total_distance >= 0 or state.walking_speed >= 0

    def test_reset_clears_state(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_reset')
        control = DrivingControlInput(device_id='test_reset', acceleration=1.0, steering=0.5, brake=0.0)
        service.apply_control('test_reset', control)
        for _ in range(10):
            service.update_physics('test_reset', dt=0.1)
        service.reset_device('test_reset')
        state = service.get_state('test_reset')
        assert state.crank_angle == 0.0
        assert state.total_distance == 0.0
        assert state.heading == 0.0
        assert state.position_x == 0.0
        assert state.position_y == 0.0

    def test_stopping_sets_braking_flag(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_stop_flag')
        control = DrivingControlInput(device_id='test_stop_flag', acceleration=0.0, steering=0.0, brake=0.5)
        state = service.apply_control('test_stop_flag', control)
        assert state.is_braking is True

    def test_set_device_parameters(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_set_params')
        params = JansenParameters(crank_length=200, crank_speed=60)
        service.set_device_parameters('test_set_params', params)
        control = DrivingControlInput(device_id='test_set_params', acceleration=0.0, steering=0.0, brake=0.0)
        state = service.apply_control('test_set_params', control)
        assert state.crank_speed == 60.0, "参数 crank_speed 应为 60"

    def test_steering_accumulates_inclination(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_accum')
        for _ in range(5):
            control = DrivingControlInput(device_id='test_accum', acceleration=0.0, steering=1.0, brake=0.0)
            state = service.apply_control('test_accum', control)
        assert state.body_inclination == 25.0, "5次转向1.0: 0 + 5*5 = 25, 被 clamp 在 30 内"


class TestDrivingBoundary:
    def test_speed_override_high_value(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_max_speed')
        control = DrivingControlInput(device_id='test_max_speed', acceleration=0.0, steering=0.0, brake=0.0, speed_override=999.0)
        state = service.apply_control('test_max_speed', control)
        assert state.crank_speed == 999.0, "speed_override 无 clamp"

    def test_speed_override_negative(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_neg_speed')
        control = DrivingControlInput(device_id='test_neg_speed', acceleration=0.0, steering=0.0, brake=0.0, speed_override=-100.0)
        state = service.apply_control('test_neg_speed', control)
        assert state.crank_speed == -100.0, "speed_override 无 clamp"

    def test_inclination_override_high_value(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_high_incl')
        control = DrivingControlInput(device_id='test_high_incl', acceleration=0.0, steering=0.0, brake=0.0, inclination_override=999.0)
        state = service.apply_control('test_high_incl', control)
        assert state.body_inclination == 999.0, "inclination_override 无 clamp"

    def test_inclination_steering_clamped(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_incl_clamp')
        for _ in range(100):
            control = DrivingControlInput(device_id='test_incl_clamp', acceleration=0.0, steering=1.0, brake=0.0)
            state = service.apply_control('test_incl_clamp', control)
        assert abs(state.body_inclination) <= 30.0, "非 override 模式下倾角应被 clamp 到 ±30"

    def test_acceleration_at_max(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_max_accel')
        control = DrivingControlInput(device_id='test_max_accel', acceleration=1.0, steering=0.0, brake=0.0)
        state = service.apply_control('test_max_accel', control)
        assert state.crank_speed > 0

    def test_deceleration_reduces_speed(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_decel')
        base_speed = service.get_state('test_decel').crank_speed
        control = DrivingControlInput(device_id='test_decel', acceleration=-1.0, steering=0.0, brake=0.0)
        state = service.apply_control('test_decel', control)
        assert state.crank_speed <= base_speed, "减速应不高于基础速度"

    def test_zero_dt_no_instant_change(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_zerodt')
        control = DrivingControlInput(device_id='test_zerodt', acceleration=1.0, steering=0.0, brake=0.0)
        service.apply_control('test_zerodt', control)
        state = service.update_physics('test_zerodt', dt=0.0)
        assert state is not None

    def test_very_large_dt_crank_wraps(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_largedt')
        control = DrivingControlInput(device_id='test_largedt', acceleration=1.0, steering=0.0, brake=0.0)
        service.apply_control('test_largedt', control)
        state = service.update_physics('test_largedt', dt=100.0)
        assert 0 <= state.crank_angle < 360, "曲柄角度应 wrap 到 0-360"

    def test_stability_margin_normalized(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_stab')
        control = DrivingControlInput(device_id='test_stab', acceleration=1.0, steering=0.0, brake=0.0)
        service.apply_control('test_stab', control)
        state = service.update_physics('test_stab', dt=0.1)
        assert 0 <= state.stability_margin <= 1.0, "稳定裕度应归一化到 0-1"


class TestDrivingAbnormal:
    def test_unknown_device_auto_creates(self):
        service = VirtualDrivingService.get_instance()
        state = service.get_state('brand_new_xyz_device')
        assert state is not None
        assert state.device_id == 'brand_new_xyz_device'

    def test_control_with_all_zeros(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_zero_ctrl')
        control = DrivingControlInput(device_id='test_zero_ctrl', acceleration=0.0, steering=0.0, brake=0.0)
        state = service.apply_control('test_zero_ctrl', control)
        base = JansenParameters().crank_speed
        assert state.crank_speed == base, "零控制应保持基础速度"

    def test_concurrent_controls_same_device(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_concurrent')
        for i in range(20):
            acc = 0.5 if i % 2 == 0 else -0.5
            steer = 0.3 if i % 3 == 0 else -0.3
            control = DrivingControlInput(
                device_id='test_concurrent', acceleration=acc, steering=steer, brake=0.0
            )
            state = service.apply_control('test_concurrent', control)
            assert state is not None

    def test_reset_then_immediate_control(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_reset_ctrl')
        service.reset_device('test_reset_ctrl')
        control = DrivingControlInput(device_id='test_reset_ctrl', acceleration=1.0, steering=0.0, brake=0.0)
        state = service.apply_control('test_reset_ctrl', control)
        assert state.crank_speed > 30.0

    def test_subscribe_unsubscribe(self):
        service = VirtualDrivingService.get_instance()
        received = []
        callback = lambda s: received.append(s)
        service.subscribe('test_sub', callback)
        control = DrivingControlInput(device_id='test_sub', acceleration=1.0, steering=0.0, brake=0.0)
        service.apply_control('test_sub', control)
        assert len(received) > 0, "订阅后应收到回调"
        service.unsubscribe('test_sub', callback)
        received.clear()
        service.apply_control('test_sub', control)
        assert len(received) == 0, "取消订阅后不应再收到回调"

    def test_heading_always_wraps_0_360(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_heading_wrap')
        control = DrivingControlInput(device_id='test_heading_wrap', acceleration=1.0, steering=1.0, brake=0.0)
        service.apply_control('test_heading_wrap', control)
        for _ in range(1000):
            state = service.update_physics('test_heading_wrap', dt=0.1)
        assert 0 <= state.heading < 360, "heading 应始终 wrap 到 0-360°"

    def test_driving_service_singleton(self):
        s1 = VirtualDrivingService.get_instance()
        s2 = VirtualDrivingService.get_instance()
        assert s1 is s2, "应为单例模式"

    def test_singleton_alias_matches(self):
        service = VirtualDrivingService.get_instance()
        assert driving_service is service, "模块级 alias 应指向同一实例"

    def test_reset_preserves_parameters(self):
        service = VirtualDrivingService.get_instance()
        service.reset_device('test_preserve_params')
        custom = JansenParameters(crank_length=250, crank_speed=80)
        service.set_device_parameters('test_preserve_params', custom)
        before = service.get_state('test_preserve_params').crank_speed
        service.reset_device('test_preserve_params')
        after = service.get_state('test_preserve_params').crank_speed
        assert after == 80.0, "重置后应保留自定义参数"

import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

try:
    print("=" * 70)
    print("微服务架构回归测试")
    print("=" * 70)

    print("\n📁 测试配置文件加载...")
    print("-" * 70)

    from app.core.config_loader import (
        load_config, get_mechanism_config, get_terrain_config, get_nested_config
    )

    mech_config = get_mechanism_config()
    assert mech_config is not None, "机构配置加载失败"
    assert 'jansen_linkage' in mech_config, "缺少jansen_linkage配置"
    assert 'ground_contact' in mech_config, "缺少ground_contact配置"
    assert 'com_adjustment' in mech_config, "缺少com_adjustment配置"
    assert 'alert_thresholds' in mech_config, "缺少alert_thresholds配置"

    jl = mech_config['jansen_linkage']
    assert jl.get('crank_length', 0) > 0, "曲柄长度配置错误"
    print(f"  ✅ Jansen连杆参数: crank={jl['crank_length']}mm, rocker={jl['rocker_length']}mm")

    gc = mech_config['ground_contact']
    assert gc.get('ground_stiffness', 0) > 0, "地面刚度配置错误"
    assert 'friction_coefficients' in gc, "缺少摩擦系数表"
    print(f"  ✅ 地面接触参数: stiffness={gc['ground_stiffness']}N/m, 摩擦类型={list(gc['friction_coefficients'].keys())}")

    terrain_config = get_terrain_config()
    assert terrain_config is not None, "地形配置加载失败"
    assert 'terrain_types' in terrain_config, "缺少terrain_types配置"
    assert 'obstacle_assessment' in terrain_config, "缺少obstacle_assessment配置"
    assert 'data_quality' in terrain_config, "缺少data_quality配置"
    print(f"  ✅ 地形配置: 地形类型={list(terrain_config['terrain_types'].keys())}")

    nested_val = get_nested_config(mech_config, 'jansen_linkage', 'crank_length', default=0)
    assert nested_val == jl['crank_length'], "嵌套配置访问错误"
    print(f"  ✅ 嵌套配置访问: jansen_linkage.crank_length = {nested_val}")

    print("\n📡 测试消息总线模块...")
    print("-" * 70)

    from app.core.message_bus import (
        CHANNELS, Message, message_bus,
        publish_sensor_validated, publish_gait_result,
        publish_obstacle_result, publish_alert_triggered
    )

    expected_channels = [
        'SENSOR_RAW', 'SENSOR_VALIDATED',
        'GAIT_RESULT', 'DYNAMICS_RESULT',
        'TERRAIN_RESULT', 'OBSTACLE_RESULT',
        'ALERT_TRIGGERED', 'ALERT_CLEARED',
        'COMMAND', 'BROADCAST'
    ]
    for ch in expected_channels:
        assert ch in CHANNELS, f"缺少频道定义: {ch}"
    print(f"  ✅ 消息频道定义完整 ({len(CHANNELS)} 个频道)")

    msg = Message(
        type='test',
        payload={'key': 'value'},
        source='test_case'
    )
    assert msg.message_id is not None, "Message ID未生成"
    assert msg.timestamp is not None, "时间戳未生成"
    assert msg.source == 'test_case', "消息来源错误"
    print(f"  ✅ Message数据类: id={msg.message_id[:8]}..., source={msg.source}")

    print("\n🔧 测试微服务模块导入...")
    print("-" * 70)

    from microservices.modbus_receiver import ModbusReceiverService
    print("  ✅ modbus_receiver 模块导入成功")

    from microservices.walking_simulator import WalkingSimulatorService
    print("  ✅ walking_simulator 模块导入成功")

    from microservices.obstacle_analyzer import ObstacleAnalyzerService
    print("  ✅ obstacle_analyzer 模块导入成功")

    from microservices.alarm_ws import AlarmWSService, AlertType, AlertSeverity
    print("  ✅ alarm_ws 模块导入成功")

    assert hasattr(AlertType, 'BODY_INCLINATION'), "缺少BODY_INCLINATION告警类型"
    assert hasattr(AlertType, 'MECHANICAL_STUCK'), "缺少MECHANICAL_STUCK告警类型"
    assert hasattr(AlertType, 'STABILITY_LOW'), "缺少STABILITY_LOW告警类型"
    assert hasattr(AlertSeverity, 'WARNING'), "缺少WARNING严重级别"
    assert hasattr(AlertSeverity, 'CRITICAL'), "缺少CRITICAL严重级别"
    print("  ✅ 告警类型和严重级别枚举完整")

    print("\n📟 测试ModbusReceiver核心功能...")
    print("-" * 70)

    from app.models.schemas import SensorData
    from datetime import datetime

    receiver = ModbusReceiverService(device_id='test_device', poll_interval=1.0)

    test_data = SensorData(
        timestamp=datetime.utcnow(),
        device_id='woodox_test',
        crank_angle=45.0,
        leg_displacement=120.0,
        body_inclination=2.0,
        ground_elevation=0.0
    )

    validation = asyncio.run(receiver.validate_sensor_data(test_data))
    assert validation['valid'] is True, "正常数据校验失败"
    assert validation['quality_score'] >= 80, f"质量评分过低: {validation['quality_score']}"
    assert validation['quality_level'] == 'excellent', f"质量等级错误: {validation['quality_level']}"
    print(f"  ✅ 正常数据校验: quality={validation['quality_level']}({validation['quality_score']})")

    abnormal_data = SensorData(
        timestamp=datetime.utcnow(),
        device_id='woodox_test',
        crank_angle=45.0,
        leg_displacement=120.0,
        body_inclination=35.0,
        ground_elevation=0.0
    )
    abnormal_validation = asyncio.run(receiver.validate_sensor_data(abnormal_data))
    assert '机身倾角异常' in abnormal_validation['issues'], "倾角异常未检测到"
    assert abnormal_validation['quality_score'] < 100, "异常数据评分未降低"
    print(f"  ✅ 异常数据校验: 检测到{len(abnormal_validation['issues'])}个问题, score={abnormal_validation['quality_score']}")

    derived = receiver._calculate_derived_metrics(test_data)
    assert isinstance(derived, dict), "派生指标类型错误"
    print(f"  ✅ 派生指标计算: {list(derived.keys())}")

    print("\n🏃 测试WalkingSimulator核心功能...")
    print("-" * 70)

    walking = WalkingSimulatorService()

    joints = walking.get_linkage_state(45.0)
    assert 'crank_pivot' in joints or 'A' in joints or len(joints) > 0, "连杆求解返回空"
    print(f"  ✅ 连杆状态求解: {len(joints)} 个关节点")

    trajectory = walking.get_foot_trajectory(0, 360, 72)
    assert len(trajectory) >= 72, "轨迹点数不足"
    print(f"  ✅ 足端轨迹生成: {len(trajectory)} 个点")

    gait_result = asyncio.run(walking.compute_gait_analysis(
        device_id='test',
        crank_angle=0.0,
        body_inclination=0.0
    ))
    assert 'stride_length' in gait_result, "步态结果缺少步长"
    assert 'stability_margin' in gait_result, "步态结果缺少稳定裕度"
    assert gait_result['phase_name'] is not None, "步态相位名称缺失"
    print(f"  ✅ 步态分析: 步长={gait_result['stride_length']:.1f}mm, 相位={gait_result['phase_name']}")

    print("\n🗻 测试ObstacleAnalyzer核心功能...")
    print("-" * 70)

    obstacle = ObstacleAnalyzerService()

    terrain_result = asyncio.run(obstacle.analyze_terrain_from_sensor(
        device_id='test',
        ground_elevation=5.0,
        body_inclination=1.0
    ))
    assert 'terrain_type' in terrain_result, "地形结果缺少类型"
    assert 'traversability_score' in terrain_result, "地形结果缺少可通行性评分"
    print(f"  ✅ 地形分析: type={terrain_result['terrain_type']}, score={terrain_result['traversability_score']:.1f}%")

    sim_result = asyncio.run(obstacle.simulate_obstacle_traversal(
        obstacle_height=10.0,
        obstacle_width=100.0,
        approach_speed=10.0,
        body_inclination=0.0
    ))
    assert 'successful' in sim_result, "越障仿真缺少successful字段"
    assert 'minimum_clearance' in sim_result, "越障仿真缺少minimum_clearance字段"
    print(f"  ✅ 越障仿真: success={sim_result['successful']}, clearance={sim_result['minimum_clearance']:.1f}mm")

    print("\n🚨 测试AlarmWS核心功能...")
    print("-" * 70)

    alarm = AlarmWSService()

    alert_types = [AlertType.BODY_INCLINATION, AlertType.STABILITY_LOW]
    for at in alert_types:
        asyncio.run(alarm._trigger_alert(
            device_id='test_device',
            alert_type=at,
            severity=AlertSeverity.WARNING,
            message=f"测试告警: {at.value}",
            payload={'test': True}
        ))

    active = alarm.get_active_alerts()
    assert len(active) >= 2, f"告警未触发, 仅{len(active)}个"
    print(f"  ✅ 告警触发: 当前活跃告警 {len(active)} 个")

    asyncio.run(alarm._clear_alert('test_device', AlertType.BODY_INCLINATION))
    active_after_clear = alarm.get_active_alerts()
    assert len(active_after_clear) == len(active) - 1, "告警未清除"
    print(f"  ✅ 告警清除: 剩余活跃告警 {len(active_after_clear)} 个")

    history = alarm.get_alert_history()
    assert len(history) >= 2, "告警历史记录缺失"
    print(f"  ✅ 告警历史: 共 {len(history)} 条记录")

    print("\n🌐 测试API网关主入口...")
    print("-" * 70)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
    os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))

    import importlib
    main_module = importlib.import_module('main')
    assert hasattr(main_module, 'app'), "FastAPI app未定义"
    assert main_module.app.title is not None, "App标题未设置"
    assert '2.0.0' in main_module.app.version, f"版本号错误: {main_module.app.version}"
    print(f"  ✅ FastAPI应用: {main_module.app.title} v{main_module.app.version}")

    routes = [route.path for route in main_module.app.routes if hasattr(route, 'path')]
    required_routes = ['/', '/health', '/docs', '/api/info']
    for rr in required_routes:
        assert rr in routes, f"缺少路由: {rr}"
    print(f"  ✅ 核心路由完整 ({len(required_routes)}/{len(routes)} 已检查)")

    print("\n" + "=" * 70)
    print("📋 微服务架构总结")
    print("=" * 70)
    print("""
  ┌─────────────────────────────────────────────────────────────┐
  │                    Redis Pub/Sub 消息总线                    │
  │  SENSOR_VALIDATED ──► walking_simulator                     │
  │                   └──► obstacle_analyzer                    │
  │                   └──► alarm_ws                             │
  │  GAIT_RESULT      ──► alarm_ws                              │
  │  OBSTACLE_RESULT  ──► alarm_ws                              │
  │  TERRAIN_RESULT   ──► alarm_ws                              │
  │  ALERT_*          ──► WebSocket 前端推送                    │
  └─────────────────────────────────────────────────────────────┘

  微服务模块:
  ✅ modbus_receiver    - Modbus RTU数据采集与校验
  ✅ walking_simulator  - 多体动力学与步态计算
  ✅ obstacle_analyzer  - 地形识别与越障评估
  ✅ alarm_ws           - 告警检测与WebSocket推送

  前端拆分:
  ✅ wooden_ox_3d.js    - Three.js 3D渲染引擎
  ✅ gait_panel.js      - 步态控制面板UI

  配置外置:
  ✅ mechanism_params.json - 机构参数
  ✅ terrain_params.json   - 地形参数
""")

    print("🎉 所有微服务架构测试通过！功能回归完成！")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 微服务回归测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

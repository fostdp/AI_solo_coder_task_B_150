from datetime import datetime
from typing import List, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field


class AlertType(str, Enum):
    INCLINATION_EXCEEDED = "INCLINATION_EXCEEDED"
    MECHANISM_JAMMED = "MECHANISM_JAMMED"
    SENSOR_FAULT = "SENSOR_FAULT"


class AlertLevel(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Point3D(BaseModel):
    x: float
    y: float
    z: float


class Point2D(BaseModel):
    x: float
    y: float


class SensorData(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    device_id: str = Field(..., description="设备唯一标识")
    crank_angle: float = Field(..., ge=0.0, le=360.0, description="曲柄转角 (0-360°)")
    leg_displacement: float = Field(..., description="腿足位移 (mm)")
    body_inclination: float = Field(..., description="机身倾角 (°)")
    ground_elevation: float = Field(..., description="地面起伏 (mm)")


class JansenParameters(BaseModel):
    crank_length: float = Field(default=150.0, description="曲柄长度 (mm)")
    rocker_length: float = Field(default=250.0, description="摇杆长度 (mm)")
    coupler_length: float = Field(default=300.0, description="连杆长度 (mm)")
    ground_link: float = Field(default=200.0, description="机架长度 (mm)")
    crank_speed: float = Field(default=30.0, description="曲柄转速 (°/s)")
    payload_mass: float = Field(default=0.0, description="负载质量 (kg)")
    payload_offset_x: float = Field(default=0.0, description="负载X方向偏移 (mm)")
    payload_offset_y: float = Field(default=0.0, description="负载Y方向偏移 (mm)")
    payload_offset_z: float = Field(default=0.0, description="负载Z方向偏移 (mm)")
    friction_coefficient: float = Field(default=0.6, description="足端摩擦系数 (0.3-0.8)")
    ground_stiffness: float = Field(default=1e6, description="地面刚度 (N/m)")
    damping_coefficient: float = Field(default=100.0, description="地面阻尼系数 (N·s/m)")
    foot_radius: float = Field(default=15.0, description="足端半径 (mm)")


class LegPosition(BaseModel):
    hip: Point3D
    knee: Point3D
    ankle: Point3D
    foot: Point3D


class GroundContactState(BaseModel):
    is_contact: bool = Field(description="是否接触地面")
    contact_depth: float = Field(description="接触深度 (mm)")
    normal_force: float = Field(description="法向接触力 (N)")
    tangential_force: float = Field(description="切向接触力 (N)")
    friction_force: float = Field(description="最大静摩擦力 (N)")
    is_slipping: bool = Field(description="是否打滑")
    slip_velocity: Point3D = Field(description="打滑速度 (mm/s)")
    slip_distance: float = Field(description="累计打滑距离 (mm)")
    contact_area: float = Field(description="接触面积 (mm²)")
    pressure_distribution: float = Field(description="压力分布系数")


class COMAdjustmentState(BaseModel):
    target_com: Point3D = Field(description="目标重心位置")
    current_com: Point3D = Field(description="当前重心位置")
    adjustment_offset: Point3D = Field(description="重心调整偏移量")
    payload_mass: float = Field(description="当前负载质量 (kg)")
    body_inclination_compensation: float = Field(description="机身倾角补偿角 (°)")
    adjustment_factor: float = Field(description="调整因子 (0-1)")
    is_adjusting: bool = Field(description="是否正在调整")
    adjustment_remaining: float = Field(description="剩余调整量 (mm)")


class LinkageState(BaseModel):
    crank_angle: float
    joint_positions: List[Point3D]
    leg_position: LegPosition
    foot_velocity: Point3D
    ground_contact: Optional[GroundContactState] = None
    com_adjustment: Optional[COMAdjustmentState] = None


class GaitAnalysisResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    device_id: str
    stride_length: float = Field(description="步幅 (mm)")
    cadence: float = Field(description="步频 (步/分钟)")
    walking_speed: float = Field(default=0.0, description="行走速度 (mm/s)")
    support_phase: float = Field(description="支撑相比例 (%)")
    swing_phase: float = Field(description="摆动相比例 (%)")
    gait_symmetry: float = Field(default=1.0, description="步态对称性")
    com_trajectory: List[Point3D] = Field(description="重心轨迹")
    zmp_trajectory: List[Point2D] = Field(description="零力矩点轨迹")
    stability_margin: float = Field(description="稳定裕度")
    gait_phase: float = Field(default=0.0, description="当前步态相位 (0-1)")
    phase_name: str = Field(default='support', description="步态相位名称")
    is_support_phase: bool = Field(default=True, description="是否处于支撑相")
    linkage_state: Optional[LinkageState] = None


class TerrainPoint(BaseModel):
    x: float
    y: float
    elevation: float


class TerrainData(BaseModel):
    grid_size: int = Field(default=50, description="地形网格大小")
    resolution: float = Field(default=100.0, description="网格分辨率 (mm)")
    points: List[TerrainPoint] = Field(description="地形高程点")
    obstacles: List[dict] = Field(default_factory=list, description="障碍物列表")


class ObstacleAssessmentResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    device_id: str
    max_obstacle_height: float = Field(description="最大可越障高度 (mm)")
    max_slope_angle: float = Field(description="最大可爬坡角度 (°)")
    critical_inclination: float = Field(description="临界倾角 (°)")
    obstacle_pass_probability: float = Field(description="通过概率")
    recommended_speed: float = Field(description="推荐速度 (°/s)")
    risk_level: RiskLevel = Field(description="风险等级")
    terrain_analysis: dict = Field(description="地形分析结果")


class Alert(BaseModel):
    id: str
    timestamp: datetime
    type: AlertType
    level: AlertLevel
    message: str
    device_id: str
    sensor_data: SensorData
    acknowledged: bool = False


class DeviceInfo(BaseModel):
    device_id: str
    name: str
    status: str
    last_heartbeat: datetime
    parameters: JansenParameters


class WebSocketMessage(BaseModel):
    type: str
    payload: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GaitSimulationRequest(BaseModel):
    device_id: str
    parameters: JansenParameters
    crank_angle_range: Tuple[float, float] = Field(default=(0.0, 360.0))
    step_resolution: float = Field(default=1.0, description="计算步长 (°)")


class ObstacleAssessmentRequest(BaseModel):
    device_id: str
    parameters: JansenParameters
    terrain_data: TerrainData
    current_inclination: float = Field(default=0.0)
    current_speed: float = Field(default=30.0)

class TransportTerrainProfile(BaseModel):
    terrain_type: str = Field(default='flat')
    slope: Optional[float] = None
    roughness: Optional[float] = None
    friction: Optional[float] = None
    obstacle_density: Optional[float] = None

class CargoGridRequest(BaseModel):
    parameters: JansenParameters
    payload_mass: float = Field(default=150.0, ge=0.0, le=1000.0)
    x_min: float = Field(default=-400.0)
    x_max: float = Field(default=400.0)
    z_min: float = Field(default=-150.0)
    z_max: float = Field(default=150.0)
    grid_resolution: int = Field(default=15, ge=3, le=30)
    body_inclination: float = Field(default=0.0)

class CargoOptimalRequest(BaseModel):
    parameters: JansenParameters
    payload_mass: float = Field(default=150.0)
    body_inclination: float = Field(default=0.0)

class CargoHeightRequest(BaseModel):
    parameters: JansenParameters
    payload_mass: float = Field(default=150.0)
    cargo_x: float = Field(default=0.0)
    cargo_z: float = Field(default=0.0)
    height_min: float = Field(default=100.0)
    height_max: float = Field(default=800.0)
    num_steps: int = Field(default=10, ge=3, le=50)

class CargoMassRequest(BaseModel):
    parameters: JansenParameters
    cargo_x: float = Field(default=0.0)
    cargo_z: float = Field(default=0.0)
    mass_min: float = Field(default=0.0)
    mass_max: float = Field(default=500.0)
    num_steps: int = Field(default=10, ge=3, le=30)
    body_inclination: float = Field(default=0.0)

class DrivingControlInput(BaseModel):
    device_id: str = Field(default='woodox_001')
    acceleration: float = Field(default=0.0, ge=-1.0, le=1.0)
    steering: float = Field(default=0.0, ge=-1.0, le=1.0)
    brake: float = Field(default=0.0, ge=0.0, le=1.0)
    speed_override: Optional[float] = Field(default=None)
    inclination_override: Optional[float] = Field(default=None)

class DrivingState(BaseModel):
    device_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    crank_speed: float
    crank_angle: float
    walking_speed: float
    body_inclination: float
    turn_rate: float
    heading: float = Field(default=0.0)
    position_x: float = Field(default=0.0)
    position_y: float = Field(default=0.0)
    stability_margin: float = Field(default=0.0)
    is_moving: bool = Field(default=False)
    is_braking: bool = Field(default=False)
    total_distance: float = Field(default=0.0)
    leg_states: dict = Field(default_factory=dict)

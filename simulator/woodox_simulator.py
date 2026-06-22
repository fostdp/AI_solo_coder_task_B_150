#!/usr/bin/env python3
"""
木牛流马传感器模拟器 - 增强版
支持:
  - 多种地形起伏模式（平坦、缓坡、陡坡、岩石、泥泞、混合）
  - 可配置负载条件（空载、轻载、重载、超载）
  - 多协议上报：Modbus TCP、HTTP REST API、MQTT
  - 多设备并行模拟
"""

import asyncio
import random
import math
import logging
import json
import time
import argparse
import os
import sys
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy

try:
    from pymodbus.server import StartAsyncTcpServer
    from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
    from pymodbus.datastore.store import ModbusSequentialDataBlock
    from pymodbus.payload import BinaryPayloadBuilder
    from pymodbus.constants import Endian
except ImportError:
    print("请安装依赖: pip install -r requirements.txt")
    raise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger("woodox_simulator")


# ======================== 地形类型 ========================
class TerrainType(str, Enum):
    FLAT = "flat"
    GENTLE_SLOPE = "gentle_slope"
    STEEP_SLOPE = "steep_slope"
    ROCKY = "rocky"
    MUDDY = "muddy"
    MIXED = "mixed"
    STAIRS = "stairs"
    OBSTACLE = "obstacle"


# ======================== 负载等级 ========================
class LoadLevel(str, Enum):
    EMPTY = "empty"
    LIGHT = "light"
    NORMAL = "normal"
    HEAVY = "heavy"
    OVERLOAD = "overload"


# ======================== 上报协议 ========================
class ReportProtocol(str, Enum):
    MODBUS = "modbus"
    HTTP = "http"
    MQTT = "mqtt"
    ALL = "all"


# ======================== 数据结构 ========================
@dataclass
class JansenLinkageParams:
    crank_length: float = 150.0
    rocker_length: float = 250.0
    coupler_length: float = 300.0
    ground_link: float = 200.0
    crank_speed: float = 30.0


@dataclass
class TerrainConfig:
    terrain_type: TerrainType = TerrainType.FLAT
    base_elevation: float = 0.0
    max_elevation: float = 200.0
    slope_angle: float = 0.0
    roughness: float = 0.0
    obstacle_height: float = 0.0
    obstacle_interval: float = 500.0


@dataclass
class LoadConfig:
    load_level: LoadLevel = LoadLevel.NORMAL
    payload_mass: float = 0.0
    payload_offset_x: float = 0.0
    payload_offset_y: float = 0.0
    payload_offset_z: float = 0.0


@dataclass
class SensorReading:
    crank_angle: float = 0.0
    leg_displacement: float = 0.0
    body_inclination: float = 0.0
    ground_elevation: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: int = 0x0001
    load_mass: float = 0.0
    terrain_type: str = "flat"


# ======================== 地形配置预设 ========================
TERRAIN_PRESETS: Dict[TerrainType, TerrainConfig] = {
    TerrainType.FLAT: TerrainConfig(
        terrain_type=TerrainType.FLAT,
        base_elevation=0.0,
        max_elevation=10.0,
        slope_angle=0.0,
        roughness=0.5,
        obstacle_height=0.0,
    ),
    TerrainType.GENTLE_SLOPE: TerrainConfig(
        terrain_type=TerrainType.GENTLE_SLOPE,
        base_elevation=0.0,
        max_elevation=50.0,
        slope_angle=5.0,
        roughness=1.0,
        obstacle_height=0.0,
    ),
    TerrainType.STEEP_SLOPE: TerrainConfig(
        terrain_type=TerrainType.STEEP_SLOPE,
        base_elevation=0.0,
        max_elevation=150.0,
        slope_angle=15.0,
        roughness=2.0,
        obstacle_height=0.0,
    ),
    TerrainType.ROCKY: TerrainConfig(
        terrain_type=TerrainType.ROCKY,
        base_elevation=0.0,
        max_elevation=80.0,
        slope_angle=3.0,
        roughness=5.0,
        obstacle_height=30.0,
        obstacle_interval=200.0,
    ),
    TerrainType.MUDDY: TerrainConfig(
        terrain_type=TerrainType.MUDDY,
        base_elevation=0.0,
        max_elevation=20.0,
        slope_angle=2.0,
        roughness=3.0,
        obstacle_height=10.0,
    ),
    TerrainType.MIXED: TerrainConfig(
        terrain_type=TerrainType.MIXED,
        base_elevation=0.0,
        max_elevation=100.0,
        slope_angle=8.0,
        roughness=3.0,
        obstacle_height=50.0,
        obstacle_interval=300.0,
    ),
    TerrainType.STAIRS: TerrainConfig(
        terrain_type=TerrainType.STAIRS,
        base_elevation=0.0,
        max_elevation=200.0,
        slope_angle=0.0,
        roughness=0.5,
        obstacle_height=80.0,
        obstacle_interval=100.0,
    ),
    TerrainType.OBSTACLE: TerrainConfig(
        terrain_type=TerrainType.OBSTACLE,
        base_elevation=0.0,
        max_elevation=200.0,
        slope_angle=0.0,
        roughness=1.0,
        obstacle_height=100.0,
        obstacle_interval=600.0,
    ),
}


# ======================== 负载预设 ========================
LOAD_PRESETS: Dict[LoadLevel, LoadConfig] = {
    LoadLevel.EMPTY: LoadConfig(
        load_level=LoadLevel.EMPTY,
        payload_mass=0.0,
    ),
    LoadLevel.LIGHT: LoadConfig(
        load_level=LoadLevel.LIGHT,
        payload_mass=50.0,
        payload_offset_z=20.0,
    ),
    LoadLevel.NORMAL: LoadConfig(
        load_level=LoadLevel.NORMAL,
        payload_mass=150.0,
        payload_offset_z=30.0,
    ),
    LoadLevel.HEAVY: LoadConfig(
        load_level=LoadLevel.HEAVY,
        payload_mass=300.0,
        payload_offset_z=40.0,
    ),
    LoadLevel.OVERLOAD: LoadConfig(
        load_level=LoadLevel.OVERLOAD,
        payload_mass=500.0,
        payload_offset_z=50.0,
        payload_offset_x=30.0,
    ),
}


# ======================== 模拟器主类 ========================
class WoodOxSimulator:
    def __init__(
        self,
        device_id: str = "woodox_001",
        slave_id: int = 1,
        terrain: TerrainType = TerrainType.FLAT,
        load: LoadLevel = LoadLevel.NORMAL,
        report_interval: float = 5.0,
        protocols: List[ReportProtocol] = None,
        api_url: str = "http://backend:8000",
        mqtt_broker: str = "mqtt-broker",
        mqtt_port: int = 1883,
        mqtt_topic: str = "woodox/sensor",
        crank_speed: float = 30.0,
        host: str = "0.0.0.0",
        modbus_port: int = 502,
    ):
        self.device_id = device_id
        self.slave_id = slave_id
        self.terrain_config = deepcopy(TERRAIN_PRESETS[terrain])
        self.load_config = deepcopy(LOAD_PRESETS[load])
        self.report_interval = report_interval
        self.protocols = protocols or [ReportProtocol.ALL]
        self.api_url = api_url
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = mqtt_topic
        self.params = JansenLinkageParams(crank_speed=crank_speed)
        self.host = host
        self.modbus_port = modbus_port

        self.current_crank_angle = 0.0
        self.start_time = time.time()
        self.distance_traveled = 0.0
        self.walking_speed = 50.0
        self.is_jammed = False
        self.jam_counter = 0

        self.store = ModbusSlaveContext(
            hr=ModbusSequentialDataBlock(0, [0] * 200),
            ir=ModbusSequentialDataBlock(0, [0] * 200),
        )
        self.context = ModbusServerContext(slaves=self.store, single=True)

        self.data_history: List[SensorReading] = []
        self.mqtt_client = None

        logger.info(
            f"初始化模拟器: {device_id} | 地形={terrain.value} | 负载={load.value} "
            f"({self.load_config.payload_mass}kg) | 协议={[p.value for p in self.protocols]}"
        )

    # ---------------- Jansen连杆求解 ----------------
    def _solve_jansen_linkage(self, crank_angle_deg: float) -> float:
        crank_rad = math.radians(crank_angle_deg)

        a = self.params.crank_length
        b = self.params.rocker_length
        c = self.params.coupler_length
        d = self.params.ground_link

        x_b = a * math.cos(crank_rad)
        y_b = a * math.sin(crank_rad)

        dist_bd = math.sqrt((d - x_b) ** 2 + y_b ** 2)
        dist_bd = max(abs(b - c), min(b + c, dist_bd))

        cos_phi = (b ** 2 + dist_bd ** 2 - c ** 2) / (2 * b * dist_bd)
        cos_phi = max(-1.0, min(1.0, cos_phi))
        phi = math.acos(cos_phi)

        angle_bd = math.atan2(-y_b, d - x_b)
        angle_bc = angle_bd + phi

        x_c = x_b + b * math.cos(angle_bc)
        y_c = y_b + b * math.sin(angle_bc)

        return math.sqrt(x_c ** 2 + y_c ** 2)

    # ---------------- 地形起伏计算 ----------------
    def _calculate_terrain_elevation(self, distance: float, elapsed_time: float) -> Tuple[float, float]:
        """
        返回 (地面起伏高度mm, 机身倾角degree)
        """
        tc = self.terrain_config
        elevation = tc.base_elevation
        inclination = 0.0

        if tc.terrain_type == TerrainType.FLAT:
            elevation = random.gauss(0, tc.roughness)

        elif tc.terrain_type == TerrainType.GENTLE_SLOPE or tc.terrain_type == TerrainType.STEEP_SLOPE:
            cycle = (distance % 2000) / 2000
            elevation = tc.max_elevation * math.sin(math.pi * cycle)
            inclination = tc.slope_angle * math.cos(math.pi * cycle)
            elevation += random.gauss(0, tc.roughness)

        elif tc.terrain_type == TerrainType.ROCKY:
            base = tc.max_elevation * 0.3 * math.sin(distance * 0.01)
            rocks = 0
            for i in range(3):
                freq = 0.003 + i * 0.007
                rocks += random.gauss(0, tc.roughness * 2) * math.sin(distance * freq + i)
            elevation = base + rocks
            # 障碍物
            if tc.obstacle_height > 0:
                pos_in_interval = distance % tc.obstacle_interval
                if pos_in_interval < 80:
                    progress = pos_in_interval / 80
                    elevation += tc.obstacle_height * math.sin(math.pi * progress)
                    inclination = tc.slope_angle + 5 * math.sin(math.pi * progress)

        elif tc.terrain_type == TerrainType.MUDDY:
            base = tc.max_elevation * 0.2 * math.sin(distance * 0.005)
            mud = tc.roughness * 3 * (random.random() - 0.5)
            elevation = base + mud
            inclination = random.gauss(tc.slope_angle, 2)

        elif tc.terrain_type == TerrainType.MIXED:
            segment = int(distance / 500) % 5
            if segment == 0:
                elevation = random.gauss(0, 1)
                inclination = 0
            elif segment == 1:
                elevation = 40 * math.sin((distance % 500) / 500 * math.pi)
                inclination = 5
            elif segment == 2:
                elevation = random.gauss(0, 8)
                inclination = random.gauss(0, 3)
            elif segment == 3:
                pos = distance % 500
                if pos < 100:
                    elevation = tc.obstacle_height * math.sin(pos / 100 * math.pi)
                    inclination = 10
            else:
                elevation = 80 * math.sin((distance % 500) / 500 * math.pi)
                inclination = 12

        elif tc.terrain_type == TerrainType.STAIRS:
            pos_in_interval = distance % tc.obstacle_interval
            if pos_in_interval < tc.obstacle_interval * 0.5:
                elevation = tc.obstacle_height
                inclination = 0
            else:
                elevation = 0
                inclination = 0
            elevation += random.gauss(0, tc.roughness)

        elif tc.terrain_type == TerrainType.OBSTACLE:
            pos_in_interval = distance % tc.obstacle_interval
            if 200 < pos_in_interval < 400:
                progress = (pos_in_interval - 200) / 200
                elevation = tc.obstacle_height * math.sin(math.pi * progress)
                inclination = 8 * math.sin(math.pi * progress)
            else:
                elevation = random.gauss(0, tc.roughness)

        return elevation, inclination

    # ---------------- 负载影响计算 ----------------
    def _apply_load_effects(self, base_inclination: float, base_displacement: float) -> Tuple[float, float, int]:
        """
        负载对机身倾角、腿部位移、设备状态的影响
        返回 (调整后倾角, 调整后位移, 状态字)
        """
        lc = self.load_config
        inclination = base_inclination
        displacement = base_displacement
        status = 0x0001  # NORMAL

        # 质量越大，倾角越大，重心偏移影响
        mass_factor = lc.payload_mass / 150.0
        inclination += lc.payload_offset_z * 0.02 * mass_factor
        inclination += lc.payload_offset_x * 0.01 * mass_factor

        # 负载导致腿部压缩
        displacement -= min(5.0, lc.payload_mass * 0.01)

        # 超载告警
        if lc.load_level == LoadLevel.OVERLOAD:
            status |= 0x0004  # ERROR
            inclination += random.gauss(0, 2)
            if random.random() < 0.01:
                self.is_jammed = True
        elif lc.load_level == LoadLevel.HEAVY:
            if random.random() < 0.05:
                status |= 0x0002  # WARNING

        return inclination, displacement, status

    # ---------------- 生成传感器读数 ----------------
    def generate_reading(self) -> SensorReading:
        elapsed = time.time() - self.start_time
        self.distance_traveled = elapsed * self.walking_speed

        # 曲柄角度
        if not self.is_jammed:
            self.current_crank_angle = (elapsed * self.params.crank_speed) % 360
        else:
            self.jam_counter += 1
            if self.jam_counter > 60:
                self.is_jammed = False
                self.jam_counter = 0

        crank_angle = self.current_crank_angle + random.gauss(0, 0.2)
        leg_displacement = self._solve_jansen_linkage(crank_angle)

        # 地形
        elevation, base_inclination = self._calculate_terrain_elevation(self.distance_traveled, elapsed)

        # 负载影响
        body_inclination, leg_displacement, status = self._apply_load_effects(
            base_inclination, leg_displacement
        )

        if self.is_jammed:
            status |= 0x0008 | 0x0004  # JAMMED | ERROR

        body_inclination += random.gauss(0, 0.3)

        reading = SensorReading(
            crank_angle=crank_angle,
            leg_displacement=leg_displacement,
            body_inclination=body_inclination,
            ground_elevation=elevation,
            status=status,
            load_mass=self.load_config.payload_mass,
            terrain_type=self.terrain_config.terrain_type.value,
        )

        self.data_history.append(reading)
        if len(self.data_history) > 1000:
            self.data_history = self.data_history[-1000:]

        return reading

    # ---------------- Modbus寄存器编码 ----------------
    def _encode_to_registers(self, data: SensorReading) -> List[int]:
        builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
        builder.add_32bit_float(data.crank_angle)
        builder.add_32bit_float(data.leg_displacement)
        builder.add_32bit_float(data.body_inclination)
        builder.add_32bit_float(data.ground_elevation)
        builder.add_32bit_float(data.load_mass)
        builder.add_16bit_uint(data.status)
        ts_int = int(data.timestamp.timestamp())
        builder.add_16bit_uint((ts_int >> 16) & 0xFFFF)
        builder.add_16bit_uint(ts_int & 0xFFFF)

        crc = 0xFFFF
        for v in builder.to_registers():
            crc ^= v
            for _ in range(16):
                crc = (crc >> 1) ^ 0xA001 if (crc & 1) else (crc >> 1)

        regs = builder.to_registers()
        regs.append((crc >> 16) & 0xFFFF)
        regs.append(crc & 0xFFFF)
        return regs

    def _update_registers(self, data: SensorReading):
        registers = self._encode_to_registers(data)
        for i, value in enumerate(registers):
            self.store.setValues(3, i, [value])

    # ---------------- HTTP上报 ----------------
    async def _report_http(self, data: SensorReading):
        if ReportProtocol.HTTP not in self.protocols and ReportProtocol.ALL not in self.protocols:
            return
        try:
            import aiohttp
            payload = {
                "timestamp": data.timestamp.isoformat(),
                "device_id": self.device_id,
                "crank_angle": round(data.crank_angle, 3),
                "leg_displacement": round(data.leg_displacement, 3),
                "body_inclination": round(data.body_inclination, 3),
                "ground_elevation": round(data.ground_elevation, 3),
                "load_mass": self.load_config.payload_mass,
                "terrain_type": self.terrain_config.terrain_type.value,
                "payload_offset": {
                    "x": self.load_config.payload_offset_x,
                    "y": self.load_config.payload_offset_y,
                    "z": self.load_config.payload_offset_z,
                },
            }
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(f"{self.api_url}/api/sensors/ingest", json=payload) as resp:
                    if resp.status == 200:
                        logger.debug(f"[{self.device_id}] HTTP上报成功")
                    else:
                        logger.warning(f"[{self.device_id}] HTTP上报失败: {resp.status}")
        except Exception as e:
            logger.debug(f"[{self.device_id}] HTTP上报异常: {e}")

    # ---------------- MQTT上报 ----------------
    async def _report_mqtt(self, data: SensorReading):
        if ReportProtocol.MQTT not in self.protocols and ReportProtocol.ALL not in self.protocols:
            return
        try:
            if self.mqtt_client is None:
                import paho.mqtt.client as mqtt
                self.mqtt_client = mqtt.Client(client_id=f"{self.device_id}_{int(time.time())}")
                self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
                self.mqtt_client.loop_start()

            payload = {
                "device_id": self.device_id,
                "timestamp": data.timestamp.isoformat(),
                "crank_angle": round(data.crank_angle, 3),
                "leg_displacement": round(data.leg_displacement, 3),
                "body_inclination": round(data.body_inclination, 3),
                "ground_elevation": round(data.ground_elevation, 3),
                "status": data.status,
                "load_mass": self.load_config.payload_mass,
                "load_level": self.load_config.load_level.value,
                "terrain_type": self.terrain_config.terrain_type.value,
                "payload_offset": {
                    "x": self.load_config.payload_offset_x,
                    "y": self.load_config.payload_offset_y,
                    "z": self.load_config.payload_offset_z,
                },
            }
            topic = f"{self.mqtt_topic}/{self.device_id}"
            self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
            logger.debug(f"[{self.device_id}] MQTT上报 -> {topic}")
        except Exception as e:
            logger.debug(f"[{self.device_id}] MQTT上报异常: {e}")

    # ---------------- 数据生成循环 ----------------
    async def _data_generation_loop(self):
        logger.info(
            f"[{self.device_id}] 启动数据循环, 间隔={self.report_interval}s, "
            f"地形={self.terrain_config.terrain_type.value}, "
            f"负载={self.load_config.payload_mass}kg"
        )
        while True:
            try:
                reading = self.generate_reading()
                if ReportProtocol.MODBUS in self.protocols or ReportProtocol.ALL in self.protocols:
                    self._update_registers(reading)
                await self._report_http(reading)
                await self._report_mqtt(reading)

                if len(self.data_history) % 60 == 0:
                    logger.info(
                        f"[{self.device_id}] 曲柄={reading.crank_angle:.1f}° "
                        f"倾角={reading.body_inclination:.1f}° "
                        f"地面={reading.ground_elevation:.1f}mm "
                        f"负载={reading.load_mass:.0f}kg "
                        f"地形={reading.terrain_type}"
                    )

                await asyncio.sleep(self.report_interval)
            except Exception as e:
                logger.error(f"[{self.device_id}] 数据生成错误: {e}")
                await asyncio.sleep(1)

    # ---------------- Modbus TCP启动 ----------------
    async def _start_modbus_server(self):
        if ReportProtocol.MODBUS not in self.protocols and ReportProtocol.ALL not in self.protocols:
            return
        logger.info(f"[{self.device_id}] Modbus TCP监听 {self.host}:{self.modbus_port}")
        await StartAsyncTcpServer(
            context=self.context,
            address=(self.host, self.modbus_port),
        )

    async def start(self):
        tasks = [self._data_generation_loop()]
        if ReportProtocol.MODBUS in self.protocols or ReportProtocol.ALL in self.protocols:
            tasks.append(self._start_modbus_server())
        await asyncio.gather(*tasks)

    def get_stats(self) -> Dict:
        if not self.data_history:
            return {}
        recent = self.data_history[-100:]
        return {
            "device_id": self.device_id,
            "terrain": self.terrain_config.terrain_type.value,
            "load_level": self.load_config.load_level.value,
            "load_mass": self.load_config.payload_mass,
            "total_samples": len(self.data_history),
            "uptime_seconds": int(time.time() - self.start_time),
            "distance_traveled": int(self.distance_traveled),
            "avg_inclination": sum(d.body_inclination for d in recent) / len(recent),
            "max_inclination": max(abs(d.body_inclination) for d in recent),
            "is_jammed": self.is_jammed,
            "current_crank_angle": self.current_crank_angle,
        }


# ======================== 多设备管理 ========================
async def run_multi_simulators(configs: List[Dict]):
    simulators = []
    for cfg in configs:
        sim = WoodOxSimulator(
            device_id=cfg["device_id"],
            slave_id=cfg.get("slave_id", 1),
            terrain=TerrainType(cfg.get("terrain", "flat")),
            load=LoadLevel(cfg.get("load", "normal")),
            report_interval=cfg.get("interval", 5.0),
            protocols=[ReportProtocol(p) for p in cfg.get("protocols", ["all"])],
            api_url=cfg.get("api_url", "http://backend:8000"),
            mqtt_broker=cfg.get("mqtt_broker", "mqtt-broker"),
            mqtt_port=cfg.get("mqtt_port", 1883),
            mqtt_topic=cfg.get("mqtt_topic", "woodox/sensor"),
            crank_speed=cfg.get("crank_speed", 30.0),
            modbus_port=cfg.get("modbus_port", 502),
        )
        simulators.append(sim)

    logger.info(f"启动 {len(simulators)} 台木牛流马模拟器")
    await asyncio.gather(*[sim.start() for sim in simulators])


async def run_single_from_args():
    parser = argparse.ArgumentParser(description="木牛流马传感器模拟器 - 增强版")
    parser.add_argument("--device-id", default=os.getenv("DEVICE_ID", "woodox_001"))
    parser.add_argument("--terrain", default=os.getenv("TERRAIN", "flat"),
                        choices=[t.value for t in TerrainType], help="地形类型")
    parser.add_argument("--load", default=os.getenv("LOAD", "normal"),
                        choices=[l.value for l in LoadLevel], help="负载等级")
    parser.add_argument("--payload-mass", type=float, default=None, help="自定义负载质量kg, 覆盖--load")
    parser.add_argument("--interval", type=float, default=float(os.getenv("INTERVAL", "5")), help="上报间隔秒")
    parser.add_argument("--protocol", default=os.getenv("PROTOCOL", "all"),
                        choices=[p.value for p in ReportProtocol], help="上报协议")
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    parser.add_argument("--mqtt-broker", default=os.getenv("MQTT_BROKER", "localhost"))
    parser.add_argument("--mqtt-port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--mqtt-topic", default=os.getenv("MQTT_TOPIC", "woodox/sensor"))
    parser.add_argument("--crank-speed", type=float, default=float(os.getenv("CRANK_SPEED", "30")))
    parser.add_argument("--modbus-port", type=int, default=int(os.getenv("MODBUS_PORT", "502")))
    parser.add_argument("--modbus-host", default=os.getenv("MODBUS_HOST", "0.0.0.0"))
    parser.add_argument("--config", help="多设备JSON配置文件路径")

    args = parser.parse_args()

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            configs = json.load(f)
        await run_multi_simulators(configs)
        return

    load_level = LoadLevel(args.load)
    load_config = deepcopy(LOAD_PRESETS[load_level])
    if args.payload_mass is not None:
        load_config.payload_mass = args.payload_mass

    sim = WoodOxSimulator(
        device_id=args.device_id,
        terrain=TerrainType(args.terrain),
        load=load_level,
        report_interval=args.interval,
        protocols=[ReportProtocol(args.protocol)],
        api_url=args.api_url,
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
        mqtt_topic=args.mqtt_topic,
        crank_speed=args.crank_speed,
        host=args.modbus_host,
        modbus_port=args.modbus_port,
    )

    if args.payload_mass is not None:
        sim.load_config = load_config

    await sim.start()


if __name__ == "__main__":
    try:
        asyncio.run(run_single_from_args())
    except KeyboardInterrupt:
        logger.info("模拟器已停止")
        sys.exit(0)

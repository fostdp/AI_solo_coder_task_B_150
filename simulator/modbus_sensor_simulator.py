#!/usr/bin/env python3

import asyncio
import random
import math
import logging
import json
import time
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum

try:
    from pymodbus.server import StartAsyncTcpServer, StartAsyncSerialServer
    from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
    from pymodbus.datastore.store import ModbusSequentialDataBlock
    from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
    from pymodbus.constants import Endian
except ImportError:
    print("请安装pymodbus: pip install pymodbus==3.6.6")
    raise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RegisterMap(Enum):
    CRANK_ANGLE_HIGH = 0
    CRANK_ANGLE_LOW = 1
    LEG_DISPLACEMENT_HIGH = 2
    LEG_DISPLACEMENT_LOW = 3
    BODY_INCLINATION_HIGH = 4
    BODY_INCLINATION_LOW = 5
    GROUND_ELEVATION_HIGH = 6
    GROUND_ELEVATION_LOW = 7
    DEVICE_STATUS = 8
    TIMESTAMP_HIGH = 9
    TIMESTAMP_LOW = 10
    CRC_HIGH = 11
    CRC_LOW = 12


class DeviceStatus(Enum):
    NORMAL = 0x0001
    WARNING = 0x0002
    ERROR = 0x0004
    JAMMED = 0x0008


class SimulationMode(Enum):
    NORMAL = "normal"
    OBSTACLE = "obstacle"
    INCLINATION_TEST = "inclination_test"
    JAM_TEST = "jam_test"
    RANDOM = "random"


@dataclass
class JansenLinkageParams:
    crank_length: float = 150.0
    rocker_length: float = 250.0
    coupler_length: float = 300.0
    ground_link: float = 200.0
    crank_speed: float = 30.0


@dataclass
class SensorData:
    crank_angle: float = 0.0
    leg_displacement: float = 0.0
    body_inclination: float = 0.0
    ground_elevation: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: DeviceStatus = DeviceStatus.NORMAL


class WoodOxSensorSimulator:
    def __init__(
        self,
        device_id: str = "woodox_001",
        slave_id: int = 1,
        mode: SimulationMode = SimulationMode.NORMAL,
        params: JansenLinkageParams = None,
        report_interval: int = 60,
        use_tcp: bool = True,
        host: str = "0.0.0.0",
        port: int = 502,
        serial_port: str = "COM1",
        baudrate: int = 9600,
        api_url: str = "http://localhost:8000"
    ):
        self.device_id = device_id
        self.slave_id = slave_id
        self.mode = mode
        self.params = params or JansenLinkageParams()
        self.report_interval = report_interval
        self.use_tcp = use_tcp
        self.host = host
        self.port = port
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.api_url = api_url
        
        self.current_crank_angle = 0.0
        self.start_time = time.time()
        self.obstacle_height = 0.0
        self.obstacle_position = 0.0
        self.is_jammed = False
        self.jam_counter = 0
        
        self.store = ModbusSlaveContext(
            hr=ModbusSequentialDataBlock(0, [0] * 100),
            ir=ModbusSequentialDataBlock(0, [0] * 100)
        )
        self.context = ModbusServerContext(slaves=self.store, single=True)
        
        self.data_history: List[SensorData] = []
        
        logger.info(f"初始化传感器模拟器: {device_id}, 模式: {mode.value}")
    
    def _solve_jansen_linkage(self, crank_angle_deg: float) -> float:
        crank_rad = math.radians(crank_angle_deg)
        
        a = self.params.crank_length
        b = self.params.rocker_length
        c = self.params.coupler_length
        d = self.params.ground_link
        
        x_b = a * math.cos(crank_rad)
        y_b = a * math.sin(crank_rad)
        
        dist_bd = math.sqrt((d - x_b) ** 2 + y_b ** 2)
        
        if dist_bd < abs(b - c) or dist_bd > b + c:
            dist_bd = max(abs(b - c), min(b + c, dist_bd))
        
        cos_phi = (b ** 2 + dist_bd ** 2 - c ** 2) / (2 * b * dist_bd)
        cos_phi = max(-1.0, min(1.0, cos_phi))
        phi = math.acos(cos_phi)
        
        angle_bd = math.atan2(-y_b, d - x_b)
        angle_bc = angle_bd + phi
        
        x_c = x_b + b * math.cos(angle_bc)
        y_c = y_b + b * math.sin(angle_bc)
        
        foot_displacement = math.sqrt(x_c ** 2 + y_c ** 2)
        return foot_displacement
    
    def _generate_normal_data(self, elapsed_time: float) -> SensorData:
        self.current_crank_angle = (elapsed_time * self.params.crank_speed) % 360
        
        leg_displacement = self._solve_jansen_linkage(self.current_crank_angle)
        
        body_inclination = 2.0 * math.sin(math.radians(self.current_crank_angle * 0.1))
        body_inclination += random.uniform(-0.5, 0.5)
        
        ground_elevation = random.uniform(-5.0, 5.0)
        
        return SensorData(
            crank_angle=self.current_crank_angle,
            leg_displacement=leg_displacement,
            body_inclination=body_inclination,
            ground_elevation=ground_elevation,
            status=DeviceStatus.NORMAL
        )
    
    def _generate_obstacle_data(self, elapsed_time: float) -> SensorData:
        base_data = self._generate_normal_data(elapsed_time)
        
        position = elapsed_time * 10.0
        
        obstacle_start = 500.0
        obstacle_end = 700.0
        obstacle_height = 80.0
        
        if obstacle_start <= position <= obstacle_end:
            progress = (position - obstacle_start) / (obstacle_end - obstacle_start)
            obstacle_profile = obstacle_height * math.sin(math.pi * progress)
            
            base_data.ground_elevation = obstacle_profile + random.uniform(-2, 2)
            base_data.body_inclination += 8.0 * math.sin(math.pi * progress)
            
            if abs(base_data.body_inclination) > 10.0:
                base_data.status = DeviceStatus.WARNING
        else:
            base_data.status = DeviceStatus.NORMAL
        
        return base_data
    
    def _generate_inclination_test_data(self, elapsed_time: float) -> SensorData:
        base_data = self._generate_normal_data(elapsed_time)
        
        cycle = elapsed_time / 120.0
        inclination_amplitude = 20.0 * math.sin(math.pi * (cycle % 1))
        
        base_data.body_inclination = inclination_amplitude + random.uniform(-1, 1)
        
        if abs(base_data.body_inclination) > 15.0:
            base_data.status = DeviceStatus.ERROR
        elif abs(base_data.body_inclination) > 10.0:
            base_data.status = DeviceStatus.WARNING
        
        return base_data
    
    def _generate_jam_test_data(self, elapsed_time: float) -> SensorData:
        base_data = self._generate_normal_data(elapsed_time)
        
        if elapsed_time > 60 and not self.is_jammed:
            if random.random() < 0.01:
                self.is_jammed = True
                logger.warning("模拟机构卡死!")
        
        if self.is_jammed:
            self.jam_counter += 1
            base_data.leg_displacement = 200.0 + random.uniform(-1, 1)
            base_data.crank_angle = (base_data.crank_angle + 30) % 360
            base_data.status = DeviceStatus.JAMMED | DeviceStatus.ERROR
            
            if self.jam_counter > 300:
                self.is_jammed = False
                self.jam_counter = 0
                logger.info("机构恢复正常")
        
        return base_data
    
    def _generate_random_data(self, elapsed_time: float) -> SensorData:
        modes = [
            self._generate_normal_data,
            self._generate_obstacle_data,
            self._generate_inclination_test_data
        ]
        
        cycle = int(elapsed_time / 300) % len(modes)
        return modes[cycle](elapsed_time)
    
    def generate_sensor_data(self) -> SensorData:
        elapsed_time = time.time() - self.start_time
        
        generators = {
            SimulationMode.NORMAL: self._generate_normal_data,
            SimulationMode.OBSTACLE: self._generate_obstacle_data,
            SimulationMode.INCLINATION_TEST: self._generate_inclination_test_data,
            SimulationMode.JAM_TEST: self._generate_jam_test_data,
            SimulationMode.RANDOM: self._generate_random_data
        }
        
        data = generators[self.mode](elapsed_time)
        data.timestamp = datetime.utcnow()
        
        self.data_history.append(data)
        if len(self.data_history) > 1000:
            self.data_history = self.data_history[-1000:]
        
        return data
    
    def _encode_to_registers(self, data: SensorData) -> list:
        builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
        
        builder.add_32bit_float(data.crank_angle)
        builder.add_32bit_float(data.leg_displacement)
        builder.add_32bit_float(data.body_inclination)
        builder.add_32bit_float(data.ground_elevation)
        builder.add_16bit_uint(data.status.value)
        
        timestamp_int = int(data.timestamp.timestamp())
        builder.add_16bit_uint((timestamp_int >> 16) & 0xFFFF)
        builder.add_16bit_uint(timestamp_int & 0xFFFF)
        
        registers = builder.to_registers()
        
        crc = self._calculate_crc(registers[:-2])
        registers.append((crc >> 16) & 0xFFFF)
        registers.append(crc & 0xFFFF)
        
        return registers
    
    def _calculate_crc(self, data: list) -> int:
        crc = 0xFFFF
        for value in data:
            crc ^= value
            for _ in range(16):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def _update_registers(self, data: SensorData):
        registers = self._encode_to_registers(data)
        
        for i, value in enumerate(registers):
            self.store.setValues(3, i, [value])
        
        logger.debug(
            f"寄存器已更新: 曲柄={data.crank_angle:.1f}°, "
            f"腿部位移={data.leg_displacement:.1f}mm, "
            f"倾角={data.body_inclination:.1f}°, "
            f"地面={data.ground_elevation:.1f}mm"
        )
    
    async def _send_to_api(self, data: SensorData):
        try:
            import aiohttp
            
            payload = {
                "timestamp": data.timestamp.isoformat(),
                "device_id": self.device_id,
                "crank_angle": round(data.crank_angle, 2),
                "leg_displacement": round(data.leg_displacement, 2),
                "body_inclination": round(data.body_inclination, 2),
                "ground_elevation": round(data.ground_elevation, 2)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/sensors/ingest",
                    json=payload,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.info(
                            f"数据已发送到API: {self.device_id}, "
                            f"告警={result.get('alerts_triggered', 0)}"
                        )
                    else:
                        logger.warning(f"API响应错误: {resp.status}")
        except ImportError:
            logger.debug("aiohttp未安装，跳过API上报")
        except Exception as e:
            logger.warning(f"发送到API失败: {e}")
    
    async def _data_generation_loop(self):
        logger.info(f"启动数据生成循环，上报间隔: {self.report_interval}秒")
        
        while True:
            try:
                data = self.generate_sensor_data()
                self._update_registers(data)
                await self._send_to_api(data)
                
                await asyncio.sleep(self.report_interval)
            except Exception as e:
                logger.error(f"数据生成错误: {e}")
                await asyncio.sleep(5)
    
    async def start(self):
        logger.info(f"启动传感器模拟器: {self.device_id}")
        logger.info(f"协议: {'TCP' if self.use_tcp else 'Serial'}")
        logger.info(f"地址: {self.host}:{self.port}" if self.use_tcp else f"串口: {self.serial_port} @ {self.baudrate}")
        
        asyncio.create_task(self._data_generation_loop())
        
        if self.use_tcp:
            await StartAsyncTcpServer(
                context=self.context,
                address=(self.host, self.port)
            )
        else:
            await StartAsyncSerialServer(
                context=self.context,
                port=self.serial_port,
                baudrate=self.baudrate,
                bytesize=8,
                parity='N',
                stopbits=1
            )
    
    def get_statistics(self) -> dict:
        if not self.data_history:
            return {}
        
        recent = self.data_history[-100:]
        inclinations = [d.body_inclination for d in recent]
        
        return {
            "device_id": self.device_id,
            "mode": self.mode.value,
            "total_samples": len(self.data_history),
            "uptime_seconds": time.time() - self.start_time,
            "avg_inclination": sum(inclinations) / len(inclinations),
            "max_inclination": max(abs(d) for d in inclinations),
            "current_crank_angle": self.current_crank_angle,
            "is_jammed": self.is_jammed
        }


async def run_single_simulator():
    import argparse
    
    parser = argparse.ArgumentParser(description="木牛流马Modbus传感器模拟器")
    parser.add_argument("--device-id", default="woodox_001", help="设备ID")
    parser.add_argument("--slave-id", type=int, default=1, help="Modbus从站ID")
    parser.add_argument("--mode", default="normal", 
                       choices=["normal", "obstacle", "inclination_test", "jam_test", "random"],
                       help="仿真模式")
    parser.add_argument("--interval", type=int, default=60, help="上报间隔(秒)")
    parser.add_argument("--tcp", action="store_true", default=True, help="使用TCP协议")
    parser.add_argument("--host", default="0.0.0.0", help="TCP主机地址")
    parser.add_argument("--port", type=int, default=502, help="TCP端口")
    parser.add_argument("--serial-port", default="COM1", help="串口地址")
    parser.add_argument("--baudrate", type=int, default=9600, help="串口波特率")
    parser.add_argument("--api-url", default="http://localhost:8000", help="后端API地址")
    parser.add_argument("--crank-speed", type=float, default=30.0, help="曲柄转速(度/秒)")
    
    args = parser.parse_args()
    
    params = JansenLinkageParams(crank_speed=args.crank_speed)
    mode = SimulationMode(args.mode)
    
    simulator = WoodOxSensorSimulator(
        device_id=args.device_id,
        slave_id=args.slave_id,
        mode=mode,
        params=params,
        report_interval=args.interval,
        use_tcp=args.tcp,
        host=args.host,
        port=args.port,
        serial_port=args.serial_port,
        baudrate=args.baudrate,
        api_url=args.api_url
    )
    
    await simulator.start()


async def run_multi_simulators():
    simulators = []
    
    configs = [
        {"device_id": "woodox_001", "mode": SimulationMode.NORMAL, "port": 502},
        {"device_id": "woodox_002", "mode": SimulationMode.OBSTACLE, "port": 503},
        {"device_id": "woodox_003", "mode": SimulationMode.INCLINATION_TEST, "port": 504},
    ]
    
    for config in configs:
        simulator = WoodOxSensorSimulator(
            device_id=config["device_id"],
            slave_id=1,
            mode=config["mode"],
            report_interval=60,
            use_tcp=True,
            host="0.0.0.0",
            port=config["port"]
        )
        simulators.append(simulator)
    
    await asyncio.gather(*[sim.start() for sim in simulators])


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--multi":
        asyncio.run(run_multi_simulators())
    else:
        asyncio.run(run_single_simulator())

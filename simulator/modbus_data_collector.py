#!/usr/bin/env python3

import asyncio
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

try:
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
    from pymodbus.payload import BinaryPayloadDecoder
    from pymodbus.constants import Endian
except ImportError:
    print("请安装pymodbus: pip install pymodbus==3.6.6")
    raise

try:
    import aiohttp
except ImportError:
    print("请安装aiohttp: pip install aiohttp==3.9.1")
    raise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class DeviceConfig:
    device_id: str
    use_tcp: bool = True
    host: str = "localhost"
    port: int = 502
    serial_port: str = "COM1"
    baudrate: int = 9600
    slave_id: int = 1
    poll_interval: int = 60


@dataclass
class SensorReading:
    device_id: str
    crank_angle: float
    leg_displacement: float
    body_inclination: float
    ground_elevation: float
    device_status: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_valid: bool = True
    crc_valid: bool = True


class ModbusDataCollector:
    def __init__(
        self,
        devices: List[DeviceConfig],
        api_url: str = "http://localhost:8000",
        batch_size: int = 10
    ):
        self.devices = devices
        self.api_url = api_url
        self.batch_size = batch_size
        
        self.clients: Dict[str, object] = {}
        self.readings: List[SensorReading] = []
        self.running = False
        
        logger.info(f"初始化数据采集器，设备数: {len(devices)}")
    
    def _connect_device(self, config: DeviceConfig) -> bool:
        try:
            if config.use_tcp:
                client = ModbusTcpClient(
                    host=config.host,
                    port=config.port,
                    timeout=10
                )
            else:
                client = ModbusSerialClient(
                    port=config.serial_port,
                    baudrate=config.baudrate,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=10
                )
            
            connection = client.connect()
            if connection:
                self.clients[config.device_id] = client
                logger.info(f"设备 {config.device_id} 连接成功")
                return True
            else:
                logger.error(f"设备 {config.device_id} 连接失败")
                return False
        except Exception as e:
            logger.error(f"设备 {config.device_id} 连接异常: {e}")
            return False
    
    def _disconnect_device(self, device_id: str):
        if device_id in self.clients:
            try:
                self.clients[device_id].close()
            except:
                pass
            del self.clients[device_id]
            logger.info(f"设备 {device_id} 已断开")
    
    def _read_registers(
        self,
        client,
        slave_id: int,
        start_address: int,
        count: int
    ) -> Optional[list]:
        try:
            result = client.read_holding_registers(
                address=start_address,
                count=count,
                slave=slave_id
            )
            
            if not result.isError():
                return result.registers
            else:
                logger.warning(f"读取寄存器错误: {result}")
                return None
        except Exception as e:
            logger.error(f"读取寄存器异常: {e}")
            return None
    
    def _decode_sensor_data(
        self,
        registers: list,
        device_id: str
    ) -> Optional[SensorReading]:
        if len(registers) < 13:
            logger.warning(f"寄存器数据不足: {len(registers)}")
            return None
        
        try:
            decoder = BinaryPayloadDecoder.fromRegisters(
                registers,
                byteorder=Endian.Big,
                wordorder=Endian.Big
            )
            
            crank_angle = decoder.decode_32bit_float()
            leg_displacement = decoder.decode_32bit_float()
            body_inclination = decoder.decode_32bit_float()
            ground_elevation = decoder.decode_32bit_float()
            device_status = decoder.decode_16bit_uint()
            
            timestamp_high = decoder.decode_16bit_uint()
            timestamp_low = decoder.decode_16bit_uint()
            timestamp_int = (timestamp_high << 16) | timestamp_low
            
            crc_high = decoder.decode_16bit_uint()
            crc_low = decoder.decode_16bit_uint()
            received_crc = (crc_high << 16) | crc_low
            
            calculated_crc = self._calculate_crc(registers[:11])
            crc_valid = (received_crc == calculated_crc)
            
            is_valid = (
                -360.0 <= crank_angle <= 720.0 and
                0.0 <= leg_displacement <= 1000.0 and
                -90.0 <= body_inclination <= 90.0 and
                -1000.0 <= ground_elevation <= 1000.0
            )
            
            return SensorReading(
                device_id=device_id,
                crank_angle=round(crank_angle, 2),
                leg_displacement=round(leg_displacement, 2),
                body_inclination=round(body_inclination, 2),
                ground_elevation=round(ground_elevation, 2),
                device_status=device_status,
                timestamp=datetime.fromtimestamp(timestamp_int),
                is_valid=is_valid,
                crc_valid=crc_valid
            )
            
        except Exception as e:
            logger.error(f"解码传感器数据失败: {e}")
            return None
    
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
    
    async def _send_to_api(self, reading: SensorReading) -> bool:
        try:
            payload = {
                "timestamp": reading.timestamp.isoformat(),
                "device_id": reading.device_id,
                "crank_angle": reading.crank_angle,
                "leg_displacement": reading.leg_displacement,
                "body_inclination": reading.body_inclination,
                "ground_elevation": reading.ground_elevation
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/sensors/ingest",
                    json=payload,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get('alerts_triggered', 0) > 0:
                            logger.warning(
                                f"设备 {reading.device_id} 触发 "
                                f"{result['alerts_triggered']} 个告警"
                            )
                        return True
                    else:
                        logger.warning(
                            f"API响应错误 {resp.status}: {await resp.text()}"
                        )
                        return False
        except Exception as e:
            logger.error(f"发送到API失败: {e}")
            return False
    
    async def _poll_device(self, config: DeviceConfig):
        if config.device_id not in self.clients:
            if not self._connect_device(config):
                return
        
        client = self.clients[config.device_id]
        
        registers = self._read_registers(
            client,
            config.slave_id,
            start_address=0,
            count=13
        )
        
        if registers is None:
            logger.warning(f"设备 {config.device_id} 读取失败，尝试重连...")
            self._disconnect_device(config.device_id)
            return
        
        reading = self._decode_sensor_data(registers, config.device_id)
        
        if reading is None:
            logger.warning(f"设备 {config.device_id} 数据解码失败")
            return
        
        if not reading.crc_valid:
            logger.warning(f"设备 {config.device_id} CRC校验失败")
        
        if not reading.is_valid:
            logger.warning(f"设备 {config.device_id} 数据范围异常")
        
        self.readings.append(reading)
        
        logger.info(
            f"设备 {config.device_id}: "
            f"曲柄={reading.crank_angle:.1f}°, "
            f"位移={reading.leg_displacement:.1f}mm, "
            f"倾角={reading.body_inclination:.1f}°, "
            f"地面={reading.ground_elevation:.1f}mm, "
            f"状态=0x{reading.device_status:04X}"
        )
        
        await self._send_to_api(reading)
        
        if len(self.readings) > 10000:
            self.readings = self.readings[-1000:]
    
    async def _polling_loop(self):
        logger.info("启动数据采集循环...")
        
        while self.running:
            try:
                tasks = []
                for config in self.devices:
                    task = asyncio.create_task(self._poll_device(config))
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"采集循环异常: {e}")
                await asyncio.sleep(5)
    
    def get_statistics(self) -> dict:
        if not self.readings:
            return {}
        
        device_stats = {}
        for config in self.devices:
            device_readings = [
                r for r in self.readings if r.device_id == config.device_id
            ]
            
            if device_readings:
                inclinations = [r.body_inclination for r in device_readings[-100:]]
                device_stats[config.device_id] = {
                    "total_readings": len(device_readings),
                    "valid_readings": sum(1 for r in device_readings if r.is_valid),
                    "crc_errors": sum(1 for r in device_readings if not r.crc_valid),
                    "avg_inclination": sum(inclinations) / len(inclinations),
                    "max_inclination": max(abs(i) for i in inclinations),
                    "connected": config.device_id in self.clients
                }
        
        return {
            "total_devices": len(self.devices),
            "connected_devices": len(self.clients),
            "total_readings": len(self.readings),
            "device_stats": device_stats
        }
    
    async def start(self):
        self.running = True
        
        logger.info("连接所有设备...")
        for config in self.devices:
            self._connect_device(config)
        
        await self._polling_loop()
    
    async def stop(self):
        self.running = False
        logger.info("停止数据采集...")
        
        for device_id in list(self.clients.keys()):
            self._disconnect_device(device_id)
        
        logger.info("数据采集已停止")


def load_config_from_file(config_path: str) -> List[DeviceConfig]:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        devices = []
        for dev in config_data.get('devices', []):
            devices.append(DeviceConfig(
                device_id=dev['device_id'],
                use_tcp=dev.get('use_tcp', True),
                host=dev.get('host', 'localhost'),
                port=dev.get('port', 502),
                serial_port=dev.get('serial_port', 'COM1'),
                baudrate=dev.get('baudrate', 9600),
                slave_id=dev.get('slave_id', 1),
                poll_interval=dev.get('poll_interval', 60)
            ))
        
        logger.info(f"从配置文件加载 {len(devices)} 个设备")
        return devices
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return []


async def run_collector():
    import argparse
    
    parser = argparse.ArgumentParser(description="Modbus数据采集服务")
    parser.add_argument("--config", help="设备配置文件(JSON)")
    parser.add_argument("--api-url", default="http://localhost:8000", help="后端API地址")
    
    group = parser.add_argument_group("单设备配置")
    group.add_argument("--device-id", help="设备ID")
    group.add_argument("--tcp", action="store_true", default=True, help="使用TCP协议")
    group.add_argument("--host", default="localhost", help="Modbus TCP主机")
    group.add_argument("--port", type=int, default=502, help="Modbus TCP端口")
    group.add_argument("--serial-port", default="COM1", help="串口地址")
    group.add_argument("--baudrate", type=int, default=9600, help="串口波特率")
    group.add_argument("--slave-id", type=int, default=1, help="Modbus从站ID")
    group.add_argument("--interval", type=int, default=60, help="采集间隔(秒)")
    
    args = parser.parse_args()
    
    devices = []
    
    if args.config:
        devices = load_config_from_file(args.config)
    elif args.device_id:
        devices.append(DeviceConfig(
            device_id=args.device_id,
            use_tcp=args.tcp,
            host=args.host,
            port=args.port,
            serial_port=args.serial_port,
            baudrate=args.baudrate,
            slave_id=args.slave_id,
            poll_interval=args.interval
        ))
    else:
        devices = [
            DeviceConfig(
                device_id="woodox_001",
                use_tcp=True,
                host="localhost",
                port=502,
                slave_id=1,
                poll_interval=60
            )
        ]
        logger.info("使用默认设备配置")
    
    if not devices:
        logger.error("没有配置任何设备")
        return
    
    collector = ModbusDataCollector(
        devices=devices,
        api_url=args.api_url
    )
    
    try:
        await collector.start()
    except KeyboardInterrupt:
        await collector.stop()


if __name__ == "__main__":
    asyncio.run(run_collector())

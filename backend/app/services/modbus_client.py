import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from app.core.config import settings
from app.models.schemas import SensorData

logger = logging.getLogger(__name__)


class ModbusRTUClient:
    def __init__(self):
        self.client = None
        self.port = settings.modbus_port
        self.baudrate = settings.modbus_baudrate
        self.slave_id = settings.modbus_slave_id
        self._connected = False
        
        self.register_map = {
            'crank_angle': {'address': 0, 'count': 2, 'scale': 0.01, 'unit': '°'},
            'leg_displacement': {'address': 2, 'count': 2, 'scale': 0.1, 'unit': 'mm'},
            'body_inclination': {'address': 4, 'count': 2, 'scale': 0.01, 'unit': '°'},
            'ground_elevation': {'address': 6, 'count': 2, 'scale': 0.1, 'unit': 'mm'},
            'device_status': {'address': 8, 'count': 1, 'scale': 1.0, 'unit': ''}
        }

    def connect(self) -> bool:
        try:
            self.client = ModbusSerialClient(
                port=self.port,
                baudrate=self.baudrate,
                timeout=3
            )
            self._connected = self.client.connect()
            logger.info(f"Modbus RTU连接状态: {self._connected}")
            return self._connected
        except Exception as e:
            logger.error(f"Modbus RTU连接失败: {e}")
            self._connected = False
            return False

    def disconnect(self):
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Modbus RTU连接已关闭")

    def is_connected(self) -> bool:
        return self._connected and self.client.is_socket_open() if hasattr(self.client, 'is_socket_open') else self._connected

    def _read_holding_registers(self, address: int, count: int) -> Optional[list]:
        try:
            if not self.is_connected():
                if not self.connect():
                    return None
            
            response = self.client.read_holding_registers(
                address=address,
                count=count,
                slave=self.slave_id
            )
            
            if response.isError():
                logger.error(f"读取寄存器错误: 地址={address}, 错误={response}")
                return None
            
            return response.registers
        except ModbusException as e:
            logger.error(f"Modbus异常: {e}")
            self._connected = False
            return None
        except Exception as e:
            logger.error(f"读取寄存器异常: {e}")
            return None

    def _combine_registers(self, registers: list) -> float:
        if not registers or len(registers) < 2:
            return 0.0
        high_word = registers[0]
        low_word = registers[1]
        combined = (high_word << 16) | low_word
        
        if combined & 0x80000000:
            combined = -((~combined + 1) & 0xFFFFFFFF)
        
        return float(combined)

    def read_sensor_data(self, device_id: str) -> Optional[SensorData]:
        if not self.is_connected():
            if not self.connect():
                return None
        
        sensor_values = {}
        
        for field, config in self.register_map.items():
            if field == 'device_status':
                continue
            
            registers = self._read_holding_registers(config['address'], config['count'])
            if registers is None:
                logger.warning(f"读取{field}失败，跳过")
                return None
            
            raw_value = self._combine_registers(registers)
            scaled_value = raw_value * config['scale']
            sensor_values[field] = scaled_value
            
            logger.debug(f"{field}: 原始值={raw_value}, 缩放后={scaled_value}{config['unit']}")
        
        if len(sensor_values) < 4:
            return None
        
        try:
            return SensorData(
                timestamp=datetime.utcnow(),
                device_id=device_id,
                crank_angle=float(sensor_values.get('crank_angle', 0.0) % 360.0),
                leg_displacement=float(sensor_values.get('leg_displacement', 0.0)),
                body_inclination=float(sensor_values.get('body_inclination', 0.0)),
                ground_elevation=float(sensor_values.get('ground_elevation', 0.0))
            )
        except Exception as e:
            logger.error(f"构造SensorData失败: {e}")
            return None

    def read_device_status(self) -> Optional[Dict[str, Any]]:
        registers = self._read_holding_registers(8, 1)
        if registers is None:
            return None
        
        status = registers[0]
        return {
            'status_code': status,
            'is_running': (status & 0x01) != 0,
            'has_error': (status & 0x02) != 0,
            'is_calibrated': (status & 0x04) != 0,
            'battery_low': (status & 0x08) != 0
        }

    def write_register(self, address: int, value: int) -> bool:
        try:
            if not self.is_connected():
                if not self.connect():
                    return False
            
            response = self.client.write_register(
                address=address,
                value=value,
                slave=self.slave_id
            )
            
            if response.isError():
                logger.error(f"写入寄存器错误: 地址={address}, 错误={response}")
                return False
            
            logger.info(f"写入寄存器成功: 地址={address}, 值={value}")
            return True
        except Exception as e:
            logger.error(f"写入寄存器异常: {e}")
            return False

    async def poll_continuous(
        self,
        device_id: str,
        interval: float = 60.0,
        callback=None
    ):
        logger.info(f"开始连续采集数据: 设备={device_id}, 间隔={interval}s")
        
        while True:
            try:
                data = self.read_sensor_data(device_id)
                if data and callback:
                    await callback(data)
                
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("数据采集已取消")
                break
            except Exception as e:
                logger.error(f"数据采集异常: {e}")
                await asyncio.sleep(interval)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

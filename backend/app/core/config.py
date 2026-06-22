from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "木牛流马仿真系统"
    app_env: str = "development"
    app_port: int = 8000

    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "your-influxdb-token"
    influxdb_org: str = "wood-ox-research"
    influxdb_bucket: str = "sensor_raw"

    redis_url: str = "redis://localhost:6379/0"

    modbus_port: str = "COM1"
    modbus_baudrate: int = 9600
    modbus_slave_id: int = 1

    alert_inclination_threshold: float = 15.0
    alert_jammed_threshold: float = 5.0

    websocket_host: str = "0.0.0.0"
    websocket_port: int = 8765

    cors_origins: list = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

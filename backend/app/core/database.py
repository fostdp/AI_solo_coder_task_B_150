from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS
from influxdb_client.client.flux_table import FluxRecord
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
import logging

from .config import settings
from app.models.schemas import SensorData, Alert, GaitAnalysisResult, ObstacleAssessmentResult

logger = logging.getLogger(__name__)


class InfluxDBManager:
    def __init__(self):
        self.client = None
        self.write_api = None
        self.query_api = None
        self.bucket = settings.influxdb_bucket
        self.org = settings.influxdb_org
        self._connect()

    def _connect(self):
        try:
            self.client = InfluxDBClient(
                url=settings.influxdb_url,
                token=settings.influxdb_token,
                org=settings.influxdb_org
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()
            logger.info("InfluxDB连接成功")
        except Exception as e:
            logger.error(f"InfluxDB连接失败: {e}")

    async def write_sensor_data(self, data: SensorData):
        point = Point("sensor_data") \
            .tag("device_id", data.device_id) \
            .field("crank_angle", data.crank_angle) \
            .field("leg_displacement", data.leg_displacement) \
            .field("body_inclination", data.body_inclination) \
            .field("ground_elevation", data.ground_elevation) \
            .time(data.timestamp, WritePrecision.NS)
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    async def write_gait_result(self, result: GaitAnalysisResult):
        point = Point("gait_results") \
            .tag("device_id", result.device_id) \
            .field("stride_length", result.stride_length) \
            .field("cadence", result.cadence) \
            .field("support_phase", result.support_phase) \
            .field("swing_phase", result.swing_phase) \
            .field("stability_margin", result.stability_margin) \
            .field("com_trajectory", json.dumps([p.model_dump() for p in result.com_trajectory])) \
            .field("zmp_trajectory", json.dumps([p.model_dump() for p in result.zmp_trajectory])) \
            .time(result.timestamp, WritePrecision.NS)
        self.write_api.write(bucket="gait_results", org=self.org, record=point)

    async def write_obstacle_assessment(self, result: ObstacleAssessmentResult):
        point = Point("obstacle_assessments") \
            .tag("device_id", result.device_id) \
            .tag("risk_level", result.risk_level.value) \
            .field("max_obstacle_height", result.max_obstacle_height) \
            .field("max_slope_angle", result.max_slope_angle) \
            .field("critical_inclination", result.critical_inclination) \
            .field("obstacle_pass_probability", result.obstacle_pass_probability) \
            .field("recommended_speed", result.recommended_speed) \
            .field("terrain_analysis", json.dumps(result.terrain_analysis)) \
            .time(result.timestamp, WritePrecision.NS)
        self.write_api.write(bucket="obstacle_assessments", org=self.org, record=point)

    async def write_alert(self, alert: Alert):
        point = Point("alerts") \
            .tag("alert_id", alert.id) \
            .tag("device_id", alert.device_id) \
            .tag("type", alert.type.value) \
            .tag("level", alert.level.value) \
            .tag("acknowledged", str(alert.acknowledged)) \
            .field("message", alert.message) \
            .field("sensor_data", json.dumps(alert.sensor_data.model_dump())) \
            .time(alert.timestamp, WritePrecision.NS)
        self.write_api.write(bucket="alerts", org=self.org, record=point)

    async def query_sensor_history(
        self,
        device_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[SensorData]:
        flux_query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                |> filter(fn: (r) => r._measurement == "sensor_data")
                |> filter(fn: (r) => r.device_id == "{device_id}")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> limit(n: {limit})
                |> sort(columns: ["_time"], desc: true)
        '''
        tables = self.query_api.query(flux_query)
        results = []
        for table in tables:
            for record in table.records:
                results.append(SensorData(
                    timestamp=record.get_time(),
                    device_id=record.values.get("device_id"),
                    crank_angle=record.values.get("crank_angle", 0.0),
                    leg_displacement=record.values.get("leg_displacement", 0.0),
                    body_inclination=record.values.get("body_inclination", 0.0),
                    ground_elevation=record.values.get("ground_elevation", 0.0)
                ))
        return results

    async def query_latest_sensor(self, device_id: str) -> Optional[SensorData]:
        flux_query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -5m)
                |> filter(fn: (r) => r._measurement == "sensor_data")
                |> filter(fn: (r) => r.device_id == "{device_id}")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: 1)
        '''
        tables = self.query_api.query(flux_query)
        for table in tables:
            for record in table.records:
                return SensorData(
                    timestamp=record.get_time(),
                    device_id=record.values.get("device_id"),
                    crank_angle=record.values.get("crank_angle", 0.0),
                    leg_displacement=record.values.get("leg_displacement", 0.0),
                    body_inclination=record.values.get("body_inclination", 0.0),
                    ground_elevation=record.values.get("ground_elevation", 0.0)
                )
        return None

    async def query_alerts(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        alert_type: Optional[str] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        start = start_time.isoformat() if start_time else "-30d"
        stop = end_time.isoformat() if end_time else "now()"
        
        flux_query = f'''
            from(bucket: "alerts")
                |> range(start: {start}, stop: {stop})
                |> filter(fn: (r) => r._measurement == "alerts")
        '''
        
        if alert_type:
            flux_query += f'|> filter(fn: (r) => r.type == "{alert_type}")\n'
        
        if acknowledged is not None:
            flux_query += f'|> filter(fn: (r) => r.acknowledged == "{str(acknowledged).lower()}")\n'
        
        flux_query += f'''
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: {limit})
        '''
        
        tables = self.query_api.query(flux_query)
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "id": record.values.get("alert_id"),
                    "timestamp": record.get_time(),
                    "type": record.values.get("type"),
                    "level": record.values.get("level"),
                    "message": record.values.get("message"),
                    "device_id": record.values.get("device_id"),
                    "acknowledged": record.values.get("acknowledged") == "true",
                    "sensor_data": json.loads(record.values.get("sensor_data", "{}"))
                })
        return results

    def close(self):
        if self.client:
            self.client.close()


class RedisManager:
    def __init__(self):
        self.redis = None
        self._connect()

    async def _connect(self):
        try:
            self.redis = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")

    async def set_cache(self, key: str, value: Any, expire: int = 60):
        if isinstance(value, dict):
            value = json.dumps(value)
        await self.redis.setex(key, expire, value)

    async def get_cache(self, key: str) -> Optional[Any]:
        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except:
                return value
        return None

    async def publish(self, channel: str, message: str) -> int:
        try:
            if not self.redis:
                await self._connect()
            return await self.redis.publish(channel, message)
        except Exception as e:
            logger.error(f"Redis发布消息失败: channel={channel}, error={e}")
            return 0

    async def get_pubsub(self):
        if not self.redis:
            await self._connect()
        return self.redis.pubsub()

    async def close(self):
        if self.redis:
            await self.redis.close()


influx_db = InfluxDBManager()
redis_db = RedisManager()

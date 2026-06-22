#!/usr/bin/env python3

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import time
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InfluxDBInitializer:
    def __init__(self):
        self.url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
        self.token = os.getenv("INFLUXDB_TOKEN", "woodox-secret-token-2024")
        self.org = os.getenv("INFLUXDB_ORG", "wood-ox-research")
        
        self.client = None
        self.write_api = None
        self.query_api = None
        self.buckets_api = None
        self.tasks_api = None
        
        self._connect()
    
    def _connect(self, max_retries=10, retry_delay=5):
        for i in range(max_retries):
            try:
                self.client = influxdb_client.InfluxDBClient(
                    url=self.url,
                    token=self.token,
                    org=self.org
                )
                self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
                self.query_api = self.client.query_api()
                self.buckets_api = self.client.buckets_api()
                self.tasks_api = self.client.tasks_api()
                
                self.client.ping()
                logger.info("InfluxDB连接成功")
                return
            except Exception as e:
                logger.warning(f"连接尝试 {i+1}/{max_retries} 失败: {e}")
                if i < max_retries - 1:
                    time.sleep(retry_delay)
        
        raise Exception("无法连接到InfluxDB")
    
    def create_buckets(self):
        buckets_config = [
            {"name": "sensor_raw", "retention_days": 30, "description": "原始传感器数据"},
            {"name": "gait_results", "retention_days": 90, "description": "步态分析结果"},
            {"name": "obstacle_assessments", "retention_days": 90, "description": "越障评估结果"},
            {"name": "alerts", "retention_days": 365, "description": "告警记录"},
            {"name": "sensor_downsampled_1m", "retention_days": 365, "description": "1分钟降采样数据"},
            {"name": "sensor_downsampled_1h", "retention_days": 730, "description": "1小时降采样数据"},
        ]
        
        existing_buckets = [b.name for b in self.buckets_api.find_buckets().buckets]
        
        for config in buckets_config:
            if config["name"] in existing_buckets:
                logger.info(f"Bucket已存在: {config['name']}")
                continue
            
            try:
                self.buckets_api.create_bucket(
                    bucket_name=config["name"],
                    org=self.org,
                    retention_rules=[{
                        "type": "expire",
                        "everySeconds": config["retention_days"] * 24 * 3600
                    }],
                    description=config["description"]
                )
                logger.info(f"创建Bucket: {config['name']} (保留{config['retention_days']}天)")
            except Exception as e:
                logger.error(f"创建Bucket失败 {config['name']}: {e}")
    
    def create_continuous_queries(self):
        tasks = [
            {
                "name": "sensor_downsample_1m",
                "every": "1m",
                "query": '''
option task = {name: "sensor_downsample_1m", every: 1m}

data = from(bucket: "sensor_raw")
    |> range(start: -task.every)
    |> filter(fn: (r) => r._measurement == "sensor_data")

data
    |> aggregateWindow(every: 1m, fn: mean)
    |> to(bucket: "sensor_downsampled_1m")
'''
            },
            {
                "name": "sensor_downsample_1h",
                "every": "1h",
                "query": '''
option task = {name: "sensor_downsample_1h", every: 1h}

data = from(bucket: "sensor_raw")
    |> range(start: -task.every)
    |> filter(fn: (r) => r._measurement == "sensor_data")

data
    |> aggregateWindow(every: 1h, fn: mean)
    |> to(bucket: "sensor_downsampled_1h")
'''
            }
        ]
        
        for task_config in tasks:
            try:
                existing = self.tasks_api.find_tasks(name=task_config["name"])
                if existing:
                    logger.info(f"任务已存在: {task_config['name']}")
                    continue
                
                self.tasks_api.create_task(
                    name=task_config["name"],
                    every=task_config["every"],
                    query=task_config["query"],
                    org=self.org
                )
                logger.info(f"创建连续查询任务: {task_config['name']}")
            except Exception as e:
                logger.error(f"创建任务失败 {task_config['name']}: {e}")
    
    def insert_sample_data(self):
        logger.info("插入示例数据...")
        
        device_ids = ["woodox_001", "woodox_002"]
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=2)
        
        points = []
        current_time = start_time
        
        for device_id in device_ids:
            current_time = start_time
            while current_time < end_time:
                import math
                import random
                
                crank_angle = (current_time.timestamp() * 30) % 360
                leg_displacement = 150 + 50 * math.sin(math.radians(crank_angle))
                body_inclination = 2 * math.sin(math.radians(crank_angle * 0.1))
                ground_elevation = random.uniform(-10, 10)
                
                point = influxdb_client.Point("sensor_data") \
                    .tag("device_id", device_id) \
                    .field("crank_angle", round(crank_angle, 2)) \
                    .field("leg_displacement", round(leg_displacement, 2)) \
                    .field("body_inclination", round(body_inclination, 2)) \
                    .field("ground_elevation", round(ground_elevation, 2)) \
                    .time(current_time)
                
                points.append(point)
                current_time += timedelta(seconds=10)
        
        if points:
            self.write_api.write(bucket="sensor_raw", org=self.org, record=points)
            logger.info(f"插入 {len(points)} 条示例数据")
    
    def verify_setup(self):
        logger.info("验证InfluxDB设置...")
        
        buckets = self.buckets_api.find_buckets().buckets
        bucket_names = [b.name for b in buckets]
        
        required_buckets = ["sensor_raw", "gait_results", "obstacle_assessments", "alerts"]
        missing = [b for b in required_buckets if b not in bucket_names]
        
        if missing:
            logger.error(f"缺少必要的Bucket: {missing}")
            return False
        
        tasks = self.tasks_api.find_tasks()
        task_names = [t.name for t in tasks.tasks]
        
        logger.info(f"可用Buckets: {bucket_names}")
        logger.info(f"可用Tasks: {task_names}")
        logger.info("InfluxDB设置验证通过")
        return True
    
    def close(self):
        if self.client:
            self.client.close()
            logger.info("InfluxDB连接已关闭")


def main():
    initializer = InfluxDBInitializer()
    
    try:
        initializer.create_buckets()
        initializer.create_continuous_queries()
        initializer.insert_sample_data()
        
        if initializer.verify_setup():
            logger.info("=== InfluxDB初始化完成 ===")
        else:
            logger.error("=== InfluxDB初始化失败 ===")
            return 1
    finally:
        initializer.close()
    
    return 0


if __name__ == "__main__":
    exit(main())

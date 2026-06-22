from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import asyncio
from datetime import datetime

from app.core.config import settings
from app.core.database import influx_db, redis_db
from app.core.message_bus import message_bus, CHANNELS
from app.api.sensor import router as sensor_router
from app.api.simulation import router as simulation_router
from app.api.analysis import router as analysis_router
from app.api.alert import router as alert_router
from app.api.comparison import router as comparison_router
from app.api.cargo import router as cargo_router
from app.api.driving import router as driving_router

from microservices.modbus_receiver import init_receiver_service
from microservices.walking_simulator import init_walking_service
from microservices.obstacle_analyzer import init_obstacle_service
from microservices.alarm_ws import init_alarm_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

_microservice_tasks = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _microservice_tasks
    logger.info(f"启动 {settings.app_name} 服务...")
    logger.info(f"环境: {settings.app_env}")
    logger.info(f"InfluxDB URL: {settings.influxdb_url}")
    logger.info(f"服务端口: {settings.app_port}")
    logger.info("开始初始化微服务...")

    receiver = await init_receiver_service(device_id='woodox_001', poll_interval=60.0)
    walking = await init_walking_service()
    obstacle = await init_obstacle_service()
    alarm = await init_alarm_service()

    logger.info("启动消息总线监听...")
    await message_bus.start_listening(list(CHANNELS.values()))

    logger.info("启动微服务后台任务...")
    _microservice_tasks = [
        asyncio.create_task(receiver.start_polling(), name="modbus_receiver"),
        asyncio.create_task(walking.start(), name="walking_simulator"),
        asyncio.create_task(obstacle.start(), name="obstacle_analyzer"),
        asyncio.create_task(alarm.start(), name="alarm_ws"),
    ]

    app.state.receiver_service = receiver
    app.state.walking_service = walking
    app.state.obstacle_service = obstacle
    app.state.alarm_service = alarm

    logger.info("所有微服务已启动完成")

    yield

    logger.info("正在关闭微服务...")
    for task in _microservice_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"关闭微服务异常: {e}")

    await message_bus.stop_listening()

    try:
        await receiver.stop()
    except Exception:
        pass
    try:
        await walking.stop()
    except Exception:
        pass
    try:
        await obstacle.stop()
    except Exception:
        pass
    try:
        await alarm.stop()
    except Exception:
        pass

    logger.info("正在关闭数据库连接...")
    influx_db.close()
    await redis_db.close()
    logger.info("服务已关闭")


app = FastAPI(
    title=settings.app_name,
    description="古代木牛流马行走机构仿真与越障能力分析系统 - API接口文档 (微服务架构版)",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensor_router)
app.include_router(simulation_router)
app.include_router(analysis_router)
app.include_router(alert_router)
app.include_router(comparison_router)
app.include_router(cargo_router)
app.include_router(driving_router)


@app.get("/", summary="根路径")
async def root():
    return {
        "name": settings.app_name,
        "version": "2.0.0",
        "architecture": "microservices",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/docs",
        "endpoints": {
            "sensors": "/api/sensors",
            "simulation": "/api/simulation",
            "analysis": "/api/analysis",
            "alerts": "/api/alerts",
            "comparison": "/api/comparison",
            "cargo": "/api/cargo",
            "driving": "/api/driving"
        },
        "microservices": [
            "modbus_receiver (数据采集校验)",
            "walking_simulator (多体动力学+步态计算)",
            "obstacle_analyzer (地形识别+越障评估)",
            "alarm_ws (告警推送+WebSocket)"
        ],
        "communication": "Redis Pub/Sub"
    }


@app.get("/health", summary="健康检查")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "architecture": "microservices",
        "services": {
            "influxdb": "connected" if influx_db.client else "disconnected",
            "redis": "connected" if redis_db.redis else "disconnected",
            "modbus_receiver": "running",
            "walking_simulator": "running",
            "obstacle_analyzer": "running",
            "alarm_ws": "running"
        }
    }


@app.get("/api/info", summary="系统信息")
async def get_system_info():
    return {
        "name": settings.app_name,
        "version": "2.0.0",
        "architecture": "microservices",
        "environment": settings.app_env,
        "features": [
            "Jansen连杆理论求解",
            "多体动力学仿真",
            "步态分析与优化",
            "地形识别与越障评估",
            "稳定性分析",
            "WebSocket实时告警",
            "Modbus RTU数据采集",
            "InfluxDB时序存储",
            "Redis Pub/Sub消息总线",
            "古代运输工具越障能力对比",
            "跨时代对比（古代木牛流马 vs 现代四足机器人）",
            "货箱装载位置稳定性分析",
            "虚拟驾驶体验（手柄/键盘/触屏控制）"
        ],
        "microservices": [
            {"name": "modbus_receiver", "description": "Modbus数据采集与校验", "channels": ["SENSOR_VALIDATED (pub)"]},
            {"name": "walking_simulator", "description": "多体动力学与步态计算", "channels": ["SENSOR_VALIDATED (sub)", "GAIT_RESULT (pub)", "DYNAMICS_RESULT (pub)"]},
            {"name": "obstacle_analyzer", "description": "地形识别与越障评估", "channels": ["SENSOR_VALIDATED (sub)", "TERRAIN_RESULT (pub)", "OBSTACLE_RESULT (pub)"]},
            {"name": "alarm_ws", "description": "告警检测与WebSocket推送", "channels": ["SENSOR_VALIDATED (sub)", "GAIT_RESULT (sub)", "OBSTACLE_RESULT (sub)", "TERRAIN_RESULT (sub)", "ALERT_TRIGGERED (pub)", "ALERT_CLEARED (pub)"]}
        ],
        "configuration_files": [
            "config/mechanism_params.json",
            "config/terrain_params.json"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development"
    )

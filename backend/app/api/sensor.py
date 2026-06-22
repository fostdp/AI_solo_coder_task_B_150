from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime, timedelta
from typing import Optional, List
import logging

from app.models.schemas import SensorData
from app.core.database import influx_db, redis_db
from app.services.data_processor import data_processor
from app.services.alert_service import alert_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sensors", tags=["传感器数据"])


@router.get("/realtime", response_model=SensorData, summary="获取实时传感器数据")
async def get_realtime_sensor_data(device_id: str = Query(..., description="设备ID")):
    cache_key = f"sensor:latest:{device_id}"
    cached = await redis_db.get_cache(cache_key)
    
    if cached:
        return SensorData(
            timestamp=datetime.fromisoformat(cached['timestamp']),
            device_id=device_id,
            crank_angle=cached['crank_angle'],
            leg_displacement=cached['leg_displacement'],
            body_inclination=cached['body_inclination'],
            ground_elevation=cached['ground_elevation']
        )
    
    latest = await influx_db.query_latest_sensor(device_id)
    if not latest:
        raise HTTPException(status_code=404, detail="未找到传感器数据")
    
    return latest


@router.get("/history", response_model=List[SensorData], summary="获取历史传感器数据")
async def get_sensor_history(
    device_id: str = Query(..., description="设备ID"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    limit: int = Query(1000, ge=1, le=10000, description="返回数量限制")
):
    if start_time is None:
        start_time = datetime.utcnow() - timedelta(hours=1)
    if end_time is None:
        end_time = datetime.utcnow()
    
    try:
        data = await influx_db.query_sensor_history(
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        return data
    except Exception as e:
        logger.error(f"查询历史数据失败: {e}")
        raise HTTPException(status_code=500, detail="查询历史数据失败")


@router.post("/ingest", summary="接收传感器数据")
async def ingest_sensor_data(data: SensorData):
    try:
        processed = await data_processor.process_sensor_data(data)
        
        alerts = await alert_service.check_alerts(data)
        
        return {
            "status": "success",
            "processed": processed,
            "alerts_triggered": len(alerts),
            "alerts": alerts
        }
    except Exception as e:
        logger.error(f"接收传感器数据失败: {e}")
        raise HTTPException(status_code=500, detail="数据处理失败")


@router.get("/statistics", summary="获取传感器数据统计")
async def get_sensor_statistics(
    device_id: str = Query(..., description="设备ID"),
    window_minutes: int = Query(5, ge=1, le=60, description="统计窗口(分钟)")
):
    stats = data_processor.get_statistics(device_id, window_minutes)
    if not stats:
        raise HTTPException(status_code=404, detail="无足够数据进行统计")
    return stats


@router.get("/derived", summary="获取派生指标")
async def get_derived_metrics(
    device_id: str = Query(..., description="设备ID"),
    count: int = Query(10, ge=1, le=100, description="数据点数")
):
    recent_data = data_processor.get_recent_data(device_id, count)
    if not recent_data:
        raise HTTPException(status_code=404, detail="无数据")
    
    metrics = []
    for data in recent_data:
        derived = data_processor._calculate_derived_metrics(data)
        metrics.append({
            "timestamp": data.timestamp.isoformat(),
            **derived
        })
    
    return metrics


@router.get("/quality", summary="获取数据质量评估")
async def get_data_quality(
    device_id: str = Query(..., description="设备ID")
):
    latest = await influx_db.query_latest_sensor(device_id)
    if not latest:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    quality = data_processor._assess_data_quality(latest)
    return {
        "timestamp": latest.timestamp.isoformat(),
        "device_id": device_id,
        "quality": quality
    }


@router.get("/trend", summary="获取数据趋势分析")
async def get_data_trend(
    device_id: str = Query(..., description="设备ID")
):
    trend = data_processor._calculate_trend(device_id)
    if not trend:
        raise HTTPException(status_code=404, detail="无足够数据进行趋势分析")
    return trend

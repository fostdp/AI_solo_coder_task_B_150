from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import json

from app.models.schemas import Alert, AlertType, AlertLevel
from app.services.alert_service import alert_service
from app.core.database import influx_db
from app.core.websocket import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["告警管理"])


@router.get("/current", response_model=List[Alert], summary="获取当前活动告警")
async def get_current_alerts(
    device_id: Optional[str] = Query(None, description="设备ID")
):
    return alert_service.get_active_alerts(device_id)


@router.get("/history", summary="获取告警历史")
async def get_alert_history(
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    alert_type: Optional[AlertType] = Query(None, description="告警类型"),
    device_id: Optional[str] = Query(None, description="设备ID"),
    acknowledged: Optional[bool] = Query(None, description="是否已确认"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制")
):
    try:
        db_alerts = await influx_db.query_alerts(
            start_time=start_time,
            end_time=end_time,
            alert_type=alert_type.value if alert_type else None,
            acknowledged=acknowledged,
            limit=limit
        )
        
        if device_id:
            db_alerts = [a for a in db_alerts if a.get('device_id') == device_id]
        
        return db_alerts
    except Exception as e:
        logger.error(f"查询告警历史失败: {e}")
        alerts = alert_service.get_alert_history(
            start_time=start_time,
            end_time=end_time,
            alert_type=alert_type,
            device_id=device_id,
            limit=limit
        )
        return [alert.model_dump() for alert in alerts]


@router.put("/{alert_id}/acknowledge", summary="确认告警")
async def acknowledge_alert(alert_id: str):
    success = await alert_service.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="告警不存在")
    return {"success": True, "message": "告警已确认"}


@router.post("/{device_id}/unsuppress", summary="取消告警抑制")
async def unsuppress_alerts(device_id: Optional[str] = None):
    await alert_service.unsuppress_alerts(device_id)
    return {"success": True, "message": "告警抑制已取消"}


@router.get("/statistics", summary="获取告警统计")
async def get_alert_statistics(
    hours: int = Query(24, ge=1, le=720, description="统计时长(小时)")
):
    stats = alert_service.get_alert_statistics(hours)
    
    for key in stats['by_type']:
        stats['by_type'][key] = int(stats['by_type'][key])
    for key in stats['by_level']:
        stats['by_level'][key] = int(stats['by_level'][key])
    for key in stats['by_device']:
        stats['by_device'][key] = int(stats['by_device'][key])
    
    return stats


@router.put("/threshold", summary="更新告警阈值")
async def update_alert_threshold(
    alert_type: AlertType = Query(..., description="告警类型"),
    threshold: float = Query(..., description="阈值")
):
    alert_service.update_threshold(alert_type, threshold)
    return {
        "success": True,
        "alert_type": alert_type.value,
        "new_threshold": threshold
    }


@router.put("/cooldown", summary="设置告警冷却时间")
async def set_alert_cooldown(
    cooldown_seconds: int = Query(..., ge=10, le=3600, description="冷却时间(秒)")
):
    alert_service.set_alert_cooldown(cooldown_seconds)
    return {
        "success": True,
        "cooldown_seconds": cooldown_seconds
    }


@router.websocket("/ws")
async def websocket_alerts(websocket: WebSocket, device_id: Optional[str] = None):
    await ws_manager.connect(websocket)
    try:
        if device_id:
            ws_manager.subscribe(websocket, device_id)
        
        active_alerts = alert_service.get_active_alerts(device_id)
        for alert in active_alerts:
            await ws_manager.broadcast_alert(alert)
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get('action')
                target_device = message.get('device_id')
                
                if action == 'subscribe' and target_device:
                    ws_manager.subscribe(websocket, target_device)
                elif action == 'unsubscribe' and target_device:
                    ws_manager.unsubscribe(websocket, target_device)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"告警WebSocket异常: {e}")
        ws_manager.disconnect(websocket)


@router.post("/test", summary="测试告警触发")
async def test_alert(
    device_id: str = Query(..., description="设备ID"),
    alert_type: AlertType = Query(..., description="告警类型"),
    level: AlertLevel = Query(AlertLevel.WARNING, description="告警级别")
):
    from app.models.schemas import SensorData
    import uuid
    
    test_data = SensorData(
        timestamp=datetime.utcnow(),
        device_id=device_id,
        crank_angle=180.0,
        leg_displacement=100.0,
        body_inclination=20.0,
        ground_elevation=0.0
    )
    
    messages = {
        AlertType.INCLINATION_EXCEEDED: "测试告警: 机身倾角超限",
        AlertType.MECHANISM_JAMMED: "测试告警: 机构卡死",
        AlertType.SENSOR_FAULT: "测试告警: 传感器故障"
    }
    
    alert = Alert(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        type=alert_type,
        level=level,
        message=messages.get(alert_type, "测试告警"),
        device_id=device_id,
        sensor_data=test_data
    )
    
    await alert_service._process_alert(alert)
    
    return {"success": True, "alert": alert.model_dump()}

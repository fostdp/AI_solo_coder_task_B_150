from fastapi import APIRouter, HTTPException, Body, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging
import json
import asyncio

from app.models.schemas import (
    DrivingControlInput,
    DrivingState,
    JansenParameters,
)
from app.services.driving_service import driving_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/driving", tags=["虚拟驾驶"])


@router.post("/control", response_model=DrivingState, summary="发送驾驶控制指令")
async def send_driving_control(control: DrivingControlInput = Body(...)):
    try:
        state = driving_service.apply_control(control.device_id, control)
        return state
    except Exception as e:
        logger.error(f"驾驶控制失败: {e}")
        raise HTTPException(status_code=500, detail=f"控制失败: {str(e)}")


@router.get("/state/{device_id}", response_model=DrivingState, summary="获取当前驾驶状态")
async def get_driving_state(device_id: str):
    try:
        state = driving_service.get_state(device_id)
        return state
    except Exception as e:
        logger.error(f"获取驾驶状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/reset/{device_id}", summary="重置驾驶状态")
async def reset_driving_state(device_id: str):
    try:
        driving_service.reset_device(device_id)
        state = driving_service.get_state(device_id)
        return {"message": "已重置", "state": state}
    except Exception as e:
        logger.error(f"重置驾驶状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置失败: {str(e)}")


@router.post("/params/{device_id}", summary="设置虚拟驾驶设备参数")
async def set_driving_params(device_id: str, params: JansenParameters = Body(...)):
    try:
        driving_service.set_device_parameters(device_id, params)
        return {"message": "参数已更新"}
    except Exception as e:
        logger.error(f"设置驾驶参数失败: {e}")
        raise HTTPException(status_code=500, detail=f"参数设置失败: {str(e)}")


@router.websocket("/ws/{device_id}")
async def driving_websocket(websocket: WebSocket, device_id: str):
    await websocket.accept()
    logger.info(f"虚拟驾驶WebSocket连接: {device_id}")

    try:
        async def physics_loop():
            while True:
                state = driving_service.update_physics(device_id, dt=0.016)
                await websocket.send_json({
                    "type": "state",
                    "payload": state.model_dump(mode='json')
                })
                await asyncio.sleep(0.016)

        physics_task = asyncio.create_task(physics_loop())

        while True:
            try:
                data = await websocket.receive_json()
                if isinstance(data, dict):
                    if data.get("type") == "control":
                        ctrl = DrivingControlInput(**data.get("payload", {}))
                        state = driving_service.apply_control(device_id, ctrl)
                    elif data.get("type") == "reset":
                        driving_service.reset_device(device_id)
                    elif data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"驾驶WebSocket消息处理异常: {e}")

    except WebSocketDisconnect:
        logger.info(f"虚拟驾驶WebSocket断开: {device_id}")
    except Exception as e:
        logger.error(f"虚拟驾驶WebSocket异常: {e}")
    finally:
        try:
            physics_task.cancel()
        except Exception:
            pass

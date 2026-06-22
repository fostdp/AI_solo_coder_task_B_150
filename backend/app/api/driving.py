import asyncio
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models.schemas import DrivingControlInput, JansenParameters
from app.services.driving_service import driving_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/driving", tags=["虚拟驾驶"])


@router.post("/control", summary="发送驾驶控制指令")
async def apply_control(device_id: str, control: DrivingControlInput):
    try:
        state = driving_service.apply_control(device_id, control)
        return state
    except Exception as e:
        logger.error(f"驾驶控制失败: {e}")
        raise HTTPException(status_code=500, detail=f"控制失败: {str(e)}")


@router.get("/state/{device_id}", summary="获取设备驾驶状态")
async def get_driving_state(device_id: str):
    try:
        state = driving_service.get_state(device_id)
        return state
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/reset/{device_id}", summary="重置设备驾驶状态")
async def reset_device(device_id: str):
    try:
        driving_service.reset_device(device_id)
        state = driving_service.get_state(device_id)
        return state
    except Exception as e:
        logger.error(f"重置失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置失败: {str(e)}")


@router.post("/params/{device_id}", summary="设置设备参数")
async def set_device_parameters(device_id: str, params: JansenParameters):
    try:
        driving_service.set_device_parameters(device_id, params)
        state = driving_service.get_state(device_id)
        return state
    except Exception as e:
        logger.error(f"设置参数失败: {e}")
        raise HTTPException(status_code=500, detail=f"设置参数失败: {str(e)}")


@router.websocket("/ws/{device_id}")
async def driving_websocket(websocket: WebSocket, device_id: str):
    await websocket.accept()
    driving_service._ensure_device(device_id)

    async def physics_loop():
        dt = 1.0 / 60.0
        while True:
            try:
                state = driving_service.update_physics(device_id, dt)
                await websocket.send_json({
                    'type': 'state_update',
                    'data': state.model_dump() if hasattr(state, 'model_dump') else {},
                })
                await asyncio.sleep(dt)
            except Exception:
                break

    physics_task = asyncio.create_task(physics_loop())

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('type', '')

            if msg_type == 'control':
                control_data = data.get('control', {})
                control = DrivingControlInput(**control_data)
                driving_service.apply_control(device_id, control)
            elif msg_type == 'reset':
                driving_service.reset_device(device_id)
            elif msg_type == 'params':
                params_data = data.get('params', {})
                params = JansenParameters(**params_data)
                driving_service.set_device_parameters(device_id, params)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
    finally:
        physics_task.cancel()
        try:
            await physics_task
        except asyncio.CancelledError:
            pass

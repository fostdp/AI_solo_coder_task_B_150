from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import logging
from datetime import datetime

from app.models.schemas import WebSocketMessage, SensorData, Alert

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.device_subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.device_subscriptions[websocket] = set()
        logger.info(f"WebSocket连接建立: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.device_subscriptions:
            del self.device_subscriptions[websocket]
        for device_id, connections in self.active_connections.items():
            if websocket in connections:
                connections.remove(websocket)
        logger.info(f"WebSocket连接断开: {websocket.client}")

    def subscribe(self, websocket: WebSocket, device_id: str):
        if device_id not in self.active_connections:
            self.active_connections[device_id] = []
        if websocket not in self.active_connections[device_id]:
            self.active_connections[device_id].append(websocket)
        if websocket in self.device_subscriptions:
            self.device_subscriptions[websocket].add(device_id)
        logger.info(f"客户端订阅设备: {device_id}")

    def unsubscribe(self, websocket: WebSocket, device_id: str):
        if device_id in self.active_connections:
            if websocket in self.active_connections[device_id]:
                self.active_connections[device_id].remove(websocket)
        if websocket in self.device_subscriptions:
            self.device_subscriptions[websocket].discard(device_id)
        logger.info(f"客户端取消订阅设备: {device_id}")

    async def broadcast_to_device(
        self,
        device_id: str,
        message_type: str,
        payload: dict
    ):
        message = WebSocketMessage(
            type=message_type,
            payload=payload
        )
        message_json = message.model_dump_json()
        
        if device_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[device_id]:
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.warning(f"发送消息失败: {e}")
                    disconnected.append(connection)
            
            for conn in disconnected:
                self.disconnect(conn)

    async def broadcast_sensor_data(self, data: SensorData):
        payload = {
            "timestamp": data.timestamp.isoformat(),
            "device_id": data.device_id,
            "crank_angle": data.crank_angle,
            "leg_displacement": data.leg_displacement,
            "body_inclination": data.body_inclination,
            "ground_elevation": data.ground_elevation
        }
        await self.broadcast_to_device(data.device_id, "SENSOR_DATA", payload)

    async def broadcast_alert(self, alert: Alert):
        payload = {
            "id": alert.id,
            "timestamp": alert.timestamp.isoformat(),
            "type": alert.type.value,
            "level": alert.level.value,
            "message": alert.message,
            "device_id": alert.device_id,
            "sensor_data": alert.sensor_data.model_dump(),
            "acknowledged": alert.acknowledged
        }
        await self.broadcast_to_device(alert.device_id, "ALERT", payload)

    async def broadcast_simulation_result(self, device_id: str, result: dict):
        await self.broadcast_to_device(device_id, "SIMULATION_RESULT", result)


ws_manager = ConnectionManager()

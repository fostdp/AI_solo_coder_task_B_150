import json
import asyncio
import logging
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
import uuid

from app.core.database import redis_db

logger = logging.getLogger(__name__)


CHANNELS = {
    'SENSOR_RAW': 'sensor:raw',
    'SENSOR_VALIDATED': 'sensor:validated',
    'GAIT_RESULT': 'simulation:gait',
    'DYNAMICS_RESULT': 'simulation:dynamics',
    'TERRAIN_RESULT': 'analysis:terrain',
    'OBSTACLE_RESULT': 'analysis:obstacle',
    'ALERT_TRIGGERED': 'alert:triggered',
    'ALERT_CLEARED': 'alert:cleared',
    'CONFIG_UPDATED': 'system:config',
    'COMMAND': 'system:command',
    'BROADCAST': 'system:broadcast'
}


@dataclass
class Message:
    type: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ''
    correlation_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        data = json.loads(json_str)
        return cls(**data)


class MessageBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._pubsub = None
        self._listen_task = None
        self._running = False

    async def publish(self, channel: str, message: Message) -> bool:
        try:
            message_json = message.to_json()
            await redis_db.publish(channel, message_json)
            logger.debug(f"消息发布成功: channel={channel}, type={message.type}, id={message.message_id}")

            if channel in self._subscribers:
                for callback in self._subscribers[channel]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(message)
                        else:
                            callback(message)
                    except Exception as e:
                        logger.error(f"本地回调执行失败: {e}")

            return True
        except Exception as e:
            logger.error(f"消息发布失败: channel={channel}, error={e}")
            return False

    def subscribe(self, channel: str, callback: Callable):
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(callback)
        logger.info(f"订阅成功: channel={channel}, callback={callback.__name__}")

    async def start_listening(self, channels: List[str]):
        if self._running:
            return

        self._running = True
        try:
            self._pubsub = await redis_db.get_pubsub()
            await self._pubsub.subscribe(*channels)

            logger.info(f"开始监听Redis频道: {channels}")

            self._listen_task = asyncio.create_task(self._listen_loop())
        except Exception as e:
            logger.error(f"启动消息监听失败: {e}")
            self._running = False

    async def _listen_loop(self):
        try:
            async for message in self._pubsub.listen():
                if message['type'] == 'message':
                    try:
                        channel = message['channel'].decode() if isinstance(message['channel'], bytes) else message['channel']
                        data = message['data'].decode() if isinstance(message['data'], bytes) else message['data']

                        msg = Message.from_json(data)

                        if channel in self._subscribers:
                            for callback in self._subscribers[channel]:
                                try:
                                    if asyncio.iscoroutinefunction(callback):
                                        await callback(msg)
                                    else:
                                        callback(msg)
                                except Exception as e:
                                    logger.error(f"回调处理失败: channel={channel}, error={e}")

                    except json.JSONDecodeError as e:
                        logger.error(f"消息解析失败: {e}")
                    except Exception as e:
                        logger.error(f"消息处理失败: {e}")
        except asyncio.CancelledError:
            logger.info("消息监听已取消")
        except Exception as e:
            logger.error(f"监听循环异常: {e}")
        finally:
            self._running = False

    async def stop_listening(self):
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        logger.info("消息监听已停止")


message_bus = MessageBus()


async def publish_sensor_validated(payload: Dict[str, Any], source: str = 'modbus_receiver') -> bool:
    msg = Message(
        type='SENSOR_VALIDATED',
        payload=payload,
        source=source
    )
    return await message_bus.publish(CHANNELS['SENSOR_VALIDATED'], msg)


async def publish_gait_result(payload: Dict[str, Any], correlation_id: Optional[str] = None) -> bool:
    msg = Message(
        type='GAIT_RESULT',
        payload=payload,
        source='walking_simulator',
        correlation_id=correlation_id
    )
    return await message_bus.publish(CHANNELS['GAIT_RESULT'], msg)


async def publish_dynamics_result(payload: Dict[str, Any], correlation_id: Optional[str] = None) -> bool:
    msg = Message(
        type='DYNAMICS_RESULT',
        payload=payload,
        source='walking_simulator',
        correlation_id=correlation_id
    )
    return await message_bus.publish(CHANNELS['DYNAMICS_RESULT'], msg)


async def publish_terrain_result(payload: Dict[str, Any], correlation_id: Optional[str] = None) -> bool:
    msg = Message(
        type='TERRAIN_RESULT',
        payload=payload,
        source='obstacle_analyzer',
        correlation_id=correlation_id
    )
    return await message_bus.publish(CHANNELS['TERRAIN_RESULT'], msg)


async def publish_obstacle_result(payload: Dict[str, Any], correlation_id: Optional[str] = None) -> bool:
    msg = Message(
        type='OBSTACLE_RESULT',
        payload=payload,
        source='obstacle_analyzer',
        correlation_id=correlation_id
    )
    return await message_bus.publish(CHANNELS['OBSTACLE_RESULT'], msg)


async def publish_alert_triggered(payload: Dict[str, Any], source: str = 'alarm_ws') -> bool:
    msg = Message(
        type='ALERT_TRIGGERED',
        payload=payload,
        source=source
    )
    return await message_bus.publish(CHANNELS['ALERT_TRIGGERED'], msg)


async def publish_alert_cleared(alert_id: str, source: str = 'alarm_ws') -> bool:
    msg = Message(
        type='ALERT_CLEARED',
        payload={'alert_id': alert_id},
        source=source
    )
    return await message_bus.publish(CHANNELS['ALERT_CLEARED'], msg)

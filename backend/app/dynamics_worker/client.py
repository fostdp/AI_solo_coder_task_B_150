import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from app.core.config import settings
from app.simulation.multibody_dynamics import MultibodyDynamics
from app.models.schemas import (
    JansenParameters,
    Point3D,
    Point2D,
)
from .messages import (
    DYNAMICS_REQUEST_CHANNEL,
    DynamicsRequest,
    DynamicsResponse,
    serialize_point,
    deserialize_point,
)

logger = logging.getLogger(__name__)


class DynamicsWorkerClient:
    def __init__(
        self,
        params: JansenParameters,
        redis_url: Optional[str] = None,
        timeout: float = 30.0,
        use_fallback: bool = True
    ):
        self.params = params
        self.redis_url = redis_url or settings.redis_url
        self.timeout = timeout
        self.use_fallback = use_fallback
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self._connected = False
        self._local_dynamics: Optional[MultibodyDynamics] = None
        self._response_channels: set[str] = set()

    async def connect(self) -> bool:
        if self._connected:
            return True

        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            self.pubsub = self.redis_client.pubsub()
            self._connected = True
            logger.info("DynamicsWorkerClient connected to Redis successfully")
            return True
        except Exception as e:
            logger.warning(f"DynamicsWorkerClient failed to connect to Redis: {e}")
            if self.use_fallback:
                logger.info("Falling back to local MultibodyDynamics computation")
                self._local_dynamics = MultibodyDynamics(self.params)
            self._connected = False
            return False

    async def _ensure_connected(self) -> bool:
        if self._connected:
            return True
        return await self.connect()

    def _get_local_dynamics(self) -> MultibodyDynamics:
        if self._local_dynamics is None:
            self._local_dynamics = MultibodyDynamics(self.params)
        return self._local_dynamics

    async def _send_request(
        self,
        method: str,
        **kwargs: Any
    ) -> Any:
        if not await self._ensure_connected():
            if self.use_fallback:
                return await asyncio.to_thread(
                    self._call_local_method,
                    method,
                    **kwargs
                )
            raise RuntimeError("Redis not available and fallback disabled")

        request_id = str(uuid.uuid4())
        response_channel = f'dynamics:response:{request_id}'

        params = serialize_point(kwargs)
        params['params'] = self.params.model_dump()

        request = DynamicsRequest(
            id=request_id,
            method=method,
            params=params
        )

        try:
            await self.pubsub.subscribe(response_channel)
            self._response_channels.add(response_channel)

            await self.redis_client.publish(
                DYNAMICS_REQUEST_CHANNEL,
                request.to_json()
            )

            response = await asyncio.wait_for(
                self._wait_for_response(response_channel),
                timeout=self.timeout
            )

            if response.error:
                raise RuntimeError(f"Worker error: {response.error}")

            return deserialize_point(response.result)

        except asyncio.TimeoutError:
            logger.warning(f"Request {request_id} timed out after {self.timeout}s")
            if self.use_fallback:
                logger.info("Falling back to local computation after timeout")
                return await asyncio.to_thread(
                    self._call_local_method,
                    method,
                    **kwargs
                )
            raise
        finally:
            if response_channel in self._response_channels:
                try:
                    await self.pubsub.unsubscribe(response_channel)
                except Exception:
                    pass
                self._response_channels.discard(response_channel)

    async def _wait_for_response(self, channel: str) -> DynamicsResponse:
        try:
            async for message in self.pubsub.listen():
                if message['type'] != 'message':
                    continue

                msg_channel = message['channel']
                if isinstance(msg_channel, bytes):
                    msg_channel = msg_channel.decode('utf-8')

                if msg_channel != channel:
                    continue

                data = message['data']
                if isinstance(data, bytes):
                    data = data.decode('utf-8')

                return DynamicsResponse.from_json(data)
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Error waiting for response: {e}")
            raise

    def _call_local_method(self, method: str, **kwargs: Any) -> Any:
        dynamics = self._get_local_dynamics()
        method_func = getattr(dynamics, method)
        return method_func(**kwargs)

    async def calculate_link_centers_of_mass(
        self,
        joints: Dict[str, Point3D],
        payload_mass: Optional[float] = None,
        payload_offset: Optional[Point3D] = None
    ) -> Dict[str, Point3D]:
        return await self._send_request(
            'calculate_link_centers_of_mass',
            joints=joints,
            payload_mass=payload_mass,
            payload_offset=payload_offset
        )

    async def calculate_total_center_of_mass(
        self,
        com_positions: Dict[str, Point3D],
        body_inclination: float = 0.0
    ) -> Point3D:
        return await self._send_request(
            'calculate_total_center_of_mass',
            com_positions=com_positions,
            body_inclination=body_inclination
        )

    async def calculate_joint_forces(
        self,
        joints: Dict[str, Point3D],
        com_positions: Dict[str, Point3D],
        body_inclination: float = 0.0,
        ground_reaction: Optional[Point3D] = None
    ) -> Dict[str, Point3D]:
        return await self._send_request(
            'calculate_joint_forces',
            joints=joints,
            com_positions=com_positions,
            body_inclination=body_inclination,
            ground_reaction=ground_reaction
        )

    async def calculate_zero_moment_point(
        self,
        com: Point3D,
        forces: Dict[str, Point3D],
        joints: Dict[str, Point3D],
        body_inclination: float = 0.0
    ) -> Point2D:
        return await self._send_request(
            'calculate_zero_moment_point',
            com=com,
            forces=forces,
            joints=joints,
            body_inclination=body_inclination
        )

    async def calculate_support_polygon(
        self,
        joints: Dict[str, Point3D],
        num_legs: int = 4,
        spacing: float = 200.0
    ) -> List[Point2D]:
        return await self._send_request(
            'calculate_support_polygon',
            joints=joints,
            num_legs=num_legs,
            spacing=spacing
        )

    async def calculate_stability_margin(
        self,
        zmp: Point2D,
        support_polygon: List[Point2D]
    ) -> float:
        return await self._send_request(
            'calculate_stability_margin',
            zmp=zmp,
            support_polygon=support_polygon
        )

    async def calculate_joint_torques(
        self,
        crank_angle: float,
        body_inclination: float = 0.0,
        external_load: float = 0.0
    ) -> Dict[str, float]:
        return await self._send_request(
            'calculate_joint_torques',
            crank_angle=crank_angle,
            body_inclination=body_inclination,
            external_load=external_load
        )

    async def simulate_gait_cycle(
        self,
        start_angle: float = 0.0,
        end_angle: float = 360.0,
        num_steps: int = 360,
        body_inclination: float = 0.0
    ) -> Dict[str, List]:
        return await self._send_request(
            'simulate_gait_cycle',
            start_angle=start_angle,
            end_angle=end_angle,
            num_steps=num_steps,
            body_inclination=body_inclination
        )

    async def close(self) -> None:
        for channel in list(self._response_channels):
            try:
                await self.pubsub.unsubscribe(channel)
            except Exception:
                pass
        self._response_channels.clear()

        if self.pubsub:
            try:
                await self.pubsub.close()
            except Exception as e:
                logger.error(f"Error closing pubsub: {e}")

        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.error(f"Error closing redis client: {e}")

        self._connected = False
        logger.info("DynamicsWorkerClient closed")

    async def __aenter__(self) -> 'DynamicsWorkerClient':
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

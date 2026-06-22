import asyncio
import json
import logging
import signal
import sys
import os
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import redis.asyncio as redis

from app.core.config import settings
from app.simulation.multibody_dynamics import MultibodyDynamics
from app.models.schemas import JansenParameters
from .messages import (
    DYNAMICS_REQUEST_CHANNEL,
    DynamicsRequest,
    DynamicsResponse,
    serialize_point,
    deserialize_params,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


SUPPORTED_METHODS = {
    'calculate_link_centers_of_mass',
    'calculate_total_center_of_mass',
    'calculate_joint_forces',
    'calculate_zero_moment_point',
    'calculate_support_polygon',
    'calculate_stability_margin',
    'calculate_joint_torques',
    'simulate_gait_cycle',
}


class DynamicsWorker:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.running = False
        self.dynamics_instances: Dict[str, MultibodyDynamics] = {}
        self._tasks: set[asyncio.Task] = set()

    async def connect(self) -> bool:
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            self.pubsub = self.redis_client.pubsub()
            logger.info("DynamicsWorker connected to Redis successfully")
            return True
        except Exception as e:
            logger.error(f"DynamicsWorker failed to connect to Redis: {e}")
            return False

    def _get_dynamics(self, params: Dict[str, Any]) -> MultibodyDynamics:
        params_key = json.dumps(params, sort_keys=True)
        if params_key not in self.dynamics_instances:
            jansen_params = JansenParameters(**params)
            self.dynamics_instances[params_key] = MultibodyDynamics(jansen_params)
        return self.dynamics_instances[params_key]

    def _process_method(self, method: str, params: Dict[str, Any]) -> Any:
        if method not in SUPPORTED_METHODS:
            raise ValueError(f"Unsupported method: {method}")

        dynamics_params = params.pop('params', {})
        dynamics = self._get_dynamics(dynamics_params)

        deserialized_params = deserialize_params(params)

        method_func = getattr(dynamics, method)
        result = method_func(**deserialized_params)

        return serialize_point(result)

    async def _handle_request(self, message: Dict[str, Any]) -> None:
        try:
            if message['type'] != 'message':
                return

            data = message['data']
            if isinstance(data, bytes):
                data = data.decode('utf-8')

            request = DynamicsRequest.from_json(data)
            logger.info(f"Received request: id={request.id}, method={request.method}")

            try:
                result = await asyncio.to_thread(
                    self._process_method,
                    request.method,
                    request.params
                )
                response = DynamicsResponse(id=request.id, result=result)
            except Exception as e:
                logger.error(f"Error processing request {request.id}: {e}", exc_info=True)
                response = DynamicsResponse(id=request.id, error=str(e))

            response_channel = request.response_channel()
            await self.redis_client.publish(response_channel, response.to_json())
            logger.info(f"Sent response: id={request.id}, channel={response_channel}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode request: {e}")
        except Exception as e:
            logger.error(f"Unexpected error handling request: {e}", exc_info=True)

    async def _listen_loop(self) -> None:
        logger.info(f"Starting dynamics worker, listening on channel: {DYNAMICS_REQUEST_CHANNEL}")

        await self.pubsub.subscribe(DYNAMICS_REQUEST_CHANNEL)

        try:
            async for message in self.pubsub.listen():
                if not self.running:
                    break
                task = asyncio.create_task(self._handle_request(message))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        except asyncio.CancelledError:
            logger.info("Listen loop cancelled")
        except Exception as e:
            logger.error(f"Listen loop error: {e}", exc_info=True)

    async def start(self) -> None:
        if not await self.connect():
            raise RuntimeError("Failed to connect to Redis")

        self.running = True

        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.stop())
            )

        await self._listen_loop()

    async def stop(self) -> None:
        logger.info("Stopping dynamics worker...")
        self.running = False

        if self.pubsub:
            try:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()
            except Exception as e:
                logger.error(f"Error closing pubsub: {e}")

        for task in list(self._tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.error(f"Error closing redis client: {e}")

        logger.info("Dynamics worker stopped")


async def start_dynamics_worker(redis_url: Optional[str] = None) -> None:
    worker = DynamicsWorker(redis_url)
    await worker.start()


async def stop_dynamics_worker(worker: DynamicsWorker) -> None:
    await worker.stop()


def main() -> None:
    try:
        asyncio.run(start_dynamics_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

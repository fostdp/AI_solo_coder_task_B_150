import os
import sys
import json
import logging
import time
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    import paho.mqtt.client as mqtt
    import aiohttp
    import asyncio
except ImportError as e:
    print(f"缺少依赖: {e}. 请 pip install paho-mqtt aiohttp")
    raise

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger('mqtt_bridge')


class MQTTBridge:
    def __init__(
        self,
        mqtt_broker: str = None,
        mqtt_port: int = None,
        mqtt_topic: str = None,
        api_url: str = None,
        username: str = None,
        password: str = None,
        client_id: str = None,
    ):
        self.mqtt_broker = mqtt_broker or os.getenv('MQTT_BROKER', 'localhost')
        self.mqtt_port = mqtt_port or int(os.getenv('MQTT_PORT', '1883'))
        self.mqtt_topic = mqtt_topic or os.getenv('MQTT_TOPIC', 'woodox/sensor/#')
        self.api_url = api_url or os.getenv('API_URL', 'http://localhost:8000')
        self.username = username or os.getenv('MQTT_USERNAME')
        self.password = password or os.getenv('MQTT_PASSWORD')
        self.client_id = client_id or f"mqtt_bridge_{int(time.time())}"

        self.client: Optional[mqtt.Client] = None
        self.running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        logger.info(
            f"MQTT桥接初始化: broker={self.mqtt_broker}:{self.mqtt_port}, "
            f"topic={self.mqtt_topic}, api={self.api_url}"
        )

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"已连接MQTT Broker, 订阅主题: {self.mqtt_topic}")
            client.subscribe(self.mqtt_topic, qos=1)
        else:
            logger.error(f"MQTT连接失败, rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"MQTT连接断开, rc={rc}, 尝试重连...")

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode('utf-8')
            payload = json.loads(payload_str)
            logger.debug(f"收到MQTT消息: {msg.topic} -> {payload.get('device_id', 'unknown')}")

            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._forward_to_api(payload),
                    self._loop
                )
        except json.JSONDecodeError as e:
            logger.warning(f"消息JSON解析失败: {e}, payload={msg.payload[:200]}")
        except Exception as e:
            logger.error(f"处理MQTT消息错误: {e}")

    async def _forward_to_api(self, payload: Dict[str, Any]):
        try:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=10)
                self._session = aiohttp.ClientSession(timeout=timeout)

            url = f"{self.api_url}/api/sensors/ingest"
            async with self._session.post(url, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.debug(
                        f"API转发成功: device={payload.get('device_id')}, "
                        f"alerts={result.get('alerts_triggered', 0)}"
                    )
                else:
                    resp_text = await resp.text()
                    logger.warning(f"API返回错误: status={resp.status}, body={resp_text[:200]}")
        except aiohttp.ClientError as e:
            logger.warning(f"API连接失败: {e}")
        except Exception as e:
            logger.error(f"API转发异常: {e}")

    def start(self):
        self.client = mqtt.Client(client_id=self.client_id, clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

        try:
            self.client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
        except Exception as e:
            logger.error(f"MQTT连接异常: {e}, 将在后台重试")

        self.running = True

        async def _runner():
            self._loop = asyncio.get_running_loop()
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
            try:
                while self.running:
                    self.client.loop(timeout=1.0)
                    await asyncio.sleep(0.01)
            finally:
                if self._session:
                    await self._session.close()
                self.client.disconnect()
                logger.info("MQTT桥接已停止")

        logger.info("MQTT桥接已启动")
        asyncio.run(_runner())

    def stop(self):
        self.running = False
        logger.info("正在停止MQTT桥接...")


def main():
    bridge = MQTTBridge()
    try:
        bridge.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
        bridge.stop()


if __name__ == '__main__':
    main()

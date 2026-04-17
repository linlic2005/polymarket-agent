"""
Polymarket WebSocket 订阅器。
"""

import asyncio
import json
import logging
from typing import Any

import websockets

logger = logging.getLogger(__name__)

POLYMARKET_WS_URL = "wss://ws-subscriptions.clob.polymarket.com"
CHANNELS = ["market", "user"]


class WebsocketSubscriber:
    """Polymarket WebSocket 订阅器，监听订单状态及市场 spread 变化。"""

    def __init__(self) -> None:
        self.connected = False
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._listen_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """建立 WebSocket 连接。"""
        if self.connected:
            logger.warning("[WebSocket] Already connected, skipping connect.")
            return
        try:
            self._ws = await websockets.connect(POLYMARKET_WS_URL)
            self.connected = True
            logger.info("[WebSocket] Connected to %s", POLYMARKET_WS_URL)
        except Exception as e:
            logger.error("[WebSocket] Connection failed: %s", e)
            self.connected = False
            raise

    async def start(self) -> None:
        """建立连接并开始订阅 channels。"""
        await self.connect()
        if self.connected and self._ws:
            for channel in CHANNELS:
                subscribe_msg = json.dumps({"type": "subscribe", "channel": channel})
                await self._ws.send(subscribe_msg)
                logger.info("[WebSocket] Sent subscribe request for channel: %s", channel)

    async def listen(self) -> None:
        """启动异步消息循环。"""
        if not self.connected or self._ws is None:
            logger.error("[WebSocket] Not connected, cannot start listening.")
            return
        self._listen_task = asyncio.create_task(self._listen_async())

    async def _listen_async(self) -> None:
        """异步消息处理循环。"""
        try:
            async for raw_message in self._ws:
                try:
                    message = json.loads(raw_message)
                    channel = message.get("channel", "unknown")
                    logger.info("[WebSocket] Message channel=%s: %s", channel, message)
                except json.JSONDecodeError:
                    logger.warning("[WebSocket] Failed to decode message: %s", raw_message)
        except websockets.ConnectionClosed as e:
            logger.warning("[WebSocket] Connection closed: code=%s reason=%s", e.code, e.reason)
            self.connected = False

    async def disconnect(self) -> None:
        """关闭 WebSocket 连接。"""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        if self._ws:
            try:
                await self._ws.close()
                logger.info("[WebSocket] WebSocket closed.")
            except Exception as e:
                logger.warning("[WebSocket] Error during close: %s", e)
        self.connected = False
        logger.info("[WebSocket] Disconnected.")

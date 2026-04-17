"""
Polymarket WebSocket 订阅器。
"""

import logging

logger = logging.getLogger(__name__)

class WebsocketSubscriber:
    """预留的 Websocket 监听器，用于订阅订单状态及市场 spread 变化。"""

    def __init__(self) -> None:
         self.connected = False

    async def connect(self) -> None:
         logger.info("[WebSocket] Connected to market feeds.")
         self.connected = True
         
    async def listen(self) -> None:
         """持续监听事件循环（预留）。"""
         pass
         
    async def disconnect(self) -> None:
         logger.info("[WebSocket] Disconnected.")
         self.connected = False

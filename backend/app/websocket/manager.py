from fastapi import WebSocket
from typing import Dict, Set
import json
import asyncio


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # channel -> connections
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str = "global"):
        await websocket.accept()
        async with self._lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)

    async def disconnect(self, websocket: WebSocket, channel: str = "global"):
        async with self._lock:
            if channel in self.active_connections:
                self.active_connections[channel].discard(websocket)

    async def broadcast(self, message: dict, channel: str = "global"):
        """특정 채널의 모든 클라이언트에게 메시지 전송"""
        if channel not in self.active_connections:
            return

        dead_connections = set()
        for websocket in self.active_connections.get(channel, set()).copy():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                dead_connections.add(websocket)

        # 끊어진 연결 정리
        async with self._lock:
            for ws in dead_connections:
                self.active_connections.get(channel, set()).discard(ws)

    async def broadcast_json(self, message: dict, channel: str = "global"):
        """broadcast의 alias — JSON dict 전송"""
        await self.broadcast(message, channel)

    async def broadcast_all(self, message: dict):
        """모든 채널에 브로드캐스트"""
        for channel in list(self.active_connections.keys()):
            await self.broadcast(message, channel)


ws_manager = ConnectionManager()

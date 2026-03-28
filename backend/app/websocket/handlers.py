from fastapi import WebSocket, WebSocketDisconnect
from app.websocket.manager import ws_manager
import logging

logger = logging.getLogger(__name__)


async def handle_websocket(websocket: WebSocket, channel: str = "global"):
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            # 클라이언트로부터 구독 요청 처리 (향후 확장)
            logger.debug(f"WS 메시지 수신: {data}")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        await ws_manager.disconnect(websocket, channel)

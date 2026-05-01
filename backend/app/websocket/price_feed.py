import asyncio
import json
import logging
from datetime import datetime, timezone
import websockets

from app.config import settings
from app.core.redis_client import get_redis
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

BINANCE_WS_BASE = (
    "wss://stream.testnet.binance.vision"
    if settings.USE_TESTNET
    else "wss://stream.binance.com:9443"
)

# 구독할 심볼 목록 (운영 중에는 DB에서 동적으로 로드)
DEFAULT_SYMBOLS = ["btcusdt", "ethusdt"]


class BinancePriceFeed:
    def __init__(self, symbols: list[str] = None):
        self.symbols = [s.lower() for s in (symbols or DEFAULT_SYMBOLS)]
        self._running = False
        self._task = None

    def _build_stream_url(self) -> str:
        streams = "/".join([f"{s}@miniTicker" for s in self.symbols])
        return f"{BINANCE_WS_BASE}/stream?streams={streams}"

    async def _process_message(self, raw: str):
        try:
            data = json.loads(raw)
            stream_data = data.get("data", data)

            symbol = stream_data.get("s", "").upper()
            price = float(stream_data.get("c", 0))
            change_24h = float(stream_data.get("P", 0))
            volume_24h = float(stream_data.get("v", 0))

            if not symbol or not price:
                return

            # Redis 캐싱
            redis = await get_redis()
            cache_key = f"price:{settings.EXCHANGE_ID}:{symbol}"
            await redis.setex(cache_key, 10, str(price))

            # WebSocket 클라이언트에 브로드캐스트
            message = {
                "type": "price_update",
                "symbol": symbol,
                "price": price,
                "change_24h": change_24h,
                "volume_24h": volume_24h,
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
            await ws_manager.broadcast_all(message)

        except Exception as e:
            logger.error(f"가격 데이터 처리 오류: {e}")

    async def start(self):
        self._running = True
        url = self._build_stream_url()
        logger.info(f"바이낸스 WebSocket 연결: {url}")

        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("바이낸스 WebSocket 연결 성공")
                    async for message in ws:
                        if not self._running:
                            break
                        await self._process_message(message)
            except Exception as e:
                if self._running:
                    logger.warning(f"WebSocket 연결 끊김: {e}. 5초 후 재연결...")
                    await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()


price_feed = BinancePriceFeed()

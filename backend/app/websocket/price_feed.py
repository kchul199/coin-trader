import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import websockets

from app.config import settings
from app.core.redis_client import get_redis
from app.exchange.symbols import (
    get_default_symbols,
    normalize_symbol,
    to_compact_symbol,
    to_upbit_market_code,
)
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

BINANCE_WS_BASE = (
    "wss://stream.testnet.binance.vision"
    if settings.USE_TESTNET
    else "wss://stream.binance.com:9443"
)
UPBIT_WS_BASE = "wss://api.upbit.com/websocket/v1"


class ExchangePriceFeed:
    def __init__(self, symbols: list[str] | None = None):
        base_symbols = symbols or get_default_symbols(
            settings.EXCHANGE_ID,
            settings.QUOTE_CURRENCY,
        )
        self.symbols = [
            normalize_symbol(symbol, settings.QUOTE_CURRENCY)
            for symbol in base_symbols
        ]
        self._running = False
        self._task = None

    async def _cache_and_broadcast(
        self,
        symbol: str,
        price: float,
        change_24h: float,
        volume_24h: float,
    ):
        if not symbol or not price:
            return

        compact_symbol = to_compact_symbol(symbol, settings.QUOTE_CURRENCY)

        redis = await get_redis()
        cache_key = f"price:{settings.EXCHANGE_ID}:{compact_symbol}"
        await redis.setex(cache_key, 10, str(price))

        await ws_manager.broadcast_all({
            "type": "price_update",
            "symbol": compact_symbol,
            "price": price,
            "change_24h": change_24h,
            "volume_24h": volume_24h,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        })

        await self._dispatch_position_watch(symbol, compact_symbol)

    async def _dispatch_position_watch(self, symbol: str, compact_symbol: str) -> None:
        throttle_seconds = max(1, int(getattr(settings, "POSITION_WATCH_EVENT_THROTTLE_SECONDS", 1)))
        redis = await get_redis()
        trigger_key = f"watch:event:{settings.EXCHANGE_ID}:{compact_symbol}"
        acquired = await redis.set(trigger_key, "1", nx=True, ex=throttle_seconds)
        if not acquired:
            return

        try:
            from app.tasks.trading_tasks import watch_symbol_positions_task

            watch_symbol_positions_task.apply_async(
                args=[symbol],
                queue="trading_priority",
            )
        except Exception as exc:
            logger.warning("실시간 포지션 감시 디스패치 실패: symbol=%s error=%s", symbol, exc)

    def _build_binance_stream_url(self) -> str:
        streams = "/".join(
            f"{to_compact_symbol(symbol, settings.QUOTE_CURRENCY).lower()}@miniTicker"
            for symbol in self.symbols
        )
        return f"{BINANCE_WS_BASE}/stream?streams={streams}"

    def _build_upbit_subscription(self) -> str:
        payload = [
            {"ticket": f"coin-trader-{uuid.uuid4()}"},
            {
                "type": "ticker",
                "codes": [
                    to_upbit_market_code(symbol, settings.QUOTE_CURRENCY)
                    for symbol in self.symbols
                ],
                "is_only_realtime": True,
            },
            {"format": "DEFAULT"},
        ]
        return json.dumps(payload)

    async def _process_binance_message(self, raw: str):
        try:
            data = json.loads(raw)
            stream_data = data.get("data", data)

            compact_symbol = (stream_data.get("s") or "").upper()
            if not compact_symbol:
                return

            price = float(stream_data.get("c", 0))
            change_24h = float(stream_data.get("P", 0))
            volume_24h = float(stream_data.get("v", 0))
            normalized_symbol = normalize_symbol(compact_symbol, settings.QUOTE_CURRENCY)

            await self._cache_and_broadcast(
                normalized_symbol,
                price,
                change_24h,
                volume_24h,
            )
        except Exception as exc:
            logger.error("바이낸스 가격 데이터 처리 오류: %s", exc)

    async def _process_upbit_message(self, raw: str | bytes):
        try:
            decoded = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            data = json.loads(decoded)
            market_code = data.get("code", "")
            if not market_code:
                return

            normalized_symbol = normalize_symbol(market_code, settings.QUOTE_CURRENCY)
            price = float(data.get("trade_price", 0))
            change_24h = float(data.get("signed_change_rate", 0)) * 100
            volume_24h = float(data.get("acc_trade_volume_24h", 0))

            await self._cache_and_broadcast(
                normalized_symbol,
                price,
                change_24h,
                volume_24h,
            )
        except Exception as exc:
            logger.error("업비트 가격 데이터 처리 오류: %s", exc)

    async def _run_upbit(self):
        subscribe_message = self._build_upbit_subscription()
        logger.info("업비트 WebSocket 연결: %s", UPBIT_WS_BASE)

        while self._running:
            try:
                async with websockets.connect(
                    UPBIT_WS_BASE,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    logger.info("업비트 WebSocket 연결 성공")
                    await ws.send(subscribe_message)
                    async for message in ws:
                        if not self._running:
                            break
                        await self._process_upbit_message(message)
            except Exception as exc:
                if self._running:
                    logger.warning("업비트 WebSocket 연결 끊김: %s. 5초 후 재연결...", exc)
                    await asyncio.sleep(5)

    async def _run_binance(self):
        url = self._build_binance_stream_url()
        logger.info("바이낸스 WebSocket 연결: %s", url)

        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("바이낸스 WebSocket 연결 성공")
                    async for message in ws:
                        if not self._running:
                            break
                        await self._process_binance_message(message)
            except Exception as exc:
                if self._running:
                    logger.warning("바이낸스 WebSocket 연결 끊김: %s. 5초 후 재연결...", exc)
                    await asyncio.sleep(5)

    async def start(self):
        self._running = True
        if settings.EXCHANGE_ID == "upbit":
            await self._run_upbit()
        else:
            await self._run_binance()

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()


price_feed = ExchangePriceFeed()

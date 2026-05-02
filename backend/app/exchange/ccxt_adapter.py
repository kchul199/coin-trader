import asyncio
import logging
import random

import ccxt.async_support as ccxt
from decimal import Decimal
from app.config import settings, ALLOWED_EXCHANGE_IDS
from app.exchange.testnet_config import BINANCE_TESTNET_URLS
from app.exchange.upbit_rules import (
    normalize_upbit_limit_price,
    normalize_upbit_market_buy_amount,
)

logger = logging.getLogger(__name__)


class CcxtAdapter:
    def __init__(self, exchange_id: str, api_key: str = "", api_secret: str = "", testnet: bool = True):
        # Whitelist check
        if exchange_id not in ALLOWED_EXCHANGE_IDS:
            raise ValueError(f"허용되지 않은 거래소: {exchange_id}")

        exchange_class = getattr(ccxt, exchange_id)
        params = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "timeout": settings.EXCHANGE_HTTP_TIMEOUT_MS,
        }

        if exchange_id == "binance" and testnet:
            params["urls"] = BINANCE_TESTNET_URLS

        self.exchange = exchange_class(params)
        self.exchange_id = exchange_id
        self.testnet = testnet if exchange_id == "binance" else False

    async def _call_with_retry(self, operation_name: str, func, *args, **kwargs):
        max_attempts = max(1, int(getattr(settings, "EXCHANGE_RETRY_MAX_ATTEMPTS", 4)))
        base_delay = float(getattr(settings, "EXCHANGE_RETRY_BASE_DELAY_SECONDS", 1.5))
        max_delay = float(getattr(settings, "EXCHANGE_RETRY_MAX_DELAY_SECONDS", 15.0))
        retryable_errors = (
            ccxt.RateLimitExceeded,
            ccxt.DDoSProtection,
            ccxt.RequestTimeout,
            ccxt.ExchangeNotAvailable,
            ccxt.NetworkError,
        )

        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except retryable_errors as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break

                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                jitter = min(0.5, delay * 0.15) * random.random()
                sleep_seconds = delay + jitter
                logger.warning(
                    "거래소 API 재시도: op=%s attempt=%d/%d exchange=%s delay=%.2fs error=%s",
                    operation_name,
                    attempt,
                    max_attempts,
                    self.exchange_id,
                    sleep_seconds,
                    exc,
                )
                await asyncio.sleep(sleep_seconds)

        if last_error:
            raise last_error
        raise RuntimeError(f"거래소 API 호출 실패: {operation_name}")

    async def get_balance(self) -> dict:
        """거래소 잔고 조회 - {symbol: {free, used, total}}"""
        balance = await self._call_with_retry("fetch_balance", self.exchange.fetch_balance)
        # Filter non-zero balances
        result = {}
        for symbol, amounts in balance.items():
            if isinstance(amounts, dict) and amounts.get("total", 0) > 0:
                result[symbol] = {
                    "available": float(amounts.get("free", 0)),
                    "locked": float(amounts.get("used", 0)),
                    "total": float(amounts.get("total", 0)),
                }
        return result

    async def get_ticker(self, symbol: str) -> dict:
        """현재가 조회 - CCXT 표준(BASE/QUOTE) 형식"""
        ticker = await self._call_with_retry("fetch_ticker", self.exchange.fetch_ticker, symbol)
        last_price = float(ticker["last"])
        return {
            "symbol": symbol,
            "price": last_price,
            "last": last_price,
            "close": last_price,
            "bid": float(ticker["bid"] or 0),
            "ask": float(ticker["ask"] or 0),
            "change_24h": float(ticker["percentage"] or 0),
            "volume_24h": float(ticker["baseVolume"] or 0),
            "timestamp": ticker["timestamp"],
        }

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> list:
        """캔들 데이터 조회"""
        ohlcv = await self._call_with_retry("fetch_ohlcv", self.exchange.fetch_ohlcv, symbol, timeframe, limit=limit)
        return [
            {
                "timestamp": candle[0],
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
            }
            for candle in ohlcv
        ]

    async def get_open_orders(self, symbol: str = None) -> list:
        """미체결 주문 조회"""
        orders = await self._call_with_retry("fetch_open_orders", self.exchange.fetch_open_orders, symbol)
        return orders

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float = None,
        quote_amount: float = None,
    ) -> dict:
        """주문 실행"""
        if self.exchange_id == "upbit" and order_type == "market":
            if side == "buy":
                if quote_amount is None:
                    raise ValueError("업비트 시장가 매수에는 주문 금액이 필요합니다.")
                spend_amount = normalize_upbit_market_buy_amount(
                    Decimal(str(quote_amount)),
                    settings.QUOTE_CURRENCY,
                )
                order = await self._call_with_retry(
                    "create_order_market_buy",
                    self.exchange.create_order,
                    symbol,
                    "price",
                    side,
                    None,
                    float(spend_amount),
                )
            else:
                order = await self._call_with_retry(
                    "create_order_market_sell",
                    self.exchange.create_order,
                    symbol,
                    "market",
                    side,
                    amount,
                    None,
                )
        elif self.exchange_id == "upbit" and order_type == "limit" and price is not None:
            normalized_price = normalize_upbit_limit_price(
                Decimal(str(price)),
                settings.QUOTE_CURRENCY,
            )
            order = await self._call_with_retry(
                "create_limit_order_upbit",
                self.exchange.create_limit_order,
                symbol,
                side,
                amount,
                float(normalized_price),
            )
        elif order_type == "market":
            order = await self._call_with_retry(
                "create_market_order",
                self.exchange.create_market_order,
                symbol,
                side,
                amount,
            )
        else:
            order = await self._call_with_retry(
                "create_limit_order",
                self.exchange.create_limit_order,
                symbol,
                side,
                amount,
                price,
            )
        return order

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """주문 취소"""
        return await self._call_with_retry("cancel_order", self.exchange.cancel_order, order_id, symbol)

    async def close(self):
        """연결 종료"""
        await self.exchange.close()


def create_exchange_adapter(api_key: str = "", api_secret: str = "") -> CcxtAdapter:
    """설정에서 거래소 어댑터 생성"""
    return CcxtAdapter(
        exchange_id=settings.EXCHANGE_ID,
        api_key=api_key,
        api_secret=api_secret,
        testnet=settings.USE_TESTNET,
    )

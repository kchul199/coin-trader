import ccxt.async_support as ccxt
from app.config import settings, ALLOWED_EXCHANGE_IDS
from app.exchange.testnet_config import BINANCE_TESTNET_URLS


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
        }

        if exchange_id == "binance" and testnet:
            params["urls"] = BINANCE_TESTNET_URLS

        self.exchange = exchange_class(params)
        self.exchange_id = exchange_id
        self.testnet = testnet

    async def get_balance(self) -> dict:
        """거래소 잔고 조회 - {symbol: {free, used, total}}"""
        balance = await self.exchange.fetch_balance()
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
        """현재가 조회 - BTC/USDT 형식"""
        ticker = await self.exchange.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "price": float(ticker["last"]),
            "bid": float(ticker["bid"] or 0),
            "ask": float(ticker["ask"] or 0),
            "change_24h": float(ticker["percentage"] or 0),
            "volume_24h": float(ticker["baseVolume"] or 0),
            "timestamp": ticker["timestamp"],
        }

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> list:
        """캔들 데이터 조회"""
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
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
        orders = await self.exchange.fetch_open_orders(symbol)
        return orders

    async def place_order(self, symbol: str, side: str, order_type: str, amount: float, price: float = None) -> dict:
        """주문 실행"""
        if order_type == "market":
            order = await self.exchange.create_market_order(symbol, side, amount)
        else:
            order = await self.exchange.create_limit_order(symbol, side, amount, price)
        return order

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """주문 취소"""
        return await self.exchange.cancel_order(order_id, symbol)

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

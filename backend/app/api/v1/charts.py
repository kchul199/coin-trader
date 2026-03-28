from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
import asyncio

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.candle import Candle
from app.models.exchange_account import ExchangeAccount
from app.core.encryption import decrypt_api_key
from app.exchange.ccxt_adapter import CcxtAdapter
from app.config import settings

router = APIRouter(prefix="/chart", tags=["chart"])

VALID_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}


class CandleData(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class TickerData(BaseModel):
    symbol: str
    price: float
    change_24h: float
    volume_24h: float
    bid: float
    ask: float


@router.get("/{symbol}/candles", response_model=list[CandleData])
async def get_candles(
    symbol: str,
    tf: str = Query("1h", pattern="^(1m|5m|15m|30m|1h|4h|1d)$"),
    limit: int = Query(200, ge=10, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캔들 데이터 조회 - DB에 없으면 거래소 API 호출"""
    # symbol 정규화: BTCUSDT → BTC/USDT
    norm_symbol = symbol.upper().replace("-", "/")
    if "/" not in norm_symbol and len(norm_symbol) > 4:
        # BTCUSDT → BTC/USDT 추정
        norm_symbol = norm_symbol[:-4] + "/" + norm_symbol[-4:]

    # 활성 거래소 계정 조회
    acc_result = await db.execute(
        select(ExchangeAccount).where(
            ExchangeAccount.user_id == current_user.id,
            ExchangeAccount.is_active == True,
        )
    )
    account = acc_result.scalar_one_or_none()

    if not account:
        # 계정 없으면 퍼블릭 API로 조회 (API키 불필요)
        api_key, api_secret = "", ""
        is_testnet = settings.USE_TESTNET
    else:
        api_key = decrypt_api_key(account.api_key_encrypted)
        api_secret = decrypt_api_key(account.api_secret_encrypted)
        is_testnet = account.is_testnet

    try:
        adapter = CcxtAdapter(
            exchange_id=settings.EXCHANGE_ID,
            api_key=api_key,
            api_secret=api_secret,
            testnet=is_testnet,
        )
        candles = await adapter.get_ohlcv(norm_symbol, tf, limit)
        await adapter.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"거래소 데이터 조회 실패: {str(e)}")

    return [
        CandleData(
            timestamp=c["timestamp"],
            open=c["open"],
            high=c["high"],
            low=c["low"],
            close=c["close"],
            volume=c["volume"],
        )
        for c in candles
    ]


@router.get("/{symbol}/ticker", response_model=TickerData)
async def get_ticker(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재가 조회 - Redis 캐시 우선"""
    from app.core.redis_client import get_redis

    norm_symbol = symbol.upper().replace("-", "/")
    if "/" not in norm_symbol and len(norm_symbol) > 4:
        norm_symbol = norm_symbol[:-4] + "/" + norm_symbol[-4:]

    # Redis 캐시 확인
    redis = await get_redis()
    cache_key = f"price:{settings.EXCHANGE_ID}:{norm_symbol.replace('/', '')}"
    cached = await redis.get(cache_key)

    if cached:
        return TickerData(
            symbol=norm_symbol,
            price=float(cached),
            change_24h=0.0,
            volume_24h=0.0,
            bid=float(cached),
            ask=float(cached),
        )

    # 캐시 없으면 직접 조회
    try:
        adapter = CcxtAdapter(
            exchange_id=settings.EXCHANGE_ID,
            api_key="",
            api_secret="",
            testnet=settings.USE_TESTNET,
        )
        ticker = await adapter.get_ticker(norm_symbol)
        await adapter.close()
        return TickerData(**ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"가격 조회 실패: {str(e)}")

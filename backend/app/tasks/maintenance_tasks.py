"""
Maintenance Celery Tasks — 유지보수 태스크
- sync_balances: 10분마다 모든 거래소 계정 잔고 동기화
- save_candles: 15분마다 주요 심볼 캔들 데이터 DB 저장
- cleanup_expired_blacklist: 매일 만료된 JWT 블랙리스트 정리
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@shared_task(name="tasks.sync_balances")
def sync_balances():
    """모든 활성 거래소 계정 잔고 동기화"""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.exchange_account import ExchangeAccount
        from app.models.balance import Balance
        from app.core.encryption import decrypt_api_key
        from app.config import settings
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExchangeAccount).where(ExchangeAccount.is_active.is_(True))
            )
            accounts = result.scalars().all()

        synced, errors = 0, 0

        for account in accounts:
            try:
                import ccxt.async_support as ccxt_async

                api_key = decrypt_api_key(account.api_key_encrypted)
                api_secret = decrypt_api_key(account.api_secret_encrypted)

                exchange_cls = getattr(ccxt_async, account.exchange_id, None)
                if not exchange_cls:
                    continue

                exchange = exchange_cls({
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                })
                if account.is_testnet and account.exchange_id == "binance":
                    exchange.set_sandbox_mode(True)

                try:
                    balance_data = await exchange.fetch_balance()
                    now = datetime.now(timezone.utc)

                    async with AsyncSessionLocal() as db:
                        for symbol, info in balance_data.get("total", {}).items():
                            if info == 0:
                                continue
                            free = balance_data.get("free", {}).get(symbol, 0)
                            used = balance_data.get("used", {}).get(symbol, 0)

                            res = await db.execute(
                                select(Balance).where(
                                    Balance.user_id == account.user_id,
                                    Balance.exchange_id == account.exchange_id,
                                    Balance.symbol == symbol,
                                )
                            )
                            existing = res.scalar_one_or_none()
                            if existing:
                                existing.available = free
                                existing.locked = used
                                existing.synced_at = now
                            else:
                                db.add(Balance(
                                    user_id=account.user_id,
                                    exchange_id=account.exchange_id,
                                    symbol=symbol,
                                    available=free,
                                    locked=used,
                                    synced_at=now,
                                ))
                        await db.commit()
                    synced += 1
                finally:
                    await exchange.close()
            except Exception as exc:
                logger.error("잔고 동기화 실패: account=%s error=%s", account.id, exc)
                errors += 1

        logger.info("잔고 동기화 완료: 성공=%d 실패=%d", synced, errors)
        return {"synced": synced, "errors": errors}

    return _run_async(_run())


@shared_task(name="tasks.save_candles")
def save_candles():
    """주요 심볼 캔들 데이터 DB 저장"""
    SYMBOLS = ["BTC/USDT", "ETH/USDT"]
    TIMEFRAMES = ["1h", "4h", "1d"]

    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.candle import Candle
        from app.exchange.ccxt_adapter import create_exchange_adapter
        from app.config import settings
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        exchange = create_exchange_adapter()
        saved_total = 0

        try:
            for symbol in SYMBOLS:
                for timeframe in TIMEFRAMES:
                    try:
                        ohlcv = await exchange.get_ohlcv(symbol, timeframe, limit=100)
                        if not ohlcv:
                            continue

                        rows = []
                        for candle in ohlcv:
                            ts = datetime.fromtimestamp(candle["timestamp"] / 1000, tz=timezone.utc)
                            rows.append({
                                "symbol": symbol,
                                "exchange": settings.EXCHANGE_ID,
                                "timeframe": timeframe,
                                "ts": ts,
                                "open": candle["open"],
                                "high": candle["high"],
                                "low": candle["low"],
                                "close": candle["close"],
                                "volume": candle["volume"],
                            })

                        async with AsyncSessionLocal() as db:
                            stmt = pg_insert(Candle).values(rows)
                            stmt = stmt.on_conflict_do_nothing(
                                index_elements=["symbol", "exchange", "timeframe", "ts"]
                            )
                            await db.execute(stmt)
                            await db.commit()
                        saved_total += len(rows)
                    except Exception as exc:
                        logger.error("캔들 저장 실패: symbol=%s tf=%s error=%s", symbol, timeframe, exc)
        finally:
            await exchange.close()

        logger.info("캔들 저장 완료: %d개", saved_total)
        return {"saved": saved_total}

    return _run_async(_run())


@shared_task(name="tasks.cleanup_expired_blacklist")
def cleanup_expired_blacklist():
    """만료된 JWT 블랙리스트 레코드 정리"""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.jwt_blacklist import JWTBlacklist as JwtBlacklist
        from sqlalchemy import delete

        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                delete(JwtBlacklist).where(JwtBlacklist.expires_at < now)
            )
            await db.commit()
            deleted = result.rowcount
            logger.info("JWT 블랙리스트 정리: %d개 삭제", deleted)
            return {"deleted": deleted}

    return _run_async(_run())

"""
Maintenance Celery Tasks — 유지보수 태스크
- sync_balances: 10분마다 모든 거래소 계정 잔고 동기화
- sync_open_orders: 1분마다 미체결 주문 상태 동기화 및 복구
- save_candles: 15분마다 주요 심볼 캔들 데이터 DB 저장
- cleanup_expired_blacklist: 매일 만료된 JWT 블랙리스트 정리
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task
from app.config import settings
from app.database import AsyncSessionLocal

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


async def run_sync_balances(notify_websocket: bool = False) -> dict:
    from app.core.encryption import decrypt_api_key
    from app.core.redis_client import get_redis
    from app.models.balance import Balance
    from app.models.exchange_account import ExchangeAccount
    from app.websocket.manager import ws_manager
    from sqlalchemy import select

    redis = await get_redis()
    ttl = int(getattr(settings, "BALANCE_RESERVATION_TTL_SECONDS", 3600))

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
                        shadow_key = f"balance:shadow:{account.exchange_id}:{account.user_id}:{symbol}"
                        await redis.setex(shadow_key, ttl, str(free))
                    await db.commit()
                synced += 1
            finally:
                await exchange.close()
        except Exception as exc:
            logger.error("잔고 동기화 실패: account=%s error=%s", account.id, exc)
            errors += 1

    logger.info("잔고 동기화 완료: 성공=%d 실패=%d", synced, errors)

    if notify_websocket and (synced > 0 or errors > 0):
        await ws_manager.broadcast_json({
            "type": "system_notice",
            "level": "info" if errors == 0 else "error",
            "title": "잔고 복구 동기화",
            "message": f"계정 {synced}건 잔고 동기화 완료, 오류 {errors}건",
        })

    return {"synced": synced, "errors": errors}


async def run_sync_open_orders(notify_websocket: bool = False, notification_context: str = "scheduled") -> dict:
    from app.config import settings
    from app.core.encryption import decrypt_api_key
    from app.core.redis_client import get_redis
    from app.exchange.ccxt_adapter import CcxtAdapter
    from app.models.exchange_account import ExchangeAccount
    from app.models.order import Order
    from app.models.strategy import Strategy
    from app.trading.order_manager import OrderManager
    from app.websocket.manager import ws_manager
    from sqlalchemy import select

    redis = await get_redis()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order.id, Strategy.user_id, Order.exchange_id)
            .join(Strategy, Strategy.id == Order.strategy_id)
            .where(
                Order.status.in_(["open", "pending"]),
                Order.exchange_order_id.is_not(None),
                Order.exchange_order_id != "",
            )
        )
        order_rows = result.all()

    if not order_rows:
        return {"synced": 0, "filled": 0, "errors": 0}

    order_ids_by_account: dict[tuple[object, str], list[str]] = {}
    for order_id, user_id, exchange_id in order_rows:
        key = (user_id, exchange_id)
        order_ids_by_account.setdefault(key, []).append(str(order_id))

    synced = 0
    filled = 0
    errors = 0

    for (user_id, exchange_id), order_ids in order_ids_by_account.items():
        async with AsyncSessionLocal() as db:
            account_result = await db.execute(
                select(ExchangeAccount).where(
                    ExchangeAccount.user_id == user_id,
                    ExchangeAccount.exchange_id == exchange_id,
                    ExchangeAccount.is_active.is_(True),
                )
            )
            account = account_result.scalar_one_or_none()

        if not account:
            logger.warning("주문 동기화용 거래소 계정 없음: user=%s exchange=%s", user_id, exchange_id)
            errors += len(order_ids)
            continue

        exchange = CcxtAdapter(
            exchange_id=account.exchange_id,
            api_key=decrypt_api_key(account.api_key_encrypted),
            api_secret=decrypt_api_key(account.api_secret_encrypted),
            testnet=account.is_testnet,
        )

        try:
            async with AsyncSessionLocal() as db:
                manager = OrderManager(
                    exchange,
                    ws_manager,
                    db,
                    redis_client=redis,
                    settings=settings,
                )
                for order_id in order_ids:
                    order_result = await db.execute(
                        select(Order).where(Order.id == order_id)
                    )
                    order = order_result.scalar_one_or_none()
                    if not order:
                        continue

                    try:
                        status = await manager.sync_order_status(order)
                        synced += 1
                        if status == "filled":
                            filled += 1
                    except Exception as exc:
                        logger.error("주문 상태 동기화 실패: order=%s error=%s", order_id, exc)
                        errors += 1
        finally:
            await exchange.close()

    logger.info("미체결 주문 동기화 완료: synced=%d filled=%d errors=%d", synced, filled, errors)

    if notify_websocket and (synced > 0 or filled > 0 or errors > 0):
        level = "error" if errors > 0 else "info"
        prefix = "시작 복구" if notification_context == "startup" else "주문 동기화"
        await ws_manager.broadcast_json({
            "type": "system_notice",
            "level": level,
            "title": prefix,
            "message": f"미체결 주문 {synced}건 점검, 체결 반영 {filled}건, 오류 {errors}건",
        })

    return {"synced": synced, "filled": filled, "errors": errors}


@shared_task(name="tasks.sync_balances")
def sync_balances():
    """모든 활성 거래소 계정 잔고 동기화"""
    async def _run():
        return await run_sync_balances()

    return _run_async(_run())


@shared_task(name="tasks.sync_open_orders")
def sync_open_orders():
    """미체결 주문 상태 동기화 및 체결 후 포트폴리오/손익 반영"""
    async def _run():
        return await run_sync_open_orders()

    return _run_async(_run())


@shared_task(name="tasks.save_candles")
def save_candles():
    """주요 심볼 캔들 데이터 DB 저장"""
    TIMEFRAMES = ["1h", "4h", "1d"]

    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.candle import Candle
        from app.exchange.ccxt_adapter import create_exchange_adapter
        from app.exchange.symbols import get_default_symbols
        from app.config import settings
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        symbols = get_default_symbols(settings.EXCHANGE_ID, settings.QUOTE_CURRENCY)
        exchange = create_exchange_adapter()
        saved_total = 0

        try:
            for symbol in symbols:
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

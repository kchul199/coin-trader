from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from jose import jwt
from sqlalchemy import select
import websockets

from app.config import settings
from app.core.encryption import decrypt_api_key
from app.core.redis_client import get_redis
from app.database import AsyncSessionLocal
from app.models.balance import Balance
from app.models.exchange_account import ExchangeAccount
from app.models.order import Order
from app.trading.order_manager import OrderManager
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

UPBIT_PRIVATE_WS_URL = "wss://api.upbit.com/websocket/v1/private"


class UpbitPrivateFeedManager:
    def __init__(self):
        self._running = False
        self._sync_task: asyncio.Task | None = None
        self._listener_tasks: dict[str, asyncio.Task] = {}

    async def start(self):
        if settings.EXCHANGE_ID != "upbit" or self._running:
            return
        self._running = True
        self._sync_task = asyncio.create_task(self._supervise())

    async def stop(self):
        self._running = False

        if self._sync_task:
            self._sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sync_task
            self._sync_task = None

        tasks = list(self._listener_tasks.values())
        self._listener_tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _supervise(self):
        while self._running:
            try:
                await self._sync_accounts()
            except Exception as exc:
                logger.warning("업비트 private feed 계정 동기화 실패: %s", exc)
            await asyncio.sleep(30)

    async def _sync_accounts(self):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExchangeAccount).where(
                    ExchangeAccount.exchange_id == "upbit",
                    ExchangeAccount.is_active.is_(True),
                )
            )
            accounts = result.scalars().all()

        active_account_ids = {str(account.id) for account in accounts}

        for account_id, task in list(self._listener_tasks.items()):
            if account_id not in active_account_ids or task.done():
                task.cancel()
                self._listener_tasks.pop(account_id, None)

        for account in accounts:
            account_id = str(account.id)
            if account_id in self._listener_tasks:
                continue
            self._listener_tasks[account_id] = asyncio.create_task(
                self._run_account_listener(
                    account_id=account_id,
                    user_id=str(account.user_id),
                    api_key=decrypt_api_key(account.api_key_encrypted),
                    api_secret=decrypt_api_key(account.api_secret_encrypted),
                )
            )

    async def _run_account_listener(
        self,
        account_id: str,
        user_id: str,
        api_key: str,
        api_secret: str,
    ):
        headers = {"Authorization": f"Bearer {self._create_jwt(api_key, api_secret)}"}
        subscribe_message = json.dumps([
            {"ticket": f"coin-trader-private-{account_id}"},
            {"type": "myOrder"},
            {"type": "myAsset"},
            {"format": "DEFAULT"},
        ])

        while self._running:
            try:
                async with websockets.connect(
                    UPBIT_PRIVATE_WS_URL,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    logger.info("업비트 private WebSocket 연결 성공: account=%s", account_id)
                    await ws.send(subscribe_message)
                    async for raw_message in ws:
                        if not self._running:
                            break
                        await self._process_message(user_id, raw_message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._running:
                    logger.warning(
                        "업비트 private WebSocket 재연결: account=%s error=%s",
                        account_id,
                        exc,
                    )
                    await asyncio.sleep(5)

    async def _process_message(self, user_id: str, raw_message: str | bytes):
        decoded = raw_message.decode("utf-8") if isinstance(raw_message, bytes) else raw_message
        payload = json.loads(decoded)
        message_type = payload.get("type")

        if message_type == "myAsset":
            await self._handle_asset_event(user_id, payload)
            return

        if message_type == "myOrder":
            await self._handle_order_event(user_id, payload)

    async def _handle_asset_event(self, user_id: str, payload: dict):
        assets = payload.get("assets") or []
        now = datetime.now(timezone.utc)
        redis = await get_redis()
        ttl = int(getattr(settings, "BALANCE_RESERVATION_TTL_SECONDS", 3600))

        async with AsyncSessionLocal() as db:
            for asset in assets:
                symbol = str(asset.get("currency", "")).upper()
                if not symbol:
                    continue

                result = await db.execute(
                    select(Balance).where(
                        Balance.user_id == uuid.UUID(user_id),
                        Balance.exchange_id == "upbit",
                        Balance.symbol == symbol,
                    )
                )
                balance = result.scalar_one_or_none()
                available = Decimal(str(asset.get("balance", 0)))
                locked = Decimal(str(asset.get("locked", 0)))

                if balance:
                    balance.available = available
                    balance.locked = locked
                    balance.synced_at = now
                else:
                    db.add(Balance(
                        user_id=uuid.UUID(user_id),
                        exchange_id="upbit",
                        symbol=symbol,
                        available=available,
                        locked=locked,
                        synced_at=now,
                    ))

                shadow_key = f"balance:shadow:upbit:{user_id}:{symbol}"
                await redis.setex(shadow_key, ttl, str(available))

            await db.commit()

    async def _handle_order_event(self, user_id: str, payload: dict):
        exchange_order_id = payload.get("uuid")
        if not exchange_order_id:
            return

        executed_volume = Decimal(str(payload.get("executed_volume", 0) or 0))
        remaining_volume = Decimal(str(payload.get("remaining_volume", 0) or 0))
        avg_price = Decimal(str(payload.get("avg_price") or payload.get("price") or 0))
        fee = Decimal(str(payload.get("paid_fee", 0) or 0))
        state = str(payload.get("state", "wait")).lower()

        mapped_status = self._map_order_state(state, executed_volume, remaining_volume)
        redis = await get_redis()
        should_broadcast_fill = False
        fill_symbol = None
        fill_side = None
        fill_strategy_id = None

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Order).where(
                    Order.exchange_id == "upbit",
                    Order.exchange_order_id == exchange_order_id,
                )
            )
            order = result.scalar_one_or_none()
            if not order:
                return

            previous_status = order.status
            order.status = mapped_status
            order.filled_quantity = executed_volume
            order.avg_fill_price = avg_price if avg_price > 0 else order.avg_fill_price
            order.fee = fee
            order.updated_at = datetime.now(timezone.utc)

            is_complete_fill = (
                executed_volume > 0
                and (
                    state in {"done", "cancel", "prevented"}
                    or mapped_status == "filled"
                )
            )
            if is_complete_fill:
                order.filled_at = datetime.now(timezone.utc)
                if previous_status != "filled":
                    manager = OrderManager(
                        exchange_adapter=None,
                        ws_manager=ws_manager,
                        db_session=db,
                        redis_client=redis,
                        settings=settings,
                    )
                    await manager._apply_filled_order_effects(order)
                    await manager._reconcile_balance_reservation(order, "filled")
                    should_broadcast_fill = True
                    fill_symbol = order.symbol
                    fill_side = order.side
                    fill_strategy_id = str(order.strategy_id)
            elif mapped_status in {"cancelled", "rejected"}:
                manager = OrderManager(
                    exchange_adapter=None,
                    ws_manager=ws_manager,
                    db_session=db,
                    redis_client=redis,
                    settings=settings,
                )
                await manager._reconcile_balance_reservation(order, mapped_status)

            await db.commit()

        if should_broadcast_fill and fill_symbol and fill_side:
            await ws_manager.broadcast_json({
                "type": "order_filled",
                "order_id": exchange_order_id,
                "strategy_id": fill_strategy_id,
                "symbol": fill_symbol,
                "side": fill_side,
                "filled_quantity": float(executed_volume),
                "avg_fill_price": float(avg_price),
            })

    def _create_jwt(self, access_key: str, secret_key: str) -> str:
        payload = {
            "access_key": access_key,
            "nonce": str(uuid.uuid4()),
        }
        return jwt.encode(payload, secret_key, algorithm="HS256")

    def _map_order_state(
        self,
        state: str,
        executed_volume: Decimal,
        remaining_volume: Decimal,
    ) -> str:
        if state in {"wait", "watch", "trade"} and remaining_volume > 0:
            return "open"
        if state == "done":
            return "filled"
        if state == "trade" and remaining_volume <= 0 and executed_volume > 0:
            return "filled"
        if state in {"cancel", "prevented"} and executed_volume > 0 and remaining_volume <= 0:
            return "filled"
        if state in {"cancel", "prevented"}:
            return "cancelled"
        return "open"

upbit_private_feed = UpbitPrivateFeedManager()

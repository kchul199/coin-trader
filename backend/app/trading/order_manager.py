"""
OrderManager — 주문 실행 및 상태 관리
거래소 주문 생성/취소, DB 저장, WebSocket 알림을 담당한다.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order

logger = logging.getLogger(__name__)


class OrderManager:
    """
    주문 실행 흐름:
    1. DB에 pending 상태 주문 레코드 생성
    2. 거래소 API 호출 (ccxt_adapter)
    3. 성공 시 DB 업데이트 (open 상태 + exchange_order_id)
    4. WebSocket으로 order_created 이벤트 브로드캐스트
    5. 실패 시 DB 업데이트 (rejected 상태) + 로깅
    """

    def __init__(self, exchange_adapter, ws_manager, db_session: AsyncSession):
        self.exchange = exchange_adapter
        self.ws = ws_manager
        self.db = db_session

    async def place_order(
        self,
        strategy_id: str,
        exchange_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        order_config: Optional[dict] = None,
    ) -> dict:
        """
        주문 실행
        Returns: {"success": bool, "order_id": str, "exchange_order_id": str, "error": str}
        """
        order_id = str(uuid.uuid4())
        order_config = order_config or {}

        # 1) DB에 pending 상태 저장
        db_order = Order(
            id=order_id,
            strategy_id=strategy_id,
            exchange_id=exchange_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=float(quantity),
            price=float(price) if price else None,
            status="pending",
        )
        self.db.add(db_order)
        await self.db.flush()  # ID 확정

        try:
            # 2) 거래소 API 호출
            ex_result = await self.exchange.place_order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                amount=float(quantity),
                price=float(price) if price else None,
            )

            exchange_order_id = ex_result.get("id", "")
            ex_status = ex_result.get("status", "open")

            # 3) DB 업데이트 (open)
            db_order.exchange_order_id = exchange_order_id
            db_order.status = ex_status if ex_status in ("open", "closed", "filled") else "open"
            db_order.updated_at = datetime.now(timezone.utc)
            await self.db.commit()

            # 4) WebSocket 알림
            await self.ws.broadcast_json({
                "type": "order_created",
                "order_id": order_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "side": side,
                "quantity": str(quantity),
                "status": db_order.status,
            })

            logger.info(
                "주문 생성 성공: order_id=%s exchange_id=%s symbol=%s side=%s qty=%s",
                order_id, exchange_order_id, symbol, side, quantity,
            )
            return {
                "success": True,
                "order_id": order_id,
                "exchange_order_id": exchange_order_id,
                "status": db_order.status,
            }

        except Exception as exc:
            # 5) 실패 처리
            logger.error("주문 실패: order_id=%s error=%s", order_id, exc)
            db_order.status = "rejected"
            db_order.updated_at = datetime.now(timezone.utc)
            await self.db.commit()

            await self.ws.broadcast_json({
                "type": "order_failed",
                "order_id": order_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "error": str(exc),
            })
            return {"success": False, "order_id": order_id, "error": str(exc)}

    async def cancel_order(
        self,
        order_id: str,
        exchange_order_id: str,
        symbol: str,
    ) -> bool:
        """주문 취소"""
        try:
            await self.exchange.cancel_order(exchange_order_id, symbol)
            await self.db.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(status="cancelled", updated_at=datetime.now(timezone.utc))
            )
            await self.db.commit()
            logger.info("주문 취소 완료: order_id=%s", order_id)
            return True
        except Exception as exc:
            logger.error("주문 취소 실패: order_id=%s error=%s", order_id, exc)
            return False

    async def sync_order_status(self, order: Order) -> str:
        """거래소에서 주문 상태 동기화"""
        try:
            ex_order = await self.exchange.exchange.fetch_order(
                order.exchange_order_id, order.symbol
            )
            new_status = ex_order.get("status", order.status)
            filled_qty = ex_order.get("filled", order.filled_quantity or 0)
            avg_price = ex_order.get("average") or ex_order.get("price")
            fee = ex_order.get("fee", {}).get("cost", 0)

            status_map = {
                "closed": "filled",
                "open": "open",
                "canceled": "cancelled",
                "expired": "cancelled",
            }
            mapped_status = status_map.get(new_status, new_status)

            await self.db.execute(
                update(Order)
                .where(Order.id == str(order.id))
                .values(
                    status=mapped_status,
                    filled_quantity=filled_qty,
                    avg_fill_price=avg_price,
                    fee=fee,
                    filled_at=datetime.now(timezone.utc) if mapped_status == "filled" else None,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self.db.commit()

            if mapped_status == "filled":
                await self.ws.broadcast_json({
                    "type": "order_filled",
                    "order_id": str(order.id),
                    "strategy_id": str(order.strategy_id),
                    "symbol": order.symbol,
                    "side": order.side,
                    "filled_quantity": filled_qty,
                    "avg_fill_price": str(avg_price),
                })

            return mapped_status

        except Exception as exc:
            logger.warning("주문 상태 동기화 실패: order_id=%s error=%s", order.id, exc)
            return order.status

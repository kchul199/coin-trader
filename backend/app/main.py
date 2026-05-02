from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.config import settings
from app.api.v1.router import router
from app.database import init_db, close_db
from app.core.redis_client import get_redis, close_redis
from app.websocket.price_feed import price_feed
from app.websocket.upbit_private_feed import upbit_private_feed
from app.websocket.handlers import handle_websocket
from app.tasks.maintenance_tasks import run_sync_balances, run_sync_open_orders

# Create FastAPI app
app = FastAPI(
    title="Coin Trader API",
    description="Trading bot backend API",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 router
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Initialize database and Redis on startup."""
    await init_db()
    await get_redis()
    # Start price feed as background task (graceful — 실패해도 서버 기동에 영향 없음)
    try:
        price_feed._task = asyncio.create_task(price_feed.start())
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Price feed 시작 실패 (나중에 재시도): {e}")

    try:
        await upbit_private_feed.start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Upbit private feed 시작 실패 (나중에 재시도): {e}")

    async def _startup_recovery():
        import logging
        log = logging.getLogger(__name__)
        try:
            await run_sync_open_orders(notify_websocket=True, notification_context="startup")
        except Exception as exc:
            log.warning("시작 복구(주문 동기화) 실패: %s", exc)
        try:
            await run_sync_balances(notify_websocket=True)
        except Exception as exc:
            log.warning("시작 복구(잔고 동기화) 실패: %s", exc)

    asyncio.create_task(_startup_recovery())


@app.on_event("shutdown")
async def shutdown_event():
    """Close database and Redis connections on shutdown."""
    await price_feed.stop()
    await upbit_private_feed.stop()
    await close_db()
    await close_redis()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "coin-trader-api"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, channel: str = "global"):
    """WebSocket endpoint for real-time price updates."""
    await handle_websocket(websocket, channel)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

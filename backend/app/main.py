from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.config import settings
from app.api.v1.router import router
from app.database import init_db, close_db
from app.core.redis_client import get_redis, close_redis
from app.websocket.price_feed import price_feed
from app.websocket.handlers import handle_websocket

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
    # Start price feed as background task
    price_feed._task = asyncio.create_task(price_feed.start())


@app.on_event("shutdown")
async def shutdown_event():
    """Close database and Redis connections on shutdown."""
    await price_feed.stop()
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

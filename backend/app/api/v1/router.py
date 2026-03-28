from fastapi import APIRouter

from app.api.v1 import auth
from app.api.v1 import settings as exchange_settings
from app.api.v1 import portfolio
from app.api.v1 import orders
from app.api.v1 import strategies
from app.api.v1 import charts
from app.api.v1 import emergency
from app.api.v1 import ai_advisor

# Create v1 router
router = APIRouter(prefix="/api/v1")

# Include routers
router.include_router(auth.router)
router.include_router(exchange_settings.router)
router.include_router(portfolio.router)
router.include_router(orders.router)
router.include_router(strategies.router)
router.include_router(charts.router)
router.include_router(emergency.router)
router.include_router(ai_advisor.router)

__all__ = ["router"]

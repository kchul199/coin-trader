from celery import Celery
from app.config import settings
from app.tasks.beat_schedule import BEAT_SCHEDULE

celery_app = Celery(
    "coin_trader",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.trading_tasks",
        "app.tasks.ai_tasks",
        "app.tasks.maintenance_tasks",
        "app.tasks.backtest_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "tasks.watch_position_exits": {"queue": "trading_priority"},
        "tasks.watch_symbol_positions": {"queue": "trading_priority"},
        "tasks.evaluate_strategy": {"queue": "trading"},
        "tasks.evaluate_all_active_strategies": {"queue": "trading"},
        "tasks.evaluate_hold_queue": {"queue": "trading"},
        "tasks.emergency_stop": {"queue": "trading"},
        "tasks.refresh_ai_advice": {"queue": "ai_advice"},
        "tasks.refresh_all_ai_advice": {"queue": "ai_advice"},
        "tasks.run_backtest": {"queue": "maintenance"},
        "tasks.sync_balances": {"queue": "maintenance"},
        "tasks.sync_open_orders": {"queue": "maintenance"},
        "tasks.save_candles": {"queue": "maintenance"},
        "tasks.cleanup_expired_blacklist": {"queue": "maintenance"},
    },
    beat_schedule=BEAT_SCHEDULE,
    beat_scheduler="redbeat.RedBeatScheduler",
)

# Explicit imports keep worker/beat registration stable inside Docker builds.
import app.tasks.ai_tasks  # noqa: F401,E402
import app.tasks.backtest_tasks  # noqa: F401,E402
import app.tasks.maintenance_tasks  # noqa: F401,E402
import app.tasks.trading_tasks  # noqa: F401,E402

from celery import Celery
from app.config import settings
from app.tasks.beat_schedule import BEAT_SCHEDULE

celery_app = Celery(
    "coin_trader",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
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
        "tasks.evaluate_strategy": {"queue": "trading"},
        "tasks.evaluate_all_active_strategies": {"queue": "trading"},
        "tasks.evaluate_hold_queue": {"queue": "trading"},
        "tasks.emergency_stop": {"queue": "trading"},
        "tasks.refresh_ai_advice": {"queue": "ai_advice"},
        "tasks.refresh_all_ai_advice": {"queue": "ai_advice"},
        "tasks.sync_balances": {"queue": "maintenance"},
        "tasks.save_candles": {"queue": "maintenance"},
        "tasks.cleanup_expired_blacklist": {"queue": "maintenance"},
    },
    beat_schedule=BEAT_SCHEDULE,
    beat_scheduler="redbeat.RedBeatScheduler",
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])

from celery import Celery
from app.config import settings

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
        "app.tasks.trading_tasks.*": {"queue": "trading"},
        "app.tasks.ai_tasks.*": {"queue": "ai_advice"},
        "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])

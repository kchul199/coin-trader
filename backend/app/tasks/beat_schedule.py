"""
Celery Beat 스케줄 정의
Redbeat를 사용하여 Redis에 스케줄을 저장한다.
"""
from celery.schedules import crontab
from app.config import settings

BEAT_SCHEDULE = {
    # 포지션 감시: 2초 기본 폴링 + 가격 이벤트 기반 즉시 트리거
    "watch-position-exits": {
        "task": "tasks.watch_position_exits",
        "schedule": float(settings.POSITION_WATCH_INTERVAL_SECONDS),
        "options": {"queue": "trading_priority"},
    },
    # 전략 평가: 30초마다
    "evaluate-all-active-strategies": {
        "task": "tasks.evaluate_all_active_strategies",
        "schedule": 30.0,
        "options": {"queue": "trading"},
    },
    # hold 대기 전략 재평가: 5분마다
    "evaluate-hold-queue": {
        "task": "tasks.evaluate_hold_queue",
        "schedule": 300.0,
        "options": {"queue": "trading"},
    },
    # AI 자문 사전 갱신: 5분마다
    "refresh-all-ai-advice": {
        "task": "tasks.refresh_all_ai_advice",
        "schedule": 300.0,
        "options": {"queue": "ai_advice"},
    },
    # 잔고 동기화: 10분마다
    "sync-balances": {
        "task": "tasks.sync_balances",
        "schedule": 600.0,
        "options": {"queue": "maintenance"},
    },
    # 미체결 주문 상태 동기화: 1분마다
    "sync-open-orders": {
        "task": "tasks.sync_open_orders",
        "schedule": 60.0,
        "options": {"queue": "maintenance"},
    },
    # 캔들 저장: 15분마다
    "save-candles": {
        "task": "tasks.save_candles",
        "schedule": 900.0,
        "options": {"queue": "maintenance"},
    },
    # JWT 블랙리스트 정리: 매일 새벽 3시
    "cleanup-expired-blacklist": {
        "task": "tasks.cleanup_expired_blacklist",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "maintenance"},
    },
}

"""
Celery application instance.

Broker/result backend default to REDIS_URL so a single Redis instance
covers both rate limiting (app.core.rate_limit) and the task queue in
simple deployments; set CELERY_BROKER_URL/CELERY_RESULT_BACKEND separately
to split them in production (e.g. a dedicated ElastiCache cluster for the
queue vs. one for rate-limit counters).
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "knowledgegpt",
    broker=settings.CELERY_BROKER_URL or settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND or settings.REDIS_URL,
    include=["app.workers.tasks.document_processing"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,              # re-deliver if a worker dies mid-task
    worker_prefetch_multiplier=1,      # avoid one worker hoarding many large-file jobs
    task_default_retry_delay=settings.CELERY_TASK_RETRY_BACKOFF_SECONDS,
    task_routes={
        "app.workers.tasks.document_processing.*": {"queue": "document_processing"},
    },
)

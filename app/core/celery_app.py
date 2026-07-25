from celery import Celery

from app.core.config import settings

broker = settings.CELERY_BROKER_URL or "redis://localhost:6379/0"
backend = settings.CELERY_RESULT_BACKEND or "redis://localhost:6379/0"

celery_app = Celery("antigravity", broker=broker, backend=backend)

celery_app.conf.update(
    task_always_eager=not bool(settings.CELERY_BROKER_URL),
    result_expires=3600,
)

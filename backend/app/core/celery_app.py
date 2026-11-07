from celery import Celery
from app.core.config import settings

celery_app = Celery("golden_touch", broker=settings.CELERY_BROKER_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.engine.worker.execute_workflow": "main-queue",
    }
)

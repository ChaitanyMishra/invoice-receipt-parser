from celery import Celery
import os

REDIS_URL=os.getenv("REDIS_URL","redis://localhost:6379/0")
# RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
RESULT_BACKEND = REDIS_URL.replace("/0", "/1")

celery_app = Celery(
broker=REDIS_URL,
backend=RESULT_BACKEND,
include=['app.tasks'],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,

)

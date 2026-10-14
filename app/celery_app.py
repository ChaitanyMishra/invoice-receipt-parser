from celery import Celery

celery_app = Celery(
"invoice parser",
broker="redis://localhost:6379/0",
backend="redis://localhost:6379/1",
include=['app.tasks'],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

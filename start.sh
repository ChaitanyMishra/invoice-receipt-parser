#!/bin/sh

# Start Celery in the background
celery -A app.celery_app worker --loglevel=info --concurrency=1 &

# Start Uvicorn in the foreground (keeps the container alive)
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

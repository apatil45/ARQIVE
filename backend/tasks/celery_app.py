"""
Celery app. Ingestion tasks added in Session 7.
"""
from __future__ import annotations

from celery import Celery
import os
from pathlib import Path

_env = Path(__file__).resolve().parents[1] / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "arqive",
    broker=redis_url,
    backend=redis_url,
    include=["tasks.ingest_task"],  # Session 7: full ingestion
)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

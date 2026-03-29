import os
from celery import Celery

app = Celery(
    "artiFACT",
    broker=os.getenv("REDIS_URL", "redis://redis:6379"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379"),
)

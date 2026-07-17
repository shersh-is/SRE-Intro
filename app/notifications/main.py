"""QuickTicket Notifications — Receive notifications about failures"""

import os
import uuid
import time
import random
import logging

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import Response
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# --- Config (fault injection via env vars) ---
NOTIFY_FAILURE_RATE = float(os.getenv("NOTIFY_FAILURE_RATE", "0.0"))
NOTIFY_LATENCY_MS = int(os.getenv("NOTIFY_LATENCY_MS", "0"))

# --- Logging ---
logging.basicConfig(
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"notifications","msg":"%(message)s"}',
    level=logging.INFO,
)
log = logging.getLogger("notifications")

# --- App ---
app = FastAPI(title="QuickTicket Notifications", version="1.0.0")

# --- Prometheus metrics ---
REQUEST_COUNT = Counter(
    "notifications_requests_total",
    "Total requests",
    ["method", "path", "status"],
)

REQUEST_DURATION = Histogram(
    "notifications_request_duration_seconds",
    "Request duration",
    ["method", "path"],
)

NOTIFY_TOTAL = Counter(
    "notifications_notify_total",
    "Total notification attempts",
    ["result"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()

    response = await call_next(request)

    duration = time.time() - start
    path = request.url.path

    if not path.startswith("/metrics"):
        REQUEST_COUNT.labels(
            request.method,
            path,
            response.status_code,
        ).inc()

        REQUEST_DURATION.labels(
            request.method,
            path,
        ).observe(duration)

    return response


@app.post("/notify")
def notify(payload: dict):
    # Simulate latency
    if NOTIFY_LATENCY_MS > 0:
        time.sleep(NOTIFY_LATENCY_MS / 1000)

    event = payload.get("event")
    order_id = payload.get("order_id")

    if not event or not order_id:
        raise HTTPException(
            status_code=400,
            detail="event and order_id are required",
        )

    # Simulate failure
    if random.random() < NOTIFY_FAILURE_RATE:
        NOTIFY_TOTAL.labels(result="failed").inc()

        log.error(
            f'Notification failed: event="{event}", order_id="{order_id}"'
        )

        raise HTTPException(
            status_code=500,
            detail="Notification service failure",
        )

    notification_id = str(uuid.uuid4())

    NOTIFY_TOTAL.labels(result="success").inc()

    log.info(
        f'Notification sent: id="{notification_id}", event="{event}", order_id="{order_id}"'
    )

    return {
        "status": "sent",
        "notification_id": notification_id,
        "event": event,
        "order_id": order_id,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "failure_rate": NOTIFY_FAILURE_RATE,
        "latency_ms": NOTIFY_LATENCY_MS,
    }


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

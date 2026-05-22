"""Client-side telemetry ingestion.

The mobile client posts one row per turn-side event (mic stop, STT done,
TTS start, TTS end) so the backend's JSONL log unifies both sides of
the round trip. Every event is replayed through the same telemetry
helper, so it appears in the demo log inline with backend events.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from api.telemetry import log_event, set_request_context

router = APIRouter()


class ClientMetric(BaseModel):
    scenario_id: Optional[str] = None
    turn_idx: Optional[int] = None
    category: str = "CLIENT"
    message: str = ""
    duration_ms: Optional[float] = None
    fields: Dict[str, Any] = {}


@router.post("/_client_metric")
async def client_metric(metric: ClientMetric):
    set_request_context(metric.scenario_id, metric.turn_idx)
    try:
        log_event(
            metric.category,
            metric.message,
            duration_ms=metric.duration_ms,
            **metric.fields,
        )
    finally:
        set_request_context(None, None)
    return {"ok": True}

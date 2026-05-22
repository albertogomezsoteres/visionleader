"""Telemetry middleware: tag each turn with scenario/turn headers and
emit a ``[TURN]`` event with backend-internal latency.

Reads ``X-Scenario-Id`` and ``X-Turn-Idx`` from the incoming request,
binds them into the per-request telemetry context (so every nested
``log_event`` is tagged), and wraps the handler with a wall-clock
measurement. Other endpoints pass through untouched.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from api.telemetry import log_event, log_separator, set_request_context


_TRACKED_PATHS = ("/api/conversation", "/api/analyze-image")


class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not any(path.startswith(p) for p in _TRACKED_PATHS):
            return await call_next(request)

        scenario_id = request.headers.get("X-Scenario-Id")
        turn_idx_raw = request.headers.get("X-Turn-Idx")
        try:
            turn_idx = int(turn_idx_raw) if turn_idx_raw is not None else None
        except ValueError:
            turn_idx = None

        set_request_context(scenario_id, turn_idx)

        # Visual separator between turns. Always emitted on tracked paths
        # so the live demo terminal reads as a clean sequence of turns.
        title_parts = []
        if scenario_id is not None and turn_idx is not None:
            title_parts.append(f"{scenario_id} · turn {turn_idx}")
        title_parts.append(f"{request.method} {path}")
        log_separator(title=" · ".join(title_parts))

        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            try:
                log_event(
                    "AGENT",
                    f"turn handled by backend",
                    duration_ms=elapsed_ms,
                    endpoint=path,
                    backend_internal_ms=elapsed_ms,
                )
            except Exception:
                pass
            set_request_context(None, None)

        return response

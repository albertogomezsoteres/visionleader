"""End-to-end validation telemetry — one helper, two sinks.

* **stdout** — pretty, color-coded line per event for the live demo log.
* **JSONL** — structured one-event-per-line file for post-processing of
  validation runs. Active only when ``TELEMETRY_JSONL_PATH`` is set.

The same call (:func:`log_event`) drives both. ``X-Scenario-Id`` and
``X-Turn-Idx`` headers set by the mobile client (or by the post script
when it replays a session) flow into per-request context via
:func:`set_request_context`, so every event ends up tagged.

Telemetry is exception-safe by construction: any failure inside the
helper is swallowed so a broken log never crashes a request.
"""

from __future__ import annotations

import contextvars
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from colorama import Fore, Style, init as _colorama_init
    _colorama_init()
    _COLORS = {
        "STT":        Fore.CYAN,
        "VLM":        Fore.MAGENTA,
        "PLANNER":    Fore.GREEN,
        "PLAN":       Fore.GREEN,
        "AGENT":      Fore.YELLOW,
        "TTS":        Fore.BLUE,
        "TURN":       Fore.WHITE + Style.BRIGHT,
        "CLOSURE":    Style.DIM,
        "ROUTE":      Style.DIM,
        "CLIENT":     Fore.LIGHTBLACK_EX,
        "FSM":        Fore.LIGHTBLUE_EX,
        "VALIDATION": Fore.LIGHTGREEN_EX,
        "SCENARIO":   Fore.WHITE + Style.BRIGHT,
    }
    _RESET = Style.RESET_ALL
except Exception:
    _COLORS = {}
    _RESET = ""


# Display label per category. STT and TTS run on the Flutter device, so we
# tag them explicitly in the log; everything else runs in the backend
# Python process and shows just its category name.
_CATEGORY_LABELS = {
    "STT": "STT FLUTTER",
    "TTS": "TTS FLUTTER",
}
_CATEGORY_COL_WIDTH = 11


_scenario_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "telemetry_scenario_id", default=None
)
_turn_idx: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "telemetry_turn_idx", default=None
)


def set_request_context(scenario_id: Optional[str], turn_idx: Optional[int]) -> None:
    """Bind scenario and turn for every event emitted from this request."""
    _scenario_id.set(scenario_id)
    if turn_idx is None:
        _turn_idx.set(None)
        return
    try:
        _turn_idx.set(int(turn_idx))
    except (TypeError, ValueError):
        _turn_idx.set(None)


_JSONL_PATH: Optional[Path] = None
_JSONL_RESOLVED: bool = False


def _resolve_jsonl_path() -> Optional[Path]:
    global _JSONL_PATH, _JSONL_RESOLVED
    if _JSONL_RESOLVED:
        return _JSONL_PATH
    raw = os.getenv("TELEMETRY_JSONL_PATH")
    if raw:
        p = Path(raw)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        _JSONL_PATH = p
    _JSONL_RESOLVED = True
    return _JSONL_PATH


def log_event(
    category: str,
    message: str,
    *,
    duration_ms: Optional[float] = None,
    **fields: Any,
) -> None:
    """Emit one event to all sinks (stdout + JSONL). Never raises."""
    try:
        ts = datetime.now(timezone.utc)
        scenario = _scenario_id.get()
        turn = _turn_idx.get()
        try:
            print(_format_line(ts, category, message, duration_ms, scenario, turn), flush=True)
        except Exception:
            pass

        payload = {
            "ts": ts.isoformat(),
            "category": category,
            "message": message,
            "duration_ms": duration_ms,
            "scenario_id": scenario,
            "turn_idx": turn,
        }
        payload.update(fields)

        path = _resolve_jsonl_path()
        if path is not None:
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
            except OSError:
                pass
    except Exception:
        pass


def _format_line(
    ts: datetime,
    category: str,
    message: str,
    duration_ms: Optional[float],
    scenario: Optional[str],
    turn: Optional[int],
) -> str:
    color = _COLORS.get(category, "")
    label = _CATEGORY_LABELS.get(category, category)
    hms = ts.astimezone().strftime("%H:%M:%S.%f")[:-3]
    parts = [f"[{hms}]"]
    if scenario is not None:
        tn = turn if turn is not None else "?"
        parts.append(f"[{scenario}/T{tn}]")
    parts.append(f"[{label:<{_CATEGORY_COL_WIDTH}}]")
    suffix = f"  ({duration_ms:.0f} ms)" if duration_ms is not None else ""
    return f"{color}{' '.join(parts)}{_RESET}  {message}{suffix}"


def log_separator(title: Optional[str] = None) -> None:
    """Print a thin horizontal rule for visually separating turns.

    When ``title`` is provided it is printed inline with the rule, in the
    TURN colour, so the operator can scan turn boundaries at a glance.
    """
    try:
        color = _COLORS.get("TURN", "")
        rule = "─" * 76
        if title:
            print(f"{color}\n┄┄┄  {title}  {'┄' * max(0, 70 - len(title))}{_RESET}",
                  flush=True)
        else:
            print(f"{color}{rule}{_RESET}", flush=True)
    except Exception:
        pass


@contextmanager
def time_block(category: str, message: str, **fields: Any):
    """Measure a code block and emit the event with its duration on exit."""
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        log_event(category, message, duration_ms=elapsed_ms, **fields)

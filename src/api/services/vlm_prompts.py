"""Prompt catalogue and response parsers for the navigation VLM.

Loads the Gemma 4 E4B prompts from
``config/prompts.json`` and exposes two operations:

* :func:`build_prompt` returns the raw text to send to the model.
* :func:`parse_response` turns the model output into a structured
  :class:`ParsedResponse` (PDDL atom or JSON state, depending on the
  prompt family).

This is the runtime prompt catalogue read by the backend.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROMPTS_PATH = Path(__file__).resolve().parents[3] / "config" / "prompts.json"

_PROMPTS: Optional[Dict[str, Dict[str, Any]]] = None


def _load() -> Dict[str, Dict[str, Any]]:
    global _PROMPTS
    if _PROMPTS is None:
        with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
            _PROMPTS = json.load(f)["prompts"]
    return _PROMPTS


def valid_prompt_ids() -> tuple[str, ...]:
    return tuple(_load().keys())


@dataclass
class ParsedResponse:
    """Outcome of parsing a single VLM response.

    Exactly one of ``location_id`` or ``state_type`` is populated for a
    successful parse. ``ok=False`` means the raw output did not match the
    prompt's expected format.
    """
    ok: bool
    location_id: Optional[str] = None
    state_type: Optional[str] = None
    state_detail: Optional[str] = None


def build_prompt(prompt_id: str) -> str:
    prompts = _load()
    if prompt_id not in prompts:
        raise KeyError(f"unknown prompt_id: {prompt_id!r}")
    text = prompts[prompt_id]["prompt_text"]
    return text if text.startswith("<image>") else f"<image>\n{text}"


_ATOM_RE = re.compile(r"\(\s*at\s+user\s+([a-zA-Z0-9_]+)\s*\)", re.IGNORECASE)
_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def parse_response(prompt_id: str, raw: str) -> ParsedResponse:
    spec = _load().get(prompt_id)
    if spec is None or not raw:
        return ParsedResponse(ok=False)

    fmt = spec["response_format"]

    if fmt == "pddl_atom":
        m = _ATOM_RE.search(raw)
        if not m:
            return ParsedResponse(ok=False)
        loc_id = m.group(1)
        if loc_id not in spec.get("valid_location_ids", []):
            return ParsedResponse(ok=False)
        return ParsedResponse(ok=True, location_id=loc_id)

    if fmt == "json_state":
        m = _JSON_RE.search(raw)
        if not m:
            return ParsedResponse(ok=False)
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return ParsedResponse(ok=False)
        schema = spec.get("expected_json_schema", {})
        type_value = obj.get("type")
        detail_value = obj.get("detail")
        if type_value != schema.get("type"):
            return ParsedResponse(ok=False)
        if detail_value not in schema.get("detail", []):
            return ParsedResponse(ok=False)
        return ParsedResponse(ok=True, state_type=type_value, state_detail=detail_value)

    return ParsedResponse(ok=False)

"""Image analysis service: thin proxy to the Colab VLM endpoint.

The mobile FSM tells us which prompt to run via ``prompt_id``. We build
the prompt text from the validated catalogue, forward image + prompt to
the Colab Gemma 4 E4B endpoint, and parse the response into the shape
the conversation agent expects.

One model call per photo. No classifier stage.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

from api.schemas import ImageAnalysisResponse
from api.services.vlm_prompts import build_prompt, parse_response
from api.telemetry import log_event

_REQUEST_TIMEOUT_S = 30
_MAX_TOKENS_BY_FORMAT = {"pddl_atom": 32, "json_state": 24}


def analyze_image(
    image_data: bytes,
    filename: str,
    content_type: str,
    prompt_id: str,
    colab_url: str,
) -> ImageAnalysisResponse:
    prompt = build_prompt(prompt_id)
    max_tokens = _MAX_TOKENS_BY_FORMAT.get(_response_format(prompt_id), 32)

    log_event(
        "VLM", f"prompt={prompt_id} size={len(image_data)} bytes",
        prompt_id=prompt_id, image_bytes=len(image_data),
    )

    started = time.perf_counter()
    try:
        http_response = requests.post(
            f"{colab_url}/analyze",
            files={"file": (filename, image_data, content_type)},
            data={"prompt": prompt, "max_tokens": str(max_tokens)},
            timeout=_REQUEST_TIMEOUT_S,
        )
    except requests.RequestException as error:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        log_event(
            "VLM", f"colab request failed: {error}",
            duration_ms=elapsed_ms, prompt_id=prompt_id, error=str(error),
        )
        return ImageAnalysisResponse(
            success=False, prompt_id=prompt_id,
            raw_response="", error=f"colab request failed: {error}",
        )

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    if http_response.status_code != 200:
        log_event(
            "VLM", f"HTTP {http_response.status_code}",
            duration_ms=elapsed_ms, prompt_id=prompt_id,
            http_status=http_response.status_code,
        )
        return ImageAnalysisResponse(
            success=False, prompt_id=prompt_id, raw_response="",
            error=f"colab HTTP {http_response.status_code} ({elapsed_ms/1000.0:.2f}s)",
        )

    body = http_response.json()
    raw = (body.get("response") or "").strip()
    log_event(
        "VLM", f"raw={raw!r}",
        duration_ms=elapsed_ms, prompt_id=prompt_id, raw_response=raw,
    )

    if not body.get("success") or not raw:
        log_event(
            "VLM", "empty colab response",
            prompt_id=prompt_id, error="empty colab response",
        )
        return ImageAnalysisResponse(
            success=False, prompt_id=prompt_id, raw_response=raw,
            error="empty colab response",
        )

    parsed = parse_response(prompt_id, raw)
    if parsed.ok:
        log_event(
            "VLM", f"neural prediction:  {raw}",
            prompt_id=prompt_id, raw_response=raw,
        )
        if parsed.location_id is not None:
            log_event(
                "VLM",
                f"symbol grounded:    location_id={parsed.location_id} "
                f"∈ valid_location_ids  ✓",
                prompt_id=prompt_id,
                location_id=parsed.location_id,
                schema="pddl_atom",
            )
        else:
            log_event(
                "VLM",
                f"symbol grounded:    state={parsed.state_type}/{parsed.state_detail}  ✓",
                prompt_id=prompt_id,
                state_type=parsed.state_type,
                state_detail=parsed.state_detail,
                schema="json_state",
            )
    else:
        log_event(
            "VLM",
            f"neural prediction:  {raw!r}",
            prompt_id=prompt_id, raw_response=raw,
        )
        log_event(
            "VLM",
            "symbol grounding FAILED  ✗  (output rejected by prompt schema)",
            prompt_id=prompt_id, parse_ok=False,
        )

    return ImageAnalysisResponse(
        success=parsed.ok,
        prompt_id=prompt_id,
        location_id=parsed.location_id,
        state_type=parsed.state_type,
        state_detail=parsed.state_detail,
        raw_response=raw,
    )


def _response_format(prompt_id: str) -> str:
    from api.services.vlm_prompts import _load
    return _load().get(prompt_id, {}).get("response_format", "")

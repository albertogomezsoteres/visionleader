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

    print(f"\n[VLM] prompt_id={prompt_id} size={len(image_data)} bytes")

    started = time.time()
    try:
        http_response = requests.post(
            f"{colab_url}/analyze",
            files={"file": (filename, image_data, content_type)},
            data={"prompt": prompt, "max_tokens": str(max_tokens)},
            timeout=_REQUEST_TIMEOUT_S,
        )
    except requests.RequestException as error:
        print(f"[VLM][ERROR] colab request failed: {error}")
        return ImageAnalysisResponse(
            success=False, prompt_id=prompt_id,
            raw_response="", error=f"colab request failed: {error}",
        )

    elapsed = time.time() - started

    if http_response.status_code != 200:
        print(f"[VLM][ERROR] HTTP {http_response.status_code} in {elapsed:.2f}s")
        return ImageAnalysisResponse(
            success=False, prompt_id=prompt_id, raw_response="",
            error=f"colab HTTP {http_response.status_code} ({elapsed:.2f}s)",
        )

    body = http_response.json()
    raw = (body.get("response") or "").strip()
    print(f"[VLM][RAW] {raw!r}  ({elapsed:.2f}s)")

    if not body.get("success") or not raw:
        print(f"[VLM][REJECTED] empty colab response")
        return ImageAnalysisResponse(
            success=False, prompt_id=prompt_id, raw_response=raw,
            error="empty colab response",
        )

    parsed = parse_response(prompt_id, raw)
    if parsed.ok:
        extracted = parsed.location_id or f"{parsed.state_type}/{parsed.state_detail}"
        print(f"[VLM][PARSED] {extracted}")
    else:
        print(f"[VLM][PARSED] FAILED to extract from {raw!r}")

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

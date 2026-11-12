"""The neuro-symbolic interface: VLM text in, symbolic claim out (or rejected)."""

from __future__ import annotations

import pytest

from visionleader.api.services import vlm_prompts


def test_catalogue_exposes_every_prompt_family() -> None:
    ids = set(vlm_prompts.valid_prompt_ids())
    assert {"room_plate", "directory_sign", "elevator_state", "stair_direction"} <= ids


@pytest.mark.parametrize("prompt_id", vlm_prompts.valid_prompt_ids())
def test_build_prompt_always_carries_the_image_token(prompt_id: str) -> None:
    text = vlm_prompts.build_prompt(prompt_id)
    assert text.startswith("<image>")
    assert len(text) > len("<image>\n")


def test_build_prompt_rejects_unknown_ids() -> None:
    with pytest.raises(KeyError):
        vlm_prompts.build_prompt("not_a_prompt")


@pytest.mark.parametrize(
    "raw",
    [
        "(at user classroom_g_1_4)",
        "The answer is (at  user  classroom_g_1_4) based on the plate.",
        "(AT USER classroom_g_1_4)",
    ],
)
def test_pddl_atom_is_extracted_from_noisy_output(raw: str) -> None:
    parsed = vlm_prompts.parse_response("room_plate", raw)
    assert parsed.ok
    assert parsed.location_id == "classroom_g_1_4"


@pytest.mark.parametrize(
    "raw",
    [
        "(at user classroom_z_9_9)",  # not in the closed vocabulary
        "classroom 1.4",  # no atom at all
        "",
    ],
)
def test_pddl_atom_outside_the_vocabulary_is_rejected(raw: str) -> None:
    assert not vlm_prompts.parse_response("room_plate", raw).ok


def test_json_state_is_validated_against_its_schema() -> None:
    parsed = vlm_prompts.parse_response(
        "elevator_state", 'Sure: {"type": "elevator", "detail": "open"}'
    )
    assert parsed.ok
    assert (parsed.state_type, parsed.state_detail) == ("elevator", "open")


@pytest.mark.parametrize(
    ("prompt_id", "raw"),
    [
        ("elevator_state", '{"type": "elevator", "detail": "half-open"}'),  # bad detail
        ("elevator_state", '{"type": "stairs", "detail": "up"}'),  # wrong type
        ("stair_direction", "{not json}"),
        ("stair_direction", "up"),
    ],
)
def test_malformed_or_off_schema_states_are_rejected(prompt_id: str, raw: str) -> None:
    assert not vlm_prompts.parse_response(prompt_id, raw).ok


def test_unknown_prompt_never_parses() -> None:
    assert not vlm_prompts.parse_response("not_a_prompt", "(at user classroom_g_1_4)").ok

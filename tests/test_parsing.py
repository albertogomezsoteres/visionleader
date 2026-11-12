"""Free-form utterance parsing: the step between the transcript and the planner."""

from __future__ import annotations

import csv

import pytest

from visionleader.navigation.agent import parsing
from visionleader.paths import REPO_ROOT

G, CD, H, P = 1, 2, 3, 4


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("yes", True),
        ("Yes, please.", True),
        ("sí, vale", True),
        ("no", False),
        ("No!", False),
    ],
)
def test_is_yes(message: str, expected: bool) -> None:
    assert parsing.is_yes(message) is expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [("no", True), ("nope, wrong one", True), ("no... yes, correct", False), ("yes", False)],
)
def test_is_no_requires_a_negation_without_an_affirmation(message: str, expected: bool) -> None:
    assert parsing.is_no(message) is expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("G", G),
        ("building CD", CD),
        ("the sports centre", CD),
        ("edificio H", H),
        ("I am in building P", P),
        ("I'm in building H", H),
    ],
)
def test_extract_building(message: str, expected: int) -> None:
    assert parsing.extract_building(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "I want to go to the cafeteria",  # the "h" and "e" inside words
        "Repeat the instructions please",
        "I'm at the cafeteria",  # the apostrophe makes "m" a word on its own
        "Yes I am ready to continue",
    ],
)
def test_building_codes_only_match_as_whole_words(message: str) -> None:
    assert parsing.extract_building(message) is None


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("ground floor", 0),
        ("planta baja", 0),
        ("the second floor", 2),
        ("basement", -1),
        ("floor 1", 1),
        ("nothing here", None),
    ],
)
def test_extract_floor(message: str, expected: int | None) -> None:
    assert parsing.extract_floor(message) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [("1.4", "1.4"), ("14", "1.4"), ("01.04", "1.4"), ("Aula 3", "aula 3")],
)
def test_normalize_room_code(code: str, expected: str) -> None:
    assert parsing.normalize_room_code(code) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(at user classroom_g_1_4)", "classroom_g_1_4"),
        ("  ( AT user Directory_Sign_G_0 ) trailing", "directory_sign_g_0"),
        ("I think it is classroom 1.4", None),
        ("", None),
    ],
)
def test_extract_location_id_from_pddl(raw: str, expected: str | None) -> None:
    assert parsing.extract_location_id_from_pddl(raw) == expected


def test_room_code_from_analysis_handles_both_buildings() -> None:
    assert parsing.extract_room_code_from_analysis({"location_id": "classroom_g_1_4"}) == "1.4"
    assert parsing.extract_room_code_from_analysis({"location_id": "classroom_cd_3"}) == "3"
    assert (
        parsing.extract_room_code_from_analysis({"raw_response": "(at user classroom_g_0_2)"})
        == "0.2"
    )
    assert parsing.extract_room_code_from_analysis(None) is None


def test_parse_location_from_room_code(room_lookup: dict) -> None:
    loc = parsing.parse_location("I am in classroom 1.4", room_lookup)
    assert loc == {"building": G, "floor": 1, "location_id": "classroom_g_1_4"}


def test_contraction_does_not_override_the_room_lookup(room_lookup: dict) -> None:
    # Regression: "I'm" used to match building M and relabel a G classroom.
    loc = parsing.parse_location("I'm in classroom 1.4", room_lookup)
    assert loc == {"building": G, "floor": 1, "location_id": "classroom_g_1_4"}


@pytest.mark.parametrize(
    ("message", "location_id"),
    [
        ("I am at entrance 2 of building G", "entrance_2"),
        ("entrance two", "entrance_2"),  # Whisper often writes "to" for "two"
        ("entrance to", "entrance_2"),
        ("I am at the main entrance", "entrance_2"),
    ],
)
def test_parse_location_entrances(room_lookup: dict, message: str, location_id: str) -> None:
    loc = parsing.parse_location(message, room_lookup)
    assert loc is not None
    assert loc["location_id"] == location_id
    assert loc["building"] == G


def test_every_initial_location_utterance_in_the_stt_set_parses(room_lookup: dict) -> None:
    """The utterances recorded for the STT benchmark must stay groundable."""
    manifest = REPO_ROOT / "data" / "stt" / "manifest.csv"
    with manifest.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["category"] == "initial_location"]
    assert rows, "no initial_location utterances in the STT manifest"
    for row in rows:
        loc = parsing.parse_location(row["reference_transcript"], room_lookup)
        assert loc is not None, row["reference_transcript"]
        assert loc["building"] == G, row["reference_transcript"]

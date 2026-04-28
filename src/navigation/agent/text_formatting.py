"""Display helpers: turn building ids, floor numbers and PDDL location ids
into natural-English fragments suitable for TTS.

All functions here are pure: they take primitives or simple dicts and
return strings. Nothing touches state or files.
"""

import re
from typing import Dict, Optional


BUILDING_NAMES: Dict[int, str] = {
    1: "G",   2: "CD",  3: "H",   4: "P",
    5: "O",   6: "M",   7: "N",   8: "CSQ",
    9: "K",  10: "CSC", 11: "C",  12: "E",
    13: "CM", 14: "LCB", 15: "Rodilla", 16: "Chapel",
}

BUILDING_FULL: Dict[int, str] = {
    1:  "Building G (EPS)",
    2:  "Building CD (Centro Deportivo)",
    3:  "Building H",
    4:  "Building P",
    5:  "Building O",
    6:  "Building M",
    7:  "Building N",
    8:  "Building CSQ",
    9:  "Building K",
    10: "Building CSC",
    11: "Building C",
    12: "Building E",
    13: "Building CM",
    14: "Building LCB",
    15: "Rodilla",
    16: "Chapel (UFV Chapel)",
}


PHOTO_LABELS: Dict[str, str] = {
    "room_plate": "classroom door plate",
    "directory_sign": "directory sign",
    "elevator_state": "elevator",
    "stair_direction": "stairs",
    "restroom_gender": "restroom sign",
}


def photo_label(prompt_id: Optional[str]) -> str:
    """TTS-friendly phrase for a VLM prompt id (e.g. 'elevator_state' -> 'elevator')."""
    if not prompt_id:
        return "area"
    return PHOTO_LABELS.get(prompt_id, prompt_id.replace("_", " "))


def floor_text(f: int) -> str:
    """Render a floor number as a human-readable English fragment."""
    if f == -1:
        return "the basement (floor -1)"
    if f == 0:
        return "the ground floor"
    return f"floor {f}"


def get_building_name(building_id: int) -> str:
    """Short building label (e.g. 'G', 'CD'). Falls back to the raw id."""
    return BUILDING_NAMES.get(building_id, str(building_id))


def nice_location_name(loc_id: str) -> str:
    """Render a campus_topology location id as a natural English name."""
    mapping = {
        "entrance_main": "the main entrance",
        "entrance_cd": "the Sports Centre entrance",
        "elevator": "the elevator",
        "stairs": "the stairs",
        "bathroom": "the restroom",
        "ai_lab": "the AI Laboratory",
        "offices": "the faculty offices",
        "eps_offices": "the EPS Faculty Offices",
        "admin_office": "the Secretary Office",
        "mentoring_room": "the Mentoring Room",
        "cafeteria": "the cafeteria",
        "gym": "the gym",
    }
    if loc_id in mapping:
        return mapping[loc_id]
    m = re.match(r"classroom_g_(\d+)_(\d+)", loc_id)
    if m:
        return f"Classroom {m.group(1)}.{m.group(2)}"
    m = re.match(r"classroom_cd_(\d+)", loc_id)
    if m:
        return f"Classroom {m.group(1)} (CD)"
    return loc_id.replace("_", " ")


def location_text(loc: Optional[Dict]) -> str:
    """Render a location dict as a single English phrase ready for TTS."""
    if not loc:
        return "an unknown location"
    bid = loc.get("building")
    flr = loc.get("floor")
    lid = loc.get("location_id")
    label = loc.get("label")
    if label:
        return label

    parts = []
    if lid:
        parts.append(nice_location_name(lid))
    if bid:
        parts.append(f"in {BUILDING_FULL.get(bid, 'the building')}")
    if flr is not None and not lid:
        parts.append(f"on {floor_text(flr)}")
    return ", ".join(parts) if parts else "an unknown location"


def normalize_instruction(text: str) -> str:
    """Normalise PDDL/Spanish vocabulary to concise, English-only phrasing."""
    if not text:
        return text
    out = text
    out = out.replace("elevator", "elevator").replace("stairs", "stairs")
    out = out.replace("entrance_main", "main entrance").replace(
        "entrada principal", "main entrance"
    )
    out = re.sub(r"directory_sign_g_\w+", "directory sign", out)
    out = out.replace("ai_lab", "AI laboratory").replace("lab ia", "AI laboratory")
    out = out.replace("bathroom", "restroom")
    out = out.replace("eps_offices", "EPS faculty offices").replace(
        "offices eps", "EPS faculty offices"
    )
    out = out.replace("mentoring_room", "mentoring room").replace(
        "sala mentorias", "mentoring room"
    )
    out = re.sub(
        r"\baula[_\s]+(\d+)[_\s]+(\d+)\b", r"room \1.\2", out, flags=re.IGNORECASE
    )
    out = re.sub(r"\s+", " ", out).strip()
    return out

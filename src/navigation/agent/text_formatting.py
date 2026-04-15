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
    13: "CM", 14: "LCB", 15: "Rodilla", 16: "Capilla",
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
    16: "Capilla (UFV Chapel)",
}


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
        "entrada_principal": "the main entrance",
        "entrada_cd": "the Sports Centre entrance",
        "ascensor": "the elevator",
        "escaleras": "the stairs",
        "bano": "the restroom",
        "lab_ia": "the AI Laboratory",
        "despachos": "the faculty offices",
        "despachos_eps": "the EPS Faculty Offices",
        "secretaria": "the Secretary Office",
        "sala_mentorias": "the Mentoring Room",
        "cafeteria": "the cafeteria",
        "gimnasio": "the gym",
    }
    if loc_id in mapping:
        return mapping[loc_id]
    m = re.match(r"aula_(\d+)_(\d+)", loc_id)
    if m:
        return f"Classroom {m.group(1)}.{m.group(2)}"
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
    out = out.replace("ascensor", "elevator").replace("escaleras", "stairs")
    out = out.replace("entrada_principal", "main entrance").replace(
        "entrada principal", "main entrance"
    )
    out = (
        out.replace("directorio_0", "directory sign")
        .replace("directorio_1", "directory sign")
        .replace("directorio_2", "directory sign")
    )
    out = out.replace("lab_ia", "AI laboratory").replace("lab ia", "AI laboratory")
    out = out.replace("bano", "restroom")
    out = out.replace("despachos_eps", "EPS faculty offices").replace(
        "despachos eps", "EPS faculty offices"
    )
    out = out.replace("sala_mentorias", "mentoring room").replace(
        "sala mentorias", "mentoring room"
    )
    out = re.sub(
        r"\baula[_\s]+(\d+)[_\s]+(\d+)\b", r"room \1.\2", out, flags=re.IGNORECASE
    )
    out = re.sub(r"\s+", " ", out).strip()
    return out

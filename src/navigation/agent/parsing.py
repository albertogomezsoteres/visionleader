"""Parsing helpers: turn raw user messages and PaliGemma analysis dicts
into structured location / destination dicts.

Functions in this module are intentionally state-free: anything they need
beyond the message itself is passed in as an argument (e.g. the room
lookup table built by the agent in __init__).
"""

import re
from typing import Any, Dict, Optional, Tuple


AFFIRM = {
    "yes", "yeah", "yep", "sure", "ok", "okay", "correct", "right",
    "sí", "si", "vale", "claro", "por supuesto", "confirm", "confirmed",
}
NEGATE = {
    "no", "nope", "nah", "cancel", "wrong", "incorrect", "not",
    "don't", "dont",
}

BUILDING_MAP: Dict[str, int] = {
    "g": 1,   "politécnica": 1, "politecnica": 1, "eps": 1,
    "cd": 2,  "centro deportivo": 2, "sports": 2, "sport": 2,
    "h": 3,
    "p": 4,
    "o": 5,
    "m": 6,
    "n": 7,
    "csq": 8,
    "k": 9,
    "csc": 10,
    "c": 11,
    "e": 12,
    "cm": 13,
    "lcb": 14,
}

FLOOR_WORDS: Dict[str, int] = {
    "ground": 0, "ground floor": 0, "first": 1, "first floor": 1,
    "second": 2, "second floor": 2,
    "basement": -1, "minus one": -1, "minus 1": -1,
    "planta baja": 0, "planta 0": 0, "planta 1": 1, "planta 2": 2,
    "planta -1": -1, "floor 0": 0, "floor 1": 1, "floor 2": 2,
    "floor -1": -1, "0": 0, "1": 1, "2": 2,
}

ENTRANCE_IDS: Dict[int, str] = {
    1: "entrance_main",
    2: "entrance_cd",
    3: "entrance_main",
}


def is_yes(msg: str) -> bool:
    """True if the message reads as an affirmative answer."""
    words = set(msg.lower().split())
    return bool(words & AFFIRM)


def is_no(msg: str) -> bool:
    """True if the message reads as a negative answer (and not also affirmative)."""
    words = set(msg.lower().split())
    has_neg = bool(words & NEGATE)
    has_aff = bool(words & AFFIRM)
    return has_neg and not has_aff


def building_id_from_name(name: str) -> int:
    """Resolve a short building name (e.g. 'g', 'cd') to its numeric id."""
    return BUILDING_MAP.get(name.lower(), 0)


def entrance_id(building_id: int) -> str:
    """Canonical entrance location_id for a given building."""
    return ENTRANCE_IDS.get(building_id, "entrance_main")


def extract_building(msg: str) -> Optional[int]:
    """Best-effort extraction of a building id from a free-form message."""
    low = msg.lower().strip()
    for keyword, bid in BUILDING_MAP.items():
        if keyword in low:
            return bid
    bm = re.search(r"\b([a-z]+)\b", low)
    if bm and bm.group(1) in BUILDING_MAP:
        return BUILDING_MAP[bm.group(1)]
    return None


def extract_floor(msg: str) -> Optional[int]:
    """Best-effort extraction of a floor number from a free-form message."""
    low = msg.lower().strip()
    for phrase, fnum in sorted(FLOOR_WORDS.items(), key=lambda x: -len(x[0])):
        if phrase in low:
            return fnum
    fm = re.search(r"(-?\d+)", low)
    if fm:
        val = int(fm.group(1))
        if -1 <= val <= 10:
            return val
    return None


def normalize_room_code(code: str) -> str:
    """Normalize room-code variants to canonical form (e.g. '14' -> '1.4')."""
    raw = str(code).strip().lower()
    m = re.search(r"(\d+\.\d+)", raw)
    if m:
        s = m.group(1)
    else:
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 2 and digits[0].isdigit() and digits[1].isdigit():
            return f"{int(digits[0])}.{int(digits[1])}"
        return raw
    try:
        parts = s.split(".")
        if len(parts) == 2:
            return f"{int(parts[0])}.{int(parts[1])}"
    except Exception:
        pass
    return s.strip()


def extract_location_id_from_pddl(raw: str) -> Optional[str]:
    """Extract a PDDL ``location_id`` from a VLM response atom.

    The on-device VLM prompts emit responses like
    ``(at user classroom_g_1_4)``, ``(at user directory_sign_g_0)`` or
    ``(at user ai_lab)``. This helper pulls out the bare location id
    (``classroom_g_1_4`` / ``directory_sign_g_0`` / ``ai_lab``) so that
    callers can hand it straight to HierarchicalPDDLConverter.

    Returns None when the string doesn't match the expected shape.
    """
    if not raw:
        return None
    match = re.search(
        r"\(\s*at\s+\w+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\)",
        str(raw),
        re.IGNORECASE,
    )
    return match.group(1).lower() if match else None


def extract_room_code_from_analysis(analysis: Optional[Dict]) -> Optional[str]:
    """Try to recover a canonical room code from a VLM analysis dict.

    Accepts three input shapes, in order of preference:
      1. A PDDL-style location_id field (``classroom_g_1_4`` -> ``1.4``),
         which is what the on-device Gemma 3n pipeline emits.
      2. Structured ``landmarks`` entries (legacy PaliGemma output).
      3. The raw response text (``'1.4'`` or bare ``'14'``).
    """
    if not analysis:
        return None

    # Preferred: explicit location_id field from LocalVlmService.
    location_id = analysis.get("location_id")
    if location_id:
        match = re.match(r"classroom_g_(\d+)_(\d+)", str(location_id).lower())
        if match:
            return normalize_room_code(f"{match.group(1)}.{match.group(2)}")

    for lm in analysis.get("landmarks", []) or []:
        match = re.search(r"(\d+\.\d+)", str(lm))
        if match:
            return normalize_room_code(match.group(1))
        compact = re.search(r"\b(\d{2})\b", str(lm))
        if compact:
            return normalize_room_code(compact.group(1))

    raw = analysis.get("raw_response") or analysis.get("raw") or ""
    # On-device VLM PDDL style: "(at user classroom_g_1_4)" -> "1.4"
    classroom = re.search(r"classroom_g_(\d+)_(\d+)", str(raw).lower())
    if classroom:
        return normalize_room_code(f"{classroom.group(1)}.{classroom.group(2)}")

    match = re.search(r"(\d+\.\d+)", str(raw))
    if match:
        return normalize_room_code(match.group(1))
    compact = re.search(r"\b(\d{2})\b", str(raw))
    if compact:
        return normalize_room_code(compact.group(1))
    return None


def parse_location(msg: str, room_lookup: Dict[str, Tuple[int, int, str]]) -> Optional[Dict]:
    """Parse a user message into ``{building, floor, location_id}``.

    ``room_lookup`` is the precomputed map ``room_code -> (building, floor, location_id)``
    that the agent builds at startup from campus_places.json.
    """
    low = msg.lower().strip()
    result: Dict[str, Any] = {"building": None, "floor": None, "location_id": None}

    room_match = re.search(r"\b(\d+\.\d+)\b", low)
    if room_match:
        code = room_match.group(1)
        if code in room_lookup:
            bid, fnum, loc_id = room_lookup[code]
            result["building"] = bid
            result["floor"] = fnum
            result["location_id"] = loc_id

    for keyword, bid in BUILDING_MAP.items():
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, low):
            result["building"] = bid
            break
    if result["building"] is None:
        bm = re.search(r"\bbuilding\s+([a-z]+)\b", low)
        if bm:
            result["building"] = BUILDING_MAP.get(bm.group(1))
        em = re.search(r"\bedificio\s+([a-z]+)\b", low)
        if em:
            result["building"] = BUILDING_MAP.get(em.group(1))

    if result["floor"] is None:
        for phrase, fnum in sorted(FLOOR_WORDS.items(), key=lambda x: -len(x[0])):
            if phrase in low:
                result["floor"] = fnum
                break
        if result["floor"] is None:
            fm = re.search(r"\bfloor\s+(-?\d+)\b", low)
            if fm:
                result["floor"] = int(fm.group(1))
            pm = re.search(r"\bplanta\s+(-?\d+)\b", low)
            if pm:
                result["floor"] = int(pm.group(1))

    if result["location_id"] is None:
        if any(w in low for w in ("entrance", "entrada", "main entrance", "entrada principal")):
            result["location_id"] = "entrance_main"
            if result["building"] is None:
                result["building"] = 1
            if result["floor"] is None:
                result["floor"] = 0
        elif any(w in low for w in ("elevator", "elevator", "lift")):
            result["location_id"] = "elevator"
        elif any(w in low for w in ("stair", "escalera")):
            result["location_id"] = "stairs"
        elif any(w in low for w in ("restroom", "bathroom", "baño", "aseo", "toilet")):
            result["location_id"] = "bathroom"
        elif any(w in low for w in (
            "ai lab", "laboratorio ia", "laboratorio de ia",
            "lab ia", "ia lab", "ai laboratory",
        )):
            result["location_id"] = "ai_lab"
            if result["building"] is None:
                result["building"] = 1
            if result["floor"] is None:
                result["floor"] = 0
        elif any(w in low for w in ("office", "despacho", "faculty", "profesor")):
            result["location_id"] = "offices"
            if result["building"] is None:
                result["building"] = 1
            if result["floor"] is None:
                result["floor"] = 1
        elif any(w in low for w in ("secretary", "secretar")):
            result["location_id"] = "admin_office"
            if result["building"] is None:
                result["building"] = 1
            if result["floor"] is None:
                result["floor"] = 2
        elif any(w in low for w in ("mentoring", "mentoría", "mentoria", "tutoring")):
            result["location_id"] = "mentoring_room"
            if result["building"] is None:
                result["building"] = 1
            if result["floor"] is None:
                result["floor"] = 2
        elif any(w in low for w in (
            "eps office", "eps faculty", "despacho eps", "offices eps",
        )):
            result["location_id"] = "eps_offices"
            if result["building"] is None:
                result["building"] = 1
            if result["floor"] is None:
                result["floor"] = 2

    if (
        result["building"] is None
        and result["floor"] is not None
        and result["location_id"]
    ):
        if result["location_id"].startswith("classroom_g_"):
            result["building"] = 1
        elif result["location_id"].startswith("classroom_cd_"):
            result["building"] = 2

    if result["building"] is None and result["floor"] is None and result["location_id"] is None:
        return None

    return result


def parse_destination(
    msg: str,
    room_lookup: Dict[str, Tuple[int, int, str]],
    last_origin: Optional[Dict] = None,
    functional_locations: Optional[Dict] = None,
) -> Optional[Dict]:
    """Parse a destination from a free-form user message.

    ``last_origin`` is used to resolve the "nearest restroom" shortcut.
    ``functional_locations`` is the campus-level mapping for cafeteria/gym
    (typically the ``functional_locations`` block inside the topology JSON);
    when missing, sensible defaults are used.
    """
    low = msg.lower().strip()
    fl_data = functional_locations or {}

    if any(w in low for w in ("rodilla", "sandwich", "bocadillo")):
        return {
            "building": 15, "floor": 0, "location_id": "entrance_rodilla",
            "label": "Rodilla",
        }
    if any(w in low for w in ("capilla", "chapel", "iglesia")):
        return {
            "building": 16, "floor": 0, "location_id": "entrance_chapel",
            "label": "the UFV Chapel",
        }

    if any(w in low for w in ("cafeteria", "cafetería", "cafe", "coffee")):
        fl = fl_data.get("cafeteria", {})
        return {
            "building": fl.get("building", 2),
            "floor": fl.get("floor", 0),
            "location_id": "cafeteria",
            "label": "the cafeteria",
            "functional": "cafeteria",
        }
    if any(w in low for w in ("gym", "gym", "gymnasium", "sport")):
        fl = fl_data.get("gym", {})
        return {
            "building": fl.get("building", 2),
            "floor": fl.get("floor", -1),
            "location_id": "gym",
            "label": "the gym",
            "functional": "gym",
        }

    if any(w in low for w in (
        "ai lab", "laboratorio ia", "laboratorio de ia",
        "lab ia", "ia lab", "ai laboratory",
    )):
        return {
            "building": 1, "floor": 0, "location_id": "ai_lab",
            "label": "the AI Laboratory",
        }
    if any(w in low for w in (
        "eps office", "eps faculty", "despacho eps",
        "offices eps", "eps professor",
    )):
        return {
            "building": 1, "floor": 2, "location_id": "eps_offices",
            "label": "the EPS Faculty Offices",
        }
    if any(w in low for w in ("faculty office", "despacho", "profesor")):
        return {
            "building": 1, "floor": 1, "location_id": "offices",
            "label": "the faculty offices",
        }
    if any(w in low for w in ("mentoring", "mentoría", "mentoria", "tutoring")):
        return {
            "building": 1, "floor": 2, "location_id": "mentoring_room",
            "label": "the Mentoring Room",
        }
    if any(w in low for w in ("secretary", "secretar")):
        return {
            "building": 1, "floor": 2, "location_id": "admin_office",
            "label": "the Secretary Office",
        }
    if any(w in low for w in ("main entrance", "entrance", "entrada")):
        return {
            "building": 1, "floor": 0, "location_id": "entrance_main",
            "label": "the main entrance",
        }

    if any(w in low for w in ("restroom", "bathroom", "baño", "aseo", "toilet")):
        if last_origin:
            return {
                "building": last_origin["building"],
                "floor": last_origin["floor"],
                "location_id": "bathroom",
                "label": "the nearest restroom",
            }
        return {
            "building": 1, "floor": 0, "location_id": "bathroom",
            "label": "the restroom",
        }

    loc = parse_location(msg, room_lookup)
    if loc and (loc.get("building") or loc.get("location_id")):
        if loc.get("building") is None:
            loc["building"] = 1
        if loc.get("floor") is None and loc.get("location_id"):
            for code, (bid, fnum, lid) in room_lookup.items():
                if lid == loc["location_id"] and bid == loc["building"]:
                    loc["floor"] = fnum
                    break
        if loc.get("floor") is None:
            loc["floor"] = 0
        return loc

    return None

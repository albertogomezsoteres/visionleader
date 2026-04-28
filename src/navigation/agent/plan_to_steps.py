"""Translate Fast Downward plan output into navigation steps for the app.

:func:`fd_plan_to_steps_room_level` consumes a room-level plan from the
shared ``domain_indoor.pddl`` and produces navigation steps. Walking hops
on the same floor are merged and enriched with hints from the campus
places table. ``mover_exterior`` actions become outdoor steps with
``use_gps`` so the mobile app opens Google Maps for the exterior segment.

The function is pure: state and lookup tables are passed in as arguments
so the agent can re-use them without coupling to the FSM.
"""

import re
from typing import Dict, List, Optional, Tuple

from .text_formatting import (
    BUILDING_FULL,
    BUILDING_NAMES,
    floor_text,
    nice_location_name,
    normalize_instruction,
)


def parse_fd_action(action_str: str) -> Optional[Dict]:
    """Parse a single PDDL action string into a structured dict."""
    clean = re.sub(r"\s*\(\d+\)\s*$", "", action_str).strip()
    parts = clean.split()
    if not parts:
        return None
    return {"name": parts[0], "params": parts[1:]}


def room_code_for_location(
    places_locations: Dict,
    building_id: int,
    floor: int,
    location_id: Optional[str],
) -> Optional[str]:
    """Look up the published room code (e.g. '1.4') for a given location."""
    if not location_id:
        return None
    floor_key = str(floor)
    for bname, floors in (places_locations or {}).items():
        bid = _building_id_from_name(bname)
        if bid != building_id:
            continue
        locs = (floors or {}).get(floor_key, []) or []
        for loc in locs:
            if loc.get("id") == location_id and loc.get("room_code"):
                return str(loc.get("room_code"))
    return None


def apply_arrival_strict_photo(
    steps: List[Dict],
    destination: Dict,
    places_locations: Dict,
) -> List[Dict]:
    """If the destination is a classroom with a published room code, force
    the LAST step to be a strict door-photo checkpoint that compares the
    photographed number against the expected one.
    """
    if not steps:
        return steps

    dest_room_code = room_code_for_location(
        places_locations,
        destination.get("building"),
        destination.get("floor"),
        destination.get("location_id"),
    )
    if not dest_room_code:
        return steps

    last = steps[-1]
    if last.get("verification") != "photo":
        last["verification"] = "photo"
        last["expected_photo_type"] = "room_plate"
        last["arrival_strict_photo"] = True
        last["expected_room_code"] = dest_room_code
    else:
        last["arrival_strict_photo"] = True
        last["expected_room_code"] = dest_room_code
    return steps


def fd_plan_to_steps_room_level(
    fd_actions: List[str],
    origin: Dict,
    destination: Dict,
    places_locations: Dict,
    local_distance: Dict[str, int],
    local_hint: Dict[str, str],
) -> Optional[List[Dict]]:
    """Convert a room-level plan into navigation steps with merged walks.

    Consecutive ``caminar`` hops on the same floor are merged into a
    single walking step whose distance is the sum of all hops and whose
    directional hint is the one from the FINAL hop (the one that ends
    at the user's immediate target). Intermediate nodes the planner
    chose for distance optimisation do not appear in the TTS — the user
    only hears the final leg.

    The generated instruction follows the demo-friendly pattern::

        "Walk {N}m, {hint}."          (when hint is present)
        "Walk {N}m to {pretty_name}." (when hint is missing)
    """
    from navigation.hierarchical_pddl_converter import HierarchicalPDDLConverter

    steps: List[Dict] = []
    origin_bname = BUILDING_NAMES.get(origin.get("building"), "G")
    current_bname = origin_bname
    current_floor = origin.get("floor", 0) or 0

    walk_buffer: List[Dict] = []

    def pddl_to_json(pddl_id: str, default_floor: int, default_bname: str) -> Tuple[str, int, str]:
        base, floor, bname = HierarchicalPDDLConverter.pddl_to_location(pddl_id)
        if floor is not None:
            return base, floor, bname or default_bname
        # Unique id (classroom_X, lab_Y, entrance_*): look it up in places.
        for bn, floors in (places_locations or {}).items():
            for f_str, locs in (floors or {}).items():
                for loc in locs:
                    if loc.get("id") == base:
                        try:
                            return base, int(f_str), bn
                        except (TypeError, ValueError):
                            pass
        return base, default_floor, default_bname

    def flush_walk() -> None:
        if not walk_buffer:
            return

        total_distance = 0
        any_distance = False
        for hop in walk_buffer:
            key = f"{hop['bname']}_{hop['floor']}_{hop['json_from']}_{hop['json_to']}"
            d = local_distance.get(key)
            if d:
                total_distance += d
                any_distance = True

        final_hop = walk_buffer[-1]
        final_key = (
            f"{final_hop['bname']}_{final_hop['floor']}_"
            f"{final_hop['json_from']}_{final_hop['json_to']}"
        )
        final_hint = local_hint.get(final_key)
        final_target = nice_location_name(final_hop["json_to"])

        if any_distance and final_hint:
            sentence = f"Walk {total_distance} meters, {final_hint}."
        elif any_distance:
            sentence = f"Walk {total_distance} meters to {final_target}."
        elif final_hint:
            sentence = f"Walk to {final_target}, {final_hint}."
        else:
            sentence = f"Walk to {final_target}."

        steps.append({
            "instruction": normalize_instruction(sentence),
            "type": "local_walk",
            "verification": "voice",
            "expected_photo_type": None,
        })
        walk_buffer.clear()

    for action_str in fd_actions:
        parsed = parse_fd_action(action_str)
        if not parsed:
            continue
        name = parsed["name"]
        params = parsed["params"]

        if name in ("verify_elevator", "validate_stairs"):
            continue

        if name == "walk":
            if len(params) < 3:
                continue
            j_from, f_from, b_from = pddl_to_json(params[1], current_floor, current_bname)
            j_to, f_to, b_to = pddl_to_json(params[2], current_floor, current_bname)
            walk_buffer.append({
                "pddl_from": params[1],
                "pddl_to": params[2],
                "json_from": j_from,
                "json_to": j_to,
                "floor": f_from,
                "bname": b_from,
            })
            current_floor = f_to
            current_bname = b_to
            continue

        if name == "use_elevator":
            flush_walk()
            _jf, from_floor, _bf = pddl_to_json(params[1], current_floor, current_bname)
            _jt, to_floor, b_to = pddl_to_json(params[2], current_floor, current_bname)
            steps.append({
                "instruction": normalize_instruction(
                    f"Take the elevator to {floor_text(to_floor)}."
                ),
                "type": "elevator",
                "verification": "photo",
                "expected_photo_type": "elevator_state",
                "post_photo_instruction": (
                    f"Press floor {to_floor} and exit when you arrive."
                ),
            })
            current_floor = to_floor
            current_bname = b_to
            continue

        if name in (
            "climb_stairs_accessible", "descend_stairs_accessible",
            "climb_stairs_fast", "descend_stairs_fast",
        ):
            flush_walk()
            _jf, from_floor, _bf = pddl_to_json(params[1], current_floor, current_bname)
            _jt, to_floor, b_to = pddl_to_json(params[2], current_floor, current_bname)
            direction = "up" if name.startswith("climb") else "down"
            is_hurry = name.endswith("_fast")

            safety_msg = f"Go {direction} the stairs to {floor_text(to_floor)}. "
            if is_hurry:
                safety_msg += "Go carefully."
            else:
                safety_msg += "Use the handrail."

            steps.append({
                "instruction": normalize_instruction(safety_msg),
                "type": "stairs",
                "verification": "photo",
                "expected_photo_type": "stair_direction",
                "two_phase_photo": True,
                "pre_photo_instruction": (
                    f"Find the stairs on {floor_text(from_floor)} and photograph them."
                ),
                "post_photo_instruction": safety_msg,
                "stairs_direction": direction,
            })
            current_floor = to_floor
            current_bname = b_to
            continue

        if name == "outdoor_walk":
            flush_walk()
            _jf, _ff, b_from = pddl_to_json(params[1], current_floor, current_bname)
            _jt, _ft, b_to = pddl_to_json(params[2], current_floor, current_bname)
            from_bld = _building_id_from_name(b_from)
            to_bld = _building_id_from_name(b_to)
            instr_text = (
                f"Exit through the main entrance of {BUILDING_FULL.get(from_bld, 'the building')}. "
                "Opening the map."
            )
            steps.append({
                "instruction": normalize_instruction(instr_text),
                "type": "outdoor",
                "verification": "voice",
                "expected_photo_type": None,
                "outdoor_from_building": from_bld,
                "outdoor_to_building": to_bld,
                "use_gps": True,
            })
            current_bname = b_to
            continue

    flush_walk()
    return steps if steps else None


def _building_id_from_name(name: Optional[str]) -> int:
    """Resolve a building name (e.g. 'G', 'cd') to its numeric id."""
    if not name:
        return 0
    mapping = {
        "g": 1,   "cd": 2,  "h": 3,   "p": 4,   "o": 5,
        "m": 6,   "n": 7,   "csq": 8, "k": 9,   "csc": 10,
        "c": 11,  "e": 12,  "cm": 13, "lcb": 14,
        "rodilla": 15, "chapel": 16,
    }
    return mapping.get(name.lower(), 0)

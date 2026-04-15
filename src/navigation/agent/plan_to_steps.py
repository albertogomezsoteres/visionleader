"""Translate Fast Downward plan output into navigation steps for the app.

Two converters live here:

- :func:`fd_plan_to_steps` consumes a *floor-level* plan from the legacy
  ``domain_outdoor.pddl`` and produces inter-building steps.
- :func:`fd_plan_to_steps_room_level` consumes a *room-level* plan from
  ``domain_indoor.pddl`` and produces intra-building steps with merged
  walking instructions enriched by the campus_places hint table.

Both functions are pure: state and lookup tables are passed in as
arguments so the agent can re-use them without coupling to the FSM.
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


def planta_to_int(planta_str: str) -> int:
    """Convert a PDDL planta_X identifier back to an int."""
    if planta_str.startswith("planta_m"):
        return -int(planta_str[8:])
    if planta_str.startswith("planta_"):
        return int(planta_str[7:])
    return 0


def edificio_to_int(edificio_str: str) -> int:
    """Convert a PDDL edificio_X identifier back to an int."""
    if edificio_str.startswith("edificio_"):
        return int(edificio_str[9:])
    return 0


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
        last["expected_photo_type"] = "door"
        last["arrival_strict_photo"] = True
        last["expected_room_code"] = dest_room_code
    else:
        last["arrival_strict_photo"] = True
        last["expected_room_code"] = dest_room_code
    return steps


def fd_plan_to_steps(
    fd_actions: List[str],
    origin: Dict,
    destination: Dict,
) -> Optional[List[Dict]]:
    """Convert a floor-level Fast Downward plan into navigation steps.

    Used for inter-building plans coming from ``domain_outdoor.pddl``.
    The resulting steps mix elevator, stairs and ``mover_edificio``
    (outdoor walking) actions.
    """
    steps: List[Dict] = []

    o_loc = origin.get("location_id")
    d_bld = destination.get("building")
    d_loc = destination.get("location_id")

    first_movement = True
    last_arrival_loc: Optional[str] = None

    for action_str in fd_actions:
        parsed = parse_fd_action(action_str)
        if not parsed:
            continue
        name = parsed["name"]
        params = parsed["params"]

        if name in ("verificar_ascensor", "validar_escaleras"):
            continue

        if name == "usar_ascensor":
            from_floor = planta_to_int(params[2])
            to_floor = planta_to_int(params[3])
            pre_verified_at_elevator = False

            instr_text = (
                f"Take the elevator from {floor_text(from_floor)} "
                f"to {floor_text(to_floor)}. "
                "Press the button and wait for the doors to open."
            )
            steps.append({
                "instruction": normalize_instruction(instr_text),
                "type": "elevator",
                "verification": "voice" if pre_verified_at_elevator else "photo",
                "expected_photo_type": None if pre_verified_at_elevator else "elevator",
                "post_photo_instruction": (
                    f"Enter the elevator, press floor {to_floor}, and exit when you arrive."
                ),
            })
            last_arrival_loc = "ascensor"
            first_movement = False

        elif name in (
            "subir_escaleras", "bajar_escaleras",
            "subir_escaleras_rapido", "bajar_escaleras_rapido",
        ):
            from_floor = planta_to_int(params[2])
            to_floor = planta_to_int(params[3])
            direction = "up" if "subir" in name else "down"
            is_hurry = "rapido" in name

            safety_msg = (
                f"Go {direction} the stairs from {floor_text(from_floor)} "
                f"to {floor_text(to_floor)}. "
            )
            if is_hurry:
                safety_msg += "Take the stairs quickly, but be careful."
            else:
                safety_msg += (
                    "Hold the handrail firmly with one hand. "
                    "Take it one step at a time."
                )

            photo_confirm_msg = (
                f"I can see the stairs going {direction}. " + safety_msg
                if not is_hurry
                else f"I can see the stairs going {direction}. Go ahead carefully."
            )
            steps.append({
                "instruction": normalize_instruction(safety_msg),
                "type": "stairs",
                "verification": "photo",
                "expected_photo_type": "stairs",
                "two_phase_photo": True,
                "pre_photo_instruction": (
                    f"Locate the stairs on {floor_text(from_floor)}. "
                    "Please take a photo so I can confirm they go "
                    f"{'up' if direction == 'up' else 'down'} and have a handrail."
                ),
                "post_photo_instruction": photo_confirm_msg,
                "stairs_direction": direction,
            })
            last_arrival_loc = "escaleras"
            first_movement = False

        elif name == "mover_edificio":
            from_bld = edificio_to_int(params[1])
            to_bld = edificio_to_int(params[2])

            from_entrance = _entrance_id(from_bld)
            to_entrance = _entrance_id(to_bld)

            instr_text = (
                f"Head to the main entrance of {BUILDING_FULL.get(from_bld, 'the building')}. "
                "Push through the two glass doors to exit the building. "
                "Opening Google Maps for outdoor route navigation."
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
            last_arrival_loc = to_entrance
            first_movement = False

    return steps if steps else None


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
    bname = BUILDING_NAMES.get(origin.get("building"), "G")
    current_floor = origin.get("floor", 0) or 0

    walk_buffer: List[Dict] = []

    def pddl_to_json(pddl_id: str, default_floor: int) -> Tuple[str, int]:
        base, floor = HierarchicalPDDLConverter.pddl_to_location(pddl_id)
        if floor is not None:
            return base, floor
        for f_str, locs in (places_locations.get(bname, {}) or {}).items():
            for loc in locs:
                if loc.get("id") == base:
                    try:
                        return base, int(f_str)
                    except (TypeError, ValueError):
                        pass
        return base, default_floor

    def flush_walk() -> None:
        if not walk_buffer:
            return

        total_distance = 0
        any_distance = False
        for hop in walk_buffer:
            key = f"{bname}_{hop['floor']}_{hop['json_from']}_{hop['json_to']}"
            d = local_distance.get(key)
            if d:
                total_distance += d
                any_distance = True

        final_hop = walk_buffer[-1]
        final_key = (
            f"{bname}_{final_hop['floor']}_"
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

        if name in ("verificar_ascensor", "validar_escaleras"):
            continue

        if name == "caminar":
            if len(params) < 3:
                continue
            j_from, f_from = pddl_to_json(params[1], current_floor)
            j_to, f_to = pddl_to_json(params[2], current_floor)
            walk_buffer.append({
                "pddl_from": params[1],
                "pddl_to": params[2],
                "json_from": j_from,
                "json_to": j_to,
                "floor": f_from,
            })
            current_floor = f_to
            continue

        if name == "usar_ascensor":
            flush_walk()
            _jf, from_floor = pddl_to_json(params[1], current_floor)
            _jt, to_floor = pddl_to_json(params[2], current_floor)
            steps.append({
                "instruction": normalize_instruction(
                    f"Take the elevator from {floor_text(from_floor)} "
                    f"to {floor_text(to_floor)}. "
                    "Press the button and wait for the doors to open."
                ),
                "type": "elevator",
                "verification": "photo",
                "expected_photo_type": "elevator",
                "post_photo_instruction": (
                    f"Enter the elevator, press floor {to_floor}, "
                    "and exit when you arrive."
                ),
            })
            current_floor = to_floor
            continue

        if name in (
            "subir_escaleras", "bajar_escaleras",
            "subir_escaleras_rapido", "bajar_escaleras_rapido",
        ):
            flush_walk()
            _jf, from_floor = pddl_to_json(params[1], current_floor)
            _jt, to_floor = pddl_to_json(params[2], current_floor)
            direction = "up" if "subir" in name else "down"
            is_hurry = "rapido" in name

            safety_msg = (
                f"Go {direction} the stairs from "
                f"{floor_text(from_floor)} to {floor_text(to_floor)}. "
            )
            if is_hurry:
                safety_msg += "Take the stairs quickly, but be careful."
            else:
                safety_msg += (
                    "Hold the handrail firmly with one hand. "
                    "Take it one step at a time."
                )

            steps.append({
                "instruction": normalize_instruction(safety_msg),
                "type": "stairs",
                "verification": "photo",
                "expected_photo_type": "stairs",
                "two_phase_photo": True,
                "pre_photo_instruction": (
                    f"Locate the stairs on {floor_text(from_floor)}. "
                    "Please take a photo so I can confirm they go "
                    f"{direction} and have a handrail."
                ),
                "post_photo_instruction": safety_msg,
                "stairs_direction": direction,
            })
            current_floor = to_floor
            continue

    flush_walk()
    return steps if steps else None


# Internal reuse: the floor-level converter still needs the entrance map.
def _entrance_id(building_id: int) -> str:
    entrances = {1: "entrada_principal", 2: "entrada_cd", 3: "entrada_principal"}
    return entrances.get(building_id, "entrada_principal")


def _building_id_from_name(name: str) -> int:
    """Local copy of building_id_from_name to avoid a circular dependency
    with :mod:`navigation.agent.parsing` (which itself imports from this
    module via its callers).
    """
    mapping = {
        "g": 1,   "cd": 2,  "h": 3,   "p": 4,   "o": 5,
        "m": 6,   "n": 7,   "csq": 8, "k": 9,   "csc": 10,
        "c": 11,  "e": 12,  "cm": 13, "lcb": 14,
    }
    return mapping.get(name.lower(), 0)

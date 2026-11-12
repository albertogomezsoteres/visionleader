"""Dynamic-availability helpers driven by ``config/closed_rooms.json``.

The agent reads closures on every routing decision so live edits to the
JSON take effect without restarting the API. These helpers know nothing
about the agent itself; they only depend on the hierarchical converter
(for the closure file path) and on the campus_places.json locations dict
(for finding alternative rooms of the same type).
"""

from typing import Any

from .text_formatting import BUILDING_NAMES


def load_current_closures(hierarchical_converter: Any) -> list[dict]:
    """Fresh read of ``config/closed_rooms.json`` via the converter."""
    if not hierarchical_converter:
        return []
    return hierarchical_converter.load_closed_rooms()


def is_room_closed(
    hierarchical_converter: Any,
    building_id: int,
    floor: int | None,
    location_id: str,
) -> dict | None:
    """Return the matching closure entry if the room is closed, else None."""
    if not location_id:
        return None
    bname = BUILDING_NAMES.get(building_id)
    if not bname:
        return None
    for entry in load_current_closures(hierarchical_converter):
        if entry.get("building") != bname:
            continue
        if entry.get("location_id") != location_id:
            continue
        entry_floor = entry.get("floor")
        if entry_floor is None or floor is None or int(entry_floor) == int(floor):
            return entry
    return None


def find_open_alternative(
    hierarchical_converter: Any,
    places_locations: dict,
    building_id: int,
    floor: int,
    location_id: str,
) -> dict | None:
    """Search ``campus_places.json`` for a room of the SAME type that is
    currently open. Prefers the same floor first, then the nearest other
    floors in the same building.

    Returns a dict ``{building, floor, location_id, type, name,
    original_location_id, original_name}`` or ``None``.
    """
    bname = BUILDING_NAMES.get(building_id)
    if not bname:
        return None
    floors_data = places_locations.get(bname, {}) or {}

    original_type: str | None = None
    original_name: str | None = None
    for locs in floors_data.values():
        for loc in locs:
            if loc.get("id") == location_id:
                original_type = loc.get("type")
                original_name = loc.get("name")
                break
        if original_type:
            break
    if not original_type:
        return None

    def candidate_on_floor(f_int: int) -> dict | None:
        locs = floors_data.get(str(f_int), []) or []
        for loc in locs:
            if loc.get("id") == location_id:
                continue
            if loc.get("type") != original_type:
                continue
            if is_room_closed(hierarchical_converter, building_id, f_int, loc["id"]):
                continue
            return {
                "building": building_id,
                "floor": f_int,
                "location_id": loc["id"],
                "type": original_type,
                "name": loc.get("name", loc["id"]),
                "original_location_id": location_id,
                "original_name": original_name or location_id,
            }
        return None

    same_floor = candidate_on_floor(floor)
    if same_floor:
        return same_floor

    all_floors = sorted(int(f) for f in floors_data)
    by_distance = sorted(all_floors, key=lambda f: abs(f - floor))
    for f_int in by_distance:
        if f_int == floor:
            continue
        alt = candidate_on_floor(f_int)
        if alt:
            return alt

    return None

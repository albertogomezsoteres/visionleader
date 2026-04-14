"""
One-shot migration for campus_graph.json — local_connections.

Adds two structured fields to every entry under local_connections:

  * distance_m : integer (meters), parsed from the existing instruction text.
  * hint       : short directional hint (null by default — filled manually
                 for the most critical edges of the demo).

The existing `instructions` field is preserved untouched for backwards
compatibility. After this migration the hierarchical PDDL converter
consumes `distance_m` as the canonical source of metric distance, and the
conversation agent consumes `hint` as the directional decoration for the
TTS messages. Everything that matters for routing lives in PDDL.

Usage:

    python scripts/migrate_local_connections.py

Idempotent: re-running it will not overwrite hints that already exist.
"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CAMPUS_JSON = ROOT / "config" / "campus_graph.json"

DISTANCE_RE = re.compile(r"(\d+)\s*met(?:er|re)s?", re.IGNORECASE)


def parse_distance(instructions) -> int | None:
    """Extract the first 'N meters' occurrence from the instruction list."""
    if not instructions:
        return None
    for line in instructions:
        m = DISTANCE_RE.search(str(line))
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def main() -> None:
    with CAMPUS_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    connections = data.get("local_connections", [])
    if not connections:
        print("No local_connections in campus_graph.json — nothing to do.")
        return

    updated = 0
    missing_distance = 0
    already_migrated = 0

    for entry in connections:
        had_distance = "distance_m" in entry
        had_hint = "hint" in entry

        if not had_distance:
            dist = parse_distance(entry.get("instructions"))
            if dist is None:
                missing_distance += 1
                dist = 10  # sensible default when the text doesn't include meters
            entry["distance_m"] = dist
            updated += 1
        else:
            already_migrated += 1

        if not had_hint:
            # null placeholder; filled manually for the critical demo edges
            entry["hint"] = None

    # Re-order keys so distance_m and hint sit next to from/to/instructions
    ordered = []
    for entry in connections:
        ordered.append({
            "building": entry.get("building"),
            "floor": entry.get("floor"),
            "from": entry.get("from"),
            "to": entry.get("to"),
            "distance_m": entry.get("distance_m"),
            "hint": entry.get("hint"),
            "instructions": entry.get("instructions"),
        })
    data["local_connections"] = ordered

    # Bump version / update metadata note
    meta = data.setdefault("metadata", {})
    meta["version"] = "6.0"
    meta["planning_model"] = (
        "PDDL is the sole reasoner: topology AND metric distances live in "
        "the building-specific problem files (see pddl/domain_G.pddl). "
        "campus_graph.json is only a display layer."
    )
    meta["local_routing"] = (
        "local_connections: structured distance_m (meters, consumed by the "
        "PDDL converter) and hint (short directional text, consumed by the "
        "conversation agent for TTS decoration only)."
    )

    with CAMPUS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")

    print(f"Migration complete.")
    print(f"  Entries touched          : {len(connections)}")
    print(f"  Added distance_m         : {updated}")
    print(f"  Already had distance_m   : {already_migrated}")
    print(f"  Defaulted (no meters)    : {missing_distance}")
    print(f"  campus_graph.json version: 6.0")


if __name__ == "__main__":
    main()

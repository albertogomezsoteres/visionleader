"""
One-shot script to replace the default 10m placeholders on Building G
floor 1 with plausible metric distances, so the planner has real
optimization choices on that floor.

Model: imagine a linear corridor with the elevator near the entrance
of the corridor, the stairs on the opposite wall, classroom 1.1 right
by the elevator (first door on the right), and classroom 1.4 near the
end of the corridor (fourth door on the left). The faculty offices
sit on the opposite side of the elevator; the bathroom is near 1.4;
the floor directory is next to the elevator.

The numbers are defendible approximations (4-5 m per door span), not
measurements. Easy to tweak by hand later.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAMPUS_JSON = ROOT / "config" / "campus_graph.json"


# (from, to) -> distance_m. Bidirectional — we apply the same value to
# both directions automatically, then check for missing pairs.
FLOOR_1_DISTANCES = {
    # From the elevator
    frozenset(("ascensor", "aula_1_1")):     3,
    frozenset(("ascensor", "aula_1_4")):    16,
    frozenset(("ascensor", "despachos")):    6,
    frozenset(("ascensor", "directorio_1")): 2,
    frozenset(("ascensor", "bano")):        18,
    frozenset(("ascensor", "escaleras")):   10,

    # From the stairs (opposite wall to the elevator)
    frozenset(("escaleras", "aula_1_1")):     8,
    frozenset(("escaleras", "aula_1_4")):    14,
    frozenset(("escaleras", "despachos")):    9,
    frozenset(("escaleras", "directorio_1")): 9,
    frozenset(("escaleras", "bano")):        19,

    # Between classrooms / offices / directory / bathroom
    frozenset(("aula_1_1", "aula_1_4")):      13,
    frozenset(("aula_1_1", "despachos")):      8,
    frozenset(("aula_1_1", "directorio_1")):   4,
    frozenset(("aula_1_1", "bano")):          16,
    frozenset(("aula_1_4", "despachos")):     10,
    frozenset(("aula_1_4", "directorio_1")): 15,
    frozenset(("aula_1_4", "bano")):           3,
    frozenset(("despachos", "directorio_1")):  5,
    frozenset(("despachos", "bano")):         12,
    frozenset(("directorio_1", "bano")):      17,
}


def main() -> None:
    with CAMPUS_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    floor_1_edges = [
        lc for lc in data.get("local_connections", [])
        if lc.get("building") == "G" and lc.get("floor") == 1
    ]
    print(f"Found {len(floor_1_edges)} directed edges on Building G, floor 1")

    updated = 0
    missing_pairs = set()

    for lc in floor_1_edges:
        pair = frozenset((lc["from"], lc["to"]))
        new_dist = FLOOR_1_DISTANCES.get(pair)
        if new_dist is None:
            missing_pairs.add(tuple(sorted(pair)))
            continue
        if lc.get("distance_m") != new_dist:
            lc["distance_m"] = new_dist
            updated += 1

    with CAMPUS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")

    print(f"Updated distances: {updated}")
    if missing_pairs:
        print(f"Pairs in JSON with no planned distance ({len(missing_pairs)}):")
        for p in sorted(missing_pairs):
            print(f"  {p}")
    else:
        print("All floor 1 pairs were assigned realistic distances.")


if __name__ == "__main__":
    main()

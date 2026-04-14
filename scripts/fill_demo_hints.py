"""
Fill the `hint` field of the ~25 most important local_connections for the
TFG demo. Each hint is a short directional decoration (3-8 words) that the
conversation agent appends after the PDDL-driven "Walk Nm, ..." sentence.

Re-runnable: it only overwrites entries whose `hint` is None or missing.
Pass --force to overwrite existing hints.
"""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CAMPUS_JSON = ROOT / "config" / "campus_graph.json"


# (building, floor, from, to) -> hint
# Each hint is short (3-8 words). The PDDL planner emits the distance, so
# the hint only carries the turn / door-side information that cannot be
# represented symbolically in PDDL.
DEMO_HINTS: dict = {
    # Floor 0 — main entrance & classrooms around the entrance hall
    ("G", 0, "entrada_principal", "aula_0_1"):  "turn left, second door on the right",
    ("G", 0, "aula_0_1", "entrada_principal"):  "exit the classroom and go back to the entrance",
    ("G", 0, "entrada_principal", "aula_0_3"):  "first door on the right",
    ("G", 0, "aula_0_3", "entrada_principal"):  "exit and turn left back to the entrance",
    ("G", 0, "entrada_principal", "lab_ia"):    "straight ahead, last door on the left",
    ("G", 0, "lab_ia", "entrada_principal"):    "exit and go straight back to the entrance",
    ("G", 0, "entrada_principal", "ascensor"):  "end of the corridor on the left",
    ("G", 0, "ascensor", "entrada_principal"):  "from the elevator go straight to the entrance",
    ("G", 0, "entrada_principal", "escaleras"): "end of the corridor on the right",
    ("G", 0, "escaleras", "entrada_principal"): "from the stairs go straight back",
    ("G", 0, "aula_0_1", "aula_0_3"):           "turn right, two doors down",
    ("G", 0, "aula_0_3", "aula_0_1"):           "turn left, two doors down",
    ("G", 0, "aula_0_1", "lab_ia"):             "turn right, third door on the left",
    ("G", 0, "aula_0_1", "bano"):               "exit the classroom and turn right, first door",
    ("G", 0, "bano", "entrada_principal"):      "exit the restroom and go left to the entrance",
    ("G", 0, "entrada_principal", "bano"):      "turn left, third door on the right",
    ("G", 0, "lab_ia", "ascensor"):             "exit the lab and turn right to the elevator",

    # Floor 1 — elevator/stairs to classrooms and offices
    ("G", 1, "ascensor", "aula_1_1"):   "exit the elevator, turn right, first door on the right",
    ("G", 1, "aula_1_1", "ascensor"):   "exit the classroom and turn left to the elevator",
    ("G", 1, "ascensor", "aula_1_4"):   "exit the elevator, turn right, fourth door on the left",
    ("G", 1, "aula_1_4", "ascensor"):   "exit the classroom and turn right to the elevator",
    ("G", 1, "ascensor", "despachos"):  "exit the elevator, turn left, second door on the right",
    ("G", 1, "despachos", "ascensor"):  "exit the offices and turn right to the elevator",
    ("G", 1, "escaleras", "aula_1_4"):  "at the top of the stairs, turn left, fourth door on the left",
    ("G", 1, "aula_1_4", "escaleras"):  "exit the classroom and turn right to the stairs",
    ("G", 1, "escaleras", "aula_1_1"):  "at the top of the stairs, turn right, first door on the right",
    ("G", 1, "aula_1_1", "escaleras"):  "exit the classroom and turn left to the stairs",
    ("G", 1, "aula_1_1", "aula_1_4"):   "turn left, three doors ahead on your left",
    ("G", 1, "aula_1_4", "aula_1_1"):   "turn right, three doors back on your right",
    ("G", 1, "aula_1_4", "bano"):       "exit the classroom and turn right, restroom is right there",
    ("G", 1, "bano", "aula_1_4"):       "exit the restroom and turn left, first door on the left",
    ("G", 1, "aula_1_1", "despachos"):  "turn left, walk past the elevator, second door on the right",
    ("G", 1, "despachos", "aula_1_1"):  "turn right, walk past the elevator, first door on the right",

    # Floor 2 — elevator/stairs to classrooms, offices and secretary
    ("G", 2, "ascensor", "aula_2_1"):       "exit the elevator, turn right, first door on the right",
    ("G", 2, "aula_2_1", "ascensor"):       "exit the classroom and turn left to the elevator",
    ("G", 2, "ascensor", "secretaria"):     "exit the elevator, turn left, first door on the right",
    ("G", 2, "secretaria", "ascensor"):     "exit the office and turn right to the elevator",
    ("G", 2, "ascensor", "sala_mentorias"): "exit the elevator, turn left, second door on the left",
    ("G", 2, "sala_mentorias", "ascensor"): "exit the room and turn right to the elevator",
    ("G", 2, "ascensor", "despachos_eps"):  "exit the elevator, turn right, second door on the left",
    ("G", 2, "despachos_eps", "ascensor"):  "exit the offices and turn left to the elevator",
    ("G", 2, "escaleras", "secretaria"):    "at the top of the stairs, turn right, second door on the left",
    ("G", 2, "secretaria", "escaleras"):    "exit the office and turn left to the stairs",
    ("G", 2, "escaleras", "aula_2_1"):      "at the top of the stairs, turn left, first door on the right",
    ("G", 2, "aula_2_1", "secretaria"):     "exit the classroom, turn left, last door on the right",
    ("G", 2, "secretaria", "aula_2_1"):     "exit the office and go right, last door on the left",
    ("G", 2, "aula_2_1", "despachos_eps"):  "turn right, last door on the right",
    ("G", 2, "aula_2_1", "sala_mentorias"): "turn left, third door on the left",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="overwrite hints even if they already exist")
    args = ap.parse_args()

    with CAMPUS_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    written = 0
    skipped = 0
    not_found: list = []

    for (bld, flr, src, dst), hint in DEMO_HINTS.items():
        matched = False
        for lc in data.get("local_connections", []):
            if (
                lc.get("building") == bld
                and lc.get("floor") == flr
                and lc.get("from") == src
                and lc.get("to") == dst
            ):
                matched = True
                if lc.get("hint") and not args.force:
                    skipped += 1
                else:
                    lc["hint"] = hint
                    written += 1
                break
        if not matched:
            not_found.append((bld, flr, src, dst))

    with CAMPUS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")

    print(f"Demo hints updated.")
    print(f"  Written : {written}")
    print(f"  Skipped : {skipped}  (already had a hint; use --force to overwrite)")
    if not_found:
        print(f"  Not found in local_connections ({len(not_found)}):")
        for e in not_found:
            print(f"    {e}")


if __name__ == "__main__":
    main()

"""
Campus graph → PDDL problem generator.

Reads campus_graph.json and emits a problem file for Fast Downward
(pddl/domain.pddl). Only the "connections" array is used as macro topology:
(building, floor) nodes and edge types (elevator, stairs_*, hallway).

Per-edge numeric fields in JSON are not used: action costs are entirely
defined in the PDDL domain (:action ... (increase (total-cost) N))).

The generated problem includes:
  - Objects: robot, edificios, plantas, tipo_conexion constants
  - Init: position, facilities, (conectado ...), flags, (= (total-cost) 0)
  - Goal: target (building, floor) or functional cafeteria/gym
  - Metric: minimize (total-cost); optional (modo_rapido) in init
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def _floor_str(floor: int) -> str:
    """Convert a floor number to a valid PDDL identifier (e.g. -1 -> planta_m1)."""
    if floor < 0:
        return f"planta_m{abs(floor)}"
    return f"planta_{floor}"


class CampusGraphToPDDL:
    """Turns the campus JSON graph into PDDL problem files."""

    def __init__(self, json_path: str):
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_buildings(self) -> List[Dict]:
        return self.data.get("buildings", [])

    def get_connections(self) -> List[Dict]:
        return self.data.get("connections", [])

    def _find_functional_goal(self, goal_functional: str) -> Tuple[Optional[int], Optional[int]]:
        """Look up a named facility (cafeteria, gym) and return (building_id, floor)."""
        goal_lower = goal_functional.lower()
        for b in self.get_buildings():
            if goal_lower == "cafeteria":
                f = b.get("cafeteria_floor")
                if f is not None:
                    return (b["id"], f)
            elif goal_lower in ("gimnasio", "gym"):
                f = b.get("gimnasio_floor")
                if f is not None:
                    return (b["id"], f)
        return (None, None)

    # ── Object generation ────────────────────────────────────────────────

    def _generate_objects(self) -> Dict[str, List[str]]:
        """Collect every PDDL object from the campus graph."""
        objects: Dict[str, list] = {
            "robots": ["robot1"],
            "edificios": [],
            "plantas": set(),
            "tipos_conexion": {"elevator", "stairs_up", "stairs_down", "hallway"},
        }
        for b in self.get_buildings():
            objects["edificios"].append(f"edificio_{b['id']}")
            for floor in b.get("floors", []):
                objects["plantas"].add(_floor_str(floor))

        objects["plantas"] = sorted(objects["plantas"])
        objects["tipos_conexion"] = sorted(objects["tipos_conexion"])
        return objects

    # ── Init generation ──────────────────────────────────────────────────

    def _generate_init(
        self,
        robot_location: Optional[Tuple[int, int]] = None,
        hurry_mode: bool = False,
    ) -> List[str]:
        """Build the list of PDDL init propositions."""
        init: List[str] = []

        # Cost function starts at zero
        init.append("    (= (total-cost) 0)")

        # Robot position
        if robot_location:
            bid, floor = robot_location
            init.append(f"    (en robot1 edificio_{bid} {_floor_str(floor)})")

        # Global flags
        if hurry_mode:
            init.append("    (modo_rapido)")

        # Connection-type tags (set once, read by every action precondition)
        init.append("    (es_ascensor elevator)")
        init.append("    (es_escalera_subir stairs_up)")
        init.append("    (es_escalera_bajar stairs_down)")
        init.append("    (es_pasillo hallway)")

        # Per-building facilities and connections
        for b in self.get_buildings():
            bid = b["id"]
            has_elev = b.get("elevators", False)
            has_stairs = b.get("stairs", False)
            caf_floor = b.get("cafeteria_floor")
            gym_floor = b.get("gimnasio_floor")

            for floor in b.get("floors", []):
                fs = _floor_str(floor)
                if has_elev:
                    init.append(f"    (hay_ascensor edificio_{bid} {fs})")
                if has_stairs:
                    init.append(f"    (hay_escalera edificio_{bid} {fs})")
                if caf_floor is not None and floor == caf_floor:
                    init.append(f"    (hay_cafeteria edificio_{bid} {fs})")
                if gym_floor is not None and floor == gym_floor:
                    init.append(f"    (hay_gimnasio edificio_{bid} {fs})")

        for conn in self.get_connections():
            fb, ff = conn["from"]["building"], conn["from"]["floor"]
            tb, tf = conn["to"]["building"],   conn["to"]["floor"]
            ctype = conn["type"]
            init.append(
                f"    (conectado edificio_{fb} {_floor_str(ff)} "
                f"edificio_{tb} {_floor_str(tf)} {ctype})"
            )

        return init

    # ── Full problem file ────────────────────────────────────────────────

    def generate_problem(
        self,
        initial_state: Tuple[int, int],
        goal_state: Optional[Tuple[int, int]] = None,
        goal_functional: Optional[str] = None,
        problem_name: str = "campus-problem",
        output_path: Optional[str] = None,
        hurry_mode: bool = False,
    ) -> str:
        """
        Generate a complete PDDL problem file.

        Either goal_state (building, floor) or goal_functional ("cafeteria",
        "gimnasio") must be provided.  When hurry_mode is True the problem
        includes the (modo_rapido) flag so the planner prefers stairs.
        """
        objects = self._generate_objects()
        init = self._generate_init(
            robot_location=initial_state,
            hurry_mode=hurry_mode,
        )

        # Build the goal clause
        if goal_functional:
            gbid, gfloor = self._find_functional_goal(goal_functional)
            if gbid is None or gfloor is None:
                raise ValueError(f"Functional goal '{goal_functional}' not found in campus_graph.json")
            gfs = _floor_str(gfloor)
            facility_pred = "hay_cafeteria" if goal_functional.lower() == "cafeteria" else "hay_gimnasio"
            goal = (
                f"    (and\n"
                f"      (en robot1 edificio_{gbid} {gfs})\n"
                f"      ({facility_pred} edificio_{gbid} {gfs})\n"
                f"    )"
            )
        elif goal_state:
            gbid, gfloor = goal_state
            goal = f"    (en robot1 edificio_{gbid} {_floor_str(gfloor)})"
        else:
            raise ValueError("Provide goal_state or goal_functional")

        content = (
            f"(define (problem {problem_name})\n"
            f"  (:domain campus-navigation)\n"
            f"\n"
            f"  (:objects\n"
            f"    {' '.join(objects['robots'])} - robot\n"
            f"    {' '.join(objects['edificios'])} - edificio\n"
            f"    {' '.join(objects['plantas'])} - planta\n"
            f"    {' '.join(objects['tipos_conexion'])} - tipo_conexion\n"
            f"  )\n"
            f"\n"
            f"  (:init\n"
            + "\n".join(init) + "\n"
            f"  )\n"
            f"\n"
            f"  (:goal\n"
            f"    (and\n"
            f"  {goal}\n"
            f"    )\n"
            f"  )\n"
            f"\n"
            f"  (:metric minimize (total-cost))\n"
            f")\n"
        )

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

        return content


def create_problem_from_states(
    json_path: str,
    initial_state: Tuple[int, int],
    goal_state: Optional[Tuple[int, int]] = None,
    goal_functional: Optional[str] = None,
    output_path: Optional[str] = None,
    hurry_mode: bool = False,
) -> str:
    """Helper to create a PDDL problem in one call."""
    converter = CampusGraphToPDDL(json_path)
    converter.generate_problem(
        initial_state=initial_state,
        goal_state=goal_state,
        goal_functional=goal_functional,
        output_path=output_path,
        hurry_mode=hurry_mode,
    )
    return output_path


if __name__ == "__main__":
    converter = CampusGraphToPDDL("config/campus_graph.json")

    print("=== Accessible mode (G floor 0 -> G floor 2) ===")
    print(converter.generate_problem(
        initial_state=(1, 0), goal_state=(1, 2),
        problem_name="g0-to-g2-accessible",
    ))

    print("\n=== Hurry mode (G floor 0 -> G floor 2) ===")
    print(converter.generate_problem(
        initial_state=(1, 0), goal_state=(1, 2),
        problem_name="g0-to-g2-hurry", hurry_mode=True,
    ))

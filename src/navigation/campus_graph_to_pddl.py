"""Legacy floor-level PDDL problem generator.

Used by ``pddl/domain_outdoor.pddl``. Reasons at (building, floor) granularity
and is still the source of inter-building plans served by ``/api/plan``.

Reads ``config/campus_topology.json`` (topology-only data) and emits a
complete PDDL problem file with objects, init facts and goal.
"""

import json
from typing import Dict, List, Optional, Tuple

from .pddl_helpers import floor_str


class CampusGraphToPDDL:
    """Turns the campus JSON graph into floor-level PDDL problem files."""

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
                objects["plantas"].add(floor_str(floor))

        objects["plantas"] = sorted(objects["plantas"])
        objects["tipos_conexion"] = sorted(objects["tipos_conexion"])
        return objects

    def _generate_init(
        self,
        robot_location: Optional[Tuple[int, int]] = None,
        hurry_mode: bool = False,
    ) -> List[str]:
        """Build the list of PDDL init propositions."""
        init: List[str] = []

        init.append("    (= (total-cost) 0)")

        if robot_location:
            bid, floor = robot_location
            init.append(f"    (en robot1 edificio_{bid} {floor_str(floor)})")

        if hurry_mode:
            init.append("    (modo_rapido)")

        init.append("    (es_ascensor elevator)")
        init.append("    (es_escalera_subir stairs_up)")
        init.append("    (es_escalera_bajar stairs_down)")
        init.append("    (es_pasillo hallway)")

        for b in self.get_buildings():
            bid = b["id"]
            has_elev = b.get("elevators", False)
            has_stairs = b.get("stairs", False)

            for floor in b.get("floors", []):
                fs = floor_str(floor)
                if has_elev:
                    init.append(f"    (hay_ascensor edificio_{bid} {fs})")
                if has_stairs:
                    init.append(f"    (hay_escalera edificio_{bid} {fs})")

        for conn in self.get_connections():
            fb, ff = conn["from"]["building"], conn["from"]["floor"]
            tb, tf = conn["to"]["building"],   conn["to"]["floor"]
            ctype = conn["type"]
            init.append(
                f"    (conectado edificio_{fb} {floor_str(ff)} "
                f"edificio_{tb} {floor_str(tf)} {ctype})"
            )

        return init

    def generate_problem(
        self,
        initial_state: Tuple[int, int],
        goal_state: Optional[Tuple[int, int]] = None,
        goal_functional: Optional[str] = None,
        problem_name: str = "campus-problem",
        output_path: Optional[str] = None,
        hurry_mode: bool = False,
    ) -> str:
        """Generate a complete floor-level PDDL problem file."""
        objects = self._generate_objects()
        init = self._generate_init(
            robot_location=initial_state,
            hurry_mode=hurry_mode,
        )

        if goal_functional:
            gbid, gfloor = self._find_functional_goal(goal_functional)
            if gbid is None or gfloor is None:
                raise ValueError(f"Functional goal '{goal_functional}' not found in campus_topology.json")
            goal = f"    (en robot1 edificio_{gbid} {floor_str(gfloor)})"
        elif goal_state:
            gbid, gfloor = goal_state
            goal = f"    (en robot1 edificio_{gbid} {floor_str(gfloor)})"
        else:
            raise ValueError("Provide goal_state or goal_functional")

        content = (
            f"(define (problem {problem_name})\n"
            f"  (:domain campus-outdoor)\n"
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

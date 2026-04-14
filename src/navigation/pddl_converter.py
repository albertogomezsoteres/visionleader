"""
PDDL problem generators — legacy floor-level and hierarchical room-level.

Two classes live here:

- CampusGraphToPDDL:
    Legacy converter used by the global domain (pddl/domain.pddl). Reasons
    at (building, floor) level and is still used for inter-building plans
    and the /api/plan route.

- HierarchicalPDDLConverter:
    Room-level converter used by building-specific domains
    (pddl/domain_G.pddl, domain_CD.pddl, domain_H.pddl). Encodes the full
    intra-building graph in the generated problem file's :init section.

Both converters read the campus graph JSON, but only to produce PDDL
problem files. The symbolic reasoning over the topology is done by
Fast Downward on the generated problem + the right domain.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def _floor_str(floor: int) -> str:
    """Convert a floor number to a valid PDDL identifier (e.g. -1 -> planta_m1)."""
    if floor < 0:
        return f"planta_m{abs(floor)}"
    return f"planta_{floor}"


# Legacy converter (global / floor-level domain)
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
                objects["plantas"].add(_floor_str(floor))

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
            init.append(f"    (en robot1 edificio_{bid} {_floor_str(floor)})")

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


# Hierarchical converter (building-specific, room-level domains)
class HierarchicalPDDLConverter:
    """
    Room-level PDDL problem generator for building-specific domains.

    Each building has its own PDDL domain (domain_G.pddl, domain_CD.pddl,
    domain_H.pddl). This converter emits problem files whose :init section
    encodes the full intra-building graph (which rooms connect to which,
    floor tags, elevator/stair tags). Fast Downward then does all the
    room-level routing by itself.

    Only Building G is fully modeled for the TFG demo. CD and H expose
    minimal graphs (basic facilities + elevator/stairs between floors).
    """

    # Location IDs that repeat on several floors (same name in the JSON)
    # must be disambiguated with a floor suffix in PDDL.
    SHARED_LOC_IDS: Set[str] = {"ascensor", "escaleras", "bano"}

    # Per-building PDDL domain filenames
    BUILDING_DOMAINS: Dict[int, str] = {
        1: "domain_G.pddl",   # Edificio G (full room-level)
        2: "domain_CD.pddl",  # Centro Deportivo (floor-level)
        3: "domain_H.pddl",   # Edificio H (floor-level)
    }

    # :domain directive name inside each problem file
    BUILDING_DOMAIN_NAMES: Dict[int, str] = {
        1: "building-g",
        2: "building-cd",
        3: "building-h",
    }

    # Mapping from numeric building id to the name used as key inside
    # campus_graph.json "locations".
    BUILDING_JSON_NAMES: Dict[int, str] = {
        1: "G",
        2: "CD",
        3: "H",
    }

    def __init__(
        self,
        json_path: str,
        pddl_dir: str,
        closed_rooms_path: Optional[str] = None,
    ):
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.pddl_dir = Path(pddl_dir)
        # Resolve the closure file: default is config/closed_rooms.json next
        # to the campus graph.
        if closed_rooms_path is None:
            closed_rooms_path = str(
                Path(json_path).parent / "closed_rooms.json"
            )
        self.closed_rooms_path = Path(closed_rooms_path)

    def load_closed_rooms(self) -> List[Dict]:
        """Read the current closure state from disk.

        The file is reloaded on every planning request so live edits take
        effect without restarting the API. Missing file → nothing is closed.
        """
        if not self.closed_rooms_path.exists():
            return []
        try:
            with self.closed_rooms_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("closed", []) or []
        except Exception:
            return []

    def _closure_key(
        self, building_name: str, floor: int, json_id: str
    ) -> Tuple[str, int, str]:
        """Canonical key used to match closure entries."""
        return (building_name, int(floor), json_id)

    def _build_closed_set(self, building_name: str) -> Set[Tuple[str, int, str]]:
        """Return the set of (building, floor, location_id) that are closed.

        For ids that repeat across floors (ascensor, escaleras, bano) the
        closure entry must include the floor; otherwise the closure
        applies to every floor that contains that id.
        """
        closed: Set[Tuple[str, int, str]] = set()
        for entry in self.load_closed_rooms():
            if entry.get("building") != building_name:
                continue
            loc_id = entry.get("location_id")
            if not loc_id:
                continue
            floor = entry.get("floor")
            if floor is None:
                # No floor specified → close every floor with that id
                for f, locs in self.building_locations(
                    self._building_id_from_name(building_name)
                ).items():
                    if any(l.get("id") == loc_id for l in locs):
                        closed.add((building_name, int(f), loc_id))
            else:
                closed.add((building_name, int(floor), loc_id))
        return closed

    def _building_id_from_name(self, name: str) -> int:
        for bid, bname in self.BUILDING_JSON_NAMES.items():
            if bname == name:
                return bid
        return 1

    # Building / domain lookup
    def get_domain_path(self, building_id: int) -> Path:
        """Return the PDDL domain file for a given building id."""
        filename = self.BUILDING_DOMAINS.get(building_id)
        if not filename:
            raise ValueError(f"No PDDL domain defined for building id={building_id}")
        return self.pddl_dir / filename

    def domain_name(self, building_id: int) -> str:
        return self.BUILDING_DOMAIN_NAMES.get(building_id, "building-g")

    def json_name(self, building_id: int) -> str:
        return self.BUILDING_JSON_NAMES.get(building_id, "G")

    # Room id translation (PDDL <-> campus_graph.json)
    @classmethod
    def location_to_pddl(cls, location_id: str, floor: int) -> str:
        """
        Convert a campus_graph location_id + floor to a unique PDDL ubicacion name.

        Locations that appear on multiple floors (ascensor, escaleras, bano)
        get a floor suffix: ascensor -> ascensor_p0 / ascensor_pm1.
        Unique ids (aula_0_1, lab_ia, ...) are returned unchanged.
        """
        if location_id in cls.SHARED_LOC_IDS:
            if floor < 0:
                return f"{location_id}_pm{abs(floor)}"
            return f"{location_id}_p{floor}"
        return location_id

    @classmethod
    def pddl_to_location(cls, pddl_id: str) -> Tuple[str, Optional[int]]:
        """
        Reverse mapping: PDDL ubicacion id -> (json location_id, floor or None).

        For shared ids like ascensor_p0 returns ('ascensor', 0).
        For unique ids like aula_1_4 returns ('aula_1_4', None) — the caller
        must look up the floor separately in campus_graph.json.
        """
        for base in cls.SHARED_LOC_IDS:
            prefix = f"{base}_p"
            if pddl_id.startswith(prefix):
                suffix = pddl_id[len(prefix):]
                try:
                    if suffix.startswith("m"):
                        return base, -int(suffix[1:])
                    return base, int(suffix)
                except ValueError:
                    pass
        return pddl_id, None

    # Data access helpers
    def building_locations(self, building_id: int) -> Dict[int, List[Dict]]:
        """Return {floor_int: [location_dicts]} for a building."""
        name = self.json_name(building_id)
        floors_data = self.data.get("locations", {}).get(name, {})
        return {int(k): v for k, v in floors_data.items()}

    def find_location_floor(self, building_id: int, location_id: str) -> Optional[int]:
        """Look up which floor a location_id is on within a building."""
        for floor, locs in self.building_locations(building_id).items():
            for loc in locs:
                if loc.get("id") == location_id:
                    return floor
        return None

    def find_functional_room(
        self, building_id: int, goal_functional: str
    ) -> Optional[Tuple[str, int]]:
        """
        Resolve a functional goal (cafeteria, gym) to (location_id, floor)
        inside a specific building. Returns None if not found.
        """
        target_types = {
            "cafeteria": "cafeteria",
            "gym": "gym",
            "gimnasio": "gym",
        }
        target = target_types.get(goal_functional.lower())
        if not target:
            return None

        # Look up in the building's locations for a type match.
        for floor, locs in self.building_locations(building_id).items():
            for loc in locs:
                if loc.get("type") == target:
                    return (loc["id"], floor)
        return None

    # Building G problem generation
    def generate_building_problem(
        self,
        building_id: int,
        origin_room: str,
        origin_floor: int,
        dest_room: Optional[str] = None,
        dest_floor: Optional[int] = None,
        goal_functional: Optional[str] = None,
        hurry_mode: bool = False,
        problem_name: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Build an intra-building PDDL problem file with the full room graph
        in :init. Only Building G is fully detailed.

        origin_room / dest_room are campus_graph location_ids. The converter
        translates them into PDDL ubicacion ids using location_to_pddl.
        """
        building_name = self.json_name(building_id)
        locations_by_floor = self.building_locations(building_id)
        if not locations_by_floor:
            raise ValueError(
                f"No locations found in campus_graph.json for building '{building_name}'"
            )

        # Resolve origin PDDL id
        origin_pddl = self.location_to_pddl(origin_room, origin_floor)

        # Resolve destination (explicit room or functional goal)
        if goal_functional and not dest_room:
            func = self.find_functional_room(building_id, goal_functional)
            if not func:
                raise ValueError(
                    f"Functional goal '{goal_functional}' not found in building {building_name}"
                )
            dest_room, dest_floor = func

        if not dest_room or dest_floor is None:
            raise ValueError("Provide dest_room+dest_floor or goal_functional")

        dest_pddl = self.location_to_pddl(dest_room, dest_floor)

        # Collect all PDDL rooms for this building
        all_rooms: List[Tuple[str, int, str]] = []  # (pddl_id, floor, json_id)
        seen_pddl: Set[str] = set()
        for floor in sorted(locations_by_floor.keys()):
            for loc in locations_by_floor[floor]:
                json_id = loc["id"]
                pddl_id = self.location_to_pddl(json_id, floor)
                if pddl_id in seen_pddl:
                    continue
                seen_pddl.add(pddl_id)
                all_rooms.append((pddl_id, floor, json_id))

        floors_set = sorted({r[1] for r in all_rooms})
        planta_names = [_floor_str(f) for f in floors_set]
        pddl_room_names = sorted(r[0] for r in all_rooms)

        # Objects section
        objects_lines = [
            f"    robot1 - robot",
            f"    {' '.join(pddl_room_names)} - ubicacion",
            f"    {' '.join(planta_names)} - planta",
        ]

        # Load current closure state and build a set of closed (pddl_id)
        closed_set = self._build_closed_set(building_name)
        closed_pddl_ids: Set[str] = set()
        for pddl_id, floor, json_id in all_rooms:
            if (building_name, int(floor), json_id) in closed_set:
                closed_pddl_ids.add(pddl_id)

        # Init section
        init_lines: List[str] = ["    (= (total-cost) 0)"]
        init_lines.append(f"    (en robot1 {origin_pddl})")

        if hurry_mode:
            init_lines.append("    (modo_rapido)")

        # (abierto X) for every room that is NOT in the closure set.
        # Closed rooms simply do not receive the fact — all actions that
        # need them fail their precondition and the planner picks around.
        for pddl_id, _floor, _json_id in sorted(all_rooms):
            if pddl_id not in closed_pddl_ids:
                init_lines.append(f"    (abierto {pddl_id})")

        # Floor assignments for every room
        for pddl_id, floor, _json_id in sorted(all_rooms):
            init_lines.append(
                f"    (en_planta {pddl_id} {_floor_str(floor)})"
            )

        # Elevator / stair tags (one per floor, at the ascensor/escaleras nodes)
        for floor in floors_set:
            init_lines.append(
                f"    (es_ascensor {self.location_to_pddl('ascensor', floor)})"
            )
            init_lines.append(
                f"    (es_escalera {self.location_to_pddl('escaleras', floor)})"
            )

        # Hallway connections derived from local_connections (per-floor edges).
        # Each edge emits BOTH the topology fact and the numeric distance
        # so the PDDL planner can cost-optimise the path in meters.
        default_distance = 10  # fallback when distance_m is missing from JSON
        for lc in self.data.get("local_connections", []):
            if lc.get("building") != building_name:
                continue
            floor = lc.get("floor")
            if floor is None:
                continue
            from_pddl = self.location_to_pddl(lc["from"], floor)
            to_pddl = self.location_to_pddl(lc["to"], floor)
            distance = lc.get("distance_m")
            if not isinstance(distance, (int, float)) or distance <= 0:
                distance = default_distance
            distance = int(round(distance))
            init_lines.append(
                f"    (conectado_pasillo {from_pddl} {to_pddl})"
            )
            init_lines.append(
                f"    (= (distancia {from_pddl} {to_pddl}) {distance})"
            )

        # Elevator vertical connections (bidirectional, all-to-all between floors)
        elevator_ids = [
            self.location_to_pddl("ascensor", f) for f in floors_set
        ]
        for i, a in enumerate(elevator_ids):
            for j, b in enumerate(elevator_ids):
                if i != j:
                    init_lines.append(f"    (conectado_ascensor {a} {b})")

        # Stair directed connections between ADJACENT floors only.
        # Unlike the elevator (which can skip floors in a single ride),
        # a real staircase forces the user to stop on every floor.
        sorted_floors = sorted(floors_set)
        for i in range(len(sorted_floors) - 1):
            lower_floor = sorted_floors[i]
            upper_floor = sorted_floors[i + 1]
            lower = self.location_to_pddl("escaleras", lower_floor)
            upper = self.location_to_pddl("escaleras", upper_floor)
            init_lines.append(
                f"    (conectado_escalera_subir {lower} {upper})"
            )
            init_lines.append(
                f"    (conectado_escalera_bajar {upper} {lower})"
            )

        # Build final PDDL problem text
        problem_name = problem_name or f"{building_name.lower()}-intra-problem"
        domain = self.domain_name(building_id)

        content = (
            f"(define (problem {problem_name})\n"
            f"  (:domain {domain})\n"
            f"\n"
            f"  (:objects\n"
            + "\n".join(objects_lines) + "\n"
            f"  )\n"
            f"\n"
            f"  (:init\n"
            + "\n".join(init_lines) + "\n"
            f"  )\n"
            f"\n"
            f"  (:goal\n"
            f"    (en robot1 {dest_pddl})\n"
            f"  )\n"
            f"\n"
            f"  (:metric minimize (total-cost))\n"
            f")\n"
        )

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

        return content


if __name__ == "__main__":
    import sys
    BASE = Path(__file__).parent.parent.parent
    converter = HierarchicalPDDLConverter(
        json_path=str(BASE / "config" / "campus_graph.json"),
        pddl_dir=str(BASE / "pddl"),
    )

    print("=== Building G: entrada_principal (floor 0) -> aula_1_4 (floor 1) ===")
    print(converter.generate_building_problem(
        building_id=1,
        origin_room="entrada_principal", origin_floor=0,
        dest_room="aula_1_4", dest_floor=1,
        problem_name="g-entrada-to-aula14",
    ))

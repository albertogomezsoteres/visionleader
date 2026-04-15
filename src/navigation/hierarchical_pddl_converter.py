"""Room-level PDDL problem generator for building-specific domains.

Used by ``pddl/domain_indoor.pddl``, which is shared by all 14 UFV buildings.

For Building G, the generated problem encodes the full room graph with
measured metric distances (`distancia` fluents), supports dynamic closures
via ``config/closed_rooms.json`` and the hurry-mode flag. For the rest of
the campus, the problem is built from the same JSON topology with a
default 15 m hop distance approximation.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .pddl_helpers import floor_str


class HierarchicalPDDLConverter:
    """Builds a per-building PDDL problem with the full room graph in :init."""

    # Location IDs that repeat on several floors (same name in the JSON)
    # must be disambiguated with a floor suffix in PDDL.
    SHARED_LOC_IDS: Set[str] = {"ascensor", "escaleras", "bano"}

    # Buildings that physically have an elevator (ascensor nodes in campus_graph).
    HAS_ELEVATOR: Set[int] = {1, 4, 5, 6}   # G, P, O, M

    # Default distance for non-G buildings (approximate, 15 m per hop).
    # G uses exact measured distances from campus_topology.json.
    DEFAULT_DISTANCE_NON_G: int = 15

    # Per-building PDDL domain filenames — all buildings share domain_indoor.pddl.
    BUILDING_DOMAINS: Dict[int, str] = {
        i: "domain_indoor.pddl" for i in range(1, 15)
    }

    # :domain directive name inside each problem file
    BUILDING_DOMAIN_NAMES: Dict[int, str] = {
        i: "building-indoor" for i in range(1, 15)
    }

    # Mapping from numeric building id to the campus_topology.json "locations" key
    BUILDING_JSON_NAMES: Dict[int, str] = {
        1:  "G",  2:  "CD",  3:  "H",   4:  "P",
        5:  "O",  6:  "M",   7:  "N",   8:  "CSQ",
        9:  "K",  10: "CSC", 11: "C",   12: "E",
        13: "CM", 14: "LCB",
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

    # Room id translation (PDDL <-> campus_topology.json)
    @classmethod
    def location_to_pddl(cls, location_id: str, floor: int) -> str:
        """Convert a campus location_id + floor to a unique PDDL ubicacion name.

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
        """Reverse mapping: PDDL ubicacion id -> (json location_id, floor or None).

        For shared ids like ascensor_p0 returns ('ascensor', 0).
        For unique ids like aula_1_4 returns ('aula_1_4', None).
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
        """Resolve a functional goal (cafeteria, gym) to (location_id, floor)
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

        for floor, locs in self.building_locations(building_id).items():
            for loc in locs:
                if loc.get("type") == target:
                    return (loc["id"], floor)
        return None

    # Building-G problem generation
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
        """Build an intra-building PDDL problem file with the full room graph
        in :init. Only Building G is fully detailed.

        origin_room / dest_room are campus_topology location_ids. The converter
        translates them into PDDL ubicacion ids using location_to_pddl.
        """
        building_name = self.json_name(building_id)
        locations_by_floor = self.building_locations(building_id)
        if not locations_by_floor:
            raise ValueError(
                f"No locations found in campus_topology.json for building '{building_name}'"
            )

        origin_pddl = self.location_to_pddl(origin_room, origin_floor)

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

        all_rooms: List[Tuple[str, int, str]] = []
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
        planta_names = [floor_str(f) for f in floors_set]
        pddl_room_names = sorted(r[0] for r in all_rooms)

        objects_lines = [
            f"    robot1 - robot",
            f"    {' '.join(pddl_room_names)} - ubicacion",
            f"    {' '.join(planta_names)} - planta",
        ]

        closed_set = self._build_closed_set(building_name)
        closed_pddl_ids: Set[str] = set()
        for pddl_id, floor, json_id in all_rooms:
            if (building_name, int(floor), json_id) in closed_set:
                closed_pddl_ids.add(pddl_id)

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

        for pddl_id, floor, _json_id in sorted(all_rooms):
            init_lines.append(
                f"    (en_planta {pddl_id} {floor_str(floor)})"
            )

        # Elevator / stair tags — only for nodes that exist in this building.
        building_has_elevator = building_id in self.HAS_ELEVATOR
        for floor in floors_set:
            locs_on_floor = {
                loc["id"]
                for loc in locations_by_floor.get(floor, [])
            }
            if building_has_elevator and "ascensor" in locs_on_floor:
                init_lines.append(
                    f"    (es_ascensor {self.location_to_pddl('ascensor', floor)})"
                )
            if "escaleras" in locs_on_floor:
                init_lines.append(
                    f"    (es_escalera {self.location_to_pddl('escaleras', floor)})"
                )

        # Hallway connections from local_connections (per-floor edges).
        # Each edge emits BOTH the topology fact and the numeric distance
        # so the planner can cost-optimise the path in meters.
        # G uses exact measured distances; other buildings fall back to 15 m.
        default_distance = (
            10 if building_id == 1 else self.DEFAULT_DISTANCE_NON_G
        )
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

        # Elevator vertical connections (bidirectional, all-to-all between floors).
        if building_has_elevator:
            elevator_ids = [
                self.location_to_pddl("ascensor", f) for f in floors_set
            ]
            for i, a in enumerate(elevator_ids):
                for j, b in enumerate(elevator_ids):
                    if i != j:
                        init_lines.append(f"    (conectado_ascensor {a} {b})")

        # Stair directed connections between ADJACENT floors only.
        all_loc_ids = {
            loc["id"]
            for locs in locations_by_floor.values()
            for loc in locs
        }
        if "escaleras" in all_loc_ids and len(floors_set) > 1:
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
    BASE = Path(__file__).parent.parent.parent
    converter = HierarchicalPDDLConverter(
        json_path=str(BASE / "config" / "campus_topology.json"),
        pddl_dir=str(BASE / "pddl"),
    )

    print("=== Building G: entrada_principal (floor 0) -> aula_1_4 (floor 1) ===")
    print(converter.generate_building_problem(
        building_id=1,
        origin_room="entrada_principal", origin_floor=0,
        dest_room="aula_1_4", dest_floor=1,
        problem_name="g-entrada-to-aula14",
    ))

"""Room-level PDDL problem generator for the shared campus domain.

Used by ``pddl/domain_indoor.pddl``, which models every UFV building plus the
outdoor hops between building entrances via the ``mover_exterior`` action.

For Building G, the generated problem encodes the full room graph with
measured metric distances (`distancia` fluents). Other buildings default
to 15 m hop distances. Cross-building routes are emitted as a single
problem containing both endpoints' rooms, linked by ``conectado_exterior``
edges between entrance nodes.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Domain filename and :domain directive shared by every problem.
DOMAIN_FILE = "domain_indoor.pddl"
DOMAIN_NAME = "campus-navigation"


class HierarchicalPDDLConverter:
    """Builds a PDDL problem encoding room graphs of one or more buildings."""

    # Location IDs that repeat across buildings / floors. To avoid name
    # collisions when two buildings appear in the same problem, these ids
    # get both a building prefix and a floor suffix in PDDL.
    SHARED_LOC_IDS: Set[str] = {"ascensor", "escaleras", "bano"}

    # Buildings that physically have an elevator (ascensor nodes in campus_graph).
    HAS_ELEVATOR: Set[int] = {1, 4, 5, 6}   # G, P, O, M

    # Default distance for non-G buildings (approximate, 15 m per hop).
    # G uses exact measured distances from campus_topology.json.
    DEFAULT_DISTANCE_NON_G: int = 15

    # Mapping from numeric building id to the campus_topology.json "locations" key
    BUILDING_JSON_NAMES: Dict[int, str] = {
        1:  "G",  2:  "CD",  3:  "H",   4:  "P",
        5:  "O",  6:  "M",   7:  "N",   8:  "CSQ",
        9:  "K",  10: "CSC", 11: "C",   12: "E",
        13: "CM", 14: "LCB",
        15: "Rodilla", 16: "Capilla",
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

    # Domain lookup — single shared domain for the whole campus.
    def get_domain_path(self, building_id: Optional[int] = None) -> Path:
        return self.pddl_dir / DOMAIN_FILE

    def domain_name(self, building_id: Optional[int] = None) -> str:
        return DOMAIN_NAME

    def json_name(self, building_id: int) -> str:
        return self.BUILDING_JSON_NAMES.get(building_id, "G")

    # Room id translation (PDDL <-> campus_topology.json)
    @classmethod
    def location_to_pddl(
        cls,
        location_id: str,
        floor: int,
        building_name: Optional[str] = None,
    ) -> str:
        """Convert a campus location_id + floor to a unique PDDL ubicacion name.

        Shared ids (ascensor, escaleras, bano) repeat across buildings and
        floors. They get both a building prefix and a floor suffix in PDDL:
        ``ascensor_G_p0``, ``escaleras_CD_pm1``.

        Unique ids (aula_0_1, lab_ia, entrada_cd, …) are returned unchanged.
        """
        if location_id in cls.SHARED_LOC_IDS:
            suffix = f"pm{abs(floor)}" if floor < 0 else f"p{floor}"
            if building_name:
                return f"{location_id}_{building_name}_{suffix}"
            return f"{location_id}_{suffix}"
        return location_id

    @classmethod
    def _canonical_building_name(cls, name: str) -> str:
        """Match a (possibly lowercased) building name to its canonical form.

        Fast Downward lowercases every id in its plan output, so a PDDL id
        that was generated as ``ascensor_CD_pm1`` comes back as
        ``ascensor_cd_pm1``. This helper maps ``'cd'`` back to ``'CD'`` so
        lookups in distance/hint tables keyed by canonical names succeed.
        """
        if not name:
            return name
        name_l = name.lower()
        for canonical in cls.BUILDING_JSON_NAMES.values():
            if canonical.lower() == name_l:
                return canonical
        return name

    @classmethod
    def pddl_to_location(
        cls, pddl_id: str
    ) -> Tuple[str, Optional[int], Optional[str]]:
        """Reverse mapping: PDDL id -> (json location_id, floor, building_name).

        Examples:
          ``ascensor_G_p0``    -> ('ascensor', 0, 'G')
          ``ascensor_g_p0``    -> ('ascensor', 0, 'G')   (lowercased by FD)
          ``escaleras_CD_pm1`` -> ('escaleras', -1, 'CD')
          ``aula_1_4``         -> ('aula_1_4', None, None)
        """
        for base in cls.SHARED_LOC_IDS:
            if not pddl_id.startswith(base + "_"):
                continue
            remainder = pddl_id[len(base) + 1:]
            # Try building-prefixed form first: {base}_{bld}_p{N} or _pm{N}
            parts = remainder.rsplit("_", 1)
            if len(parts) == 2:
                bld_name, floor_tag = parts
                bld_name = cls._canonical_building_name(bld_name)
                if floor_tag.startswith("pm"):
                    try:
                        return base, -int(floor_tag[2:]), bld_name
                    except ValueError:
                        pass
                elif floor_tag.startswith("p"):
                    try:
                        return base, int(floor_tag[1:]), bld_name
                    except ValueError:
                        pass
            # Fallback: no building prefix -> {base}_p{N} or _pm{N}
            if remainder.startswith("pm"):
                try:
                    return base, -int(remainder[2:]), None
                except ValueError:
                    pass
            elif remainder.startswith("p"):
                try:
                    return base, int(remainder[1:]), None
                except ValueError:
                    pass
        return pddl_id, None, None

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

    def find_functional_anywhere(
        self, goal_functional: str
    ) -> Optional[Tuple[int, str, int]]:
        """Scan every building for a functional goal. Returns
        (building_id, location_id, floor) or None.
        """
        for bid in self.BUILDING_JSON_NAMES:
            hit = self.find_functional_room(bid, goal_functional)
            if hit:
                return (bid, hit[0], hit[1])
        return None

    # Entrance helpers (for cross-building outdoor edges)
    def _entrance_of(self, building_id: int) -> Optional[Tuple[str, int]]:
        """Return (entrance_location_id, floor) for a building, or None."""
        for floor, locs in self.building_locations(building_id).items():
            for loc in locs:
                if loc.get("type") == "entrance":
                    return loc["id"], floor
        return None

    # Problem generation — supports one or two buildings in the same problem.
    def generate_building_problem(
        self,
        origin_building: int,
        origin_room: str,
        origin_floor: int,
        dest_building: Optional[int] = None,
        dest_room: Optional[str] = None,
        dest_floor: Optional[int] = None,
        goal_functional: Optional[str] = None,
        hurry_mode: bool = False,
        problem_name: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Build a PDDL problem encoding one or more buildings.

        If ``dest_building`` differs from ``origin_building``, both buildings
        are included in the :init section and linked by ``conectado_exterior``
        edges between their entrance nodes, so a single Fast Downward call
        finds the whole door-to-door route.
        """
        if goal_functional and not dest_room:
            # If the caller did not pin the destination building, scan the
            # whole campus so goals like "cafeteria" or "gym" resolve to
            # whichever building actually hosts them.
            if dest_building is None:
                hit = self.find_functional_anywhere(goal_functional)
                if not hit:
                    raise ValueError(
                        f"Functional goal '{goal_functional}' not found anywhere on campus"
                    )
                dest_building, dest_room, dest_floor = hit
            else:
                func = self.find_functional_room(dest_building, goal_functional)
                if not func:
                    raise ValueError(
                        f"Functional goal '{goal_functional}' not found in building "
                        f"{self.json_name(dest_building)}"
                    )
                dest_room, dest_floor = func

        if dest_building is None:
            dest_building = origin_building

        origin_bname = self.json_name(origin_building)
        dest_bname = self.json_name(dest_building)

        if not dest_room or dest_floor is None:
            raise ValueError("Provide dest_room+dest_floor or goal_functional")

        buildings_in_problem: List[int] = [origin_building]
        if dest_building != origin_building:
            buildings_in_problem.append(dest_building)

        origin_pddl = self.location_to_pddl(
            origin_room, origin_floor, origin_bname
        )
        dest_pddl = self.location_to_pddl(
            dest_room, dest_floor, dest_bname
        )

        all_rooms: List[Tuple[str, int, str, str]] = []  # (pddl, floor, json_id, bname)
        seen_pddl: Set[str] = set()
        for bid in buildings_in_problem:
            bname = self.json_name(bid)
            locations_by_floor = self.building_locations(bid)
            if not locations_by_floor:
                raise ValueError(
                    f"No locations found in campus_topology.json for building '{bname}'"
                )
            for floor in sorted(locations_by_floor.keys()):
                for loc in locations_by_floor[floor]:
                    json_id = loc["id"]
                    pddl_id = self.location_to_pddl(json_id, floor, bname)
                    if pddl_id in seen_pddl:
                        continue
                    seen_pddl.add(pddl_id)
                    all_rooms.append((pddl_id, floor, json_id, bname))

        floors_set = sorted({r[1] for r in all_rooms})
        pddl_room_names = sorted(r[0] for r in all_rooms)

        objects_lines = [
            f"    robot1 - robot",
            f"    {' '.join(pddl_room_names)} - location",
        ]

        closed_sets: Dict[str, Set[Tuple[str, int, str]]] = {
            self.json_name(bid): self._build_closed_set(self.json_name(bid))
            for bid in buildings_in_problem
        }
        closed_pddl_ids: Set[str] = set()
        for pddl_id, floor, json_id, bname in all_rooms:
            if (bname, int(floor), json_id) in closed_sets.get(bname, set()):
                closed_pddl_ids.add(pddl_id)

        init_lines: List[str] = ["    (= (total-cost) 0)"]
        init_lines.append(f"    (at robot1 {origin_pddl})")

        if hurry_mode:
            init_lines.append("    (hurry_mode)")

        for pddl_id, _floor, _json_id, _bname in sorted(all_rooms):
            if pddl_id not in closed_pddl_ids:
                init_lines.append(f"    (open {pddl_id})")

        # Elevator / stair tags — per building.
        for bid in buildings_in_problem:
            bname = self.json_name(bid)
            building_has_elevator = bid in self.HAS_ELEVATOR
            locations_by_floor = self.building_locations(bid)
            for floor, locs in locations_by_floor.items():
                locs_on_floor = {loc["id"] for loc in locs}
                if building_has_elevator and "ascensor" in locs_on_floor:
                    init_lines.append(
                        f"    (is_elevator {self.location_to_pddl('ascensor', floor, bname)})"
                    )
                if "escaleras" in locs_on_floor:
                    init_lines.append(
                        f"    (is_stairs {self.location_to_pddl('escaleras', floor, bname)})"
                    )

        # Hallway connections from local_connections (per-floor edges).
        for bid in buildings_in_problem:
            bname = self.json_name(bid)
            default_distance = 10 if bid == 1 else self.DEFAULT_DISTANCE_NON_G
            for lc in self.data.get("local_connections", []):
                if lc.get("building") != bname:
                    continue
                floor = lc.get("floor")
                if floor is None:
                    continue
                from_pddl = self.location_to_pddl(lc["from"], floor, bname)
                to_pddl = self.location_to_pddl(lc["to"], floor, bname)
                distance = lc.get("distance_m")
                if not isinstance(distance, (int, float)) or distance <= 0:
                    distance = default_distance
                distance = int(round(distance))
                init_lines.append(
                    f"    (hallway_connected {from_pddl} {to_pddl})"
                )
                init_lines.append(
                    f"    (= (distance {from_pddl} {to_pddl}) {distance})"
                )

        # Elevator vertical connections (per building).
        for bid in buildings_in_problem:
            if bid not in self.HAS_ELEVATOR:
                continue
            bname = self.json_name(bid)
            locations_by_floor = self.building_locations(bid)
            bld_floors = sorted(locations_by_floor.keys())
            elevator_ids = [
                self.location_to_pddl("ascensor", f, bname)
                for f in bld_floors
                if any(l.get("id") == "ascensor" for l in locations_by_floor.get(f, []))
            ]
            for i, a in enumerate(elevator_ids):
                for j, b in enumerate(elevator_ids):
                    if i != j:
                        init_lines.append(f"    (elevator_connected {a} {b})")

        # Stair directed connections (adjacent floors only, per building).
        for bid in buildings_in_problem:
            bname = self.json_name(bid)
            locations_by_floor = self.building_locations(bid)
            stair_floors = sorted(
                f for f, locs in locations_by_floor.items()
                if any(l.get("id") == "escaleras" for l in locs)
            )
            for i in range(len(stair_floors) - 1):
                lower_floor = stair_floors[i]
                upper_floor = stair_floors[i + 1]
                lower = self.location_to_pddl("escaleras", lower_floor, bname)
                upper = self.location_to_pddl("escaleras", upper_floor, bname)
                init_lines.append(
                    f"    (stairs_up_connected {lower} {upper})"
                )
                init_lines.append(
                    f"    (stairs_down_connected {upper} {lower})"
                )

        # Outdoor edges between entrances — only emitted when at least two
        # buildings are in the problem.
        if len(buildings_in_problem) > 1:
            bset = set(buildings_in_problem)
            for conn in self.data.get("connections", []) or []:
                f_bld = (conn.get("from") or {}).get("building")
                t_bld = (conn.get("to") or {}).get("building")
                if f_bld is None or t_bld is None or f_bld == t_bld:
                    continue
                if f_bld not in bset or t_bld not in bset:
                    continue
                f_entry = self._entrance_of(f_bld)
                t_entry = self._entrance_of(t_bld)
                if not f_entry or not t_entry:
                    continue
                f_pddl = self.location_to_pddl(
                    f_entry[0], f_entry[1], self.json_name(f_bld)
                )
                t_pddl = self.location_to_pddl(
                    t_entry[0], t_entry[1], self.json_name(t_bld)
                )
                init_lines.append(
                    f"    (outdoor_connected {f_pddl} {t_pddl})"
                )

        problem_name = problem_name or (
            f"{origin_bname.lower()}-to-{dest_bname.lower()}-problem"
        )

        content = (
            f"(define (problem {problem_name})\n"
            f"  (:domain {DOMAIN_NAME})\n"
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
            f"    (at robot1 {dest_pddl})\n"
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
        origin_building=1,
        origin_room="entrada_principal", origin_floor=0,
        dest_room="aula_1_4", dest_floor=1,
        problem_name="g-entrada-to-aula14",
    ))

    print("=== Cross-building: aula_1_4 of G -> gym of CD ===")
    print(converter.generate_building_problem(
        origin_building=1,
        origin_room="aula_1_4", origin_floor=1,
        dest_building=2,
        goal_functional="gym",
        problem_name="g-to-cd-gym",
    ))

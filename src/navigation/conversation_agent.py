"""
Conversational Navigation Agent: full interactive flow.

States:
  WELCOME → ASK_KNOWS_LOCATION → (voice) ASK_LOCATION_VOICE / (photo) ASK_SITUATION
  → CONFIRMING_ORIGIN → ASK_DESTINATION → CONFIRMING_PLAN
  → EXECUTING → AWAITING_STEP_DONE / WAITING_STEP_PHOTO
  → NAVIGATION_COMPLETE
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from pathlib import Path
import logging
import re
import json
import tempfile

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    WELCOME = "welcome"
    ASK_KNOWS_LOCATION = "ask_knows_location"
    ASK_LOCATION_VOICE = "ask_location_voice"
    ASK_SITUATION = "ask_situation"
    WAITING_PHOTO_DOOR = "waiting_photo_door"
    WAITING_PHOTO_SIGN = "waiting_photo_sign"
    ASK_BUILDING = "ask_building"
    ASK_FLOOR = "ask_floor"
    CONFIRMING_ORIGIN = "confirming_origin"
    ASK_DESTINATION = "ask_destination"
    CONFIRMING_PLAN = "confirming_plan"
    EXECUTING = "executing"
    AWAITING_STEP_DONE = "awaiting_step_done"
    WAITING_STEP_PHOTO = "waiting_step_photo"
    NAVIGATION_COMPLETE = "navigation_complete"


# Parsing helpers
_AFFIRM = {"yes", "yeah", "yep", "sure", "ok", "okay", "correct", "right",
           "sí", "si", "vale", "claro", "por supuesto", "confirm", "confirmed"}
_NEGATE = {"no", "nope", "nah", "cancel", "wrong", "incorrect", "not",
           "don't", "dont"}

_BUILDING_MAP = {
    "g": 1,   "politécnica": 1, "politecnica": 1, "eps": 1,
    "cd": 2,  "centro deportivo": 2, "sports": 2, "sport": 2,
    "h": 3,
    "p": 4,
    "o": 5,
    "m": 6,
    "n": 7,
    "csq": 8,
    "k": 9,
    "csc": 10,
    "c": 11,
    "e": 12,
    "cm": 13,
    "lcb": 14,
}
_BUILDING_NAMES = {
    1: "G",  2: "CD",  3: "H",  4: "P",
    5: "O",  6: "M",   7: "N",  8: "CSQ",
    9: "K",  10: "CSC", 11: "C", 12: "E",
    13: "CM", 14: "LCB",
}
_BUILDING_FULL = {
    1:  "Building G (EPS)",
    2:  "Building CD (Centro Deportivo)",
    3:  "Building H",
    4:  "Building P",
    5:  "Building O",
    6:  "Building M",
    7:  "Building N",
    8:  "Building CSQ",
    9:  "Building K",
    10: "Building CSC",
    11: "Building C",
    12: "Building E",
    13: "Building CM",
    14: "Building LCB",
}

_FLOOR_WORDS = {
    "ground": 0, "ground floor": 0, "first": 1, "first floor": 1,
    "second": 2, "second floor": 2, 
    "basement": -1, "minus one": -1, "minus 1": -1,
    "planta baja": 0, "planta 0": 0, "planta 1": 1, "planta 2": 2,
    "planta -1": -1, "floor 0": 0, "floor 1": 1, "floor 2": 2,
    "floor -1": -1, "0": 0, "1": 1, "2": 2,
}


def _is_yes(msg: str) -> bool:
    words = set(msg.lower().split())
    return bool(words & _AFFIRM)


def _is_no(msg: str) -> bool:
    words = set(msg.lower().split())
    has_neg = bool(words & _NEGATE)
    has_aff = bool(words & _AFFIRM)
    return has_neg and not has_aff


def _floor_text(f: int) -> str:
    if f == -1:
        return "the basement (floor −1)"
    if f == 0:
        return "the ground floor"
    return f"floor {f}"


# Context
class ConversationContext:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = ConversationState.WELCOME

        self.origin: Optional[Dict[str, Any]] = None
        self.destination: Optional[Dict[str, Any]] = None

        self.route_steps: List[Dict[str, Any]] = []
        self.current_step_idx: int = 0

        self.last_tts: str = ""
        self.photo_attempts: int = 0
        self.voice_retries: int = 0
        self.history: List[Dict[str, str]] = []
        self.hurry_mode: bool = False

        # Closure handling — populated by _compute_route when the original
        # destination was closed. Consumed by _present_plan (success) or
        # destination handlers (failure) to prepend an explanation.
        self.pending_announcement: Optional[str] = None
        self.closure_blocked: bool = False

        # Partial location accumulation (building known but floor unknown, etc.)
        self.partial_building: Optional[int] = None
        self.partial_floor: Optional[int] = None
        self.partial_location_id: Optional[str] = None

    # Convenience
    def current_location(self) -> Optional[Dict]:
        return self.origin

    def add(self, role: str, text: str):
        self.history.append({"role": role, "text": text})

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "current_location": self.origin,
            "goal": self.destination,
            "hurry_mode": self.hurry_mode,
            "conversation_history": self.history,
            "plan_steps": [s.get("instruction", "") for s in self.route_steps],
            "current_step_idx": self.current_step_idx,
        }


# Agent
class ConversationAgent:
    """Full conversational navigation agent."""

    def __init__(self, topology: Dict, places: Dict):
        """
        topology  — contents of config/campus_topology.json
                    (buildings, connections, local_connections, functional_locations).
                    Used only to instantiate the PDDL converters.
        places    — contents of config/campus_places.json
                    (building display names, room names/types/room_codes, TTS hints).
                    Used only for TTS decoration and room recognition.
        """
        self._topology = topology
        self._places   = places
        self.contexts: Dict[str, ConversationContext] = {}

        # Distance lookup: "<building>_<floor>_<from>_<to>" -> meters (int)
        # Populated from topology — distances are PDDL data, not display data.
        self._local_distance: Dict[str, int] = {}
        for lc in topology.get("local_connections", []):
            dist = lc.get("distance_m")
            if isinstance(dist, (int, float)) and dist > 0:
                key = f"{lc['building']}_{lc['floor']}_{lc['from']}_{lc['to']}"
                self._local_distance[key] = int(round(dist))

        # Hint lookup: "<building>_<floor>_<from>_<to>" -> short directional string
        # Populated from places — hints are TTS decoration only.
        self._local_hint: Dict[str, str] = dict(places.get("hints", {}))

        # Location index: {building_name -> {floor_str -> [loc_dicts]}}
        self._locations = places.get("locations", {})

        # Known room codes -> (building_id, floor, location_id)
        self._room_lookup: Dict[str, tuple] = {}
        for bname, floors in self._locations.items():
            bid = self._building_id(bname)
            for fstr, locs in floors.items():
                for loc in locs:
                    if loc.get("room_code"):
                        self._room_lookup[loc["room_code"].lower()] = (bid, int(fstr), loc["id"])
                    self._room_lookup[f"{bname.lower()}_{fstr}_{loc['id']}"] = (bid, int(fstr), loc["id"])

        # Fast Downward integration
        self._planner = None
        self._converter = None                # legacy floor-level converter
        self._hierarchical_converter = None   # room-level building converter
        self._domain_path = None
        self._pddl_dir = None
        self._init_planner()

    def _init_planner(self):
        """Initialize Fast Downward planner and both PDDL converters.

        Two converters are created:
          - CampusGraphToPDDL: used by domain_outdoor.pddl for
            inter-building (building + floor level) plans.
          - HierarchicalPDDLConverter: used by domain_indoor.pddl for
            room-level planning inside any single building.
        """
        try:
            from navigation.fast_downward_client import FastDownwardPlanner
            from navigation.pddl_converter import (
                CampusGraphToPDDL,
                HierarchicalPDDLConverter,
            )

            base_dir = Path(__file__).parent.parent.parent
            campus_json = base_dir / "config" / "campus_topology.json"
            self._domain_path = base_dir / "pddl" / "domain_outdoor.pddl"
            self._pddl_dir = base_dir / "pddl"

            self._planner = FastDownwardPlanner()
            self._converter = CampusGraphToPDDL(str(campus_json))
            closed_rooms_path = base_dir / "config" / "closed_rooms.json"
            self._hierarchical_converter = HierarchicalPDDLConverter(
                json_path=str(campus_json),
                pddl_dir=str(self._pddl_dir),
                closed_rooms_path=str(closed_rooms_path),
            )
            logger.info(
                "Fast Downward + hierarchical converter initialized OK"
            )
        except Exception as e:
            logger.warning("Could not init Fast Downward: %s", e)
            self._planner = None
            self._converter = None
            self._hierarchical_converter = None

    def _run_fast_downward(
        self, origin_building: int, origin_floor: int,
        dest_building: int, dest_floor: int,
        goal_functional: Optional[str] = None,
        hurry_mode: bool = False,
    ) -> Optional[List[str]]:
        """
        Call Fast Downward to generate a PDDL plan.
        Returns list of action strings or None on failure.
        """
        if not self._planner or not self._converter:
            logger.warning("FD planner not available")
            return None

        initial_state = (origin_building, origin_floor)
        goal_state = None if goal_functional else (dest_building, dest_floor)

        problem_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.pddl',
                dir=str(self._pddl_dir), delete=False
            ) as f:
                problem_path = f.name
                self._converter.generate_problem(
                    initial_state=initial_state,
                    goal_state=goal_state,
                    goal_functional=goal_functional,
                    problem_name="conv-problem",
                    output_path=problem_path,
                    hurry_mode=hurry_mode,
                )

            result = self._planner.plan(
                domain_path=str(self._domain_path),
                problem_path=problem_path,
            )

            if result.get("success"):
                actions = result.get("plan", [])
                logger.info(
                    "FD plan found: %d actions, cost=%s",
                    len(actions), result.get("cost"),
                )
                for a in actions:
                    logger.debug("  FD: %s", a)
                return actions
            logger.warning("FD no plan found: %s", result.get("error"))
            return None
        except Exception as e:
            logger.exception("FD error: %s", e)
            return None
        finally:
            if problem_path:
                try:
                    Path(problem_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _run_hierarchical_building_planner(
        self,
        building_id: int,
        origin_room: str, origin_floor: int,
        dest_room: Optional[str], dest_floor: Optional[int],
        goal_functional: Optional[str] = None,
        hurry_mode: bool = False,
    ) -> Optional[List[str]]:
        """
        Call Fast Downward with a building-specific, room-level domain.

        Uses self._hierarchical_converter to generate a problem file whose
        :init section encodes the full intra-building graph, and loads
        domain_indoor.pddl. Returns the list of PDDL action strings or None on failure.
        """
        if not self._planner or not self._hierarchical_converter:
            logger.warning("FD hierarchical planner/converter not available")
            return None

        try:
            domain_path = self._hierarchical_converter.get_domain_path(building_id)
        except ValueError as e:
            logger.warning("FD hierarchical: %s", e)
            return None

        if not domain_path.exists():
            logger.error("FD hierarchical domain file not found: %s", domain_path)
            return None

        problem_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.pddl',
                dir=str(self._pddl_dir), delete=False
            ) as f:
                problem_path = f.name
                self._hierarchical_converter.generate_building_problem(
                    building_id=building_id,
                    origin_room=origin_room,
                    origin_floor=origin_floor,
                    dest_room=dest_room,
                    dest_floor=dest_floor,
                    goal_functional=goal_functional,
                    hurry_mode=hurry_mode,
                    output_path=problem_path,
                )

            result = self._planner.plan(
                domain_path=str(domain_path),
                problem_path=problem_path,
            )

            if result.get("success"):
                actions = result.get("plan", [])
                logger.info(
                    "FD hierarchical plan for building %d: %d actions, cost=%s",
                    building_id, len(actions), result.get("cost"),
                )
                for a in actions:
                    logger.debug("  FD-H: %s", a)
                return actions
            logger.warning(
                "FD hierarchical no plan found: %s", result.get("error")
            )
            return None
        except Exception as e:
            logger.exception("FD hierarchical error: %s", e)
            return None
        finally:
            if problem_path:
                try:
                    Path(problem_path).unlink(missing_ok=True)
                except Exception:
                    pass

    # PDDL action parsing
    @staticmethod
    def _parse_fd_action(action_str: str) -> Optional[Dict]:
        """Parse a single PDDL action string into structured dict."""
        clean = re.sub(r'\s*\(\d+\)\s*$', '', action_str).strip()
        parts = clean.split()
        if not parts:
            return None
        return {"name": parts[0], "params": parts[1:]}

    @staticmethod
    def _normalize_room_code(code: str) -> str:
        """
        Normalize room-code variants to canonical form (e.g. "14" -> "1.4").
        """
        raw = str(code).strip().lower()
        m = re.search(r"(\d+\.\d+)", raw)
        if m:
            s = m.group(1)
        else:
            digits = re.sub(r"\D", "", raw)
            # PaliGemma sometimes emits "14" instead of "1.4"
            if len(digits) == 2 and digits[0].isdigit() and digits[1].isdigit():
                return f"{int(digits[0])}.{int(digits[1])}"
            return raw
        # Avoid float string artifacts: "1.30" should become "1.3"
        try:
            parts = s.split(".")
            if len(parts) == 2:
                return f"{int(parts[0])}.{int(parts[1])}"
        except Exception:
            pass
        return s.strip()

    def _extract_room_code_from_analysis(
        self, analysis: Optional[Dict]
    ) -> Optional[str]:
        if not analysis:
            return None
        for lm in analysis.get("landmarks", []) or []:
            match = re.search(r"(\d+\.\d+)", str(lm))
            if match:
                return self._normalize_room_code(match.group(1))
            compact = re.search(r"\b(\d{2})\b", str(lm))
            if compact:
                return self._normalize_room_code(compact.group(1))
        # Some image types (e.g., door) may not return landmarks, but the raw
        # response often contains the extracted classroom number.
        raw = analysis.get("raw_response") or analysis.get("raw") or ""
        match = re.search(r"(\d+\.\d+)", str(raw))
        if match:
            return self._normalize_room_code(match.group(1))
        compact = re.search(r"\b(\d{2})\b", str(raw))
        if compact:
            return self._normalize_room_code(compact.group(1))
        return None

    def _room_code_for_location(
        self,
        building_id: int,
        floor: int,
        location_id: Optional[str],
    ) -> Optional[str]:
        if not location_id:
            return None
        floor_key = str(floor)
        for bname, floors in (self._locations or {}).items():
            bid = self._building_id(bname)
            if bid != building_id:
                continue
            locs = (floors or {}).get(floor_key, []) or []
            for loc in locs:
                if loc.get("id") == location_id and loc.get("room_code"):
                    return str(loc.get("room_code"))
        return None

    def _apply_arrival_strict_photo(
        self, steps: List[Dict], destination: Dict
    ) -> List[Dict]:
        """If destination is a classroom with a room_code (e.g. 1.3),
        replace the last local step into a strict door-photo checkpoint."""
        if not steps:
            return steps

        dest_room_code = self._room_code_for_location(
            destination.get("building"),
            destination.get("floor"),
            destination.get("location_id"),
        )
        if not dest_room_code:
            return steps

        last = steps[-1]
        # Only override if the last step is currently a voice/travel step.
        if last.get("verification") != "photo":
            last["verification"] = "photo"
            last["expected_photo_type"] = "door"
            last["arrival_strict_photo"] = True
            last["expected_room_code"] = dest_room_code
        else:
            # If it is already a photo checkpoint, still enforce strict room code.
            last["arrival_strict_photo"] = True
            last["expected_room_code"] = dest_room_code
        return steps

    @staticmethod
    def _planta_to_int(planta_str: str) -> int:
        if planta_str.startswith("planta_m"):
            return -int(planta_str[8:])
        if planta_str.startswith("planta_"):
            return int(planta_str[7:])
        return 0

    @staticmethod
    def _edificio_to_int(edificio_str: str) -> int:
        if edificio_str.startswith("edificio_"):
            return int(edificio_str[9:])
        return 0

    def _fd_plan_to_steps(
        self, fd_actions: List[str], origin: Dict, destination: Dict
    ) -> Optional[List[Dict]]:
        """Convert Fast Downward PDDL actions into navigation steps
        enriched with local walking instructions from the campus graph."""
        steps: List[Dict] = []

        o_loc = origin.get("location_id")
        d_bld = destination.get("building")
        d_flr = destination.get("floor")
        d_loc = destination.get("location_id")

        first_movement = True
        last_arrival_loc: Optional[str] = None

        for action_str in fd_actions:
            parsed = self._parse_fd_action(action_str)
            if not parsed:
                continue
            name = parsed["name"]
            params = parsed["params"]

            if name in ("verificar_ascensor", "validar_escaleras"):
                continue

            if name == "usar_ascensor":
                # params: robot1 edificio_X planta_from planta_to elevator
                bld_id = self._edificio_to_int(params[1])
                from_floor = self._planta_to_int(params[2])
                to_floor = self._planta_to_int(params[3])
                bname = _BUILDING_NAMES.get(bld_id, "G")
                pre_verified_at_elevator = False

                if first_movement and o_loc and o_loc != "ascensor":
                    instr = None
                    if instr:
                        steps.append({
                            "instruction": self._normalize_instruction(
                                " ".join(instr)
                                + " When you reach the elevator, please take a photo to verify it."
                            ),
                            "type": "local_walk",
                            "verification": "photo",
                            "expected_photo_type": "elevator",
                            "inline_photo_prompt": True,
                        })
                        pre_verified_at_elevator = True

                conn_instr = None
                instr_text = (
                    " ".join(conn_instr) if conn_instr
                    else (
                        f"Take the elevator from {_floor_text(from_floor)} "
                        f"to {_floor_text(to_floor)}. "
                        "Press the button and wait for the doors to open."
                    )
                )
                steps.append({
                    "instruction": self._normalize_instruction(instr_text),
                    "type": "elevator",
                    "verification": "voice" if pre_verified_at_elevator else "photo",
                    "expected_photo_type": None if pre_verified_at_elevator else "elevator",
                    "post_photo_instruction": f"Enter the elevator, press floor {to_floor}, and exit when you arrive.",
                })
                last_arrival_loc = "ascensor"
                first_movement = False

            elif name in ("subir_escaleras", "bajar_escaleras",
                         "subir_escaleras_rapido", "bajar_escaleras_rapido"):
                bld_id = self._edificio_to_int(params[1])
                from_floor = self._planta_to_int(params[2])
                to_floor = self._planta_to_int(params[3])
                bname = _BUILDING_NAMES.get(bld_id, "G")
                direction = "up" if "subir" in name else "down"

                if first_movement and o_loc and o_loc != "escaleras":
                    instr = None
                    if instr:
                        steps.append({
                            "instruction": self._normalize_instruction(" ".join(instr)),
                            "type": "local_walk",
                            "verification": "voice",
                            "expected_photo_type": None,
                        })

                conn_instr = None
                is_hurry = "rapido" in name
                safety_msg = (
                    f"Go {direction} the stairs from {_floor_text(from_floor)} "
                    f"to {_floor_text(to_floor)}. "
                )
                if is_hurry:
                    safety_msg += "Take the stairs quickly, but be careful."
                else:
                    safety_msg += (
                        "Hold the handrail firmly with one hand. "
                        "Take it one step at a time."
                    )
                instr_text = " ".join(conn_instr) if conn_instr else safety_msg

                photo_confirm_msg = (
                    f"I can see the stairs going {direction}. " + safety_msg
                    if not is_hurry
                    else f"I can see the stairs going {direction}. Go ahead carefully."
                )
                steps.append({
                    "instruction": self._normalize_instruction(instr_text),
                    "type": "stairs",
                    "verification": "photo",
                    "expected_photo_type": "stairs",
                    "two_phase_photo": True,
                    "pre_photo_instruction": (
                        f"Locate the stairs on {_floor_text(from_floor)}. "
                        "Please take a photo so I can confirm they go "
                        f"{'up' if direction == 'up' else 'down'} and have a handrail."
                    ),
                    "post_photo_instruction": photo_confirm_msg,
                    "stairs_direction": direction,
                })
                last_arrival_loc = "escaleras"
                first_movement = False

            elif name == "mover_edificio":
                from_bld = self._edificio_to_int(params[1])
                to_bld = self._edificio_to_int(params[2])
                floor = self._planta_to_int(params[3])

                from_entrance = self._entrance_id(from_bld)
                to_entrance = self._entrance_id(to_bld)

                added_walk_to_entrance = False
                if first_movement and o_loc and o_loc != from_entrance:
                    bname = _BUILDING_NAMES.get(from_bld, "G")
                    instr = None
                    if instr:
                        steps.append({
                            "instruction": self._normalize_instruction(
                                " ".join(instr)
                                + " Then exit the building through the two glass doors."
                            ),
                            "type": "local_walk",
                            "verification": "voice",
                            "expected_photo_type": None,
                        })
                        added_walk_to_entrance = True

                to_name = _BUILDING_FULL.get(to_bld, "the destination building")
                hallway_instr = None
                if hallway_instr:
                    instr_text = " ".join(hallway_instr)
                elif added_walk_to_entrance:
                    instr_text = "Opening Google Maps for outdoor route navigation."
                else:
                    instr_text = (
                        f"Head to the main entrance of {_BUILDING_FULL.get(from_bld, 'the building')}. "
                        "Push through the two glass doors to exit the building. "
                        "Opening Google Maps for outdoor route navigation."
                    )
                steps.append({
                    "instruction": self._normalize_instruction(instr_text),
                    "type": "outdoor",
                    "verification": "voice",
                    "expected_photo_type": None,
                    "outdoor_from_building": from_bld,
                    "outdoor_to_building": to_bld,
                    "use_gps": True,
                })
                last_arrival_loc = to_entrance
                first_movement = False

        # Final local walk: from arrival point to destination location
        if d_loc and last_arrival_loc and d_loc != last_arrival_loc:
            bname = _BUILDING_NAMES.get(d_bld, "G")
            instr = None
            if instr:
                steps.append({
                    "instruction": self._normalize_instruction(" ".join(instr)),
                    "type": "local_walk",
                    "verification": "voice",
                    "expected_photo_type": None,
                })

        return steps if steps else None

    def _fd_plan_to_steps_room_level(
        self, fd_actions: List[str], origin: Dict, destination: Dict
    ) -> Optional[List[Dict]]:
        """
        Convert a room-level plan (from a building-specific PDDL domain) into
        navigation steps. Actions at this level carry ubicacion parameters:

          caminar robot1 <room_from> <room_to>
          verificar_ascensor robot1 <ascensor_pX>       (skipped in instructions)
          usar_ascensor robot1 <ascensor_pX> <ascensor_pY>
          validar_escaleras robot1 <escaleras_pX>       (skipped in instructions)
          subir_escaleras robot1 <escaleras_pX> <escaleras_pY>
          bajar_escaleras robot1 <escaleras_pX> <escaleras_pY>
          subir_escaleras_rapido / bajar_escaleras_rapido

        Consecutive caminar hops are merged into a single walking step
        enriched with the text from campus_graph.json local_connections
        (so the user still hears natural navigation instructions).
        """
        from navigation.pddl_converter import HierarchicalPDDLConverter

        steps: List[Dict] = []
        bname = _BUILDING_NAMES.get(origin.get("building"), "G")
        current_floor = origin.get("floor", 0) or 0

        walk_buffer: List[Dict] = []  # buffered caminar hops

        def pddl_to_json(pddl_id: str, default_floor: int):
            """Return (json_location_id, floor) for a PDDL ubicacion id."""
            base, floor = HierarchicalPDDLConverter.pddl_to_location(pddl_id)
            if floor is not None:
                return base, floor
            # Unique id: look up its floor in campus_graph.json locations
            for f_str, locs in (self._locations.get(bname, {}) or {}).items():
                for loc in locs:
                    if loc.get("id") == base:
                        try:
                            return base, int(f_str)
                        except (TypeError, ValueError):
                            pass
            return base, default_floor

        def flush_walk():
            """Turn the buffered caminar hops into a single TTS step.

            Consecutive caminar hops on the same floor are merged: the
            distances are summed (so PDDL stays the authoritative source
            for the metric total) and the directional hint of the FINAL
            hop is used, since that is the one that ends at the user's
            immediate target. Intermediate nodes chosen by the planner
            for distance optimisation (e.g. passing by bano on a shortcut)
            do not appear in the TTS — the user only hears the final leg.

            The generated instruction follows the short demo-friendly
            pattern:
                "Walk {N}m, {hint}."          (when hint is present)
                "Walk {N}m to {pretty_name}." (when hint is missing)
            """
            if not walk_buffer:
                return

            total_distance = 0
            any_distance = False
            for hop in walk_buffer:
                key = f"{bname}_{hop['floor']}_{hop['json_from']}_{hop['json_to']}"
                d = self._local_distance.get(key)
                if d:
                    total_distance += d
                    any_distance = True

            final_hop = walk_buffer[-1]
            final_key = (
                f"{bname}_{final_hop['floor']}_"
                f"{final_hop['json_from']}_{final_hop['json_to']}"
            )
            final_hint = self._local_hint.get(final_key)
            final_target = self._nice_location_name(final_hop["json_to"])

            if any_distance and final_hint:
                sentence = f"Walk {total_distance} meters, {final_hint}."
            elif any_distance:
                sentence = f"Walk {total_distance} meters to {final_target}."
            elif final_hint:
                sentence = f"Walk to {final_target}, {final_hint}."
            else:
                sentence = f"Walk to {final_target}."

            steps.append({
                "instruction": self._normalize_instruction(sentence),
                "type": "local_walk",
                "verification": "voice",
                "expected_photo_type": None,
            })
            walk_buffer.clear()

        for action_str in fd_actions:
            parsed = self._parse_fd_action(action_str)
            if not parsed:
                continue
            name = parsed["name"]
            params = parsed["params"]

            # Skip internal safety-check actions (no user-visible step)
            if name in ("verificar_ascensor", "validar_escaleras"):
                continue

            if name == "caminar":
                # params: robot1 <from> <to>
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
                    "instruction": self._normalize_instruction(
                        f"Take the elevator from {_floor_text(from_floor)} "
                        f"to {_floor_text(to_floor)}. "
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
                    f"{_floor_text(from_floor)} to {_floor_text(to_floor)}. "
                )
                if is_hurry:
                    safety_msg += "Take the stairs quickly, but be careful."
                else:
                    safety_msg += (
                        "Hold the handrail firmly with one hand. "
                        "Take it one step at a time."
                    )

                steps.append({
                    "instruction": self._normalize_instruction(safety_msg),
                    "type": "stairs",
                    "verification": "photo",
                    "expected_photo_type": "stairs",
                    "two_phase_photo": True,
                    "pre_photo_instruction": (
                        f"Locate the stairs on {_floor_text(from_floor)}. "
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

    # Session management
    def get_or_create_context(self, session_id: str) -> ConversationContext:
        if session_id not in self.contexts:
            self.contexts[session_id] = ConversationContext(session_id)
        return self.contexts[session_id]

    # Main entry point
    def process_turn(
        self,
        session_id: str,
        user_message: Optional[str] = None,
        image_analysis: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Single entry-point for every conversational turn.
        Returns: {tts_message, next_input, state, action, context, ...}
        """
        ctx = self.get_or_create_context(session_id)
        msg = (user_message or "").strip()

        if msg:
            ctx.add("user", msg)

        # Universal voice commands during navigation
        if ctx.state in (
            ConversationState.EXECUTING,
            ConversationState.AWAITING_STEP_DONE,
            ConversationState.WAITING_STEP_PHOTO,
        ):
            low = msg.lower()
            if any(w in low for w in ("repeat", "again", "repite", "otra vez")):
                return self._reply(ctx, ctx.last_tts, self._current_next_input(ctx), "repeat")
            if any(w in low for w in ("lost", "help", "perdido", "ayuda")):
                return self._handle_lost(ctx)
            if any(w in low for w in ("cancel", "stop", "cancelar", "parar")):
                return self._cancel_navigation(ctx)

        # State routing
        handler = {
            ConversationState.WELCOME: lambda: self._handle_welcome(ctx),
            ConversationState.ASK_KNOWS_LOCATION: lambda: self._handle_ask_knows_location(ctx, msg),
            ConversationState.ASK_LOCATION_VOICE: lambda: self._handle_ask_location_voice(ctx, msg),
            ConversationState.ASK_SITUATION: lambda: self._handle_ask_situation(ctx, msg),
            ConversationState.WAITING_PHOTO_DOOR: lambda: self._handle_waiting_photo(ctx, image_analysis),
            ConversationState.WAITING_PHOTO_SIGN: lambda: self._handle_waiting_photo(ctx, image_analysis),
            ConversationState.ASK_BUILDING: lambda: self._handle_ask_building(ctx, msg),
            ConversationState.ASK_FLOOR: lambda: self._handle_ask_floor(ctx, msg),
            ConversationState.CONFIRMING_ORIGIN: lambda: self._handle_confirming_origin(ctx, msg),
            ConversationState.ASK_DESTINATION: lambda: self._handle_ask_destination(ctx, msg),
            ConversationState.CONFIRMING_PLAN: lambda: self._handle_confirming_plan(ctx, msg),
            ConversationState.EXECUTING: lambda: self._handle_executing(ctx, msg, image_analysis),
            ConversationState.AWAITING_STEP_DONE: lambda: self._handle_step_done(ctx, msg),
            ConversationState.WAITING_STEP_PHOTO: lambda: self._handle_step_photo(ctx, image_analysis, msg),
            ConversationState.NAVIGATION_COMPLETE: lambda: self._handle_nav_complete(ctx, msg),
        }.get(ctx.state)

        if handler:
            return handler()

        return self._reply(ctx, "Something went wrong. Let's start over.", "voice", "error")

    # State handlers
    def _handle_welcome(self, ctx: ConversationContext) -> Dict:
        tts = (
            "Hello! I am your campus navigation assistant. "
            "Do you know where you are right now?"
        )
        ctx.state = ConversationState.ASK_KNOWS_LOCATION
        return self._reply(ctx, tts, "voice", "welcome")

    def _handle_ask_knows_location(self, ctx: ConversationContext, msg: str) -> Dict:
        if _is_yes(msg):
            tts = "Tell me your location. For example: classroom 0.3, building G."
            ctx.state = ConversationState.ASK_LOCATION_VOICE
            return self._reply(ctx, tts, "voice", "ask_location")

        if _is_no(msg):
            tts = (
                "No problem, I will help you figure out your location. "
                "Let me ask you a few questions. "
                "Have you just come out of a classroom, or have you just exited "
                "an elevator or walked up the stairs?"
            )
            ctx.state = ConversationState.ASK_SITUATION
            return self._reply(ctx, tts, "voice", "ask_situation")

        # Attempt direct location parse from the answer
        loc = self._parse_location(msg)
        if loc:
            ctx.origin = loc
            return self._confirm_origin(ctx)

        tts = (
            "I did not quite catch that. Do you know where you are? "
            "Just say yes or no."
        )
        return self._reply(ctx, tts, "voice", "ask_knows_location")

    def _handle_ask_location_voice(self, ctx: ConversationContext, msg: str) -> Dict:
        loc = self._parse_location(msg)
        if loc and loc.get("building") and loc.get("floor") is not None:
            ctx.origin = loc
            return self._confirm_origin(ctx)

        if loc and loc.get("building") and loc.get("floor") is None:
            ctx.partial_building = loc["building"]
            tts = (
                f"I heard you are in {_BUILDING_FULL.get(loc['building'], 'that building')}. "
                "What floor are you on?"
            )
            ctx.state = ConversationState.ASK_FLOOR
            return self._reply(ctx, tts, "voice", "ask_floor")

        if loc and loc.get("floor") is not None and not loc.get("building"):
            ctx.partial_floor = loc["floor"]
            tts = (
                f"I heard you are on {_floor_text(loc['floor'])}. "
                "What building are you in? For example, building G, Centro Deportivo, or building H."
            )
            ctx.state = ConversationState.ASK_BUILDING
            return self._reply(ctx, tts, "voice", "ask_building")

        ctx.voice_retries += 1
        if ctx.voice_retries >= 3:
            tts = (
                "I am having trouble understanding your location. "
                "Would you like to take a photo instead? "
                "You can photograph a room number sign on a door, "
                "or a floor directory sign near the elevator."
            )
            ctx.state = ConversationState.ASK_SITUATION
            ctx.voice_retries = 0
            return self._reply(ctx, tts, "voice", "ask_situation")

        tts = (
            "I could not understand your location. Please try again. "
            "Say something like: classroom 0.3 in building G, "
            "or main entrance of building G."
        )
        return self._reply(ctx, tts, "voice", "ask_location")

    def _handle_ask_situation(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()

        if any(w in low for w in ("classroom", "door", "aula", "puerta", "room", "clase")):
            tts = (
                "Perfect. Please take a photo of the classroom door so I can "
                "read the room number. Try to capture the sign clearly, "
                "from about 2 to 3 metres away."
            )
            ctx.state = ConversationState.WAITING_PHOTO_DOOR
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "photo", "request_photo_door")

        if any(w in low for w in ("elevator", "lift", "ascensor")):
            tts = (
                "If you just exited the elevator, the floor directory sign "
                "is usually on the wall right next to it. Turn to your left and "
                "walk about 2 metres. You should see a sign showing the building "
                "letter and floor number, like G 0. Please take a photo of it."
            )
            ctx.state = ConversationState.WAITING_PHOTO_SIGN
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "photo", "request_photo_sign")

        if any(w in low for w in ("stairs", "stair", "escalera")):
            tts = (
                "If you just came up or down the stairs, look for a floor "
                "directory sign nearby. It is usually on the wall right next "
                "to the staircase. It shows the building letter and floor number, "
                "like G 1. Please take a photo of it."
            )
            ctx.state = ConversationState.WAITING_PHOTO_SIGN
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "photo", "request_photo_sign")

        if any(w in low for w in ("directory", "directorio", "sign", "cartel", "panel")):
            tts = (
                "Great. Please take a photo of the directory sign so I can "
                "read the building and floor information."
            )
            ctx.state = ConversationState.WAITING_PHOTO_SIGN
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "photo", "request_photo_sign")

        if any(w in low for w in ("don't know", "dont know", "no idea", "not sure",
                                   "no sé", "no se", "ni idea")):
            tts = (
                "That is okay. Can you see any doors near you? If you are "
                "near a classroom, the door should have a room number on it. "
                "If not, try to find the elevator or stairs area, where there "
                "is always a directory sign on the wall. "
                "Just tell me what you see around you."
            )
            return self._reply(ctx, tts, "voice", "ask_situation")

        loc = self._parse_location(msg)
        if loc and loc.get("building") and loc.get("floor") is not None:
            ctx.origin = loc
            return self._confirm_origin(ctx)

        tts = (
            "I need a bit more detail to find you. "
            "Are you near a classroom door where you can see a room number? "
            "Or are you near the elevator or stairs area? "
            "You can also just tell me your location by voice, for example: "
            "classroom 0.3 in building G."
        )
        return self._reply(ctx, tts, "voice", "ask_situation")

    def _handle_waiting_photo(
        self, ctx: ConversationContext, analysis: Optional[Dict]
    ) -> Dict:
        if not analysis:
            tts = "I am waiting for a photo. Please take one now."
            return self._reply(ctx, tts, "photo", "waiting_photo")

        ctx.photo_attempts += 1
        building = analysis.get("building")
        floor = analysis.get("floor")
        image_type = analysis.get("image_type")
        confidence = analysis.get("confidence", "none")

        # Try to extract room code from landmarks
        room_code = None
        for lm in analysis.get("landmarks", []):
            match = re.search(r"(\d+\.\d+)", str(lm))
            if match:
                room_code = match.group(1)
                break

        if room_code and room_code.lower() in self._room_lookup:
            bid, fnum, loc_id = self._room_lookup[room_code.lower()]
            ctx.origin = {"building": bid, "floor": fnum, "location_id": loc_id}
            return self._confirm_origin(ctx)

        if building is not None and floor is not None:
            ctx.origin = {"building": building, "floor": floor, "location_id": None}
            if image_type == "elevator":
                ctx.origin["location_id"] = "ascensor"
            elif image_type == "stairs":
                ctx.origin["location_id"] = "escaleras"
            return self._confirm_origin(ctx)

        if building is not None and floor is None:
            ctx.partial_building = building
            tts = (
                f"I can see you are in {_BUILDING_FULL.get(building, 'a building')}. "
                "What floor are you on?"
            )
            ctx.state = ConversationState.ASK_FLOOR
            return self._reply(ctx, tts, "voice", "ask_floor")

        if floor is not None and building is None:
            ctx.partial_floor = floor
            tts = (
                f"I can see you are on {_floor_text(floor)}. "
                "What building are you in?"
            )
            ctx.state = ConversationState.ASK_BUILDING
            return self._reply(ctx, tts, "voice", "ask_building")

        if ctx.photo_attempts >= 3:
            tts = (
                "I have not been able to determine your location from photos. "
                "Let me try a different approach. Please tell me your location by voice. "
                "For example: classroom 0.3 in building G."
            )
            ctx.state = ConversationState.ASK_LOCATION_VOICE
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "voice", "fallback_to_voice")

        tts = (
            "I could not read your location from that photo. "
            "Please try again. Make sure the sign or room number is clearly visible."
        )
        return self._reply(ctx, tts, "photo", "retry_photo")

    def _handle_ask_building(self, ctx: ConversationContext, msg: str) -> Dict:
        bid = self._extract_building(msg)
        if bid:
            floor = ctx.partial_floor
            loc_id = ctx.partial_location_id
            ctx.origin = {"building": bid, "floor": floor, "location_id": loc_id}
            if floor is not None:
                return self._confirm_origin(ctx)
            ctx.partial_building = bid
            tts = (
                f"You are in {_BUILDING_FULL.get(bid, 'that building')}. "
                "What floor are you on?"
            )
            ctx.state = ConversationState.ASK_FLOOR
            return self._reply(ctx, tts, "voice", "ask_floor")

        tts = (
            "I did not recognize that building. "
            "Available buildings are: G (Escuela Politécnica), "
            "CD (Centro Deportivo), and H. Which one?"
        )
        return self._reply(ctx, tts, "voice", "ask_building")

    def _handle_ask_floor(self, ctx: ConversationContext, msg: str) -> Dict:
        floor = self._extract_floor(msg)
        if floor is not None:
            bid = ctx.partial_building
            loc_id = ctx.partial_location_id
            ctx.origin = {"building": bid, "floor": floor, "location_id": loc_id}
            if bid is not None:
                return self._confirm_origin(ctx)
            tts = f"You are on {_floor_text(floor)}. What building are you in?"
            ctx.state = ConversationState.ASK_BUILDING
            return self._reply(ctx, tts, "voice", "ask_building")

        tts = (
            "I did not catch the floor number. "
            "Please say something like: ground floor, floor 1, or floor 2."
        )
        return self._reply(ctx, tts, "voice", "ask_floor")

    def _confirm_origin(self, ctx: ConversationContext) -> Dict:
        loc = ctx.origin
        loc_text = self._location_text(loc)

        # Demo-optimised flow: skip explicit yes/no origin confirmation.
        # If we already had a destination (e.g. after "I'm lost"), reroute directly.
        if ctx.destination:
            route = self._compute_route(ctx.origin, ctx.destination)
            if route:
                ctx.route_steps = route
                ctx.current_step_idx = 0
                tts = (
                    f"Got it: {loc_text}. "
                    f"I still have your destination as {self._location_text(ctx.destination)}. "
                    "Recalculating the route now."
                )
                ctx.add("system", tts)
                return self._present_plan(ctx)
            tts = self._planner_failure_message(ctx)
            ctx.add("system", tts)
            return self._reply(ctx, tts, "voice", "ask_destination")

        tts = f"Got it: {loc_text}. Where do you want to go?"
        ctx.state = ConversationState.ASK_DESTINATION
        return self._reply(ctx, tts, "voice", "ask_destination")

    def _handle_confirming_origin(self, ctx: ConversationContext, msg: str) -> Dict:
        if _is_yes(msg):
            loc_text = self._location_text(ctx.origin)

            if ctx.destination:
                dest_text = self._location_text(ctx.destination)
                route = self._compute_route(ctx.origin, ctx.destination)
                if route:
                    ctx.route_steps = route
                    ctx.current_step_idx = 0
                    tts = (
                        f"Your location is confirmed: {loc_text}. "
                        f"I still have your destination as {dest_text}. "
                        "Let me recalculate the route."
                    )
                    ctx.add("system", tts)
                    return self._present_plan(ctx)
                tts = self._planner_failure_message(ctx)
                ctx.add("system", tts)
                return self._reply(ctx, tts, "voice", "ask_destination")

            tts = f"Confirmed: {loc_text}. Where do you want to go?"
            ctx.state = ConversationState.ASK_DESTINATION
            return self._reply(ctx, tts, "voice", "ask_destination")

        if _is_no(msg):
            ctx.origin = None
            ctx.partial_building = None
            ctx.partial_floor = None
            ctx.partial_location_id = None
            tts = (
                "Let me try again. Do you know your location, "
                "or would you like to take a photo to help me identify it?"
            )
            ctx.state = ConversationState.ASK_KNOWS_LOCATION
            return self._reply(ctx, tts, "voice", "retry_location")

        # Maybe user directly said the correct location
        loc = self._parse_location(msg)
        if loc and loc.get("building") and loc.get("floor") is not None:
            ctx.origin = loc
            return self._confirm_origin(ctx)

        tts = "Please say yes to confirm, or no to try again."
        return self._reply(ctx, tts, "voice", "confirm_origin")

    def _handle_ask_destination(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()
        if any(w in low for w in ("hurry", "rush", "fast", "quick", "prisa",
                                   "rápido", "rapido", "deprisa", "urgente")):
            ctx.hurry_mode = True

        dest = self._parse_destination(msg)
        if dest:
            ctx.destination = dest
            route = self._compute_route(ctx.origin, dest)
            if not route:
                tts = self._planner_failure_message(ctx)
                return self._reply(ctx, tts, "voice", "ask_destination")
            ctx.route_steps = route
            ctx.current_step_idx = 0
            return self._present_plan(ctx)

        tts = (
            "I did not understand your destination. "
            "You can say things like: classroom 1.4, the cafeteria, "
            "the gym, the nearest restroom, or main entrance."
        )
        return self._reply(ctx, tts, "voice", "ask_destination")

    def _present_plan(self, ctx: ConversationContext) -> Dict:
        dest_text = self._location_text(ctx.destination)
        n = len(ctx.route_steps)

        overview_parts = []
        seen = set()
        for s in ctx.route_steps:
            label = {"local_walk": "walk", "elevator": "elevator",
                     "stairs": "stairs", "outdoor": "outdoor walk"}.get(s["type"], s["type"])
            if label not in seen:
                overview_parts.append(label)
                seen.add(label)
        overview = ", ".join(overview_parts) if overview_parts else "walk"

        hurry_note = " Hurry mode on." if ctx.hurry_mode else ""

        needs_elevator = "elevator" in overview_parts
        needs_stairs = "stairs" in overview_parts
        needs_outdoor = "outdoor walk" in overview_parts
        if needs_elevator:
            requirement = "You will need to use the elevator."
        elif needs_stairs:
            requirement = "You will need to use the stairs."
        elif needs_outdoor:
            requirement = "You will need to walk outdoors."
        else:
            requirement = f"There {'is' if n == 1 else 'are'} {n} step{'s' if n != 1 else ''} required: {overview}."

        # If the route was substituted because the original destination was
        # closed, prepend the announcement to the plan presentation so the
        # user understands why we are heading somewhere they did not ask for.
        prefix = ""
        if ctx.pending_announcement:
            prefix = ctx.pending_announcement.rstrip() + " "
            ctx.pending_announcement = None

        tts = (
            f"{prefix}"
            f"Perfect. I will guide you to {dest_text}. "
            f"{requirement} "
            f"Click Start Navigation or say start.{hurry_note}"
        )
        ctx.state = ConversationState.CONFIRMING_PLAN
        return self._reply(ctx, tts, "confirm", "confirm_plan")

    def _handle_confirming_plan(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()

        if any(w in low for w in ("change dest", "cambiar dest", "different", "otro destino",
                                   "otra cosa", "change")):
            tts = "Sure. What would you like the new destination to be?"
            ctx.state = ConversationState.ASK_DESTINATION
            ctx.destination = None
            ctx.route_steps = []
            return self._reply(ctx, tts, "voice", "ask_destination")

        if _is_yes(msg) or any(w in low for w in ("start", "begin", "go", "vamos", "empezar")):
            ctx.state = ConversationState.EXECUTING
            return self._deliver_step(ctx)

        if _is_no(msg):
            tts = (
                "Navigation cancelled. Tell me a new destination, or say cancel to end."
            )
            ctx.state = ConversationState.ASK_DESTINATION
            return self._reply(ctx, tts, "voice", "ask_destination")

        # Maybe user said a new destination directly
        dest = self._parse_destination(msg)
        if dest:
            ctx.destination = dest
            route = self._compute_route(ctx.origin, dest)
            if route:
                ctx.route_steps = route
                ctx.current_step_idx = 0
                return self._present_plan(ctx)
            tts = self._planner_failure_message(ctx)
            return self._reply(ctx, tts, "voice", "confirm_plan")

        tts = (
            "Please say yes to start navigation, no to cancel, "
            "or 'change destination' to pick a different place."
        )
        return self._reply(ctx, tts, "voice", "confirm_plan")

    def _handle_executing(
        self, ctx: ConversationContext, msg: str, analysis: Optional[Dict]
    ) -> Dict:
        return self._deliver_step(ctx)

    def _handle_step_done(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()
        if any(w in low for w in ("done", "next", "ready", "listo", "siguiente",
                                   "yes", "ok", "okay", "continue", "continuar")):
            ctx.current_step_idx += 1
            if ctx.current_step_idx >= len(ctx.route_steps):
                return self._navigation_complete(ctx)
            ctx.state = ConversationState.EXECUTING
            return self._deliver_step(ctx)

        tts = "Let me know when you are ready. Tap Next or say done to continue."
        return self._reply(ctx, tts, "voice", "awaiting_step_done")

    def _handle_step_photo(
        self, ctx: ConversationContext, analysis: Optional[Dict], msg: str
    ) -> Dict:
        step = ctx.route_steps[ctx.current_step_idx]
        expected = step.get("expected_photo_type")

        # Allow voice confirmation as fallback
        if not analysis and msg:
            low = msg.lower()
            if any(w in low for w in ("done", "next", "ready", "listo", "skip", "saltar",
                                       "yes", "ok", "i am here", "i'm here")):
                ctx.current_step_idx += 1
                if ctx.current_step_idx >= len(ctx.route_steps):
                    return self._navigation_complete(ctx)
                ctx.state = ConversationState.EXECUTING
                return self._deliver_step(ctx)

        if not analysis:
            tts = (
                f"Please take a photo of the {expected or 'area'} to verify your position. "
                "Use the Photo button, or say done to continue without a photo."
            )
            return self._reply(ctx, tts, "photo", "waiting_step_photo")

        image_type = analysis.get("image_type", "")
        if expected and image_type == expected:
            if step.get("arrival_strict_photo"):
                expected_code = step.get("expected_room_code")
                seen_code = self._extract_room_code_from_analysis(analysis)

                if not expected_code:
                    tts = f"Confirmed! I can see the {expected}."
                    ctx.current_step_idx += 1
                    if ctx.current_step_idx >= len(ctx.route_steps):
                        return self._navigation_complete(ctx)
                    ctx.state = ConversationState.EXECUTING
                    ctx.add("system", tts)
                    return self._deliver_step(ctx, prefix=tts + " ")

                if seen_code and self._normalize_room_code(seen_code) == self._normalize_room_code(expected_code):
                    tts = (
                        f"Confirmed! I can see classroom {self._normalize_room_code(expected_code)}."
                    )
                    ctx.current_step_idx += 1
                    if ctx.current_step_idx >= len(ctx.route_steps):
                        return self._navigation_complete(ctx)
                    ctx.state = ConversationState.EXECUTING
                    ctx.add("system", tts)
                    return self._deliver_step(ctx, prefix=tts + " ")

                tts = (
                    f"I expected classroom {self._normalize_room_code(expected_code)}, "
                    f"but the photo seems to show {self._normalize_room_code(seen_code) if seen_code else 'a different location'}. "
                    "Please take another photo and make sure the classroom number is clearly visible."
                )
                return self._reply(ctx, tts, "photo", "retry_step_photo")

            if step.get("two_phase_photo") and not step.get("_phase2_started"):
                step["_phase2_started"] = True
                post_tts = step.get("post_photo_instruction", step.get("instruction", ""))
                tts = (
                    f"Confirmed! I can see the {expected}. "
                    f"{post_tts} "
                    "Tap Next or say next when you have completed this step."
                )
                ctx.state = ConversationState.AWAITING_STEP_DONE
                return self._reply(ctx, tts, "voice", "step_after_photo_confirm")

            tts = f"Confirmed! I can see the {expected}."
            ctx.current_step_idx += 1
            if ctx.current_step_idx >= len(ctx.route_steps):
                return self._navigation_complete(ctx)
            ctx.state = ConversationState.EXECUTING
            ctx.add("system", tts)
            return self._deliver_step(ctx, prefix=tts + " ")

        # Photo didn't match but let's be lenient for the demo
        tts = (
            f"I was expecting to see the {expected or 'checkpoint'}, "
            f"but I see something different. "
            "If you are at the right place, say 'done' to continue. "
            "Otherwise, please take another photo."
        )
        return self._reply(ctx, tts, "photo", "retry_step_photo")

    def _handle_nav_complete(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()

        # Allow direct destination after arrival (without requiring a separate "yes")
        dest = self._parse_destination(msg)
        if dest:
            ctx.destination = dest
            route = self._compute_route(ctx.origin, dest)
            if route:
                ctx.route_steps = route
                ctx.current_step_idx = 0
                ctx.state = ConversationState.CONFIRMING_PLAN
                return self._present_plan(ctx)
            tts = self._planner_failure_message(ctx)
            return self._reply(ctx, tts, "voice", "nav_complete")

        if any(w in low for w in ("yes", "new", "another", "sí", "si", "otra", "new route")):
            tts = "Where would you like to go next?"
            ctx.destination = None
            ctx.route_steps = []
            ctx.current_step_idx = 0
            ctx.state = ConversationState.ASK_DESTINATION
            return self._reply(ctx, tts, "voice", "ask_destination")

        if any(w in low for w in ("no", "bye", "end", "exit", "adiós", "salir")):
            tts = "Thank you for using VisionLeader. Have a great day! Goodbye."
            return self._reply(ctx, tts, "none", "goodbye")

        tts = (
            "Would you like to navigate somewhere else? "
            "Say yes and tell me where, or say goodbye to end."
        )
        return self._reply(ctx, tts, "voice", "nav_complete")

    # Navigation helpers
    def _deliver_step(self, ctx: ConversationContext, prefix: str = "") -> Dict:
        if ctx.current_step_idx >= len(ctx.route_steps):
            return self._navigation_complete(ctx)

        step = ctx.route_steps[ctx.current_step_idx]
        idx = ctx.current_step_idx + 1
        total = len(ctx.route_steps)
        instruction = step["instruction"]

        tts = f"{prefix}Step {idx} of {total}. {instruction}"

        extra: Dict = {}

        if step.get("use_gps"):
            from_bld = step.get("outdoor_from_building")
            to_bld = step.get("outdoor_to_building")
            if from_bld and to_bld:
                extra["gps_route"] = {
                    "from_building": from_bld,
                    "to_building": to_bld,
                    "auto_open": True,
                }
            tts += (
                " Tap I've arrived when you reach the building."
            )
            ctx.state = ConversationState.AWAITING_STEP_DONE
            return self._reply(ctx, tts, "voice", "navigation_step_outdoor", **extra)

        if step.get("verification") == "photo":
            expected = step.get("expected_photo_type", "area")
            if step.get("arrival_strict_photo"):
                rc = step.get("expected_room_code")
                aula_txt = f"classroom {rc}" if rc else "your classroom"
                tts = (
                    f"{prefix}Step {idx} of {total}. {instruction} "
                    f"When you arrive, please take a photo of the {expected} "
                    f"to confirm {aula_txt}."
                )
                ctx.state = ConversationState.WAITING_STEP_PHOTO
                next_input = "photo"
                return self._reply(ctx, tts, next_input, "navigation_step")
            if step.get("elevator_photo_flow") and step.get("_elevator_stage", 1) == 1:
                pre_tts = step.get("pre_photo_instruction")
                if pre_tts:
                    tts = f"{prefix}Step {idx} of {total}. {pre_tts}"
                tts += f" Please take a photo of the {expected} to confirm."
            elif step.get("two_phase_photo") and not step.get("_phase2_started"):
                pre_tts = step.get("pre_photo_instruction")
                if pre_tts:
                    tts = f"{prefix}Step {idx} of {total}. {pre_tts}"
                tts += f" Please take a photo of the {expected} to confirm."
            else:
                if step.get("inline_photo_prompt"):
                    ctx.state = ConversationState.WAITING_STEP_PHOTO
                    next_input = "photo"
                    return self._reply(ctx, tts, next_input, "navigation_step")
                tts += f" When you arrive, please take a photo of the {expected} to confirm."
            ctx.state = ConversationState.WAITING_STEP_PHOTO
            next_input = "photo"
        else:
            tts += " Tap Next or say next when you have completed this step."
            ctx.state = ConversationState.AWAITING_STEP_DONE
            next_input = "voice"

        return self._reply(ctx, tts, next_input, "navigation_step")

    def _navigation_complete(self, ctx: ConversationContext) -> Dict:
        dest_text = self._location_text(ctx.destination)
        # Persist final destination as new current location for a fluent next route.
        if ctx.destination:
            ctx.origin = {
                "building": ctx.destination.get("building"),
                "floor": ctx.destination.get("floor"),
                "location_id": ctx.destination.get("location_id"),
            }
        # Clear goal to reflect that next destination is pending.
        ctx.destination = None
        tts = (
            f"You have arrived at {dest_text}! "
            "Would you like to navigate somewhere else?"
        )
        ctx.state = ConversationState.NAVIGATION_COMPLETE
        return self._reply(ctx, tts, "voice", "navigation_complete")

    def _handle_lost(self, ctx: ConversationContext) -> Dict:
        dest_text = self._location_text(ctx.destination) if ctx.destination else "your destination"
        tts = (
            "No worries, I will help you get back on track. "
            "I still remember you want to go to " + dest_text + ". "
            "First, let me figure out where you are now. "
            "Have you just come out of a classroom, or are you near "
            "the elevator or stairs area? You can also take a photo "
            "of a door sign or directory sign."
        )
        ctx.state = ConversationState.ASK_SITUATION
        ctx.origin = None
        ctx.route_steps = []
        ctx.current_step_idx = 0
        return self._reply(ctx, tts, "voice_or_photo", "replanning")

    def _cancel_navigation(self, ctx: ConversationContext) -> Dict:
        tts = (
            "Navigation cancelled. "
            "Would you like to start a new route? Just tell me your destination."
        )
        ctx.state = ConversationState.ASK_DESTINATION
        ctx.route_steps = []
        ctx.current_step_idx = 0
        return self._reply(ctx, tts, "voice", "cancelled")

    def _current_next_input(self, ctx: ConversationContext) -> str:
        if ctx.state == ConversationState.WAITING_STEP_PHOTO:
            return "photo"
        return "voice"

    # Closure handling (dynamic availability state)

    def _find_matching_ctx(
        self, origin: Dict, destination: Dict
    ) -> Optional["ConversationContext"]:
        """Locate the ConversationContext that owns this (origin, dest) pair."""
        for ctx in self.contexts.values():
            if ctx.origin == origin and ctx.destination == destination:
                return ctx
        return None

    def _load_current_closures(self) -> List[Dict]:
        """Fresh read of config/closed_rooms.json via the hierarchical converter."""
        if not self._hierarchical_converter:
            return []
        return self._hierarchical_converter.load_closed_rooms()

    def _is_room_closed(
        self, building_id: int, floor: Optional[int], location_id: str
    ) -> Optional[Dict]:
        """Return the closure entry if the given room is closed, None otherwise."""
        if not location_id:
            return None
        bname = _BUILDING_NAMES.get(building_id)
        if not bname:
            return None
        for entry in self._load_current_closures():
            if entry.get("building") != bname:
                continue
            if entry.get("location_id") != location_id:
                continue
            entry_floor = entry.get("floor")
            if entry_floor is None or floor is None or int(entry_floor) == int(floor):
                return entry
        return None

    def _find_open_alternative(
        self, building_id: int, floor: int, location_id: str
    ) -> Optional[Dict]:
        """Search campus_graph.json for a room of the SAME type as `location_id`
        that is currently open. Prefers the same floor; falls back to any
        floor in the same building.

        Returns a dict {building, floor, location_id, type, name} or None.
        """
        bname = _BUILDING_NAMES.get(building_id)
        if not bname:
            return None
        floors_data = self._locations.get(bname, {}) or {}

        # Resolve the original room type
        original_type: Optional[str] = None
        original_name: Optional[str] = None
        for f_str, locs in floors_data.items():
            for loc in locs:
                if loc.get("id") == location_id:
                    original_type = loc.get("type")
                    original_name = loc.get("name")
                    break
            if original_type:
                break
        if not original_type:
            return None

        # Candidates: same type, not closed, not the original room
        def candidate_on_floor(f_int: int) -> Optional[Dict]:
            locs = floors_data.get(str(f_int), []) or []
            for loc in locs:
                if loc.get("id") == location_id:
                    continue
                if loc.get("type") != original_type:
                    continue
                if self._is_room_closed(building_id, f_int, loc["id"]):
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

        # 1. Same floor first
        same_floor = candidate_on_floor(floor)
        if same_floor:
            return same_floor

        # 2. Then nearest other floors
        all_floors = sorted(
            int(f) for f in floors_data.keys()
        )
        by_distance = sorted(all_floors, key=lambda f: abs(f - floor))
        for f_int in by_distance:
            if f_int == floor:
                continue
            alt = candidate_on_floor(f_int)
            if alt:
                return alt

        return None

    # Route computation
    @staticmethod
    def _macro_planner_failed_message() -> str:
        return (
            "I could not compute a route with the symbolic planner. "
            "Ensure Docker is running with the Fast Downward image "
            "(fast-downward:latest), then try your destination again."
        )

    def _planner_failure_message(self, ctx: "ConversationContext") -> str:
        """Return the right user-facing error when _compute_route returns None.

        Prefers a pending closure announcement (informative: "X is closed,
        no alternative") over the generic planner failure message.
        """
        if ctx and ctx.pending_announcement:
            msg = ctx.pending_announcement
            ctx.pending_announcement = None
            ctx.closure_blocked = False
            return msg
        return self._planner_failure_message(ctx)

    def _compute_route(
        self, origin: Dict, destination: Dict
    ) -> Optional[List[Dict]]:
        """Build navigation steps.

        Routing strategy (hierarchical):

          - Intra-building (any building): use domain_indoor.pddl via
            HierarchicalPDDLConverter. PDDL reasons over the full room graph
            so the plan contains walk-room / elevator / stairs actions at
            ubicacion level.

          - Different building: fall back to domain_outdoor.pddl through
            Fast Downward (building-floor level).
        """
        o_bld = origin.get("building")
        o_flr = origin.get("floor")
        o_loc = origin.get("location_id")

        d_bld = destination.get("building")
        d_flr = destination.get("floor")
        d_loc = destination.get("location_id")

        if o_bld is None or o_flr is None or d_bld is None or d_flr is None:
            return None

        matching_ctx = self._find_matching_ctx(origin, destination)
        if matching_ctx:
            matching_ctx.pending_announcement = None
            matching_ctx.closure_blocked = False

        # Closure preflight: if the destination is closed, either substitute
        # a same-type alternative in-place or return None with an explanation.
        if d_loc:
            closure = self._is_room_closed(d_bld, d_flr, d_loc)
            if closure:
                alt = self._find_open_alternative(d_bld, d_flr, d_loc)
                orig_name = self._nice_location_name(d_loc)
                reason = closure.get("reason") or "currently unavailable"

                if alt:
                    # Mutate destination dict in-place so the planner, ctx
                    # and every downstream check see the new target.
                    destination["location_id"] = alt["location_id"]
                    destination["floor"] = alt["floor"]
                    destination.pop("functional", None)
                    alt_name = self._nice_location_name(alt["location_id"])
                    announcement = (
                        f"{orig_name} is {reason}. "
                        f"I'll guide you to {alt_name} instead."
                    )
                    if matching_ctx:
                        matching_ctx.pending_announcement = announcement
                    # fall through with the new destination
                    d_loc = destination["location_id"]
                    d_flr = destination["floor"]
                    print(
                        f"[Closure] {orig_name} closed ({reason}); "
                        f"redirecting to {alt_name}"
                    )
                else:
                    announcement = (
                        f"{orig_name} is {reason}, and there is no equivalent "
                        "alternative available right now. Please try a "
                        "different destination."
                    )
                    if matching_ctx:
                        matching_ctx.pending_announcement = announcement
                        matching_ctx.closure_blocked = True
                    print(
                        f"[Closure] {orig_name} closed ({reason}); "
                        "no alternative found"
                    )
                    return None

        # Determine hurry mode from the (possibly already found) matching context
        goal_functional = destination.get("functional")
        ctx_hurry = matching_ctx.hurry_mode if matching_ctx else False

        # Intra-building: hierarchical room-level planning for all buildings.
        # Uses domain_indoor.pddl (building G gets measured distances,
        # others use 15m defaults — same action schema throughout).
        if (
            o_bld == d_bld
            and o_loc
            and (d_loc or goal_functional)
            and self._hierarchical_converter is not None
        ):
            try:
                domain_path = self._hierarchical_converter.get_domain_path(o_bld)
                domain_exists = domain_path.exists()
            except ValueError:
                domain_exists = False

            if domain_exists:
                fd_actions = self._run_hierarchical_building_planner(
                    building_id=o_bld,
                    origin_room=o_loc, origin_floor=o_flr,
                    dest_room=d_loc, dest_floor=d_flr,
                    goal_functional=goal_functional,
                    hurry_mode=ctx_hurry,
                )
                bname = _BUILDING_NAMES.get(o_bld, str(o_bld))
                if fd_actions:
                    steps = self._fd_plan_to_steps_room_level(
                        fd_actions, origin, destination
                    )
                    if steps:
                        print(
                            f"[Route] Built {len(steps)} room-level steps "
                            f"for building {bname}"
                        )
                        return self._apply_arrival_strict_photo(steps, destination)
                    print(
                        f"[Route] Plan found for {bname} but could not be "
                        "converted to steps — falling back."
                    )
                else:
                    print(
                        f"[Route] Hierarchical planner failed for {bname} "
                        "— falling back to legacy routing."
                    )

        # Same building, same floor → local graph instructions
        if o_bld == d_bld and o_flr == d_flr:
            steps = self._compute_same_floor(o_bld, o_flr, o_loc, d_loc)
            return self._apply_arrival_strict_photo(steps, destination)

        # Different floor or building → global Fast Downward (legacy domain)
        fd_actions = self._run_fast_downward(
            o_bld, o_flr, d_bld, d_flr, goal_functional, hurry_mode=ctx_hurry
        )
        if fd_actions:
            steps = self._fd_plan_to_steps(fd_actions, origin, destination)
            if steps:
                print(f"[Route] Built {len(steps)} navigation steps from FD plan")
                return self._apply_arrival_strict_photo(steps, destination)
            print(
                "[Route] Fast Downward returned actions but they could not be "
                "converted to navigation steps."
            )
        else:
            print(
                "[Route] Fast Downward did not return a plan "
                "(check Docker, domain, and problem generation)."
            )
        return None

    def _compute_same_floor(
        self, bld: int, flr: int, o_loc: Optional[str], d_loc: Optional[str]
    ) -> List[Dict]:
        if o_loc and d_loc:
            pass  # no legacy instruction lookup; fallback below
        return [{
            "instruction": (
                f"Walk along {_floor_text(flr)} in "
                f"{_BUILDING_FULL.get(bld, 'the building')} "
                f"to reach your destination."
            ),
            "type": "local_walk",
            "verification": "voice",
            "expected_photo_type": None,
        }]


    def _normalize_instruction(self, text: str) -> str:
        """Normalize instruction wording to concise, English-only phrasing."""
        if not text:
            return text
        out = text
        out = out.replace("ascensor", "elevator").replace("escaleras", "stairs")
        out = out.replace("entrada_principal", "main entrance").replace("entrada principal", "main entrance")
        out = out.replace("directorio_0", "directory sign").replace("directorio_1", "directory sign").replace("directorio_2", "directory sign")
        out = out.replace("lab_ia", "AI laboratory").replace("lab ia", "AI laboratory")
        out = out.replace("bano", "restroom")
        out = out.replace("despachos_eps", "EPS faculty offices").replace("despachos eps", "EPS faculty offices")
        out = out.replace("sala_mentorias", "mentoring room").replace("sala mentorias", "mentoring room")
        out = re.sub(r"\baula[_\s]+(\d+)[_\s]+(\d+)\b", r"room \1.\2", out, flags=re.IGNORECASE)
        out = re.sub(r"\s+", " ", out).strip()
        return out

    def _entrance_id(self, building_id: int) -> str:
        """Return the entrance location_id for a building."""
        entrances = {1: "entrada_principal", 2: "entrada_cd", 3: "entrada_principal"}
        return entrances.get(building_id, "entrada_principal")

    def _building_id(self, name: str) -> int:
        return _BUILDING_MAP.get(name.lower(), 0)

    # Parsing
    def _parse_location(self, msg: str) -> Optional[Dict]:
        """Parse a user message into {building, floor, location_id}."""
        low = msg.lower().strip()
        result: Dict[str, Any] = {"building": None, "floor": None, "location_id": None}

        # Room code like "0.3", "1.4", "2.1"
        room_match = re.search(r"\b(\d+\.\d+)\b", low)
        if room_match:
            code = room_match.group(1)
            if code in self._room_lookup:
                bid, fnum, loc_id = self._room_lookup[code]
                result["building"] = bid
                result["floor"] = fnum
                result["location_id"] = loc_id

        # Building
        for keyword, bid in _BUILDING_MAP.items():
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, low):
                result["building"] = bid
                break
        if result["building"] is None:
            bm = re.search(r"\bbuilding\s+([a-z]+)\b", low)
            if bm:
                result["building"] = _BUILDING_MAP.get(bm.group(1))
            em = re.search(r"\bedificio\s+([a-z]+)\b", low)
            if em:
                result["building"] = _BUILDING_MAP.get(em.group(1))

        # Floor
        if result["floor"] is None:
            for phrase, fnum in sorted(_FLOOR_WORDS.items(), key=lambda x: -len(x[0])):
                if phrase in low:
                    result["floor"] = fnum
                    break
            if result["floor"] is None:
                fm = re.search(r"\bfloor\s+(-?\d+)\b", low)
                if fm:
                    result["floor"] = int(fm.group(1))
                pm = re.search(r"\bplanta\s+(-?\d+)\b", low)
                if pm:
                    result["floor"] = int(pm.group(1))

        # Location keywords
        if result["location_id"] is None:
            if any(w in low for w in ("entrance", "entrada", "main entrance", "entrada principal")):
                result["location_id"] = "entrada_principal"
                if result["building"] is None:
                    result["building"] = 1
                if result["floor"] is None:
                    result["floor"] = 0
            elif any(w in low for w in ("elevator", "ascensor", "lift")):
                result["location_id"] = "ascensor"
            elif any(w in low for w in ("stair", "escalera")):
                result["location_id"] = "escaleras"
            elif any(w in low for w in ("restroom", "bathroom", "baño", "aseo", "toilet")):
                result["location_id"] = "bano"
            elif any(w in low for w in ("ai lab", "laboratorio ia", "laboratorio de ia",
                                         "lab ia", "ia lab", "ai laboratory")):
                result["location_id"] = "lab_ia"
                if result["building"] is None:
                    result["building"] = 1
                if result["floor"] is None:
                    result["floor"] = 0
            elif any(w in low for w in ("office", "despacho", "faculty", "profesor")):
                result["location_id"] = "despachos"
                if result["building"] is None:
                    result["building"] = 1
                if result["floor"] is None:
                    result["floor"] = 1
            elif any(w in low for w in ("secretary", "secretar")):
                result["location_id"] = "secretaria"
                if result["building"] is None:
                    result["building"] = 1
                if result["floor"] is None:
                    result["floor"] = 2
            elif any(w in low for w in ("mentoring", "mentoría", "mentoria", "tutoring")):
                result["location_id"] = "sala_mentorias"
                if result["building"] is None:
                    result["building"] = 1
                if result["floor"] is None:
                    result["floor"] = 2
            elif any(w in low for w in ("eps office", "eps faculty", "despacho eps",
                                         "despachos eps")):
                result["location_id"] = "despachos_eps"
                if result["building"] is None:
                    result["building"] = 1
                if result["floor"] is None:
                    result["floor"] = 2

        # Default building to G if we found a room code in G
        if result["building"] is None and result["floor"] is not None and result["location_id"]:
            if result["location_id"].startswith("aula_"):
                result["building"] = 1

        if result["building"] is None and result["floor"] is None and result["location_id"] is None:
            return None

        return result

    def _parse_destination(self, msg: str) -> Optional[Dict]:
        """Parse a destination from user message."""
        low = msg.lower().strip()

        # Functional destinations
        if any(w in low for w in ("cafeteria", "cafetería", "cafe", "coffee")):
            fl = self.graph.get("functional_locations", {}).get("cafeteria", {})
            return {
                "building": fl.get("building", 2),
                "floor": fl.get("floor", 0),
                "location_id": "cafeteria",
                "label": "the cafeteria",
                "functional": "cafeteria",
            }
        if any(w in low for w in ("gym", "gimnasio", "gymnasium", "sport")):
            fl = self.graph.get("functional_locations", {}).get("gimnasio", {})
            return {
                "building": fl.get("building", 2),
                "floor": fl.get("floor", -1),
                "location_id": "gimnasio",
                "label": "the gym",
                "functional": "gimnasio",
            }

        # Named locations in Building G
        if any(w in low for w in ("ai lab", "laboratorio ia", "laboratorio de ia",
                                   "lab ia", "ia lab", "ai laboratory")):
            return {
                "building": 1, "floor": 0, "location_id": "lab_ia",
                "label": "the AI Laboratory",
            }
        if any(w in low for w in ("eps office", "eps faculty", "despacho eps",
                                   "despachos eps", "eps professor")):
            return {
                "building": 1, "floor": 2, "location_id": "despachos_eps",
                "label": "the EPS Faculty Offices",
            }
        if any(w in low for w in ("faculty office", "despacho", "profesor")):
            return {
                "building": 1, "floor": 1, "location_id": "despachos",
                "label": "the faculty offices",
            }
        if any(w in low for w in ("mentoring", "mentoría", "mentoria", "tutoring")):
            return {
                "building": 1, "floor": 2, "location_id": "sala_mentorias",
                "label": "the Mentoring Room",
            }
        if any(w in low for w in ("secretary", "secretar")):
            return {
                "building": 1, "floor": 2, "location_id": "secretaria",
                "label": "the Secretary Office",
            }
        if any(w in low for w in ("main entrance", "entrance", "entrada")):
            return {
                "building": 1, "floor": 0, "location_id": "entrada_principal",
                "label": "the main entrance",
            }

        # Nearest restroom
        if any(w in low for w in ("restroom", "bathroom", "baño", "aseo", "toilet")):
            origin = self.contexts.get(list(self.contexts.keys())[-1] if self.contexts else "").origin if self.contexts else None
            if origin:
                return {
                    "building": origin["building"],
                    "floor": origin["floor"],
                    "location_id": "bano",
                    "label": "the nearest restroom",
                }
            return {
                "building": 1, "floor": 0, "location_id": "bano",
                "label": "the restroom",
            }

        # Try as a regular location
        loc = self._parse_location(msg)
        if loc and (loc.get("building") or loc.get("location_id")):
            if loc.get("building") is None:
                loc["building"] = 1
            if loc.get("floor") is None and loc.get("location_id"):
                # Infer floor from location_id
                for code, (bid, fnum, lid) in self._room_lookup.items():
                    if lid == loc["location_id"] and bid == loc["building"]:
                        loc["floor"] = fnum
                        break
            if loc.get("floor") is None:
                loc["floor"] = 0
            return loc

        return None

    def _extract_building(self, msg: str) -> Optional[int]:
        low = msg.lower().strip()
        for keyword, bid in _BUILDING_MAP.items():
            if keyword in low:
                return bid
        bm = re.search(r"\b([a-z]+)\b", low)
        if bm and bm.group(1) in _BUILDING_MAP:
            return _BUILDING_MAP[bm.group(1)]
        return None

    def _extract_floor(self, msg: str) -> Optional[int]:
        low = msg.lower().strip()
        for phrase, fnum in sorted(_FLOOR_WORDS.items(), key=lambda x: -len(x[0])):
            if phrase in low:
                return fnum
        fm = re.search(r"(-?\d+)", low)
        if fm:
            val = int(fm.group(1))
            if -1 <= val <= 10:
                return val
        return None

    # Display helpers
    def _location_text(self, loc: Optional[Dict]) -> str:
        if not loc:
            return "an unknown location"
        bid = loc.get("building")
        flr = loc.get("floor")
        lid = loc.get("location_id")
        label = loc.get("label")
        if label:
            return label

        parts = []
        if lid:
            nice = self._nice_location_name(lid)
            parts.append(nice)
        if bid:
            parts.append(f"in {_BUILDING_FULL.get(bid, 'the building')}")
        if flr is not None and not lid:
            parts.append(f"on {_floor_text(flr)}")
        return ", ".join(parts) if parts else "an unknown location"

    def _nice_location_name(self, loc_id: str) -> str:
        mapping = {
            "entrada_principal": "the main entrance",
            "entrada_cd": "the Sports Centre entrance",
            "ascensor": "the elevator",
            "escaleras": "the stairs",
            "bano": "the restroom",
            "lab_ia": "the AI Laboratory",
            "despachos": "the faculty offices",
            "despachos_eps": "the EPS Faculty Offices",
            "secretaria": "the Secretary Office",
            "sala_mentorias": "the Mentoring Room",
            "cafeteria": "the cafeteria",
            "gimnasio": "the gym",
        }
        if loc_id in mapping:
            return mapping[loc_id]
        m = re.match(r"aula_(\d+)_(\d+)", loc_id)
        if m:
            return f"Classroom {m.group(1)}.{m.group(2)}"
        return loc_id.replace("_", " ")

    def _get_building_name(self, building_id: int) -> str:
        return _BUILDING_NAMES.get(building_id, str(building_id))

    # Response builder
    def _reply(
        self,
        ctx: ConversationContext,
        tts: str,
        next_input: str,
        action: str,
        **extra: Any,
    ) -> Dict[str, Any]:
        ctx.last_tts = tts
        ctx.add("system", tts)
        result = {
            "tts_message": tts,
            "next_input": next_input,
            "state": ctx.state.value,
            "action": action,
            "context": ctx.to_dict(),
        }
        result.update(extra)
        return result

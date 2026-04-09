"""
Conversational Navigation Agent — Full interactive flow.

States:
  WELCOME → ASK_KNOWS_LOCATION → (voice) ASK_LOCATION_VOICE / (photo) ASK_SITUATION
  → CONFIRMING_ORIGIN → ASK_DESTINATION → CONFIRMING_PLAN
  → EXECUTING → AWAITING_STEP_DONE / WAITING_STEP_PHOTO
  → NAVIGATION_COMPLETE
"""

from typing import Dict, List, Optional, Any
from collections import deque
from enum import Enum
from pathlib import Path
import re
import json
import tempfile


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


# ── Parsing helpers ────────────────────────────────────────────────────────

_AFFIRM = {"yes", "yeah", "yep", "sure", "ok", "okay", "correct", "right",
           "sí", "si", "vale", "claro", "por supuesto", "confirm", "confirmed"}
_NEGATE = {"no", "nope", "nah", "cancel", "wrong", "incorrect", "not",
           "don't", "dont"}

_BUILDING_MAP = {
    "g": 1, "politécnica": 1, "politecnica": 1, "eps": 1,
    "cd": 2, "centro deportivo": 2, "sports": 2, "sport": 2,
    "h": 3, "edificio h": 3,
}
_BUILDING_NAMES = {1: "G", 2: "CD", 3: "H"}
_BUILDING_FULL = {
    1: "Building G",
    2: "Building CD",
    3: "Building H",
}

_FLOOR_WORDS = {
    "ground": 0, "ground floor": 0, "first": 1, "first floor": 1,
    "second": 1, "second floor": 2, "third": 2,
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


# ── Context ────────────────────────────────────────────────────────────────

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

        # Partial location accumulation (building known but floor unknown, etc.)
        self.partial_building: Optional[int] = None
        self.partial_floor: Optional[int] = None
        self.partial_location_id: Optional[str] = None

    # Convenience ──────────────────────────────────────

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


# ── Agent ──────────────────────────────────────────────────────────────────

class ConversationAgent:
    """Full conversational navigation agent."""

    def __init__(self, campus_graph: Dict):
        self.graph = campus_graph
        self.contexts: Dict[str, ConversationContext] = {}

        # Pre-index local connections for fast lookup
        self._local_idx: Dict[str, List[str]] = {}
        # Adjacency list per (building, floor) for BFS fallback
        self._local_adj: Dict[str, Dict[str, List[str]]] = {}
        for lc in self.graph.get("local_connections", []):
            key = f"{lc['building']}_{lc['floor']}_{lc['from']}_{lc['to']}"
            self._local_idx[key] = lc["instructions"]
            bf_key = f"{lc['building']}_{lc['floor']}"
            self._local_adj.setdefault(bf_key, {}).setdefault(lc["from"], []).append(lc["to"])

        # Location index  {building_name -> {floor_str -> [loc_dicts]}}
        self._locations = self.graph.get("locations", {})

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
        self._converter = None
        self._domain_path = None
        self._pddl_dir = None
        self._init_planner()

    def _init_planner(self):
        """Initialize Fast Downward planner and PDDL converter."""
        try:
            from navigation.fast_downward_client import FastDownwardPlanner
            from navigation.pddl_converter import CampusGraphToPDDL

            base_dir = Path(__file__).parent.parent.parent
            campus_json = base_dir / "config" / "campus_graph.json"
            self._domain_path = base_dir / "pddl" / "domain.pddl"
            self._pddl_dir = base_dir / "pddl"

            self._planner = FastDownwardPlanner()
            self._converter = CampusGraphToPDDL(str(campus_json))
            print("[ConversationAgent] Fast Downward planner initialized OK")
        except Exception as e:
            print(f"[ConversationAgent] WARNING: Could not init Fast Downward: {e}")
            self._planner = None
            self._converter = None

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
            print("[FD] Planner not available, falling back to local routing")
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
                print(f"[FD] Plan found: {len(actions)} actions, cost={result.get('cost')}")
                for a in actions:
                    print(f"  [FD]   {a}")
                return actions
            else:
                print(f"[FD] No plan found: {result.get('error')}")
                return None
        except Exception as e:
            print(f"[FD] Error running Fast Downward: {e}")
            return None
        finally:
            if problem_path:
                try:
                    Path(problem_path).unlink(missing_ok=True)
                except Exception:
                    pass

    # ── PDDL action parsing ───────────────────────────────────────────────

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
        # Keep only digits + dot; normalize "1.30" -> "1.3"
        m = re.search(r"(\d+\.\d+)", str(code))
        if not m:
            return str(code).strip().lower()
        s = m.group(1)
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
                return match.group(1)
        # Some image types (e.g., door) may not return landmarks, but the raw
        # response often contains the extracted classroom number.
        raw = analysis.get("raw_response") or analysis.get("raw") or ""
        match = re.search(r"(\d+\.\d+)", str(raw))
        if match:
            return match.group(1)
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

            if name in ("pedir_ayuda_ascensor",
                        "verificar_seguridad_escaleras",
                        "preparar_escaleras"):
                continue

            if name == "usar_ascensor":
                # params: robot1 edificio_X planta_from planta_to elevator
                bld_id = self._edificio_to_int(params[1])
                from_floor = self._planta_to_int(params[2])
                to_floor = self._planta_to_int(params[3])
                bname = _BUILDING_NAMES.get(bld_id, "G")

                if first_movement and o_loc and o_loc != "ascensor":
                    instr = self._get_local_instructions(bname, from_floor, o_loc, "ascensor")
                    if instr:
                        steps.append({
                            "instruction": self._normalize_instruction(" ".join(instr)),
                            "type": "local_walk",
                            "verification": "voice",
                            "expected_photo_type": None,
                        })

                conn_instr = self._get_connection_instructions(
                    bld_id, from_floor, bld_id, to_floor, "elevator"
                )
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
                    "verification": "photo",
                    "expected_photo_type": "elevator",
                    "pre_photo_instruction": f"Locate the elevator on {_floor_text(from_floor)}.",
                    "elevator_photo_flow": True,
                    "_elevator_stage": 1,
                    "elevator_stage2_instruction": (
                        "Press the button to call the elevator. "
                        "When the doors are open, send me a photo so I can confirm."
                    ),
                    "post_photo_instruction": (
                        f"Enter the elevator, press floor {to_floor}, "
                        "wait until you arrive, and exit the elevator."
                    ),
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
                    instr = self._get_local_instructions(bname, from_floor, o_loc, "escaleras")
                    if instr:
                        steps.append({
                            "instruction": self._normalize_instruction(" ".join(instr)),
                            "type": "local_walk",
                            "verification": "voice",
                            "expected_photo_type": None,
                        })

                conn_instr = self._get_connection_instructions(
                    bld_id, from_floor, bld_id, to_floor, "stairs"
                )
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
                    instr = self._get_local_instructions(
                        bname, floor, o_loc, from_entrance
                    )
                    if instr:
                        steps.append({
                            "instruction": self._normalize_instruction(" ".join(instr)),
                            "type": "local_walk",
                            "verification": "voice",
                            "expected_photo_type": None,
                        })
                        added_walk_to_entrance = True

                to_name = _BUILDING_FULL.get(to_bld, "the destination building")
                hallway_instr = self._get_connection_instructions(
                    from_bld, floor, to_bld, floor, "hallway"
                )
                if hallway_instr:
                    instr_text = " ".join(hallway_instr)
                elif added_walk_to_entrance:
                    instr_text = (
                        "Push through the two glass doors to exit the building. "
                        f"Google Maps will guide you walking to {to_name}."
                    )
                else:
                    instr_text = (
                        f"Head to the main entrance of {_BUILDING_FULL.get(from_bld, 'the building')}. "
                        "Push through the two glass doors to exit the building. "
                        f"Google Maps will guide you walking to {to_name}."
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
            instr = self._get_local_instructions(bname, d_flr, last_arrival_loc, d_loc)
            if not instr and last_arrival_loc == "ascensor":
                instr = self._get_local_instructions(bname, d_flr, "escaleras", d_loc)
            if not instr and last_arrival_loc == "escaleras":
                instr = self._get_local_instructions(bname, d_flr, "ascensor", d_loc)
            if instr:
                steps.append({
                    "instruction": self._normalize_instruction(" ".join(instr)),
                    "type": "local_walk",
                    "verification": "voice",
                    "expected_photo_type": None,
                })

        return steps if steps else None

    # ── Session management ─────────────────────────────────────────────────

    def get_or_create_context(self, session_id: str) -> ConversationContext:
        if session_id not in self.contexts:
            self.contexts[session_id] = ConversationContext(session_id)
        return self.contexts[session_id]

    # ── Main entry point ───────────────────────────────────────────────────

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

    # ── State handlers ─────────────────────────────────────────────────────

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
                tts = (
                    "I could not find a route to that destination. "
                    "Please try a different one."
                )
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

        tts = (
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
        elevator_stage = step.get("_elevator_stage", 1)

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
            if step.get("elevator_photo_flow") and elevator_stage == 2:
                tts = (
                    "Please take a photo of the elevator doors when they are open. "
                    "You can use the Photo button, or say done to continue without a photo."
                )
                return self._reply(ctx, tts, "photo", "waiting_elevator_open_photo")
            tts = (
                f"Please take a photo of the {expected or 'area'} to verify your position. "
                "Use the Photo button, or say done to continue without a photo."
            )
            return self._reply(ctx, tts, "photo", "waiting_step_photo")

        image_type = analysis.get("image_type", "")
        elevator_state = str(analysis.get("elevator_state", "") or "").lower().strip()

        if step.get("elevator_photo_flow"):
            if image_type != "elevator":
                tts = (
                    "I was expecting an elevator photo. "
                    "Please take another photo focused on the elevator."
                )
                return self._reply(ctx, tts, "photo", "retry_elevator_photo")

            if elevator_stage == 1:
                step["_elevator_stage"] = 2
                stage2_tts = step.get(
                    "elevator_stage2_instruction",
                    "Press the button to call the elevator. "
                    "When the doors are open, send me a photo so I can confirm.",
                )
                tts = f"Confirmed! I can see the elevator. {stage2_tts}"
                ctx.state = ConversationState.WAITING_STEP_PHOTO
                return self._reply(ctx, tts, "photo", "waiting_elevator_open_photo")

            if elevator_stage == 2:
                if elevator_state != "open":
                    tts = (
                        "I can see the elevator, but the doors do not seem open yet. "
                        "Please wait for the doors to open and send another photo."
                    )
                    return self._reply(ctx, tts, "photo", "retry_elevator_open_photo")

                step["_elevator_stage"] = 3
                post_tts = step.get(
                    "post_photo_instruction",
                    step.get("instruction", "Enter the elevator and continue."),
                )
                tts = (
                    "Confirmed! The elevator doors are open. "
                    f"{post_tts} "
                    f"{self._next_local_walk_hint(ctx)}"
                    "Tap Next when you have completed this step."
                )
                ctx.state = ConversationState.AWAITING_STEP_DONE
                return self._reply(ctx, tts, "voice", "elevator_ready_to_board")
        if expected and image_type == expected:
            if step.get("arrival_strict_photo"):
                expected_code = step.get("expected_room_code")
                seen_code = self._extract_room_code_from_analysis(analysis)

                if not expected_code:
                    tts = f"Confirmed! I can see the {expected}. Moving to the next step."
                    ctx.current_step_idx += 1
                    if ctx.current_step_idx >= len(ctx.route_steps):
                        return self._navigation_complete(ctx)
                    ctx.state = ConversationState.EXECUTING
                    ctx.add("system", tts)
                    return self._deliver_step(ctx, prefix=tts + " ")

                if seen_code and self._normalize_room_code(seen_code) == self._normalize_room_code(expected_code):
                    tts = (
                        f"Confirmed! I can see classroom {self._normalize_room_code(expected_code)}. "
                        "Moving to the next step."
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
                    "Tap Next when you have completed this step."
                )
                ctx.state = ConversationState.AWAITING_STEP_DONE
                return self._reply(ctx, tts, "voice", "step_after_photo_confirm")

            tts = f"Confirmed! I can see the {expected}. Moving to the next step."
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

    # ── Navigation helpers ─────────────────────────────────────────────────

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
                tts += f" When you arrive, please take a photo of the {expected} to confirm."
            ctx.state = ConversationState.WAITING_STEP_PHOTO
            next_input = "photo"
        else:
            tts += " Tap Next when you have completed this step."
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

    # ── Route computation ──────────────────────────────────────────────────

    def _compute_route(
        self, origin: Dict, destination: Dict
    ) -> Optional[List[Dict]]:
        """Build navigation steps. Uses Fast Downward for any route that
        requires changing floor or building; falls back to manual graph
        traversal only when Docker / FD is unavailable."""
        o_bld = origin.get("building")
        o_flr = origin.get("floor")
        o_loc = origin.get("location_id")

        d_bld = destination.get("building")
        d_flr = destination.get("floor")
        d_loc = destination.get("location_id")

        if o_bld is None or o_flr is None or d_bld is None or d_flr is None:
            return None

        # Same building, same floor → local only (PDDL operates at floor level)
        if o_bld == d_bld and o_flr == d_flr:
            steps = self._compute_same_floor(o_bld, o_flr, o_loc, d_loc)
            return self._apply_arrival_strict_photo(steps, destination)

        # Different floor or different building → call Fast Downward
        goal_functional = destination.get("functional")
        ctx_hurry = False
        for ctx in self.contexts.values():
            if ctx.origin == origin and ctx.destination == destination:
                ctx_hurry = ctx.hurry_mode
                break
        fd_actions = self._run_fast_downward(
            o_bld, o_flr, d_bld, d_flr, goal_functional, hurry_mode=ctx_hurry
        )
        if fd_actions:
            steps = self._fd_plan_to_steps(fd_actions, origin, destination)
            if steps:
                print(f"[Route] Built {len(steps)} navigation steps from FD plan")
                return self._apply_arrival_strict_photo(steps, destination)
            print("[Route] FD plan could not be converted to steps, using fallback")

        # Fallback: manual graph traversal (if Docker is not running, etc.)
        print("[Route] Using manual graph-based fallback routing")
        return self._apply_arrival_strict_photo(
            self._compute_route_fallback(origin, destination) or [],
            destination,
        )

    def _compute_same_floor(
        self, bld: int, flr: int, o_loc: Optional[str], d_loc: Optional[str]
    ) -> List[Dict]:
        bname = _BUILDING_NAMES.get(bld, "G")
        if o_loc and d_loc:
            instr = self._get_local_instructions(bname, flr, o_loc, d_loc)
            if instr:
                return [{
                    "instruction": self._normalize_instruction(" ".join(instr)),
                    "type": "local_walk",
                    "verification": "voice",
                    "expected_photo_type": None,
                }]
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

    def _compute_route_fallback(
        self, origin: Dict, destination: Dict
    ) -> Optional[List[Dict]]:
        """Manual graph-based routing used when Fast Downward is unavailable."""
        o_bld = origin.get("building")
        o_flr = origin.get("floor")
        o_loc = origin.get("location_id")
        d_bld = destination.get("building")
        d_flr = destination.get("floor")
        d_loc = destination.get("location_id")

        steps: List[Dict] = []

        ctx_hurry = False
        for ctx in self.contexts.values():
            if ctx.origin == origin and ctx.destination == destination:
                ctx_hurry = ctx.hurry_mode
                break

        if o_bld == d_bld:
            bname = _BUILDING_NAMES.get(o_bld, "G")
            use_elevator = self._has_elevator(o_bld) and not ctx_hurry
            mobility = "ascensor" if use_elevator else "escaleras"
            mobility_type = "elevator" if use_elevator else "stairs"

            if o_loc and o_loc != mobility:
                instr = self._get_local_instructions(bname, o_flr, o_loc, mobility)
                if instr:
                    steps.append({
                        "instruction": self._normalize_instruction(" ".join(instr)),
                        "type": "local_walk",
                        "verification": "voice",
                        "expected_photo_type": None,
                    })

            conn_instr = self._get_connection_instructions(
                o_bld, o_flr, o_bld, d_flr, mobility_type
            )
            direction = "up" if d_flr > o_flr else "down"
            if conn_instr:
                instr_text = " ".join(conn_instr)
            elif use_elevator:
                instr_text = (
                    f"Take the elevator from {_floor_text(o_flr)} to "
                    f"{_floor_text(d_flr)}. Press the button and wait."
                )
            else:
                safety = (
                    "Take it one step at a time and hold the handrail firmly."
                    if not ctx_hurry else "Take the stairs quickly, but be careful."
                )
                instr_text = (
                    f"Go {direction} the stairs from {_floor_text(o_flr)} to "
                    f"{_floor_text(d_flr)}. {safety}"
                )

            step_data = {
                "instruction": self._normalize_instruction(instr_text),
                "type": mobility_type,
                "verification": "photo",
                "expected_photo_type": mobility_type,
                "two_phase_photo": True,
                "pre_photo_instruction": (
                    f"Locate the {'elevator' if mobility_type == 'elevator' else 'stairs'} "
                    f"on {_floor_text(o_flr)}."
                ),
                "elevator_photo_flow": mobility_type == "elevator",
            }
            if mobility_type == "elevator":
                step_data["post_photo_instruction"] = (
                    f"Enter the elevator, press floor {d_flr}, "
                    "wait until you arrive, and exit the elevator."
                )
                step_data["_elevator_stage"] = 1
                step_data["elevator_stage2_instruction"] = (
                    "Press the button to call the elevator. "
                    "When the doors are open, send me a photo so I can confirm."
                )
            else:
                step_data["post_photo_instruction"] = (
                    f"I can see the stairs going {direction}. {safety}"
                )
                step_data["stairs_direction"] = direction
            steps.append(step_data)

            if d_loc and d_loc != mobility:
                instr = self._get_local_instructions(bname, d_flr, mobility, d_loc)
                if instr:
                    steps.append({
                        "instruction": self._normalize_instruction(" ".join(instr)),
                        "type": "local_walk",
                        "verification": "voice",
                        "expected_photo_type": None,
                    })
            return steps if steps else None

        # Different buildings
        bname_o = _BUILDING_NAMES.get(o_bld, "G")
        bname_d = _BUILDING_NAMES.get(d_bld, "")

        if o_flr != 0:
            mobility = "ascensor" if self._has_elevator(o_bld) else "escaleras"
            mtype = "elevator" if mobility == "ascensor" else "stairs"
            if o_loc and o_loc != mobility:
                instr = self._get_local_instructions(bname_o, o_flr, o_loc, mobility)
                if instr:
                    steps.append({
                        "instruction": self._normalize_instruction(" ".join(instr)),
                        "type": "local_walk",
                        "verification": "voice",
                        "expected_photo_type": None,
                    })
            conn_instr = self._get_connection_instructions(o_bld, o_flr, o_bld, 0, mtype)
            instr_text = (
                " ".join(conn_instr) if conn_instr
                else f"Take the {mtype} from {_floor_text(o_flr)} to the ground floor."
            )
            steps.append({
                "instruction": self._normalize_instruction(instr_text),
                "type": mtype,
                "verification": "photo",
                "expected_photo_type": mtype,
                "two_phase_photo": True,
                "pre_photo_instruction": (
                    f"Locate the {'elevator' if mtype == 'elevator' else 'stairs'} "
                    f"on {_floor_text(o_flr)}."
                ),
                "post_photo_instruction": (
                    "Enter the elevator, press floor 0, "
                    "wait until you arrive, and exit the elevator."
                ) if mtype == "elevator" else instr_text,
                "elevator_photo_flow": mtype == "elevator",
                "_elevator_stage": 1 if mtype == "elevator" else None,
                "elevator_stage2_instruction": (
                    "Press the button to call the elevator. "
                    "When the doors are open, send me a photo so I can confirm."
                ) if mtype == "elevator" else None,
            })

        to_name = _BUILDING_FULL.get(d_bld, "the destination building")
        hallway_instr = self._get_connection_instructions(o_bld, 0, d_bld, 0, "hallway")
        if hallway_instr:
            instr_text = " ".join(hallway_instr)
        elif o_flr != 0:
            instr_text = (
                "Push through the two glass doors to exit the building. "
                f"Google Maps will guide you walking to {to_name}."
            )
        else:
            instr_text = (
                f"Head to the main entrance of {_BUILDING_FULL.get(o_bld, 'the building')}. "
                "Push through the two glass doors to exit the building. "
                f"Google Maps will guide you walking to {to_name}."
            )
        steps.append({
            "instruction": self._normalize_instruction(instr_text),
            "type": "outdoor",
            "verification": "voice",
            "expected_photo_type": None,
            "outdoor_from_building": o_bld,
            "outdoor_to_building": d_bld,
            "use_gps": True,
        })

        if d_flr != 0:
            mobility = "ascensor" if self._has_elevator(d_bld) else "escaleras"
            mtype = "elevator" if mobility == "ascensor" else "stairs"
            conn_instr = self._get_connection_instructions(d_bld, 0, d_bld, d_flr, mtype)
            instr_text = (
                " ".join(conn_instr) if conn_instr
                else (
                    f"In {_BUILDING_FULL.get(d_bld, 'the building')}, "
                    f"take the {mtype} from the ground floor to {_floor_text(d_flr)}."
                )
            )
            steps.append({
                "instruction": self._normalize_instruction(instr_text),
                "type": mtype,
                "verification": "photo",
                "expected_photo_type": mtype,
                "two_phase_photo": True,
                "pre_photo_instruction": (
                    f"Locate the {'elevator' if mtype == 'elevator' else 'stairs'} "
                    "on the ground floor."
                ),
                "post_photo_instruction": (
                    f"Enter the elevator, press floor {d_flr}, "
                    "wait until you arrive, and exit the elevator."
                ) if mtype == "elevator" else instr_text,
                "elevator_photo_flow": mtype == "elevator",
                "_elevator_stage": 1 if mtype == "elevator" else None,
                "elevator_stage2_instruction": (
                    "Press the button to call the elevator. "
                    "When the doors are open, send me a photo so I can confirm."
                ) if mtype == "elevator" else None,
            })

        if d_loc:
            dest_entrance = self._entrance_id(d_bld)
            arrival_point = "ascensor" if d_flr != 0 else dest_entrance
            instr = self._get_local_instructions(bname_d, d_flr, arrival_point, d_loc)
            if not instr:
                instr = self._get_local_instructions(bname_d, d_flr, "ascensor", d_loc)
            if not instr:
                instr = self._get_local_instructions(bname_d, d_flr, "escaleras", d_loc)
            if not instr:
                instr = self._get_local_instructions(bname_d, d_flr, dest_entrance, d_loc)
            if instr:
                steps.append({
                    "instruction": self._normalize_instruction(" ".join(instr)),
                    "type": "local_walk",
                    "verification": "voice",
                    "expected_photo_type": None,
                })

        return steps if steps else None

    # ── Graph lookups ──────────────────────────────────────────────────────

    def _get_local_instructions(
        self, building_name: str, floor: int, from_loc: str, to_loc: str
    ) -> Optional[List[str]]:
        """Return walking instructions between two POIs on the same floor.
        Falls back to BFS through intermediate nodes when no direct edge exists."""
        key = f"{building_name}_{floor}_{from_loc}_{to_loc}"
        direct = self._local_idx.get(key)
        if direct:
            return direct
        return self._bfs_local_instructions(building_name, floor, from_loc, to_loc)

    def _bfs_local_instructions(
        self, building_name: str, floor: int, from_loc: str, to_loc: str
    ) -> Optional[List[str]]:
        """BFS across local_connections to chain instructions when no direct link exists."""
        bf_key = f"{building_name}_{floor}"
        adjacency = self._local_adj.get(bf_key, {})
        if from_loc not in adjacency:
            return None

        visited = {from_loc}
        queue: deque = deque([(from_loc, [from_loc])])

        while queue:
            current, path = queue.popleft()
            for neighbor in adjacency.get(current, []):
                if neighbor in visited:
                    continue
                new_path = path + [neighbor]
                if neighbor == to_loc:
                    instructions: List[str] = []
                    for i in range(len(new_path) - 1):
                        k = f"{building_name}_{floor}_{new_path[i]}_{new_path[i+1]}"
                        seg = self._local_idx.get(k, [])
                        instructions.extend(seg)
                    return instructions if instructions else None
                visited.add(neighbor)
                queue.append((neighbor, new_path))

        return None

    def _get_connection_instructions(
        self, from_bld: int, from_flr: int, to_bld: int, to_flr: int, conn_type: str
    ) -> Optional[List[str]]:
        for c in self.graph.get("connections", []):
            cfrom = c["from"]
            cto = c["to"]
            if (cfrom["building"] == from_bld and cfrom["floor"] == from_flr
                    and cto["building"] == to_bld and cto["floor"] == to_flr):
                ctype = c.get("type", "")
                if conn_type == "elevator" and ctype == "elevator":
                    return c.get("instructions")
                if conn_type == "stairs" and ctype.startswith("stairs"):
                    return c.get("instructions")
                if conn_type == "hallway" and ctype == "hallway":
                    return c.get("instructions")
                if conn_type == ctype:
                    return c.get("instructions")
        return None

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

    def _next_local_walk_hint(self, ctx: ConversationContext) -> str:
        """Return a short hint about the immediate next walking step, if available."""
        next_idx = ctx.current_step_idx + 1
        if next_idx < len(ctx.route_steps):
            nxt = ctx.route_steps[next_idx]
            if nxt.get("type") == "local_walk":
                return f" After you arrive, {nxt.get('instruction', '').strip()} "
        return ""

    def _entrance_id(self, building_id: int) -> str:
        """Return the entrance location_id for a building."""
        entrances = {1: "entrada_principal", 2: "entrada_cd", 3: "entrada_principal"}
        return entrances.get(building_id, "entrada_principal")

    def _has_elevator(self, building_id: int) -> bool:
        for b in self.graph.get("buildings", []):
            if b["id"] == building_id:
                return b.get("elevators", False)
        return False

    def _building_id(self, name: str) -> int:
        return _BUILDING_MAP.get(name.lower(), 0)

    # ── Parsing ────────────────────────────────────────────────────────────

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

    # ── Display helpers ────────────────────────────────────────────────────

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

    # ── Response builder ───────────────────────────────────────────────────

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

    # ── Backwards-compatible methods (called by planning_api.py) ───────

    def get_system_greeting(self, session_id: str) -> Dict[str, Any]:
        return self.process_turn(session_id)

    def handle_photo_analysis(
        self, session_id: str, analysis_result: Dict
    ) -> Dict[str, Any]:
        return self.process_turn(session_id, image_analysis=analysis_result)

    def handle_voice_for_location(
        self, session_id: str, message: str
    ) -> Dict[str, Any]:
        return self.process_turn(session_id, user_message=message)

    def handle_goal_voice(
        self, session_id: str, message: str
    ) -> Dict[str, Any]:
        return self.process_turn(session_id, user_message=message)

    def handle_goal_confirmation(
        self, session_id: str, confirmed: bool
    ) -> Dict[str, Any]:
        msg = "yes" if confirmed else "no"
        return self.process_turn(session_id, user_message=msg)

    def handle_navigation_photo(self, session_id: str, **kwargs) -> Dict[str, Any]:
        return self.process_turn(session_id, image_analysis=kwargs)

    def handle_navigation_voice(self, session_id: str, message: str) -> Dict[str, Any]:
        return self.process_turn(session_id, user_message=message)

    def process_user_message(
        self, session_id: str, user_message: str, image_analysis: Optional[Dict] = None
    ) -> Dict[str, Any]:
        return self.process_turn(session_id, user_message=user_message, image_analysis=image_analysis)

    def generate_plan_request(self, session_id: str) -> Optional[Dict]:
        ctx = self.get_or_create_context(session_id)
        if ctx.origin and ctx.destination:
            return {
                "initial_state": {
                    "building": ctx.origin.get("building"),
                    "floor": ctx.origin.get("floor"),
                },
                "goal_state": {
                    "building": ctx.destination.get("building"),
                    "floor": ctx.destination.get("floor"),
                },
            }
        return None

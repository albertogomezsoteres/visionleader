"""Conversational Navigation Agent: full interactive flow.

States::

    WELCOME -> ASK_KNOWS_LOCATION -> (voice) ASK_LOCATION_VOICE / (photo) ASK_SITUATION
    -> CONFIRMING_ORIGIN -> ASK_DESTINATION -> CONFIRMING_PLAN
    -> EXECUTING -> AWAITING_STEP_DONE / WAITING_STEP_PHOTO
    -> NAVIGATION_COMPLETE

Everything that is not *FSM logic* lives in :mod:`navigation.agent`:
text formatting, message parsing, closure handling, plan-to-step
translation and the Fast Downward bridge. This file keeps only the
state machine itself, the routing decision, and the reply builder.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agent.text_formatting import (
    BUILDING_FULL,
    BUILDING_NAMES,
    floor_text,
    location_text,
    nice_location_name,
)
from .agent.parsing import (
    extract_building,
    extract_floor,
    extract_room_code_from_analysis,
    is_no,
    is_yes,
    normalize_room_code,
    parse_destination,
    parse_location,
)
from .agent.closures import (
    find_open_alternative,
    is_room_closed,
)
from .agent.planner_bridge import run_indoor_planner
from .agent.plan_to_steps import (
    apply_arrival_strict_photo,
    fd_plan_to_steps_room_level,
)

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


class ConversationContext:
    """Per-session conversation state."""

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

        # Closure handling: populated by _compute_route when the original
        # destination was closed. Consumed by _present_plan (success path)
        # or by destination handlers (failure path) to prepend the reason.
        self.pending_announcement: Optional[str] = None
        self.closure_blocked: bool = False

        # Partial location accumulation (building known but floor unknown, etc.)
        self.partial_building: Optional[int] = None
        self.partial_floor: Optional[int] = None
        self.partial_location_id: Optional[str] = None

    def current_location(self) -> Optional[Dict]:
        return self.origin

    def add(self, role: str, text: str) -> None:
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


class ConversationAgent:
    """Full conversational navigation agent (FSM + routing dispatcher)."""

    def __init__(self, topology: Dict, places: Dict):
        """
        topology  -- contents of config/campus_topology.json
                     (buildings, connections, local_connections, functional_locations).
                     Used to build the PDDL converters and the metric-distance lookup.
        places    -- contents of config/campus_places.json
                     (display names, room types, hint table for TTS decoration).
        """
        self._topology = topology
        self._places = places
        self.contexts: Dict[str, ConversationContext] = {}

        # Distance lookup: "<building>_<floor>_<from>_<to>" -> meters (int).
        # Sourced from topology — distances are PDDL data, not display data.
        self._local_distance: Dict[str, int] = {}
        for lc in topology.get("local_connections", []):
            dist = lc.get("distance_m")
            if isinstance(dist, (int, float)) and dist > 0:
                key = f"{lc['building']}_{lc['floor']}_{lc['from']}_{lc['to']}"
                self._local_distance[key] = int(round(dist))

        # Hint lookup: "<building>_<floor>_<from>_<to>" -> short directional string.
        # Sourced from places — hints are TTS decoration only.
        self._local_hint: Dict[str, str] = dict(places.get("hints", {}))

        # Location index: {building_name -> {floor_str -> [loc_dicts]}}
        self._locations = places.get("locations", {})

        # Known room codes -> (building_id, floor, location_id)
        self._room_lookup: Dict[str, tuple] = {}
        for bname, floors in self._locations.items():
            bid = self._building_id_from_name(bname)
            for fstr, locs in floors.items():
                for loc in locs:
                    if loc.get("room_code"):
                        self._room_lookup[loc["room_code"].lower()] = (
                            bid, int(fstr), loc["id"]
                        )
                    self._room_lookup[f"{bname.lower()}_{fstr}_{loc['id']}"] = (
                        bid, int(fstr), loc["id"]
                    )

        # Fast Downward integration (lazy-loaded; tolerates a missing image)
        self._planner = None
        self._hierarchical_converter = None   # shared campus PDDL converter
        self._pddl_dir: Optional[Path] = None
        self._init_planner()

    @staticmethod
    def _building_id_from_name(name: str) -> int:
        """Resolve a building name (e.g. 'G', 'cd') to its numeric id."""
        from .agent.parsing import building_id_from_name
        return building_id_from_name(name)

    def _init_planner(self) -> None:
        """Initialise Fast Downward and the shared PDDL converter."""
        try:
            from .fast_downward_client import FastDownwardPlanner
            from .hierarchical_pddl_converter import HierarchicalPDDLConverter

            base_dir = Path(__file__).parent.parent.parent
            campus_json = base_dir / "config" / "campus_topology.json"
            self._pddl_dir = base_dir / "pddl"

            self._planner = FastDownwardPlanner()
            closed_rooms_path = base_dir / "config" / "closed_rooms.json"
            self._hierarchical_converter = HierarchicalPDDLConverter(
                json_path=str(campus_json),
                pddl_dir=str(self._pddl_dir),
                closed_rooms_path=str(closed_rooms_path),
            )
            logger.info("Fast Downward + PDDL converter initialized OK")
        except Exception as e:
            logger.warning("Could not init Fast Downward: %s", e)
            self._planner = None
            self._hierarchical_converter = None

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
        """Single entry point for every conversational turn.

        Returns ``{tts_message, next_input, state, action, context, ...}``.
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
        tts = "Hi. Do you know where you are?"
        ctx.state = ConversationState.ASK_KNOWS_LOCATION
        return self._reply(ctx, tts, "voice", "welcome")

    def _handle_ask_knows_location(self, ctx: ConversationContext, msg: str) -> Dict:
        if is_yes(msg):
            tts = "Where are you? For example, classroom 0.3, building G."
            ctx.state = ConversationState.ASK_LOCATION_VOICE
            return self._reply(ctx, tts, "voice", "ask_location")

        if is_no(msg):
            tts = "Did you just leave a classroom, elevator, or stairs?"
            ctx.state = ConversationState.ASK_SITUATION
            return self._reply(ctx, tts, "voice", "ask_situation")

        loc = parse_location(msg, self._room_lookup)
        if loc:
            ctx.origin = loc
            return self._confirm_origin(ctx)

        tts = "Do you know where you are? Yes or no."
        return self._reply(ctx, tts, "voice", "ask_knows_location")

    def _handle_ask_location_voice(self, ctx: ConversationContext, msg: str) -> Dict:
        loc = parse_location(msg, self._room_lookup)
        if loc and loc.get("building") and loc.get("floor") is not None:
            ctx.origin = loc
            return self._confirm_origin(ctx)

        if loc and loc.get("building") and loc.get("floor") is None:
            ctx.partial_building = loc["building"]
            tts = (
                f"I heard you are in {BUILDING_FULL.get(loc['building'], 'that building')}. "
                "What floor are you on?"
            )
            ctx.state = ConversationState.ASK_FLOOR
            return self._reply(ctx, tts, "voice", "ask_floor")

        if loc and loc.get("floor") is not None and not loc.get("building"):
            ctx.partial_floor = loc["floor"]
            tts = (
                f"I heard you are on {floor_text(loc['floor'])}. "
                "What building are you in? For example, building G, Centro Deportivo, or building H."
            )
            ctx.state = ConversationState.ASK_BUILDING
            return self._reply(ctx, tts, "voice", "ask_building")

        ctx.voice_retries += 1
        if ctx.voice_retries >= 3:
            tts = "Let's try a photo. Photograph a door sign, or a floor sign near the elevator."
            ctx.state = ConversationState.ASK_SITUATION
            ctx.voice_retries = 0
            return self._reply(ctx, tts, "voice", "ask_situation")

        tts = "I didn't catch that. For example, 'classroom 0.3, building G'."
        return self._reply(ctx, tts, "voice", "ask_location")

    def _handle_ask_situation(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()

        if any(w in low for w in ("classroom", "door", "aula", "puerta", "room", "clase")):
            tts = "Take a photo of the classroom door."
            ctx.state = ConversationState.WAITING_PHOTO_DOOR
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "photo", "request_photo_door")

        if any(w in low for w in ("elevator", "lift", "ascensor")):
            tts = "Turn left, walk two metres, and photograph the floor sign."
            ctx.state = ConversationState.WAITING_PHOTO_SIGN
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "photo", "request_photo_sign")

        if any(w in low for w in ("stairs", "stair", "escalera")):
            tts = "Find the floor sign near the stairs and photograph it."
            ctx.state = ConversationState.WAITING_PHOTO_SIGN
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "photo", "request_photo_sign")

        if any(w in low for w in ("directory", "directorio", "sign", "cartel", "panel")):
            tts = "Photograph the directory sign."
            ctx.state = ConversationState.WAITING_PHOTO_SIGN
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "photo", "request_photo_sign")

        if any(w in low for w in (
            "don't know", "dont know", "no idea", "not sure",
            "no sé", "no se", "ni idea",
        )):
            tts = "Tell me what you see. A classroom door, the elevator, or the stairs?"
            return self._reply(ctx, tts, "voice", "ask_situation")

        loc = parse_location(msg, self._room_lookup)
        if loc and loc.get("building") and loc.get("floor") is not None:
            ctx.origin = loc
            return self._confirm_origin(ctx)

        tts = (
            "Are you near a classroom door, the elevator, or the stairs? "
            "Or say your location, like 'classroom 0.3, building G'."
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

        room_code = extract_room_code_from_analysis(analysis)
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
                f"I can see you are in {BUILDING_FULL.get(building, 'a building')}. "
                "What floor are you on?"
            )
            ctx.state = ConversationState.ASK_FLOOR
            return self._reply(ctx, tts, "voice", "ask_floor")

        if floor is not None and building is None:
            ctx.partial_floor = floor
            tts = (
                f"I can see you are on {floor_text(floor)}. "
                "What building are you in?"
            )
            ctx.state = ConversationState.ASK_BUILDING
            return self._reply(ctx, tts, "voice", "ask_building")

        if ctx.photo_attempts >= 3:
            tts = "Let's try voice. Say your location, like 'classroom 0.3, building G'."
            ctx.state = ConversationState.ASK_LOCATION_VOICE
            ctx.photo_attempts = 0
            return self._reply(ctx, tts, "voice", "fallback_to_voice")

        tts = "I couldn't read that photo. Try again with the sign clearly visible."
        return self._reply(ctx, tts, "photo", "retry_photo")

    def _handle_ask_building(self, ctx: ConversationContext, msg: str) -> Dict:
        bid = extract_building(msg)
        if bid:
            floor = ctx.partial_floor
            loc_id = ctx.partial_location_id
            ctx.origin = {"building": bid, "floor": floor, "location_id": loc_id}
            if floor is not None:
                return self._confirm_origin(ctx)
            ctx.partial_building = bid
            tts = (
                f"You are in {BUILDING_FULL.get(bid, 'that building')}. "
                "What floor are you on?"
            )
            ctx.state = ConversationState.ASK_FLOOR
            return self._reply(ctx, tts, "voice", "ask_floor")

        tts = "Which building? G, CD, or H."
        return self._reply(ctx, tts, "voice", "ask_building")

    def _handle_ask_floor(self, ctx: ConversationContext, msg: str) -> Dict:
        floor = extract_floor(msg)
        if floor is not None:
            bid = ctx.partial_building
            loc_id = ctx.partial_location_id
            ctx.origin = {"building": bid, "floor": floor, "location_id": loc_id}
            if bid is not None:
                return self._confirm_origin(ctx)
            tts = f"You are on {floor_text(floor)}. What building are you in?"
            ctx.state = ConversationState.ASK_BUILDING
            return self._reply(ctx, tts, "voice", "ask_building")

        tts = "Which floor? Ground, one, or two."
        return self._reply(ctx, tts, "voice", "ask_floor")

    def _confirm_origin(self, ctx: ConversationContext) -> Dict:
        loc = ctx.origin
        loc_text = location_text(loc)

        # Demo-optimised: skip explicit yes/no origin confirmation. If a
        # destination is already pending (e.g. after "I'm lost"), reroute.
        if ctx.destination:
            route = self._compute_route(ctx.origin, ctx.destination)
            if route:
                ctx.route_steps = route
                ctx.current_step_idx = 0
                tts = (
                    f"Got it: {loc_text}. "
                    f"Recalculating route to {location_text(ctx.destination)}."
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
        if is_yes(msg):
            loc_text = location_text(ctx.origin)

            if ctx.destination:
                dest_text = location_text(ctx.destination)
                route = self._compute_route(ctx.origin, ctx.destination)
                if route:
                    ctx.route_steps = route
                    ctx.current_step_idx = 0
                    tts = (
                        f"Confirmed: {loc_text}. "
                        f"Recalculating route to {dest_text}."
                    )
                    ctx.add("system", tts)
                    return self._present_plan(ctx)
                tts = self._planner_failure_message(ctx)
                ctx.add("system", tts)
                return self._reply(ctx, tts, "voice", "ask_destination")

            tts = f"Confirmed: {loc_text}. Where do you want to go?"
            ctx.state = ConversationState.ASK_DESTINATION
            return self._reply(ctx, tts, "voice", "ask_destination")

        if is_no(msg):
            ctx.origin = None
            ctx.partial_building = None
            ctx.partial_floor = None
            ctx.partial_location_id = None
            tts = "Do you know your location? Or we can try a photo."
            ctx.state = ConversationState.ASK_KNOWS_LOCATION
            return self._reply(ctx, tts, "voice", "retry_location")

        loc = parse_location(msg, self._room_lookup)
        if loc and loc.get("building") and loc.get("floor") is not None:
            ctx.origin = loc
            return self._confirm_origin(ctx)

        tts = "Please say yes to confirm, or no to try again."
        return self._reply(ctx, tts, "voice", "confirm_origin")

    def _handle_ask_destination(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()
        if any(w in low for w in (
            "hurry", "rush", "fast", "quick", "prisa",
            "rápido", "rapido", "deprisa", "urgente",
        )):
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

        tts = "Where to? For example, classroom 1.4, the cafeteria, or main entrance."
        return self._reply(ctx, tts, "voice", "ask_destination")

    def _present_plan(self, ctx: ConversationContext) -> Dict:
        dest_text = location_text(ctx.destination)
        n = len(ctx.route_steps)

        overview_parts = []
        seen = set()
        for s in ctx.route_steps:
            label = {
                "local_walk": "walk", "elevator": "elevator",
                "stairs": "stairs", "outdoor": "outdoor walk",
            }.get(s["type"], s["type"])
            if label not in seen:
                overview_parts.append(label)
                seen.add(label)
        overview = ", ".join(overview_parts) if overview_parts else "walk"

        hurry_note = " Hurry mode on." if ctx.hurry_mode else ""

        needs_elevator = "elevator" in overview_parts
        needs_stairs = "stairs" in overview_parts
        needs_outdoor = "outdoor walk" in overview_parts
        if needs_elevator:
            requirement = "Uses the elevator."
        elif needs_stairs:
            requirement = "Uses the stairs."
        elif needs_outdoor:
            requirement = "Includes an outdoor segment."
        else:
            requirement = f"{n} step{'s' if n != 1 else ''}: {overview}."

        prefix = ""
        if ctx.pending_announcement:
            prefix = ctx.pending_announcement.rstrip() + " "
            ctx.pending_announcement = None

        tts = (
            f"{prefix}"
            f"Route to {dest_text}. "
            f"{requirement} "
            f"Say start.{hurry_note}"
        )
        ctx.state = ConversationState.CONFIRMING_PLAN
        return self._reply(ctx, tts, "confirm", "confirm_plan")

    def _handle_confirming_plan(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()

        if any(w in low for w in (
            "change dest", "cambiar dest", "different",
            "otro destino", "otra cosa", "change",
        )):
            tts = "Sure. What would you like the new destination to be?"
            ctx.state = ConversationState.ASK_DESTINATION
            ctx.destination = None
            ctx.route_steps = []
            return self._reply(ctx, tts, "voice", "ask_destination")

        if is_yes(msg) or any(w in low for w in ("start", "begin", "go", "vamos", "empezar")):
            ctx.state = ConversationState.EXECUTING
            return self._deliver_step(ctx)

        if is_no(msg):
            tts = (
                "Navigation cancelled. Tell me a new destination, or say cancel to end."
            )
            ctx.state = ConversationState.ASK_DESTINATION
            return self._reply(ctx, tts, "voice", "ask_destination")

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

        tts = "Say yes to start, no to cancel, or change destination."
        return self._reply(ctx, tts, "voice", "confirm_plan")

    def _handle_executing(
        self, ctx: ConversationContext, msg: str, analysis: Optional[Dict]
    ) -> Dict:
        return self._deliver_step(ctx)

    def _handle_step_done(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()
        if any(w in low for w in (
            "done", "next", "ready", "listo", "siguiente",
            "yes", "ok", "okay", "continue", "continuar",
        )):
            ctx.current_step_idx += 1
            if ctx.current_step_idx >= len(ctx.route_steps):
                return self._navigation_complete(ctx)
            ctx.state = ConversationState.EXECUTING
            return self._deliver_step(ctx)

        tts = "Say next when done."
        return self._reply(ctx, tts, "voice", "awaiting_step_done")

    def _handle_step_photo(
        self, ctx: ConversationContext, analysis: Optional[Dict], msg: str
    ) -> Dict:
        step = ctx.route_steps[ctx.current_step_idx]
        expected = step.get("expected_photo_type")

        if not analysis and msg:
            low = msg.lower()
            if any(w in low for w in (
                "done", "next", "ready", "listo", "skip", "saltar",
                "yes", "ok", "i am here", "i'm here",
            )):
                ctx.current_step_idx += 1
                if ctx.current_step_idx >= len(ctx.route_steps):
                    return self._navigation_complete(ctx)
                ctx.state = ConversationState.EXECUTING
                return self._deliver_step(ctx)

        if not analysis:
            tts = f"Photograph the {expected or 'area'}, or say done to skip."
            return self._reply(ctx, tts, "photo", "waiting_step_photo")

        image_type = analysis.get("image_type", "")
        # PaliGemma sometimes classifies a door plate as 'sign'; treat both as
        # matching when the step expected a door.
        effective_type = image_type
        if expected == "door" and image_type == "sign":
            effective_type = "door"
        if expected and effective_type == expected:
            if step.get("arrival_strict_photo"):
                expected_code = step.get("expected_room_code")
                seen_code = extract_room_code_from_analysis(analysis)

                if not expected_code:
                    tts = f"Confirmed! I can see the {expected}."
                    ctx.current_step_idx += 1
                    if ctx.current_step_idx >= len(ctx.route_steps):
                        return self._navigation_complete(ctx)
                    ctx.state = ConversationState.EXECUTING
                    ctx.add("system", tts)
                    return self._deliver_step(ctx, prefix=tts + " ")

                if seen_code and normalize_room_code(seen_code) == normalize_room_code(expected_code):
                    tts = (
                        f"Confirmed! I can see classroom {normalize_room_code(expected_code)}."
                    )
                    ctx.current_step_idx += 1
                    if ctx.current_step_idx >= len(ctx.route_steps):
                        return self._navigation_complete(ctx)
                    ctx.state = ConversationState.EXECUTING
                    ctx.add("system", tts)
                    return self._deliver_step(ctx, prefix=tts + " ")

                tts = (
                    f"I expected classroom {normalize_room_code(expected_code)}, "
                    f"but I see {normalize_room_code(seen_code) if seen_code else 'a different location'}. "
                    "Retake the photo."
                )
                return self._reply(ctx, tts, "photo", "retry_step_photo")

            if step.get("two_phase_photo") and not step.get("_phase2_started"):
                step["_phase2_started"] = True
                post_tts = step.get("post_photo_instruction", step.get("instruction", ""))
                tts = (
                    f"Confirmed. {post_tts} Say next when done."
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

        tts = (
            f"That doesn't look like the {expected or 'checkpoint'}. "
            "Retake the photo, or say done if you're there."
        )
        return self._reply(ctx, tts, "photo", "retry_step_photo")

    def _handle_nav_complete(self, ctx: ConversationContext, msg: str) -> Dict:
        low = msg.lower()

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
            tts = "Goodbye."
            return self._reply(ctx, tts, "none", "goodbye")

        tts = "Go somewhere else? Say a destination, or say goodbye."
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
            tts += " Say done when you arrive."
            ctx.state = ConversationState.AWAITING_STEP_DONE
            return self._reply(ctx, tts, "voice", "navigation_step_outdoor", **extra)

        if step.get("verification") == "photo":
            expected = step.get("expected_photo_type", "area")
            if step.get("arrival_strict_photo"):
                rc = step.get("expected_room_code")
                aula_txt = f"classroom {rc}" if rc else "your classroom"
                tts = (
                    f"{prefix}Step {idx} of {total}. {instruction} "
                    f"On arrival, photograph the {expected} to confirm {aula_txt}."
                )
                ctx.state = ConversationState.WAITING_STEP_PHOTO
                return self._reply(ctx, tts, "photo", "navigation_step")
            if step.get("elevator_photo_flow") and step.get("_elevator_stage", 1) == 1:
                pre_tts = step.get("pre_photo_instruction")
                if pre_tts:
                    tts = f"{prefix}Step {idx} of {total}. {pre_tts}"
                tts += f" Photograph the {expected} to confirm."
            elif step.get("two_phase_photo") and not step.get("_phase2_started"):
                pre_tts = step.get("pre_photo_instruction")
                if pre_tts:
                    tts = f"{prefix}Step {idx} of {total}. {pre_tts}"
                tts += f" Photograph the {expected} to confirm."
            else:
                if step.get("inline_photo_prompt"):
                    ctx.state = ConversationState.WAITING_STEP_PHOTO
                    return self._reply(ctx, tts, "photo", "navigation_step")
                tts += f" On arrival, photograph the {expected}."
            ctx.state = ConversationState.WAITING_STEP_PHOTO
            next_input = "photo"
        else:
            tts += " Say next when done."
            ctx.state = ConversationState.AWAITING_STEP_DONE
            next_input = "voice"

        return self._reply(ctx, tts, next_input, "navigation_step")

    def _navigation_complete(self, ctx: ConversationContext) -> Dict:
        dest_text = location_text(ctx.destination)
        # Persist final destination as the new origin so the next route
        # request flows naturally without re-asking for the location.
        if ctx.destination:
            ctx.origin = {
                "building": ctx.destination.get("building"),
                "floor": ctx.destination.get("floor"),
                "location_id": ctx.destination.get("location_id"),
            }
        ctx.destination = None
        tts = f"You have arrived at {dest_text}. Want to go somewhere else?"
        ctx.state = ConversationState.NAVIGATION_COMPLETE
        return self._reply(ctx, tts, "voice", "navigation_complete")

    def _handle_lost(self, ctx: ConversationContext) -> Dict:
        dest_text = location_text(ctx.destination) if ctx.destination else "your destination"
        tts = (
            f"Okay. Destination saved: {dest_text}. "
            "Did you just leave a classroom, elevator, or stairs? Or photograph a sign."
        )
        ctx.state = ConversationState.ASK_SITUATION
        ctx.origin = None
        ctx.route_steps = []
        ctx.current_step_idx = 0
        return self._reply(ctx, tts, "voice_or_photo", "replanning")

    def _cancel_navigation(self, ctx: ConversationContext) -> Dict:
        tts = "Navigation cancelled. Tell me a new destination."
        ctx.state = ConversationState.ASK_DESTINATION
        ctx.route_steps = []
        ctx.current_step_idx = 0
        return self._reply(ctx, tts, "voice", "cancelled")

    def _current_next_input(self, ctx: ConversationContext) -> str:
        if ctx.state == ConversationState.WAITING_STEP_PHOTO:
            return "photo"
        return "voice"

    # Routing decision

    def _find_matching_ctx(
        self, origin: Dict, destination: Dict
    ) -> Optional[ConversationContext]:
        """Locate the ConversationContext that owns this (origin, dest) pair."""
        for ctx in self.contexts.values():
            if ctx.origin == origin and ctx.destination == destination:
                return ctx
        return None

    @staticmethod
    def _macro_planner_failed_message() -> str:
        return "I couldn't compute a route. Please try a different destination."

    def _planner_failure_message(self, ctx: "ConversationContext") -> str:
        """User-facing error when ``_compute_route`` returns None.

        Prefers a pending closure announcement (informative: "X is
        closed, no alternative") over the generic planner-failed message.
        """
        if ctx and ctx.pending_announcement:
            msg = ctx.pending_announcement
            ctx.pending_announcement = None
            ctx.closure_blocked = False
            return msg
        return self._macro_planner_failed_message()

    def _parse_destination(self, msg: str) -> Optional[Dict]:
        """Thin wrapper around :func:`agent.parsing.parse_destination` that
        injects the agent's room lookup, last-known origin and topology."""
        last_origin = None
        if self.contexts:
            last_session = list(self.contexts.keys())[-1]
            last_origin = self.contexts[last_session].origin
        return parse_destination(
            msg,
            self._room_lookup,
            last_origin=last_origin,
            functional_locations=self._topology.get("functional_locations", {}),
        )

    def _compute_route(
        self, origin: Dict, destination: Dict
    ) -> Optional[List[Dict]]:
        """Build navigation steps for an (origin, destination) pair.

        A single Fast Downward call on ``domain_indoor.pddl`` resolves both
        intra- and inter-building routes. For cross-building pairs the
        converter emits rooms of both buildings plus ``conectado_exterior``
        edges between their entrances, so the resulting plan interleaves
        ``caminar`` / ``usar_ascensor`` / ``mover_exterior`` actions as
        needed.
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
        # a same-type alternative in-place or return None with explanation.
        if d_loc:
            closure = is_room_closed(
                self._hierarchical_converter, d_bld, d_flr, d_loc
            )
            if closure:
                alt = find_open_alternative(
                    self._hierarchical_converter,
                    self._locations,
                    d_bld, d_flr, d_loc,
                )
                orig_name = nice_location_name(d_loc)
                reason = closure.get("reason") or "currently unavailable"

                if alt:
                    destination["location_id"] = alt["location_id"]
                    destination["floor"] = alt["floor"]
                    destination.pop("functional", None)
                    alt_name = nice_location_name(alt["location_id"])
                    announcement = (
                        f"{orig_name} is {reason}. "
                        f"I'll guide you to {alt_name} instead."
                    )
                    if matching_ctx:
                        matching_ctx.pending_announcement = announcement
                    d_loc = destination["location_id"]
                    d_flr = destination["floor"]
                    print(
                        f"[Closure] {orig_name} closed ({reason}); "
                        f"redirecting to {alt_name}"
                    )
                else:
                    announcement = (
                        f"{orig_name} is {reason}. Try a different destination."
                    )
                    if matching_ctx:
                        matching_ctx.pending_announcement = announcement
                        matching_ctx.closure_blocked = True
                    print(
                        f"[Closure] {orig_name} closed ({reason}); "
                        "no alternative found"
                    )
                    return None

        goal_functional = destination.get("functional")
        ctx_hurry = matching_ctx.hurry_mode if matching_ctx else False

        if self._hierarchical_converter is None or not o_loc:
            return None

        if not (d_loc or goal_functional):
            return None

        fd_actions = run_indoor_planner(
            planner=self._planner,
            hierarchical_converter=self._hierarchical_converter,
            pddl_dir=self._pddl_dir,
            origin_building=o_bld,
            origin_room=o_loc, origin_floor=o_flr,
            dest_building=d_bld,
            dest_room=d_loc, dest_floor=d_flr,
            goal_functional=goal_functional,
            hurry_mode=ctx_hurry,
        )
        if not fd_actions:
            bname = BUILDING_NAMES.get(o_bld, str(o_bld))
            print(
                f"[Route] Planner did not return a plan for {bname} -> "
                f"{BUILDING_NAMES.get(d_bld, d_bld)} "
                "(check Docker, domain, and problem generation)."
            )
            return None

        steps = fd_plan_to_steps_room_level(
            fd_actions, origin, destination,
            places_locations=self._locations,
            local_distance=self._local_distance,
            local_hint=self._local_hint,
        )
        if not steps:
            if o_bld == d_bld and o_flr == d_flr:
                steps = self._compute_same_floor(o_bld, o_flr)
            else:
                print(
                    "[Route] Planner returned actions but they could not be "
                    "converted to navigation steps."
                )
                return None

        print(f"[Route] Built {len(steps)} navigation steps from PDDL plan")
        return apply_arrival_strict_photo(steps, destination, self._locations)

    @staticmethod
    def _compute_same_floor(bld: int, flr: int) -> List[Dict]:
        """Trivial fallback when origin and destination are on the same floor."""
        return [{
            "instruction": (
                f"Walk along {floor_text(flr)} in "
                f"{BUILDING_FULL.get(bld, 'the building')} "
                f"to reach your destination."
            ),
            "type": "local_walk",
            "verification": "voice",
            "expected_photo_type": None,
        }]

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

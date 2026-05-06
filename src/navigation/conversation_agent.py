"""Conversational Navigation Agent.

The agent is implemented as a finite state machine over fifteen states.
Each state has its own handler in :mod:`navigation.agent.state_handlers`,
named after the conversational phase it belongs to:

- ``welcome``             — greeting and yes/no entry into the flow
- ``location_discovery``  — voice or photo-based origin discovery
- ``origin``              — confirm origin and bridge to destination
- ``destination``         — parse the user's free-form destination
- ``plan_confirmation``   — present the route summary and act on the answer
- ``execution``           — step-by-step delivery and photo verification
- ``completion``          — arrival and follow-up

This file keeps only the dispatcher (:meth:`process_turn`), the shared
response builder (:meth:`_reply`) and the singletons every handler needs:
the room lookup, the PDDL converter, and the planner. Routing logic
lives in :mod:`navigation.agent.routing`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .agent.context import ConversationContext, ConversationState
from .agent.state_handlers import (
    completion,
    destination,
    execution,
    location_discovery,
    origin,
    plan_confirmation,
    welcome,
)

logger = logging.getLogger(__name__)


_REPEAT_WORDS = ("repeat", "again", "repite", "otra vez")
_LOST_WORDS   = ("lost", "help", "perdido", "ayuda")
_CANCEL_WORDS = ("cancel", "stop", "cancelar", "parar")

_NAVIGATING_STATES = (
    ConversationState.EXECUTING,
    ConversationState.AWAITING_STEP_DONE,
    ConversationState.WAITING_STEP_PHOTO,
)


class ConversationAgent:
    """FSM dispatcher and shared singleton holder.

    Only contains state and helpers that the handler modules need to
    share — the conversational logic itself lives in
    :mod:`navigation.agent.state_handlers`.
    """

    def __init__(self, topology: Dict, places: Dict):
        """``topology`` is ``config/campus_topology.json`` and ``places``
        is ``config/campus_places.json``."""
        self._topology = topology
        self._places = places
        self.contexts: Dict[str, ConversationContext] = {}

        # Distance lookup: "<building>_<floor>_<from>_<to>" -> meters.
        # PDDL data, keyed by edge — used by plan_to_steps for TTS distances.
        self._local_distance: Dict[str, int] = {}
        for lc in topology.get("local_connections", []):
            dist = lc.get("distance_m")
            if isinstance(dist, (int, float)) and dist > 0:
                key = f"{lc['building']}_{lc['floor']}_{lc['from']}_{lc['to']}"
                self._local_distance[key] = int(round(dist))

        # Hint lookup: same key -> short directional string. Display only.
        self._local_hint: Dict[str, str] = dict(places.get("hints", {}))

        # Location index: {building_name -> {floor_str -> [loc_dicts]}}
        self._locations = places.get("locations", {})

        # Known room codes -> (building_id, floor, location_id), used by
        # parsing helpers to resolve free-form references like "1.4".
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

        # Fast Downward integration (lazy-loaded; tolerates a missing image).
        self._planner = None
        self._hierarchical_converter = None
        self._pddl_dir: Optional[Path] = None
        self._init_planner()

    @staticmethod
    def _building_id_from_name(name: str) -> int:
        from .agent.parsing import building_id_from_name
        return building_id_from_name(name)

    def _init_planner(self) -> None:
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

    def get_or_create_context(self, session_id: str) -> ConversationContext:
        if session_id not in self.contexts:
            self.contexts[session_id] = ConversationContext(session_id)
        return self.contexts[session_id]

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

        # Universal voice commands during navigation.
        if ctx.state in _NAVIGATING_STATES:
            low = msg.lower()
            if any(w in low for w in _REPEAT_WORDS):
                return self._reply(ctx, ctx.last_tts, self._current_next_input(ctx), "repeat")
            if any(w in low for w in _LOST_WORDS):
                return execution.handle_lost(self, ctx)
            if any(w in low for w in _CANCEL_WORDS):
                return execution.cancel_navigation(self, ctx)

        handler = self._dispatch(ctx, msg, image_analysis)
        if handler:
            return handler()
        return self._reply(ctx, "Something went wrong. Let's start over.", "voice", "error")

    def _dispatch(
        self,
        ctx: ConversationContext,
        msg: str,
        image_analysis: Optional[Dict],
    ):
        """Map ``ctx.state`` to the zero-argument handler that runs this turn."""
        return {
            ConversationState.WELCOME:
                lambda: welcome.handle_welcome(self, ctx),
            ConversationState.ASK_KNOWS_LOCATION:
                lambda: welcome.handle_ask_knows_location(self, ctx, msg),
            ConversationState.ASK_LOCATION_VOICE:
                lambda: location_discovery.handle_ask_location_voice(self, ctx, msg),
            ConversationState.ASK_SITUATION:
                lambda: location_discovery.handle_ask_situation(self, ctx, msg),
            ConversationState.WAITING_PHOTO_DOOR:
                lambda: location_discovery.handle_waiting_photo(self, ctx, image_analysis),
            ConversationState.WAITING_PHOTO_SIGN:
                lambda: location_discovery.handle_waiting_photo(self, ctx, image_analysis),
            ConversationState.ASK_BUILDING:
                lambda: location_discovery.handle_ask_building(self, ctx, msg),
            ConversationState.ASK_FLOOR:
                lambda: location_discovery.handle_ask_floor(self, ctx, msg),
            ConversationState.CONFIRMING_ORIGIN:
                lambda: origin.handle_confirming_origin(self, ctx, msg),
            ConversationState.ASK_DESTINATION:
                lambda: destination.handle_ask_destination(self, ctx, msg),
            ConversationState.CONFIRMING_PLAN:
                lambda: plan_confirmation.handle_confirming_plan(self, ctx, msg),
            ConversationState.EXECUTING:
                lambda: execution.handle_executing(self, ctx, msg, image_analysis),
            ConversationState.AWAITING_STEP_DONE:
                lambda: execution.handle_step_done(self, ctx, msg),
            ConversationState.WAITING_STEP_PHOTO:
                lambda: execution.handle_step_photo(self, ctx, image_analysis, msg),
            ConversationState.NAVIGATION_COMPLETE:
                lambda: completion.handle_nav_complete(self, ctx, msg),
        }.get(ctx.state)

    def _reply(
        self,
        ctx: ConversationContext,
        tts: str,
        next_input: str,
        action: str,
        **extra: Any,
    ) -> Dict[str, Any]:
        """Build the standard response dict, persist the TTS line and add
        the per-state ``expect_photo`` hint for the mobile client."""
        ctx.last_tts = tts
        ctx.add("system", tts)
        result = {
            "tts_message": tts,
            "next_input": next_input,
            "state": ctx.state.value,
            "action": action,
            "context": ctx.to_dict(),
        }
        expect_photo = self._compute_expect_photo(ctx)
        if expect_photo:
            result["expect_photo"] = expect_photo
        result.update(extra)
        return result

    def _compute_expect_photo(self, ctx: ConversationContext) -> Optional[str]:
        """Map the current FSM state to the VLM prompt the client should run.

        Returns a prompt id from ``extraction_validation/prompts.json``
        (``room_plate``, ``directory_sign``, ``elevator_state``,
        ``stair_direction``) or ``None`` if no photo is currently expected.
        """
        if ctx.state == ConversationState.WAITING_PHOTO_DOOR:
            return "room_plate"
        if ctx.state == ConversationState.WAITING_PHOTO_SIGN:
            return "directory_sign"
        if ctx.state == ConversationState.WAITING_STEP_PHOTO:
            if 0 <= ctx.current_step_idx < len(ctx.route_steps):
                step = ctx.route_steps[ctx.current_step_idx]
                return step.get("expected_photo_type")
        return None

    def _current_next_input(self, ctx: ConversationContext) -> str:
        if ctx.state == ConversationState.WAITING_STEP_PHOTO:
            return "photo"
        return "voice"

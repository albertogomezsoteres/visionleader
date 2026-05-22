"""Per-session conversational state for the navigation agent.

Holds the FSM enum (:class:`ConversationState`) and the mutable
:class:`ConversationContext` carried across turns. Both types are pure
data: no IO, no model calls, no planner calls.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


class ConversationState(Enum):
    WELCOME = "welcome"
    ASK_KNOWS_LOCATION = "ask_knows_location"
    ASK_LOCATION_VOICE = "ask_location_voice"
    ASK_SITUATION = "ask_situation"
    WAITING_PHOTO_DOOR = "waiting_photo_door"
    WAITING_PHOTO_SIGN = "waiting_photo_sign"
    WAITING_PHOTO_ORIGIN = "waiting_photo_origin"
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
    """All state belonging to one user session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = ConversationState.WELCOME

        self.origin: Optional[Dict[str, Any]] = None
        self.destination: Optional[Dict[str, Any]] = None

        self.route_steps: List[Dict[str, Any]] = []
        self.current_step_idx: int = 0

        # Raw PDDL plan from Fast Downward (action strings with "(N)" cost
        # annotations) plus the total cost it found. Surfaced on the
        # conversation response so the mobile can render the symbolic plan
        # card. Cleared on navigation completion / cancellation.
        self.pddl_plan: List[str] = []
        self.plan_cost: int = 0
        self.plan_search_time_s: Optional[float] = None

        self.last_tts: str = ""
        self.photo_attempts: int = 0
        self.voice_retries: int = 0
        self.history: List[Dict[str, str]] = []
        self.hurry_mode: bool = False

        # Closure handling: populated by routing.compute_route when the
        # original destination was closed. Consumed by present_plan (success
        # path) or by destination handlers (failure path) to prepend the
        # reason.
        self.pending_announcement: Optional[str] = None
        self.closure_blocked: bool = False

        # Partial location accumulation (building known but floor unknown,
        # etc.) Used while the FSM is still gathering origin pieces.
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
            "pddl_plan": list(self.pddl_plan),
            "plan_cost": self.plan_cost,
            "plan_search_time_s": self.plan_search_time_s,
        }

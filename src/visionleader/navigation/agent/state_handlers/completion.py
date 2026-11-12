"""Phase 7 - arrival and what to do next.

``navigation_complete`` is the transition called by execution handlers
when ``current_step_idx`` walks off the end of the route. It also
promotes the destination to the new origin so a follow-up route does
not re-ask for the location. ``handle_nav_complete`` then waits for the
user to either give a new destination, ask for one, or end the session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from visionleader.api.telemetry import log_event

from ..context import ConversationContext, ConversationState
from ..routing import compute_route, planner_failure_message
from ..text_formatting import location_text
from . import destination as destination_handler

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


def navigation_complete(agent: "ConversationAgent", ctx: ConversationContext) -> Dict:
    dest_text = location_text(ctx.destination)
    arrived_at = ctx.destination
    # Promote arrival to the new origin so the follow-up route does not
    # ask for the location again.
    if ctx.destination:
        ctx.origin = {
            "building": ctx.destination.get("building"),
            "floor": ctx.destination.get("floor"),
            "location_id": ctx.destination.get("location_id"),
        }
    ctx.destination = None
    ctx.pddl_plan = []
    ctx.plan_cost = 0
    ctx.plan_search_time_s = None
    tts = f"You have arrived at {dest_text}. Want to go somewhere else?"
    ctx.state = ConversationState.NAVIGATION_COMPLETE
    log_event(
        "SCENARIO",
        f"scenario completed  PASS  ·  arrived at {arrived_at.get('location_id') if arrived_at else '?'}",
        session_id=ctx.session_id,
        status="completed",
        result="pass",
        arrived_at=arrived_at,
    )
    return agent._reply(ctx, tts, "voice", "navigation_complete")


def handle_nav_complete(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    from . import plan_confirmation  # lazy: cross-handler dependency

    low = msg.lower()

    # "I am lost" / "perdido" after arrival: drop the just-promoted origin
    # and re-enter the welcome-style photo-origin flow. Mirrors what the
    # in-navigation handle_lost does, but starts from a clean slate
    # because the previous trip is already over. Generous keyword set
    # because Whisper sometimes nibbles the short utterance.
    if any(w in low for w in (
        "lost", "lose", "help",
        "i am lost", "i'm lost", "im lost", "i lost",
        "perdido", "estoy perdido", "ayuda",
        "find me", "where am i", "i don't know", "no idea",
    )):
        tts = "OK. Photograph any sign nearby so I can extract your location."
        ctx.origin = None
        ctx.destination = None
        ctx.route_steps = []
        ctx.current_step_idx = 0
        ctx.pddl_plan = []
        ctx.plan_cost = 0
        ctx.plan_search_time_s = None
        ctx.state = ConversationState.WAITING_PHOTO_ORIGIN
        ctx.photo_attempts = 0
        return agent._reply(ctx, tts, "photo", "ask_origin_photo")

    dest = destination_handler.parse_destination_for(agent, msg)
    if dest:
        ctx.destination = dest
        route = compute_route(agent, ctx.origin, dest, ctx=ctx)
        if route:
            ctx.route_steps = route
            ctx.current_step_idx = 0
            ctx.state = ConversationState.CONFIRMING_PLAN
            return plan_confirmation.present_plan(agent, ctx)
        tts = planner_failure_message(ctx)
        return agent._reply(ctx, tts, "voice", "nav_complete")

    if any(w in low for w in ("yes", "new", "another", "sí", "si", "otra", "new route")):
        tts = "Where would you like to go next?"
        ctx.destination = None
        ctx.route_steps = []
        ctx.current_step_idx = 0
        ctx.state = ConversationState.ASK_DESTINATION
        return agent._reply(ctx, tts, "voice", "ask_destination")

    if any(w in low for w in ("no", "bye", "end", "exit", "adiós", "salir")):
        tts = "Goodbye."
        return agent._reply(ctx, tts, "none", "goodbye")

    tts = "Go somewhere else? Say a destination, or say goodbye."
    return agent._reply(ctx, tts, "voice", "nav_complete")

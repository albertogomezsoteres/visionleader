"""Phase 7 — arrival and what to do next.

``navigation_complete`` is the transition called by execution handlers
when ``current_step_idx`` walks off the end of the route. It also
promotes the destination to the new origin so a follow-up route does
not re-ask for the location. ``handle_nav_complete`` then waits for the
user to either give a new destination, ask for one, or end the session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from ..context import ConversationContext, ConversationState
from ..routing import compute_route, planner_failure_message
from ..text_formatting import location_text
from . import destination as destination_handler

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


def navigation_complete(agent: "ConversationAgent", ctx: ConversationContext) -> Dict:
    dest_text = location_text(ctx.destination)
    # Promote arrival to the new origin so the follow-up route does not
    # ask for the location again.
    if ctx.destination:
        ctx.origin = {
            "building": ctx.destination.get("building"),
            "floor": ctx.destination.get("floor"),
            "location_id": ctx.destination.get("location_id"),
        }
    ctx.destination = None
    tts = f"You have arrived at {dest_text}. Want to go somewhere else?"
    ctx.state = ConversationState.NAVIGATION_COMPLETE
    return agent._reply(ctx, tts, "voice", "navigation_complete")


def handle_nav_complete(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    from . import plan_confirmation  # lazy: cross-handler dependency

    low = msg.lower()

    dest = destination_handler.parse_destination_for(agent, msg)
    if dest:
        ctx.destination = dest
        route = compute_route(agent, ctx.origin, dest)
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

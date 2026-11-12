"""Phase 3 - confirm the resolved origin and bridge to destination.

``confirm_origin`` is the universal "we now know where the user is"
transition. Most location-discovery handlers funnel here once they have
a complete ``(building, floor, location_id)`` tuple. From there the FSM
either jumps to ASK_DESTINATION or, if a destination was already pending
(replanning after "I'm lost"), recomputes the route and presents the
new plan immediately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from visionleader.api.telemetry import log_event

from ..context import ConversationContext, ConversationState
from ..parsing import is_no, is_yes, parse_location
from ..routing import compute_route, planner_failure_message
from ..text_formatting import BUILDING_NAMES, location_text

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


def confirm_origin(agent: ConversationAgent, ctx: ConversationContext) -> dict:
    """Origin is fully resolved -> either present a pending plan or ask
    for a destination."""
    from . import plan_confirmation  # lazy: plan_confirmation imports execution

    if ctx.origin:
        loc_id = ctx.origin.get("location_id")
        bld = ctx.origin.get("building")
        flr = ctx.origin.get("floor")
        log_event(
            "AGENT",
            f"origin grounded: (at user {loc_id})  "
            f"- building={BUILDING_NAMES.get(bld, bld)}  floor={flr}",
            origin=ctx.origin,
        )
        log_event(
            "VALIDATION",
            f"origin_grounding  PASS  ·  (at user {loc_id})",
            check="origin_grounding",
            result="pass",
            location_id=loc_id,
        )

    loc_text = location_text(ctx.origin)

    if ctx.destination:
        route = compute_route(agent, ctx.origin, ctx.destination)
        if route:
            ctx.route_steps = route
            ctx.current_step_idx = 0
            tts = f"Got it: {loc_text}. Recalculating route to {location_text(ctx.destination)}."
            ctx.add("system", tts)
            return plan_confirmation.present_plan(agent, ctx)
        tts = planner_failure_message(ctx)
        ctx.add("system", tts)
        return agent._reply(ctx, tts, "voice", "ask_destination")

    tts = f"Got it: {loc_text}. Where do you want to go?"
    ctx.state = ConversationState.ASK_DESTINATION
    return agent._reply(ctx, tts, "voice", "ask_destination")


def handle_confirming_origin(agent: ConversationAgent, ctx: ConversationContext, msg: str) -> dict:
    """State CONFIRMING_ORIGIN.

    Reachable only from earlier flows that explicitly ask the user to
    confirm. The demo flow normally skips this state by calling
    :func:`confirm_origin` directly.
    """
    from . import plan_confirmation  # lazy: cross-handler dependency

    if is_yes(msg):
        loc_text = location_text(ctx.origin)
        if ctx.destination:
            dest_text = location_text(ctx.destination)
            route = compute_route(agent, ctx.origin, ctx.destination, ctx=ctx)
            if route:
                ctx.route_steps = route
                ctx.current_step_idx = 0
                tts = f"Confirmed: {loc_text}. Recalculating route to {dest_text}."
                ctx.add("system", tts)
                return plan_confirmation.present_plan(agent, ctx)
            tts = planner_failure_message(ctx)
            ctx.add("system", tts)
            return agent._reply(ctx, tts, "voice", "ask_destination")

        tts = f"Confirmed: {loc_text}. Where do you want to go?"
        ctx.state = ConversationState.ASK_DESTINATION
        return agent._reply(ctx, tts, "voice", "ask_destination")

    if is_no(msg):
        ctx.origin = None
        ctx.partial_building = None
        ctx.partial_floor = None
        ctx.partial_location_id = None
        tts = "Do you know your location? Or we can try a photo."
        ctx.state = ConversationState.ASK_KNOWS_LOCATION
        return agent._reply(ctx, tts, "voice", "retry_location")

    loc = parse_location(msg, agent._room_lookup)
    if loc and loc.get("building") and loc.get("floor") is not None:
        ctx.origin = loc
        return confirm_origin(agent, ctx)

    tts = "Please say yes to confirm, or no to try again."
    return agent._reply(ctx, tts, "voice", "confirm_origin")

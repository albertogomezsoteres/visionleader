"""Phase 5 — present the route summary and act on the user's answer.

``present_plan`` builds the one-shot description of the upcoming route
("Route to the cafeteria. Uses the elevator. Say start.") and parks the
FSM in CONFIRMING_PLAN. ``handle_confirming_plan`` then interprets the
user reply: start, change destination, cancel, or a brand new
destination.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from ..context import ConversationContext, ConversationState
from ..parsing import is_no, is_yes
from ..routing import compute_route, planner_failure_message
from ..text_formatting import location_text
from . import destination as destination_handler

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


_STEP_TYPE_LABELS = {
    "local_walk": "walk",
    "elevator":   "elevator",
    "stairs":     "stairs",
    "outdoor":    "outdoor walk",
}


def present_plan(agent: "ConversationAgent", ctx: ConversationContext) -> Dict:
    """Summarise ``ctx.route_steps`` for TTS and ask for confirmation."""
    dest_text = location_text(ctx.destination)
    n = len(ctx.route_steps)

    overview_parts = []
    seen = set()
    for s in ctx.route_steps:
        label = _STEP_TYPE_LABELS.get(s["type"], s["type"])
        if label not in seen:
            overview_parts.append(label)
            seen.add(label)
    overview = ", ".join(overview_parts) if overview_parts else "walk"

    hurry_note = " Hurry mode on." if ctx.hurry_mode else ""

    if "elevator" in overview_parts:
        requirement = "Uses the elevator."
    elif "stairs" in overview_parts:
        requirement = "Uses the stairs."
    elif "outdoor walk" in overview_parts:
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
    return agent._reply(ctx, tts, "confirm", "confirm_plan")


def handle_confirming_plan(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    from . import execution  # lazy: execution.deliver_step

    low = msg.lower()

    if any(w in low for w in (
        "change dest", "cambiar dest", "different",
        "otro destino", "otra cosa", "change",
    )):
        tts = "Sure. What would you like the new destination to be?"
        ctx.state = ConversationState.ASK_DESTINATION
        ctx.destination = None
        ctx.route_steps = []
        return agent._reply(ctx, tts, "voice", "ask_destination")

    if is_yes(msg) or any(w in low for w in ("start", "begin", "go", "vamos", "empezar")):
        ctx.state = ConversationState.EXECUTING
        return execution.deliver_step(agent, ctx)

    if is_no(msg):
        tts = "Navigation cancelled. Tell me a new destination, or say cancel to end."
        ctx.state = ConversationState.ASK_DESTINATION
        return agent._reply(ctx, tts, "voice", "ask_destination")

    dest = destination_handler.parse_destination_for(agent, msg)
    if dest:
        ctx.destination = dest
        route = compute_route(agent, ctx.origin, dest)
        if route:
            ctx.route_steps = route
            ctx.current_step_idx = 0
            return present_plan(agent, ctx)
        tts = planner_failure_message(ctx)
        return agent._reply(ctx, tts, "voice", "confirm_plan")

    tts = "Say yes to start, no to cancel, or change destination."
    return agent._reply(ctx, tts, "voice", "confirm_plan")

"""Phase 4 - gather and parse the user's destination.

The single state ASK_DESTINATION accepts free-form text ("classroom 1.4",
"the cafeteria", "main entrance"). Parsing is delegated to
:func:`navigation.agent.parsing.parse_destination`; this module only
wires up the agent's room lookup and last-known origin and decides what
to do with the result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from api.telemetry import log_event

from ..context import ConversationContext
from ..parsing import parse_destination
from ..routing import compute_route, planner_failure_message

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


# A user can reach hurry mode either by stating urgency ("I'm in a hurry",
# "rápido"…) or by stating a stair preference ("I'll take the stairs").
# Both map to the same `(hurry_mode)` PDDL flag, which favours stairs in
# the cost model - we just expose more phrasings so STT variations don't
# trip people up.
_HURRY_KEYWORDS = (
    "hurry", "rush", "fast", "quick", "prisa",
    "rápido", "rapido", "deprisa", "urgente",
    "stairs", "stair", "escaleras", "escalera",
    "by foot", "on foot",
)


def handle_ask_destination(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    from . import plan_confirmation  # lazy: cross-handler dependency

    low = msg.lower()
    matched_hurry = [w for w in _HURRY_KEYWORDS if w in low]
    if matched_hurry:
        ctx.hurry_mode = True

    dest = parse_destination_for(agent, msg)

    log_event(
        "AGENT",
        f"destination parsed: {dest.get('location_id') if dest else 'NONE'}  "
        f"hurry={str(ctx.hurry_mode).lower()}",
        user_message=msg,
        destination=dest,
        hurry_mode=ctx.hurry_mode,
        hurry_matched=matched_hurry,
    )

    if dest:
        log_event(
            "AGENT",
            f"goal grounded: (at user {dest['location_id']})  "
            f"- hurry_mode={str(ctx.hurry_mode).lower()}",
            destination=dest,
            hurry_mode=ctx.hurry_mode,
        )
        log_event(
            "VALIDATION",
            f"destination_grounding  PASS  ·  (at user {dest['location_id']})",
            check="destination_grounding",
            result="pass",
            location_id=dest['location_id'],
            hurry_mode=ctx.hurry_mode,
        )
        ctx.destination = dest
        route = compute_route(agent, ctx.origin, dest, ctx=ctx)
        if not route:
            tts = planner_failure_message(ctx)
            return agent._reply(ctx, tts, "voice", "ask_destination")
        ctx.route_steps = route
        ctx.current_step_idx = 0
        return plan_confirmation.present_plan(agent, ctx)

    tts = "Where to? For example, classroom 1.4, the cafeteria, or main entrance."
    return agent._reply(ctx, tts, "voice", "ask_destination")


def parse_destination_for(
    agent: "ConversationAgent", msg: str
) -> Optional[Dict]:
    """Inject the agent's room lookup, last origin and topology into the
    pure parser."""
    last_origin = None
    if agent.contexts:
        last_session = list(agent.contexts.keys())[-1]
        last_origin = agent.contexts[last_session].origin
    return parse_destination(
        msg,
        agent._room_lookup,
        last_origin=last_origin,
        functional_locations=agent._topology.get("functional_locations", {}),
    )

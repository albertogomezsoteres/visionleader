"""Phase 4 — gather and parse the user's destination.

The single state ASK_DESTINATION accepts free-form text ("classroom 1.4",
"the cafeteria", "main entrance"). Parsing is delegated to
:func:`navigation.agent.parsing.parse_destination`; this module only
wires up the agent's room lookup and last-known origin and decides what
to do with the result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from ..context import ConversationContext
from ..parsing import parse_destination
from ..routing import compute_route, planner_failure_message

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


_HURRY_KEYWORDS = (
    "hurry", "rush", "fast", "quick", "prisa",
    "rápido", "rapido", "deprisa", "urgente",
)


def handle_ask_destination(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    from . import plan_confirmation  # lazy: cross-handler dependency

    low = msg.lower()
    if any(w in low for w in _HURRY_KEYWORDS):
        ctx.hurry_mode = True

    dest = parse_destination_for(agent, msg)
    if dest:
        ctx.destination = dest
        route = compute_route(agent, ctx.origin, dest)
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

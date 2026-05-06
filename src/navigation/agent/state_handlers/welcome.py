"""Phase 1 — welcome and yes/no entry into the location flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from ..context import ConversationContext, ConversationState
from ..parsing import is_no, is_yes, parse_location
from . import origin

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


def handle_welcome(agent: "ConversationAgent", ctx: ConversationContext) -> Dict:
    tts = "Hi. Do you know where you are?"
    ctx.state = ConversationState.ASK_KNOWS_LOCATION
    return agent._reply(ctx, tts, "voice", "welcome")


def handle_ask_knows_location(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    if is_yes(msg):
        tts = "Where are you? For example, classroom 0.3, building G."
        ctx.state = ConversationState.ASK_LOCATION_VOICE
        return agent._reply(ctx, tts, "voice", "ask_location")

    if is_no(msg):
        tts = "Did you just leave a classroom, elevator, or stairs?"
        ctx.state = ConversationState.ASK_SITUATION
        return agent._reply(ctx, tts, "voice", "ask_situation")

    loc = parse_location(msg, agent._room_lookup)
    if loc:
        ctx.origin = loc
        return origin.confirm_origin(agent, ctx)

    tts = "Do you know where you are? Yes or no."
    return agent._reply(ctx, tts, "voice", "ask_knows_location")

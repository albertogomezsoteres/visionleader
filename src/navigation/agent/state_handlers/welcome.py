"""Phase 1 — welcome and yes/no entry into the location flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from api.telemetry import log_event

from ..context import ConversationContext, ConversationState
from ..parsing import is_no, is_yes, parse_location
from . import location_discovery, origin

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


def handle_welcome(agent: "ConversationAgent", ctx: ConversationContext) -> Dict:
    tts = (
        "VisionLeader ready. Do you know where you are? "
        "If not, photograph any sign nearby so I can extract your location."
    )
    ctx.state = ConversationState.ASK_KNOWS_LOCATION
    log_event(
        "SCENARIO",
        "scenario started",
        session_id=ctx.session_id,
        status="started",
    )
    return agent._reply(ctx, tts, "voice_or_photo", "welcome")


def handle_ask_knows_location(
    agent: "ConversationAgent",
    ctx: ConversationContext,
    msg: str,
    image_analysis: Optional[Dict] = None,
) -> Dict:
    # Photo taken directly from the welcome screen: route through the
    # unified origin-photo handler. The user skipped the verbal "no".
    if image_analysis is not None:
        ctx.state = ConversationState.WAITING_PHOTO_ORIGIN
        ctx.photo_attempts = 0
        return location_discovery.handle_waiting_photo(agent, ctx, image_analysis)

    if is_yes(msg):
        tts = "Where are you? For example, classroom 0.3, building G."
        ctx.state = ConversationState.ASK_LOCATION_VOICE
        return agent._reply(ctx, tts, "voice", "ask_location")

    if is_no(msg):
        tts = "OK. Photograph any sign nearby so I can extract your location."
        ctx.state = ConversationState.WAITING_PHOTO_ORIGIN
        ctx.photo_attempts = 0
        return agent._reply(ctx, tts, "photo", "ask_origin_photo")

    loc = parse_location(msg, agent._room_lookup)
    if loc:
        ctx.origin = loc
        return origin.confirm_origin(agent, ctx)

    tts = "Do you know where you are? Yes or no."
    return agent._reply(ctx, tts, "voice_or_photo", "ask_knows_location")

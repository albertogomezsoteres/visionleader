"""Phase 2 — discover the user's origin via voice or photo.

Covers the five states the FSM can sit in while it still does not have a
fully resolved ``(building, floor, location_id)`` tuple:

- ASK_LOCATION_VOICE  — free-form voice answer ("classroom 0.3, building G")
- ASK_SITUATION       — what the user can see, leading to a photo request
- WAITING_PHOTO_DOOR / WAITING_PHOTO_SIGN — process VLM photo result
- ASK_BUILDING / ASK_FLOOR — fill in whichever piece is still missing
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Tuple

from ..context import ConversationContext, ConversationState
from ..parsing import (
    extract_building,
    extract_floor,
    extract_location_id_from_pddl,
    parse_location,
)
from ..text_formatting import BUILDING_FULL, floor_text
from . import origin

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


def handle_ask_location_voice(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    loc = parse_location(msg, agent._room_lookup)
    if loc and loc.get("building") and loc.get("floor") is not None:
        ctx.origin = loc
        return origin.confirm_origin(agent, ctx)

    if loc and loc.get("building") and loc.get("floor") is None:
        ctx.partial_building = loc["building"]
        tts = (
            f"I heard you are in {BUILDING_FULL.get(loc['building'], 'that building')}. "
            "What floor are you on?"
        )
        ctx.state = ConversationState.ASK_FLOOR
        return agent._reply(ctx, tts, "voice", "ask_floor")

    if loc and loc.get("floor") is not None and not loc.get("building"):
        ctx.partial_floor = loc["floor"]
        tts = (
            f"I heard you are on {floor_text(loc['floor'])}. "
            "What building are you in? For example, building G, Centro Deportivo, or building H."
        )
        ctx.state = ConversationState.ASK_BUILDING
        return agent._reply(ctx, tts, "voice", "ask_building")

    ctx.voice_retries += 1
    if ctx.voice_retries >= 3:
        tts = "Let's try a photo. Photograph a door sign, or a floor sign near the elevator."
        ctx.state = ConversationState.ASK_SITUATION
        ctx.voice_retries = 0
        return agent._reply(ctx, tts, "voice", "ask_situation")

    tts = "I didn't catch that. For example, 'classroom 0.3, building G'."
    return agent._reply(ctx, tts, "voice", "ask_location")


def handle_ask_situation(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    low = msg.lower()

    if any(w in low for w in ("classroom", "door", "aula", "puerta", "room", "clase")):
        tts = "Take a photo of the classroom door."
        ctx.state = ConversationState.WAITING_PHOTO_DOOR
        ctx.photo_attempts = 0
        return agent._reply(ctx, tts, "photo", "request_photo_door")

    if any(w in low for w in ("elevator", "lift")):
        tts = "Turn left, walk two metres, and photograph the floor sign."
        ctx.state = ConversationState.WAITING_PHOTO_SIGN
        ctx.photo_attempts = 0
        return agent._reply(ctx, tts, "photo", "request_photo_sign")

    if any(w in low for w in ("stairs", "stair", "escalera")):
        tts = "Find the floor sign near the stairs and photograph it."
        ctx.state = ConversationState.WAITING_PHOTO_SIGN
        ctx.photo_attempts = 0
        return agent._reply(ctx, tts, "photo", "request_photo_sign")

    if any(w in low for w in ("directory", "directorio", "sign", "cartel", "panel")):
        tts = "Photograph the directory sign."
        ctx.state = ConversationState.WAITING_PHOTO_SIGN
        ctx.photo_attempts = 0
        return agent._reply(ctx, tts, "photo", "request_photo_sign")

    if any(w in low for w in (
        "don't know", "dont know", "no idea", "not sure",
        "no sé", "no se", "ni idea",
    )):
        tts = "Tell me what you see. A classroom door, the elevator, or the stairs?"
        return agent._reply(ctx, tts, "voice", "ask_situation")

    loc = parse_location(msg, agent._room_lookup)
    if loc and loc.get("building") and loc.get("floor") is not None:
        ctx.origin = loc
        return origin.confirm_origin(agent, ctx)

    tts = (
        "Are you near a classroom door, the elevator, or the stairs? "
        "Or say your location, like 'classroom 0.3, building G'."
    )
    return agent._reply(ctx, tts, "voice", "ask_situation")


def handle_waiting_photo(
    agent: "ConversationAgent",
    ctx: ConversationContext,
    analysis: Optional[Dict],
) -> Dict:
    if not analysis:
        tts = "I am waiting for a photo. Please take one now."
        return agent._reply(ctx, tts, "photo", "waiting_photo")

    ctx.photo_attempts += 1

    location_id = analysis.get("location_id") or extract_location_id_from_pddl(
        analysis.get("raw_response", "")
    )
    if location_id:
        resolved = resolve_location_id(agent, location_id)
        if resolved:
            bid, fnum, loc_id = resolved
            ctx.origin = {"building": bid, "floor": fnum, "location_id": loc_id}
            return origin.confirm_origin(agent, ctx)

    if ctx.photo_attempts >= 3:
        tts = "Let's try voice. Say your location, like 'classroom 0.3, building G'."
        ctx.state = ConversationState.ASK_LOCATION_VOICE
        ctx.photo_attempts = 0
        return agent._reply(ctx, tts, "voice", "fallback_to_voice")

    tts = "I couldn't read that photo. Try again with the sign clearly visible."
    return agent._reply(ctx, tts, "photo", "retry_photo")


def handle_ask_building(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    bid = extract_building(msg)
    if bid:
        floor = ctx.partial_floor
        loc_id = ctx.partial_location_id
        ctx.origin = {"building": bid, "floor": floor, "location_id": loc_id}
        if floor is not None:
            return origin.confirm_origin(agent, ctx)
        ctx.partial_building = bid
        tts = (
            f"You are in {BUILDING_FULL.get(bid, 'that building')}. "
            "What floor are you on?"
        )
        ctx.state = ConversationState.ASK_FLOOR
        return agent._reply(ctx, tts, "voice", "ask_floor")

    tts = "Which building? G, CD, or H."
    return agent._reply(ctx, tts, "voice", "ask_building")


def handle_ask_floor(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    floor = extract_floor(msg)
    if floor is not None:
        bid = ctx.partial_building
        loc_id = ctx.partial_location_id
        ctx.origin = {"building": bid, "floor": floor, "location_id": loc_id}
        if bid is not None:
            return origin.confirm_origin(agent, ctx)
        tts = f"You are on {floor_text(floor)}. What building are you in?"
        ctx.state = ConversationState.ASK_BUILDING
        return agent._reply(ctx, tts, "voice", "ask_building")

    tts = "Which floor? Ground, one, or two."
    return agent._reply(ctx, tts, "voice", "ask_floor")


def resolve_location_id(
    agent: "ConversationAgent", location_id: str
) -> Optional[Tuple[int, int, str]]:
    """Resolve a bare PDDL ``location_id`` to ``(building, floor, id)``.

    Validated prompts emit atoms scoped to buildings G and CD, so this
    helper scans G first, then CD, and returns the first match.
    """
    for bid in (1, 2):
        fnum = agent._hierarchical_converter.find_location_floor(bid, location_id)
        if fnum is not None:
            return (bid, fnum, location_id)
    return None

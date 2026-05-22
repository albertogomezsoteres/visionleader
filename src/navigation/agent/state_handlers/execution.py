"""Phase 6 — execute the plan step by step.

Three states share this module:

- EXECUTING            — between voice steps, dispatches the next step
- AWAITING_STEP_DONE   — waiting for the user to say "done" / "next"
- WAITING_STEP_PHOTO   — waiting for a verification photo

Plus the universal recovery actions reachable from any of these via the
shortcuts handled in :func:`ConversationAgent.process_turn`:
:func:`handle_lost` and :func:`cancel_navigation`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from api.telemetry import log_event

from ..context import ConversationContext, ConversationState
from ..parsing import extract_room_code_from_analysis, normalize_room_code
from ..text_formatting import location_text, nice_location_name, photo_label

if TYPE_CHECKING:
    from ...conversation_agent import ConversationAgent


_DONE_WORDS_VOICE = (
    "done", "next", "ready", "listo", "siguiente",
    "yes", "ok", "okay", "continue", "continuar",
)
_DONE_WORDS_PHOTO_SKIP = (
    "done", "next", "ready", "listo", "skip", "saltar",
    "yes", "ok", "i am here", "i'm here",
)


def handle_executing(
    agent: "ConversationAgent",
    ctx: ConversationContext,
    msg: str,
    analysis: Optional[Dict],
) -> Dict:
    return deliver_step(agent, ctx)


def handle_step_done(
    agent: "ConversationAgent", ctx: ConversationContext, msg: str
) -> Dict:
    from . import completion  # lazy: completion.navigation_complete

    low = msg.lower()
    if any(w in low for w in _DONE_WORDS_VOICE):
        ctx.current_step_idx += 1
        if ctx.current_step_idx >= len(ctx.route_steps):
            return completion.navigation_complete(agent, ctx)
        ctx.state = ConversationState.EXECUTING
        return deliver_step(agent, ctx)

    tts = "Say next."
    return agent._reply(ctx, tts, "voice", "awaiting_step_done")


def handle_step_photo(
    agent: "ConversationAgent",
    ctx: ConversationContext,
    analysis: Optional[Dict],
    msg: str,
) -> Dict:
    from . import completion  # lazy: completion.navigation_complete

    step = ctx.route_steps[ctx.current_step_idx]
    expected = step.get("expected_photo_type")

    # User can skip a photo verification by voice.
    if not analysis and msg:
        low = msg.lower()
        if any(w in low for w in _DONE_WORDS_PHOTO_SKIP):
            ctx.current_step_idx += 1
            if ctx.current_step_idx >= len(ctx.route_steps):
                return completion.navigation_complete(agent, ctx)
            ctx.state = ConversationState.EXECUTING
            return deliver_step(agent, ctx)

    expected_text = photo_label(expected)

    if not analysis:
        tts = f"Photograph the {expected_text}, or say done to skip."
        return agent._reply(ctx, tts, "photo", "waiting_step_photo")

    prompt_id = analysis.get("prompt_id", "")
    if expected and prompt_id == expected and analysis.get("success"):
        if step.get("arrival_strict_photo"):
            return _handle_arrival_strict_photo(
                agent, ctx, analysis, step, expected_text, completion,
            )

        # stair_direction safety check: the planner emits the action's
        # direction ("up" / "down") on the step; if the VLM's reading of
        # the staircase disagrees, the user is facing the wrong side and
        # advancing would send them in the wrong direction.
        if prompt_id == "stair_direction" and step.get("stairs_direction"):
            seen_dir = analysis.get("state_detail")
            expected_dir = step["stairs_direction"]
            if seen_dir and seen_dir != expected_dir:
                log_event(
                    "VALIDATION",
                    f"stairs_verification  FAIL  ·  expected={expected_dir} seen={seen_dir}",
                    check="stairs_verification", result="fail",
                    expected_direction=expected_dir, seen_direction=seen_dir,
                )
                tts = (
                    f"I see stairs going {seen_dir}, but you need to go "
                    f"{expected_dir}. Please find the {expected_dir}-going "
                    "side of the staircase and photograph it again."
                )
                return agent._reply(ctx, tts, "photo", "retry_step_photo")
            log_event(
                "VALIDATION",
                f"stairs_verification  PASS  ·  direction={seen_dir}",
                check="stairs_verification", result="pass",
                seen_direction=seen_dir,
            )

        # Elevator state-aware messaging: doors closed = the cabin is there
        # but the user must press the call button and wait; doors open =
        # step in directly. The target floor button to press travels with
        # the step so the message stays specific.
        # Auto-advance after a verification photo: the photo IS the step
        # completion, so we attach the confirmation to the next step's TTS
        # instead of stopping for an extra "Say next" round-trip. This
        # eliminates the lone "confirm and ask to advance" turn that adds
        # latency without accepting any meaningful user input.
        if step.get("elevator_photo_flow") and not step.get("_phase2_started"):
            step["_phase2_started"] = True
            seen_state = (analysis or {}).get("state_detail")
            target_floor = step.get("elevator_target_floor")
            log_event(
                "VALIDATION",
                f"elevator_verification  PASS  ·  doors={seen_state or 'unknown'}",
                check="elevator_verification", result="pass",
                seen_state=seen_state, target_floor=target_floor,
            )
            ctx.current_step_idx += 1
            if ctx.current_step_idx >= len(ctx.route_steps):
                return completion.navigation_complete(agent, ctx)

            # Compact merged TTS for the elevator-then-next-step transition.
            # The verbose "Press floor X. Step N of M. Exit the elevator..."
            # cascade is collapsed into a single line that keeps just the
            # directional cue plus a short photo verification trigger.
            next_step = ctx.route_steps[ctx.current_step_idx]
            next_instruction = (next_step.get("instruction") or "").strip()
            low = next_instruction.lower()
            if low.startswith("exit the elevator,"):
                next_instruction = next_instruction[len("exit the elevator,"):].strip()
            elif low.startswith("exit the elevator"):
                next_instruction = next_instruction[len("exit the elevator"):].lstrip(" ,.").strip()
            # Drop the first internal ", then " so the merged TTS doesn't
            # pile up two "then"s in a row ("...elevator, then turn left,
            # then walk 10 meters" → "...elevator, then turn left, walk
            # 10 meters"). The remaining "then"s, if any, stay as natural
            # sequence markers further down the sentence.
            next_instruction = next_instruction.replace(", then ", ", ", 1)

            if next_step.get("verification") == "photo":
                tts = f"Confirmed. Use the elevator, then {next_instruction} Photograph to verify."
                ctx.state = ConversationState.WAITING_STEP_PHOTO
                ctx.add("system", tts)
                return agent._reply(ctx, tts, "photo", "step_after_photo_confirm")

            tts = f"Confirmed. Use the elevator, then {next_instruction} Say next."
            ctx.state = ConversationState.AWAITING_STEP_DONE
            ctx.add("system", tts)
            return agent._reply(ctx, tts, "voice", "step_after_photo_confirm")

        if step.get("two_phase_photo") and not step.get("_phase2_started"):
            step["_phase2_started"] = True
            post_tts = step.get("post_photo_instruction", step.get("instruction", ""))
            confirm_tts = f"Confirmed. {post_tts}"
            ctx.current_step_idx += 1
            if ctx.current_step_idx >= len(ctx.route_steps):
                return completion.navigation_complete(agent, ctx)
            ctx.state = ConversationState.EXECUTING
            ctx.add("system", confirm_tts)
            return deliver_step(agent, ctx, prefix=confirm_tts + " ")

        tts = f"Confirmed! I can see the {expected_text}."
        ctx.current_step_idx += 1
        if ctx.current_step_idx >= len(ctx.route_steps):
            return completion.navigation_complete(agent, ctx)
        ctx.state = ConversationState.EXECUTING
        ctx.add("system", tts)
        return deliver_step(agent, ctx, prefix=tts + " ")

    tts = (
        f"That doesn't look like the {expected_text}. "
        "Retake the photo, or say done if you're there."
    )
    return agent._reply(ctx, tts, "photo", "retry_step_photo")


def _handle_arrival_strict_photo(
    agent: "ConversationAgent",
    ctx: ConversationContext,
    analysis: Dict,
    step: Dict,
    expected_text: str,
    completion,
) -> Dict:
    """Final arrival check: the VLM output must match the expected room
    code (classroom plate) or the expected location id (service sign)."""
    expected_code = step.get("expected_room_code")
    expected_loc = step.get("expected_location_id")

    # Service-style verification (e.g. cafeteria via service_plate).
    if expected_loc:
        seen_loc = (analysis or {}).get("location_id")
        loc_label = nice_location_name(expected_loc)
        if seen_loc == expected_loc:
            log_event(
                "AGENT",
                f"arrival verified: (at user {seen_loc}) == expected (at user {expected_loc})  ✓",
                expected_location_id=expected_loc, seen_location_id=seen_loc, ok=True,
            )
            log_event(
                "VALIDATION",
                f"arrival_verification  PASS  ·  (at user {seen_loc}) matches expected",
                check="arrival_verification", result="pass",
                expected_location_id=expected_loc, seen_location_id=seen_loc,
            )
            tts = f"Confirmed! I can see {loc_label}."
            ctx.current_step_idx += 1
            if ctx.current_step_idx >= len(ctx.route_steps):
                return completion.navigation_complete(agent, ctx)
            ctx.state = ConversationState.EXECUTING
            ctx.add("system", tts)
            return deliver_step(agent, ctx, prefix=tts + " ")
        log_event(
            "AGENT",
            f"arrival mismatch: seen={seen_loc!r} expected={expected_loc!r}  ✗",
            expected_location_id=expected_loc, seen_location_id=seen_loc, ok=False,
        )
        log_event(
            "VALIDATION",
            f"arrival_verification  FAIL  ·  seen={seen_loc!r} expected={expected_loc!r}",
            check="arrival_verification", result="fail",
            expected_location_id=expected_loc, seen_location_id=seen_loc,
        )
        tts = f"That doesn't look like {loc_label}. Retake the photo."
        return agent._reply(ctx, tts, "photo", "retry_step_photo")

    # Classroom-style verification: compare normalized room codes.
    seen_code = extract_room_code_from_analysis(analysis)

    if not expected_code:
        tts = f"Confirmed! I can see the {expected_text}."
        ctx.current_step_idx += 1
        if ctx.current_step_idx >= len(ctx.route_steps):
            return completion.navigation_complete(agent, ctx)
        ctx.state = ConversationState.EXECUTING
        ctx.add("system", tts)
        return deliver_step(agent, ctx, prefix=tts + " ")

    if seen_code and normalize_room_code(seen_code) == normalize_room_code(expected_code):
        log_event(
            "AGENT",
            f"arrival verified: room_code {seen_code!r} matches expected {expected_code!r}  ✓",
            expected_room_code=expected_code, seen_room_code=seen_code, ok=True,
        )
        log_event(
            "VALIDATION",
            f"arrival_verification  PASS  ·  room_code {seen_code!r} matches expected",
            check="arrival_verification", result="pass",
            expected_room_code=expected_code, seen_room_code=seen_code,
        )
        tts = f"Confirmed! I can see classroom {normalize_room_code(expected_code)}."
        ctx.current_step_idx += 1
        if ctx.current_step_idx >= len(ctx.route_steps):
            return completion.navigation_complete(agent, ctx)
        ctx.state = ConversationState.EXECUTING
        ctx.add("system", tts)
        return deliver_step(agent, ctx, prefix=tts + " ")

    log_event(
        "AGENT",
        f"arrival mismatch: room_code {seen_code!r} != expected {expected_code!r}  ✗",
        expected_room_code=expected_code, seen_room_code=seen_code, ok=False,
    )
    log_event(
        "VALIDATION",
        f"arrival_verification  FAIL  ·  room_code {seen_code!r} != expected {expected_code!r}",
        check="arrival_verification", result="fail",
        expected_room_code=expected_code, seen_room_code=seen_code,
    )
    tts = (
        f"I expected classroom {normalize_room_code(expected_code)}, "
        f"but I see {normalize_room_code(seen_code) if seen_code else 'a different location'}. "
        "Retake the photo."
    )
    return agent._reply(ctx, tts, "photo", "retry_step_photo")


def deliver_step(
    agent: "ConversationAgent", ctx: ConversationContext, prefix: str = "",
) -> Dict:
    """Format the current ``route_steps[idx]`` as TTS and pick the next FSM
    state (waiting for voice "done", waiting for a verification photo, or
    waiting for the GPS leg to complete)."""
    from . import completion  # lazy: completion.navigation_complete

    if ctx.current_step_idx >= len(ctx.route_steps):
        return completion.navigation_complete(agent, ctx)

    step = ctx.route_steps[ctx.current_step_idx]
    idx = ctx.current_step_idx + 1
    total = len(ctx.route_steps)
    instruction = step["instruction"]

    # The "Step N of M" counter is rendered by the mobile UI as a chip
    # (status_row.dart reads current_step_idx + route_step_count from
    # the context), so the spoken / displayed TTS does not repeat it.
    tts = f"{prefix}{instruction}"
    extra: Dict = {}

    if step.get("use_gps"):
        from_bld = step.get("outdoor_from_building")
        to_bld = step.get("outdoor_to_building")
        if from_bld and to_bld:
            extra["gps_route"] = {
                "from_building": from_bld,
                "to_building": to_bld,
                "auto_open": True,
            }
        tts += " Say done."
        ctx.state = ConversationState.AWAITING_STEP_DONE
        return agent._reply(ctx, tts, "voice", "navigation_step_outdoor", **extra)

    if step.get("verification") == "photo":
        return _deliver_photo_step(agent, ctx, step, idx, total, instruction, prefix)

    tts += " Say next."
    ctx.state = ConversationState.AWAITING_STEP_DONE
    return agent._reply(ctx, tts, "voice", "navigation_step")


def _deliver_photo_step(
    agent: "ConversationAgent",
    ctx: ConversationContext,
    step: Dict,
    idx: int,
    total: int,
    instruction: str,
    prefix: str,
) -> Dict:
    """Build TTS for a step that requires VLM photo verification."""
    expected_text = photo_label(step.get("expected_photo_type"))

    if step.get("arrival_strict_photo"):
        tts = f"{prefix}{instruction} Photograph to verify."
        ctx.state = ConversationState.WAITING_STEP_PHOTO
        return agent._reply(ctx, tts, "photo", "navigation_step")

    base_tts = f"{prefix}{instruction}"

    if step.get("elevator_photo_flow") and step.get("_elevator_stage", 1) == 1:
        pre_tts = step.get("pre_photo_instruction")
        if pre_tts:
            base_tts = f"{prefix}{pre_tts}"
        tts = f"{base_tts} Photograph the {expected_text}."
    elif step.get("two_phase_photo") and not step.get("_phase2_started"):
        pre_tts = step.get("pre_photo_instruction")
        if pre_tts:
            base_tts = f"{prefix}{pre_tts}"
        tts = f"{base_tts} Photograph the {expected_text}."
    else:
        if step.get("inline_photo_prompt"):
            ctx.state = ConversationState.WAITING_STEP_PHOTO
            return agent._reply(ctx, base_tts, "photo", "navigation_step")
        tts = f"{base_tts} Photograph to verify."

    ctx.state = ConversationState.WAITING_STEP_PHOTO
    return agent._reply(ctx, tts, "photo", "navigation_step")


def handle_lost(agent: "ConversationAgent", ctx: ConversationContext) -> Dict:
    """User said "I'm lost": save the destination and restart the
    location-discovery flow."""
    dest_text = location_text(ctx.destination) if ctx.destination else "your destination"
    tts = (
        f"Okay. Destination saved: {dest_text}. "
        "Did you just leave a classroom, elevator, or stairs? Or photograph a sign."
    )
    ctx.state = ConversationState.ASK_SITUATION
    ctx.origin = None
    ctx.route_steps = []
    ctx.current_step_idx = 0
    return agent._reply(ctx, tts, "voice_or_photo", "replanning")


def cancel_navigation(agent: "ConversationAgent", ctx: ConversationContext) -> Dict:
    """User said "cancel": clear the route and ask for a new destination."""
    tts = "Navigation cancelled. Tell me a new destination."
    ctx.state = ConversationState.ASK_DESTINATION
    ctx.route_steps = []
    ctx.current_step_idx = 0
    return agent._reply(ctx, tts, "voice", "cancelled")

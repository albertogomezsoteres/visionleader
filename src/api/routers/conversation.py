"""Conversation endpoint: single unified turn-based interface."""

import traceback

from fastapi import APIRouter

from api.schemas import ConversationRequest, ConversationResponse
from api.dependencies import get_conversation_agent

router = APIRouter()


@router.post("/conversation", response_model=ConversationResponse)
async def conversation(request: ConversationRequest):
    """
    Accept one user turn (text and/or image analysis) and return the
    assistant's reply plus the next expected input type.

    All state routing is handled inside ConversationAgent.process_turn().
    """
    try:
        agent = get_conversation_agent()
        image_analysis = request.image_analysis if isinstance(request.image_analysis, dict) else None
        user_message = request.user_message or ""

        result = agent.process_turn(
            session_id=request.session_id,
            user_message=user_message if user_message else None,
            image_analysis=image_analysis,
        )

        ctx = result.get("context", {})
        return ConversationResponse(
            response=result.get("tts_message", ""),
            action=result.get("action", ""),
            needs_input=result.get("next_input", "voice") != "none",
            context=ctx,
            tts_message=result.get("tts_message"),
            next_input=result.get("next_input"),
            expect_photo=result.get("expect_photo"),
            plan_request=result.get("plan_request"),
            location_partial=result.get("location_partial"),
            auto_fill=result.get("auto_fill"),
            auto_fill_goal=result.get("auto_fill_goal"),
            gps_route=result.get("gps_route"),
        )

    except Exception as e:
        traceback.print_exc()
        return ConversationResponse(
            response=f"Sorry, I encountered an error: {e}",
            action="error", needs_input=True, context={},
            error=str(e),
            tts_message=f"Sorry, I encountered an error: {e}",
            next_input="voice",
        )

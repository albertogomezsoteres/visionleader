"""Image analysis endpoints: analyse a photo, clarify missing location info."""

from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from api.models import ImageAnalysisResponse, ClarificationRequest, ClarificationResponse
from api.dependencies import load_campus_graph, COLAB_API_URL
from api.services.image_analysis import (
    analyze_image_via_colab,
    analyze_image_locally,
    parse_location_from_paligemma_response,
    generate_clarification_question,
    validate_user_response,
)

router = APIRouter()


@router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    current_building: Optional[str] = Form(None),
    current_floor: Optional[str] = Form(None),
):
    """
    Send a photo and get back the detected building + floor.

    Optionally pass current_building / current_floor if the app already
    knows part of the location from a previous interaction.
    """
    try:
        allowed = ["image/jpeg", "image/jpg", "image/png", "application/octet-stream"]
        if file.content_type not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported image format: {file.content_type}")

        image_data = await file.read()
        campus_graph = load_campus_graph()

        # Parse optional known state sent by the app
        known_building: Optional[int] = None
        known_floor: Optional[int] = None
        if current_floor is not None and str(current_floor).strip():
            try: known_floor = int(str(current_floor).strip())
            except ValueError: pass
        if current_building is not None and str(current_building).strip():
            try: known_building = int(str(current_building).strip())
            except ValueError: pass

        # Route to Colab or local inference
        if COLAB_API_URL:
            try:
                return analyze_image_via_colab(
                    image_data, file.filename or "image.jpg", file.content_type or "image/jpeg",
                    campus_graph, known_building, known_floor, COLAB_API_URL,
                )
            except Exception:
                # Colab unreachable — fall back to local model
                return await analyze_image_locally(image_data, campus_graph, file.filename, file.content_type)
        else:
            return await analyze_image_locally(image_data, campus_graph, file.filename, file.content_type)

    except HTTPException:
        raise
    except Exception as e:
        return ImageAnalysisResponse(
            success=False, raw_response="", error=f"Error processing image: {e}",
            needs_clarification=False, clarification_question=None,
        )


@router.post("/clarify-location", response_model=ClarificationResponse)
async def clarify_location(request: ClarificationRequest):
    """Process the user's voice reply to fill in the missing building or floor."""
    try:
        campus_graph = load_campus_graph()
        is_valid, err = validate_user_response(request.user_response, campus_graph)

        prev_building = request.previous_context.get("building")
        prev_floor = request.previous_context.get("floor")

        if not is_valid:
            q = generate_clarification_question(prev_building, prev_floor, campus_graph)
            if err:
                q = f"{err} {q}"
            return ClarificationResponse(
                success=False, building=prev_building, floor=prev_floor,
                needs_clarification=True, clarification_question=q,
            )

        parsed = parse_location_from_paligemma_response(request.user_response, campus_graph)
        final_building = prev_building if prev_building is not None else parsed.get("building")
        final_floor = prev_floor if prev_floor is not None else parsed.get("floor")

        if final_building is not None and final_floor is not None:
            return ClarificationResponse(
                success=True, building=final_building, floor=final_floor,
                needs_clarification=False, clarification_question=None,
            )

        q = generate_clarification_question(final_building, final_floor, campus_graph)
        return ClarificationResponse(
            success=False, building=final_building, floor=final_floor,
            needs_clarification=True, clarification_question=q,
        )
    except Exception as e:
        return ClarificationResponse(
            success=False, needs_clarification=False,
            clarification_question=None, error=f"Error during clarification: {e}",
        )

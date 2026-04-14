"""Image analysis endpoint: send a photo and get back the detected location."""

from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from api.schemas import ImageAnalysisResponse
from api.dependencies import load_places, COLAB_API_URL
from api.services.image_analysis import analyzeImageViaColab

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
        campus_graph = load_places()

        # Parse optional known state sent by the app
        known_building: Optional[int] = None
        known_floor: Optional[int] = None
        if current_floor is not None and str(current_floor).strip():
            try: known_floor = int(str(current_floor).strip())
            except ValueError: pass
        if current_building is not None and str(current_building).strip():
            try: known_building = int(str(current_building).strip())
            except ValueError: pass

        if not COLAB_API_URL:
            raise HTTPException(status_code=503, detail="Colab inference endpoint not configured")

        return analyzeImageViaColab(
            image_data, file.filename or "image.jpg", file.content_type or "image/jpeg",
            campus_graph, known_building, known_floor, COLAB_API_URL,
        )

    except HTTPException:
        raise
    except Exception as e:
        return ImageAnalysisResponse(
            success=False, raw_response="", error=f"Error processing image: {e}",
            needs_clarification=False, clarification_question=None,
        )



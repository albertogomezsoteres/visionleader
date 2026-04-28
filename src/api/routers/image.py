"""Image analysis endpoint: run a validated VLM prompt on a photo."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.dependencies import COLAB_API_URL
from api.schemas import ImageAnalysisResponse
from api.services.image_analysis import analyze_image
from api.services.vlm_prompts import valid_prompt_ids

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "application/octet-stream"}


@router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image_endpoint(
    file: UploadFile = File(...),
    prompt_id: str = Form(...),
):
    """Run the prompt named by ``prompt_id`` on ``file`` and return the parsed result.

    The mobile FSM picks the prompt based on its current state, so this
    endpoint never has to guess what's in the photo.
    """
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported image format: {file.content_type}")

    if prompt_id not in valid_prompt_ids():
        raise HTTPException(status_code=400, detail=f"Unknown prompt_id: {prompt_id}")

    if not COLAB_API_URL:
        raise HTTPException(status_code=503, detail="Colab inference endpoint not configured")

    image_data = await file.read()
    return analyze_image(
        image_data,
        file.filename or "image.jpg",
        file.content_type or "image/jpeg",
        prompt_id,
        COLAB_API_URL,
    )

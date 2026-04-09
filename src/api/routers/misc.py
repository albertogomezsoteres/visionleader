"""Root-level endpoints: health check and web demo."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/")
async def root():
    """Quick summary of available endpoints."""
    return {
        "message": "Campus Navigation Planning API",
        "version": "1.0.0",
        "endpoints": {
            "plan": "POST /api/plan",
            "domain": "GET /api/domain",
            "validate": "POST /api/validate",
            "analyze-image": "POST /api/analyze-image",
            "clarify-location": "POST /api/clarify-location",
            "transcribe-audio": "POST /api/transcribe-audio",
            "conversation": "POST /api/conversation",
            "demo": "GET /demo",
            "docs": "GET /docs",
        },
    }


@router.get("/demo")
async def demo():
    """Serve the interactive HTML demo page."""
    html_file = Path(__file__).resolve().parents[3] / "demo_interactiva.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="demo_interactiva.html not found")
    with open(html_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), headers={"Content-Type": "text/html; charset=utf-8"})

"""
Campus Navigation API: application factory.

Creates the FastAPI app and wires up all routers.
Each router handles a specific domain (planning, image, speech, etc.).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from visionleader import __version__
from visionleader.api.middleware import TelemetryMiddleware
from visionleader.api.routers import _telemetry, conversation, gps, image, plan

app = FastAPI(
    title="Campus Navigation Planning API",
    description="Indoor navigation for the UFV campus: PDDL planner and Gemma 4 E4B vision. STT runs on-device.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TelemetryMiddleware)

app.include_router(plan.router, prefix="/api", tags=["Planning"])
app.include_router(image.router, prefix="/api", tags=["Image Analysis"])
app.include_router(conversation.router, prefix="/api", tags=["Conversation"])
app.include_router(gps.router, prefix="/api", tags=["GPS"])
app.include_router(_telemetry.router, prefix="/api", tags=["Telemetry"])


@app.get("/")
async def root():
    """Quick summary of available endpoints."""
    return {
        "message": "Campus Navigation Planning API",
        "version": __version__,
        "endpoints": {
            "plan": "POST /api/plan",
            "domain": "GET /api/domain",
            "validate": "POST /api/validate",
            "analyze-image": "POST /api/analyze-image",
            "conversation": "POST /api/conversation",
            "gps-route": "POST /api/gps-route",
            "docs": "GET /docs",
        },
    }

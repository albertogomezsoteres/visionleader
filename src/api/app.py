"""
Campus Navigation API: application factory.

Creates the FastAPI app and wires up all routers.
Each router handles a specific domain (planning, image, speech, etc.).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import plan, image, conversation, gps

app = FastAPI(
    title="Campus Navigation Planning API",
    description="Indoor navigation for the UFV campus: PDDL planner and Gemma 4 E4B vision. STT runs on-device.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan.router, prefix="/api", tags=["Planning"])
app.include_router(image.router, prefix="/api", tags=["Image Analysis"])
app.include_router(conversation.router, prefix="/api", tags=["Conversation"])
app.include_router(gps.router, prefix="/api", tags=["GPS"])


@app.get("/")
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
            "conversation": "POST /api/conversation",
            "gps-route": "POST /api/gps-route",
            "docs": "GET /docs",
        },
    }

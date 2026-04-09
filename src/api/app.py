"""
Campus Navigation API — application factory.

Here we create the FastAPI app and wire up all the routers.
Each router handles a specific domain (planning, image, speech, etc.)
so the API stays organised as it grows.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import plan, image, conversation, speech, gps, misc

app = FastAPI(
    title="Campus Navigation Planning API",
    description="Navigation planning for the UFV campus using PDDL, PaliGemma and voice",
    version="1.0.0",
)

# Allow any origin during development; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level endpoints (home page, demo)
app.include_router(misc.router)

# Domain-specific routers, all under /api
app.include_router(plan.router, prefix="/api", tags=["Planning"])
app.include_router(image.router, prefix="/api", tags=["Image Analysis"])
app.include_router(conversation.router, prefix="/api", tags=["Conversation"])
app.include_router(speech.router, prefix="/api", tags=["Speech"])
app.include_router(gps.router, prefix="/api", tags=["GPS"])

"""Pydantic request and response schemas for every API endpoint."""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any


class PlanningRequest(BaseModel):
    """Request to generate a navigation plan.

    initial_state and goal_state accept:
      {'building': int, 'floor': int, 'room': 'classroom_g_1_4'}

    The shared `domain_indoor.pddl` handles both intra- and cross-building
    routes. When origin and goal are in different buildings the converter
    emits rooms of both plus `conectado_exterior` edges between entrances.
    """
    initial_state: Dict[str, Any] = Field(
        ...,
        description="Starting location. Required: building, floor, room.",
    )
    goal_state: Optional[Dict[str, Any]] = Field(
        None,
        description="Target location. Required: building, floor, room (unless goal_functional).",
    )
    goal_functional: Optional[str] = Field(
        None,
        description="Named destination: 'cafeteria' or 'gym'",
    )
    hurry_mode: bool = Field(
        False,
        description="When true the planner prefers stairs over elevator",
    )


class PlanningResponse(BaseModel):
    """Response with the generated plan."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    plan: List[str] = Field(default_factory=list)
    steps: int = 0
    cost: int = 0
    initial_state: Optional[Dict[str, Any]] = None
    goal_state: Optional[Any] = None
    error: Optional[str] = None
    output: Optional[str] = None


class ValidationRequest(BaseModel):
    """Request to validate a plan."""
    plan: List[str]
    initial_state: Dict[str, Any]
    goal_state: Dict[str, Any]


class ValidationResponse(BaseModel):
    """Response from plan validation."""
    valid: bool
    message: str


class DomainResponse(BaseModel):
    """Response with the PDDL domain file contents."""
    domain: str


class ImageAnalysisResponse(BaseModel):
    """Result of running one validated VLM prompt on a photo.

    For PDDL-atom prompts (`room_plate`, `directory_sign`) the model
    returns a campus location identifier in ``location_id``. For JSON
    state prompts (`elevator_state`, `stair_direction`, `restroom_gender`)
    the model returns ``state_type`` and ``state_detail``.
    """
    success: bool
    prompt_id: str
    location_id: Optional[str] = None
    state_type: Optional[str] = None
    state_detail: Optional[str] = None
    raw_response: str = ""
    error: Optional[str] = None


class TranscribeResponse(BaseModel):
    """Response from Whisper audio transcription."""
    success: bool
    text: str
    error: Optional[str] = None


class GPSRouteRequest(BaseModel):
    """Request for walking directions between two campus buildings."""
    from_building: int
    to_building: int


class GPSRouteResponse(BaseModel):
    """Response with the Google Maps walking route."""
    success: bool
    distance: Optional[str] = None
    duration: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    polyline: Optional[str] = None
    error: Optional[str] = None


class ConversationRequest(BaseModel):
    """Request for one conversation turn."""
    session_id: str
    user_message: str
    image_analysis: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    """Response from one conversation turn."""
    response: str
    action: str
    needs_input: bool
    context: Dict[str, Any]
    tts_message: Optional[str] = None
    next_input: Optional[str] = None
    # Tells the client which VLM prompt to run on the next photo. One of
    # the prompt ids defined in extraction_validation/prompts.json
    # (room_plate, directory_sign, elevator_state, stair_direction,
    # restroom_gender). Null when no photo is expected.
    expect_photo: Optional[str] = None
    plan_request: Optional[Dict[str, Any]] = None
    location_partial: Optional[Dict[str, Any]] = None
    auto_fill: Optional[Dict[str, Any]] = None
    auto_fill_goal: Optional[Dict[str, Any]] = None
    gps_route: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

"""Pydantic request and response schemas for every API endpoint."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanningRequest(BaseModel):
    """Request to generate a navigation plan.

    initial_state and goal_state accept:
      {'building': int, 'floor': int, 'room': 'classroom_g_1_4'}

    The shared `domain.pddl` handles both intra- and cross-building
    routes. When origin and goal are in different buildings the converter
    emits rooms of both plus `outdoor_connected` edges between entrances.
    """

    initial_state: dict[str, Any] = Field(
        ...,
        description="Starting location. Required: building, floor, room.",
    )
    goal_state: dict[str, Any] | None = Field(
        None,
        description="Target location. Required: building, floor, room (unless goal_functional).",
    )
    goal_functional: str | None = Field(
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
    plan: list[str] = Field(default_factory=list)
    steps: int = 0
    cost: int = 0
    initial_state: dict[str, Any] | None = None
    goal_state: Any | None = None
    error: str | None = None
    output: str | None = None


class ValidationRequest(BaseModel):
    """Request to validate a plan."""

    plan: list[str]
    initial_state: dict[str, Any]
    goal_state: dict[str, Any]


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
    state prompts (`elevator_state`, `stair_direction`)
    the model returns ``state_type`` and ``state_detail``.
    """

    success: bool
    prompt_id: str
    location_id: str | None = None
    state_type: str | None = None
    state_detail: str | None = None
    raw_response: str = ""
    error: str | None = None


class GPSRouteRequest(BaseModel):
    """Request for walking directions between two campus buildings."""

    from_building: int
    to_building: int


class GPSRouteResponse(BaseModel):
    """Response with the Google Maps walking route."""

    success: bool
    distance: str | None = None
    duration: str | None = None
    steps: list[dict[str, Any]] | None = None
    polyline: str | None = None
    error: str | None = None


class ConversationRequest(BaseModel):
    """Request for one conversation turn."""

    session_id: str
    user_message: str
    image_analysis: dict[str, Any] | None = None


class ConversationResponse(BaseModel):
    """Response from one conversation turn."""

    response: str
    action: str
    needs_input: bool
    context: dict[str, Any]
    tts_message: str | None = None
    next_input: str | None = None
    # Tells the client which VLM prompt to run on the next photo. One of
    # the prompt ids defined in config/prompts.json
    # (room_plate, directory_sign, elevator_state, stair_direction).
    # Null when no photo is expected.
    expect_photo: str | None = None
    plan_request: dict[str, Any] | None = None
    location_partial: dict[str, Any] | None = None
    auto_fill: dict[str, Any] | None = None
    auto_fill_goal: dict[str, Any] | None = None
    gps_route: dict[str, Any] | None = None
    error: str | None = None

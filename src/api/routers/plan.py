"""Planning endpoints — generate, validate and inspect PDDL plans.

A single /api/plan path uses the shared `domain_indoor.pddl`. The converter
encodes one or two buildings in the same problem depending on whether the
goal is in the same building as the origin, so both intra- and cross-building
routes are resolved by the same Fast Downward call.
"""

import os
import tempfile

from fastapi import APIRouter, HTTPException

from api.schemas import (
    PlanningRequest, PlanningResponse,
    ValidationRequest, ValidationResponse,
    DomainResponse,
)
from api.dependencies import (
    planner,
    hierarchical_converter,
    DOMAIN_PATH,
    PDDL_DIR,
)

router = APIRouter()


def _run_plan(request: PlanningRequest) -> PlanningResponse:
    initial = request.initial_state or {}
    goal = request.goal_state or {}

    if initial.get("building") is None or initial.get("floor") is None:
        raise HTTPException(
            status_code=400,
            detail="initial_state must contain 'building' and 'floor'",
        )
    if not goal and not request.goal_functional:
        raise HTTPException(
            status_code=400,
            detail="Provide 'goal_state' or 'goal_functional'",
        )

    origin_building = int(initial["building"])
    origin_floor = int(initial["floor"])
    origin_room = initial.get("room")

    dest_building = (
        int(goal["building"]) if goal.get("building") is not None else None
    )
    dest_floor = int(goal["floor"]) if goal.get("floor") is not None else None
    dest_room = goal.get("room")

    if not origin_room:
        raise HTTPException(
            status_code=400,
            detail="initial_state must contain 'room' for indoor planning",
        )
    if not (dest_room or request.goal_functional):
        raise HTTPException(
            status_code=400,
            detail="Provide 'goal_state.room' or 'goal_functional'",
        )

    domain_path = hierarchical_converter.get_domain_path()
    if not domain_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"PDDL domain not found: {domain_path.name}",
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".pddl", dir=str(PDDL_DIR), delete=False
    ) as f:
        problem_path = f.name
        try:
            hierarchical_converter.generate_building_problem(
                origin_building=origin_building,
                origin_room=origin_room,
                origin_floor=origin_floor,
                dest_building=dest_building,
                dest_room=dest_room,
                dest_floor=dest_floor,
                goal_functional=request.goal_functional,
                hurry_mode=request.hurry_mode,
                output_path=problem_path,
            )
        except ValueError as e:
            if os.path.exists(problem_path):
                os.remove(problem_path)
            raise HTTPException(status_code=400, detail=str(e))

    try:
        result = planner.plan(
            domain_path=str(domain_path), problem_path=problem_path,
        )
        result["initial_state"] = initial
        result["goal_state"] = {
            "building": dest_building,
            "floor": dest_floor,
            "room": dest_room,
            "functional": request.goal_functional,
            "mode": "room-level",
            "domain": domain_path.name,
        }
        return PlanningResponse(**result)
    finally:
        if os.path.exists(problem_path):
            os.remove(problem_path)


@router.post("/plan", response_model=PlanningResponse)
async def generate_plan(request: PlanningRequest):
    """Generate a navigation plan from an initial state to a goal."""
    try:
        return _run_plan(request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating plan: {e}")


@router.get("/domain", response_model=DomainResponse)
async def get_domain():
    """Return the current PDDL domain file contents."""
    if not DOMAIN_PATH.exists():
        raise HTTPException(status_code=404, detail="Domain file not found")
    try:
        return DomainResponse(domain=DOMAIN_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading domain: {e}")


@router.post("/validate", response_model=ValidationResponse)
async def validate_plan(request: ValidationRequest):
    """Re-solve the problem and check whether the provided plan is non-empty."""
    try:
        initial = request.initial_state or {}
        goal = request.goal_state or {}
        pr = PlanningRequest(
            initial_state=initial,
            goal_state=goal,
            hurry_mode=False,
        )
        result = _run_plan(pr)
        if not result.success:
            return ValidationResponse(
                valid=False,
                message=f"Could not generate plan: {result.error or 'unknown'}",
            )
        if not request.plan:
            return ValidationResponse(valid=False, message="Provided plan is empty")
        return ValidationResponse(
            valid=True,
            message=f"Plan validated. Generated plan has {len(result.plan)} steps.",
        )
    except HTTPException as e:
        return ValidationResponse(valid=False, message=str(e.detail))
    except Exception as e:
        return ValidationResponse(valid=False, message=f"Error validating plan: {e}")

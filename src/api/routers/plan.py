"""Planning endpoints: generate, validate and inspect PDDL plans.

Two planning paths are exposed by the same /api/plan endpoint:

  1. Floor-level (global domain_outdoor.pddl):
     {"initial_state": {"building": 1, "floor": 0},
      "goal_state":    {"building": 1, "floor": 1}}

  2. Room-level hierarchical (domain_indoor.pddl, all buildings):
     {"initial_state": {"building": 1, "floor": 0, "room": "entrada_principal"},
      "goal_state":    {"building": 1, "floor": 1, "room": "aula_1_4"}}

The endpoint auto-selects path (2) when both origin and goal carry a
`room` field and belong to the same building. Otherwise it falls back to
path (1).
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
    converter,
    hierarchical_converter,
    DOMAIN_PATH,
    PDDL_DIR,
    load_topology,
)

router = APIRouter()


def _resolve_functional_goal(goal: str, campus_graph: dict):
    """Resolves a functional destination (cafeteria, gym) to (building_id, floor)."""
    goal_lower = goal.lower()
    for b in campus_graph.get("buildings", []):
        if goal_lower == "cafeteria":
            f = b.get("cafeteria_floor")
            if f is not None:
                return b["id"], f
        elif goal_lower in ("gimnasio", "gym"):
            f = b.get("gimnasio_floor")
            if f is not None:
                return b["id"], f
    return None, None


def _run_hierarchical_plan(request: PlanningRequest) -> PlanningResponse:
    """Room-level plan via the building-specific PDDL domain."""
    initial = request.initial_state
    goal = request.goal_state or {}

    building_id = int(initial["building"])
    origin_room = initial.get("room")
    origin_floor = int(initial["floor"])
    dest_room = goal.get("room")
    dest_floor = int(goal["floor"]) if goal.get("floor") is not None else None

    try:
        domain_path = hierarchical_converter.get_domain_path(building_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not domain_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Building-specific PDDL domain not found: {domain_path.name}",
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".pddl", dir=str(PDDL_DIR), delete=False
    ) as f:
        problem_path = f.name
        try:
            hierarchical_converter.generate_building_problem(
                building_id=building_id,
                origin_room=origin_room,
                origin_floor=origin_floor,
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
        result = planner.plan(domain_path=str(domain_path), problem_path=problem_path)
        result["initial_state"] = initial
        result["goal_state"] = {
            "building": building_id,
            "floor": dest_floor,
            "room": dest_room,
            "mode": "room-level",
            "domain": domain_path.name,
        }
        return PlanningResponse(**result)
    finally:
        if os.path.exists(problem_path):
            os.remove(problem_path)


@router.post("/plan", response_model=PlanningResponse)
async def generate_plan(request: PlanningRequest):
    """Generate a navigation plan from an initial state to a goal.

    Auto-routes to hierarchical (room-level) planning when both origin and
    goal carry a `room` field and share the same building. Otherwise falls
    back to the floor-level global domain.
    """
    try:
        initial = request.initial_state or {}
        initial_building = initial.get("building")
        initial_floor = initial.get("floor")
        if initial_building is None or initial_floor is None:
            raise HTTPException(
                status_code=400,
                detail="initial_state must contain 'building' and 'floor'",
            )

        if not request.goal_state and not request.goal_functional:
            raise HTTPException(
                status_code=400,
                detail="Provide 'goal_state' or 'goal_functional'",
            )

        goal = request.goal_state or {}

        # Pick hierarchical path when origin/goal both have a room and sit in
        # the same building (that is where the per-building PDDL domain shines).
        same_building = (
            not request.goal_functional
            and goal.get("building") is not None
            and int(goal["building"]) == int(initial_building)
        )
        origin_has_room = bool(initial.get("room"))
        goal_has_room = bool(goal.get("room"))
        if same_building and origin_has_room and goal_has_room:
            return _run_hierarchical_plan(request)

        # Legacy floor-level global planner
        goal_info: dict = {}
        goal_building_id = None
        goal_floor = None

        if request.goal_functional:
            campus_graph = load_topology()
            goal_building_id, goal_floor = _resolve_functional_goal(
                request.goal_functional, campus_graph
            )
            if goal_building_id is None or goal_floor is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Functional goal '{request.goal_functional}' not found on campus",
                )

            bname = None
            for b in campus_graph.get("buildings", []):
                if b.get("id") == goal_building_id:
                    bname = b.get("name", f"Building {goal_building_id}")
                    break
            floor_text = "floor 0" if goal_floor == 0 else f"floor {goal_floor}"
            label = request.goal_functional.capitalize()
            goal_info = {
                "functional": request.goal_functional,
                "description": f"{label} ({bname} {floor_text})",
                "mode": "floor-level",
                "domain": DOMAIN_PATH.name,
            }
        else:
            goal_building_id = goal.get("building")
            goal_floor = goal.get("floor")
            if goal_building_id is None or goal_floor is None:
                raise HTTPException(
                    status_code=400,
                    detail="goal_state must contain 'building' and 'floor'",
                )
            goal_info = {
                "building": goal_building_id,
                "floor": goal_floor,
                "mode": "floor-level",
                "domain": DOMAIN_PATH.name,
            }

        initial_state = (int(initial_building), int(initial_floor))
        goal_state = (
            None if request.goal_functional
            else (int(goal_building_id), int(goal_floor))
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pddl", dir=str(PDDL_DIR), delete=False) as f:
            problem_path = f.name
            converter.generate_problem(
                initial_state=initial_state,
                goal_state=goal_state,
                goal_functional=request.goal_functional,
                problem_name="api-problem",
                output_path=problem_path,
                hurry_mode=request.hurry_mode,
            )
        try:
            result = planner.plan(domain_path=str(DOMAIN_PATH), problem_path=problem_path)
            result["initial_state"] = request.initial_state
            result["goal_state"] = goal_info
            return PlanningResponse(**result)
        finally:
            if os.path.exists(problem_path):
                os.remove(problem_path)

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
    """Re-solve the problem and check whether the provided plan is reasonable."""
    try:
        initial_state = (
            int(request.initial_state["building"]),
            int(request.initial_state["floor"]),
        )
        goal_state = (
            int(request.goal_state["building"]),
            int(request.goal_state["floor"]),
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pddl", dir=str(PDDL_DIR), delete=False) as f:
            problem_path = f.name
            converter.generate_problem(
                initial_state=initial_state, goal_state=goal_state,
                problem_name="validation-problem", output_path=problem_path,
            )
        try:
            result = planner.plan(domain_path=str(DOMAIN_PATH), problem_path=problem_path)
            if not result["success"]:
                return ValidationResponse(valid=False, message=f"Could not generate plan: {result.get('error', 'Unknown')}")
            if not request.plan:
                return ValidationResponse(valid=False, message="Provided plan is empty")
            return ValidationResponse(valid=True, message=f"Plan validated. Generated plan has {len(result['plan'])} steps.")
        finally:
            if os.path.exists(problem_path):
                os.remove(problem_path)

    except Exception as e:
        return ValidationResponse(valid=False, message=f"Error validating plan: {e}")

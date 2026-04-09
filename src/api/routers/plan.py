"""Planning endpoints: generate, validate and inspect PDDL plans."""

import os
import tempfile

from fastapi import APIRouter, HTTPException

from api.models import (
    PlanningRequest, PlanningResponse,
    ValidationRequest, ValidationResponse,
    DomainResponse,
)
from api.dependencies import planner, converter, DOMAIN_PATH, PDDL_DIR, load_campus_graph
from navigation.agents import Agent2_Searcher, Agent3_Planner

router = APIRouter()


@router.post("/plan", response_model=PlanningResponse)
async def generate_plan(request: PlanningRequest):
    """Generate a navigation plan from an initial state to a goal."""
    try:
        initial_building = request.initial_state.get("building")
        initial_floor = request.initial_state.get("floor")
        if initial_building is None or initial_floor is None:
            raise HTTPException(status_code=400, detail="initial_state must contain 'building' and 'floor'")

        if not request.goal_state and not request.goal_functional:
            raise HTTPException(status_code=400, detail="Provide 'goal_state' or 'goal_functional'")

        # Resolve the goal — either a functional name or explicit building+floor
        goal_info: dict = {}
        goal_building_id = None
        goal_floor = None

        if request.goal_functional:
            campus_graph = load_campus_graph()
            goal_building_id, goal_floor, source = Agent2_Searcher.search_goal(
                request.goal_functional, agent1_detection=None, campus_graph=campus_graph,
            )
            if goal_building_id is None or goal_floor is None:
                raise HTTPException(status_code=404, detail=f"Functional goal '{request.goal_functional}' not found on campus")

            # Human-readable description
            bname = None
            for b in campus_graph.get("buildings", []):
                if b.get("id") == goal_building_id:
                    bname = b.get("name", f"Building {goal_building_id}")
                    break
            floor_text = "floor 0" if goal_floor == 0 else f"floor {goal_floor}"
            label = request.goal_functional.capitalize()
            goal_info = {"functional": request.goal_functional, "description": f"{label} ({bname} {floor_text})"}
        else:
            goal_building_id = request.goal_state.get("building")
            goal_floor = request.goal_state.get("floor")
            if goal_building_id is None or goal_floor is None:
                raise HTTPException(status_code=400, detail="goal_state must contain 'building' and 'floor'")
            goal_info = {"building": goal_building_id, "floor": goal_floor}

        # Write a temporary PDDL problem file and solve it
        initial_state = (initial_building, initial_floor)
        goal_state = None if request.goal_functional else (goal_building_id, goal_floor)

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
        initial_state = (request.initial_state["building"], request.initial_state["floor"])
        goal_state = (request.goal_state["building"], request.goal_state["floor"])

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

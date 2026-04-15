"""Wrappers around the Fast Downward client.

These helpers handle the boring bits — generating a tempfile, calling the
planner, parsing the result, deleting the tempfile — so the agent's
routing logic only has to worry about *what* to plan, not *how*.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def run_fast_downward(
    planner: Any,
    converter: Any,
    domain_path: Path,
    pddl_dir: Path,
    origin_building: int,
    origin_floor: int,
    dest_building: int,
    dest_floor: int,
    goal_functional: Optional[str] = None,
    hurry_mode: bool = False,
) -> Optional[List[str]]:
    """Generate a floor-level PDDL problem and solve it with Fast Downward.

    Returns a list of action strings or ``None`` on any failure (planner
    not initialised, no plan found, exception during execution).
    """
    if not planner or not converter:
        logger.warning("FD planner not available")
        return None

    initial_state = (origin_building, origin_floor)
    goal_state: Optional[Tuple[int, int]] = None if goal_functional else (dest_building, dest_floor)

    problem_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pddl", dir=str(pddl_dir), delete=False
        ) as f:
            problem_path = f.name
            converter.generate_problem(
                initial_state=initial_state,
                goal_state=goal_state,
                goal_functional=goal_functional,
                problem_name="conv-problem",
                output_path=problem_path,
                hurry_mode=hurry_mode,
            )

        result = planner.plan(
            domain_path=str(domain_path),
            problem_path=problem_path,
        )

        if result.get("success"):
            actions = result.get("plan", [])
            logger.info(
                "FD plan found: %d actions, cost=%s",
                len(actions), result.get("cost"),
            )
            return actions
        logger.warning("FD no plan found: %s", result.get("error"))
        return None
    except Exception as e:
        logger.exception("FD error: %s", e)
        return None
    finally:
        if problem_path:
            try:
                Path(problem_path).unlink(missing_ok=True)
            except Exception:
                pass


def run_hierarchical_building_planner(
    planner: Any,
    hierarchical_converter: Any,
    pddl_dir: Path,
    building_id: int,
    origin_room: str,
    origin_floor: int,
    dest_room: Optional[str],
    dest_floor: Optional[int],
    goal_functional: Optional[str] = None,
    hurry_mode: bool = False,
) -> Optional[List[str]]:
    """Generate a room-level PDDL problem for a single building and solve it.

    Loads ``domain_indoor.pddl`` via the hierarchical converter and writes
    a temp problem whose ``:init`` section encodes the full intra-building
    graph. Returns the list of PDDL action strings or ``None`` on failure.
    """
    if not planner or not hierarchical_converter:
        logger.warning("FD hierarchical planner/converter not available")
        return None

    try:
        domain_path = hierarchical_converter.get_domain_path(building_id)
    except ValueError as e:
        logger.warning("FD hierarchical: %s", e)
        return None

    if not domain_path.exists():
        logger.error("FD hierarchical domain file not found: %s", domain_path)
        return None

    problem_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pddl", dir=str(pddl_dir), delete=False
        ) as f:
            problem_path = f.name
            hierarchical_converter.generate_building_problem(
                building_id=building_id,
                origin_room=origin_room,
                origin_floor=origin_floor,
                dest_room=dest_room,
                dest_floor=dest_floor,
                goal_functional=goal_functional,
                hurry_mode=hurry_mode,
                output_path=problem_path,
            )

        result = planner.plan(
            domain_path=str(domain_path),
            problem_path=problem_path,
        )

        if result.get("success"):
            actions = result.get("plan", [])
            logger.info(
                "FD hierarchical plan for building %d: %d actions, cost=%s",
                building_id, len(actions), result.get("cost"),
            )
            return actions
        logger.warning(
            "FD hierarchical no plan found: %s", result.get("error")
        )
        return None
    except Exception as e:
        logger.exception("FD hierarchical error: %s", e)
        return None
    finally:
        if problem_path:
            try:
                Path(problem_path).unlink(missing_ok=True)
            except Exception:
                pass

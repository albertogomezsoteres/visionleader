"""Wrappers around the Fast Downward client.

These helpers handle the boring bits — generating a tempfile, calling the
planner, parsing the result, deleting the tempfile — so the agent's
routing logic only has to worry about *what* to plan, not *how*.

Each call also prints a short banner with the input and the resulting
plan, which doubles as live telemetry during a demo: the operator (and
the tribunal) can see in the terminal exactly what the symbolic planner
received and produced for every user interaction.
"""

import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

from .text_formatting import BUILDING_NAMES, floor_text

logger = logging.getLogger(__name__)


# -- Pretty-printing helpers ------------------------------------------------

_BANNER = "=" * 60


def _print_call_banner(
    label: str,
    *,
    building: Optional[int],
    origin: str,
    origin_floor: Optional[int],
    destination: Optional[str],
    dest_floor: Optional[int],
    goal_functional: Optional[str],
    hurry_mode: bool,
) -> None:
    print(_BANNER)
    print(f"[FAST DOWNWARD] {label}")
    if building is not None:
        bname = BUILDING_NAMES.get(building, str(building))
        print(f"  building:    {building} ({bname})")
    if origin_floor is not None:
        print(f"  origin:      {origin} ({floor_text(origin_floor)})")
    else:
        print(f"  origin:      {origin}")
    if goal_functional:
        print(f"  destination: <functional:{goal_functional}>")
    elif destination is not None and dest_floor is not None:
        print(f"  destination: {destination} ({floor_text(dest_floor)})")
    elif destination is not None:
        print(f"  destination: {destination}")
    print(f"  hurry mode:  {'true' if hurry_mode else 'false'}")


def _print_plan(actions: List[str], elapsed_s: float, cost: Any) -> None:
    print(
        f"[FAST DOWNWARD] plan found in {elapsed_s:.2f}s, "
        f"cost={cost}, {len(actions)} actions:"
    )
    for i, raw in enumerate(actions, start=1):
        # Strip the trailing "(NN)" cost annotation Fast Downward appends
        # so we can pull it out and present it in our own column.
        m = re.search(r"\((\d+)\)\s*$", raw)
        action_cost = m.group(1) if m else None
        clean = re.sub(r"\s*\(\d+\)\s*$", "", raw).strip()
        if action_cost is not None:
            print(f"  {i}. {clean:<55}  (cost {action_cost})")
        else:
            print(f"  {i}. {clean}")
    _print_plan_summary(actions, cost)
    print(_BANNER)


def _print_plan_summary(actions: List[str], cost: Any) -> None:
    """One-line summary so the watcher sees the headline metric instantly."""
    uses_elevator = any("ascensor" in a for a in actions)
    uses_stairs = any("escaleras" in a for a in actions)
    uses_outdoor = any("mover_edificio" in a for a in actions)
    pieces = []
    if uses_elevator:
        pieces.append("uses elevator")
    if uses_stairs:
        pieces.append("uses stairs")
    if uses_outdoor:
        pieces.append("uses outdoor walk")
    suffix = ", ".join(pieces) if pieces else "walk only"
    print(f"[PLAN SUMMARY] {len(actions)} actions, total cost {cost}, {suffix}")


def _print_no_plan(elapsed_s: float, error: Any) -> None:
    print(f"[FAST DOWNWARD] no plan found in {elapsed_s:.2f}s: {error}")
    print(_BANNER)


# -- Public planner wrappers ------------------------------------------------


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

    _print_call_banner(
        "outdoor (floor-level) planner call",
        building=None,
        origin=f"edificio_{origin_building}",
        origin_floor=origin_floor,
        destination=f"edificio_{dest_building}" if not goal_functional else None,
        dest_floor=dest_floor if not goal_functional else None,
        goal_functional=goal_functional,
        hurry_mode=hurry_mode,
    )

    problem_path: Optional[str] = None
    started = time.time()
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
        elapsed = time.time() - started

        if result.get("success"):
            actions = result.get("plan", [])
            _print_plan(actions, elapsed, result.get("cost"))
            logger.info(
                "FD plan found: %d actions, cost=%s",
                len(actions), result.get("cost"),
            )
            return actions
        _print_no_plan(elapsed, result.get("error"))
        logger.warning("FD no plan found: %s", result.get("error"))
        return None
    except Exception as e:
        elapsed = time.time() - started
        _print_no_plan(elapsed, f"exception: {e}")
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

    _print_call_banner(
        "indoor (room-level) hierarchical planner call",
        building=building_id,
        origin=origin_room,
        origin_floor=origin_floor,
        destination=dest_room,
        dest_floor=dest_floor,
        goal_functional=goal_functional,
        hurry_mode=hurry_mode,
    )

    problem_path: Optional[str] = None
    started = time.time()
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
        elapsed = time.time() - started

        if result.get("success"):
            actions = result.get("plan", [])
            _print_plan(actions, elapsed, result.get("cost"))
            logger.info(
                "FD hierarchical plan for building %d: %d actions, cost=%s",
                building_id, len(actions), result.get("cost"),
            )
            return actions
        _print_no_plan(elapsed, result.get("error"))
        logger.warning(
            "FD hierarchical no plan found: %s", result.get("error")
        )
        return None
    except Exception as e:
        elapsed = time.time() - started
        _print_no_plan(elapsed, f"exception: {e}")
        logger.exception("FD hierarchical error: %s", e)
        return None
    finally:
        if problem_path:
            try:
                Path(problem_path).unlink(missing_ok=True)
            except Exception:
                pass

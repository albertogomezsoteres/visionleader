"""Wrappers around the Fast Downward client.

These helpers handle the boring bits — generating a tempfile, calling the
planner, parsing the result, deleting the tempfile — so the agent's
routing logic only has to worry about *what* to plan, not *how*. Live
telemetry for the demo is emitted from :mod:`navigation.agent.routing`
via the unified ``log_event`` helper, plus a ``[PLANNER] domain= …
problem: …`` snapshot from this module so the operator can see what
enters Fast Downward on every turn.
"""

import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from api.telemetry import log_event

logger = logging.getLogger(__name__)


def _problem_stats(text: str) -> Dict[str, Any]:
    """Cheap structural stats from a generated PDDL problem file.

    Used for the demo log line so the operator can tell at a glance how
    many objects and facts end up in the problem Fast Downward sees,
    plus whether the dynamic availability layer ((open …) facts) and
    the user preference flag ((hurry_mode)) are present.
    """
    obj_section = re.search(r"\(:objects(.*?)\)", text, re.DOTALL)
    n_objects = 0
    if obj_section:
        cleaned = re.sub(r"\s*-\s*\w+", "", obj_section.group(1))
        n_objects = len(cleaned.split())

    init_section = re.search(r"\(:init(.*?)\(:goal", text, re.DOTALL)
    n_init_facts = init_section.group(1).count("(") if init_section else 0

    n_open = len(re.findall(r"\(open\s+\w+\)", text))
    has_hurry = bool(re.search(r"\(hurry_mode\)", text))

    goal_match = re.search(r"\(:goal\s*(\([^)]+\))", text)
    goal_expr = goal_match.group(1).strip() if goal_match else "?"

    return {
        "n_objects": n_objects,
        "n_init_facts": n_init_facts,
        "n_open": n_open,
        "hurry_mode": has_hurry,
        "goal_expr": goal_expr,
    }


def run_indoor_planner(
    planner: Any,
    hierarchical_converter: Any,
    pddl_dir: Path,
    origin_building: int,
    origin_room: str,
    origin_floor: int,
    dest_building: Optional[int] = None,
    dest_room: Optional[str] = None,
    dest_floor: Optional[int] = None,
    goal_functional: Optional[str] = None,
    hurry_mode: bool = False,
) -> Optional[dict]:
    """Generate a room-level PDDL problem and solve it with Fast Downward.

    Returns ``{"actions": List[str], "cost": int, "search_time_s": float}``
    on success, ``None`` on failure. Callers that only need the action
    list can read ``result["actions"]``.

    When ``dest_building`` differs from ``origin_building``, both buildings
    are encoded in the same problem and linked by ``outdoor_connected``
    edges between their entrances, so a single planner run finds the full
    door-to-door route including any outdoor hop between buildings.
    """
    if not planner or not hierarchical_converter:
        logger.warning("FD planner/converter not available")
        return None

    if dest_building is None:
        dest_building = origin_building

    domain_path = hierarchical_converter.get_domain_path()
    if not domain_path.exists():
        logger.error("PDDL domain file not found: %s", domain_path)
        return None

    problem_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pddl", dir=str(pddl_dir), delete=False
        ) as f:
            problem_path = f.name
            hierarchical_converter.generate_building_problem(
                origin_building=origin_building,
                origin_room=origin_room,
                origin_floor=origin_floor,
                dest_building=dest_building,
                dest_room=dest_room,
                dest_floor=dest_floor,
                goal_functional=goal_functional,
                hurry_mode=hurry_mode,
                output_path=problem_path,
            )

        # Dump problem stats for the demo log: domain file is fixed,
        # problem is generated fresh each turn from the live topology
        # plus the closure layer.
        try:
            problem_text = Path(problem_path).read_text(encoding="utf-8")
            stats = _problem_stats(problem_text)
            log_event(
                "PLANNER",
                f"domain={domain_path.name}  ·  problem=dynamic ({Path(problem_path).name})",
                domain_path=str(domain_path),
                problem_path=str(problem_path),
            )
            log_event(
                "PLANNER",
                f"problem: {stats['n_objects']} objects  ·  "
                f"{stats['n_init_facts']} init facts  ·  "
                f"{stats['n_open']} open rooms  ·  "
                f"hurry_mode={'on' if stats['hurry_mode'] else 'off'}",
                **{k: v for k, v in stats.items() if k != "goal_expr"},
            )
        except Exception:
            pass

        result = planner.plan(
            domain_path=str(domain_path),
            problem_path=problem_path,
        )

        if result.get("success"):
            return {
                "actions": result.get("plan", []),
                "cost": result.get("cost", 0),
                "search_time_s": result.get("search_time_s"),
            }
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

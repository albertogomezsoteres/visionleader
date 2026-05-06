"""Bridge between the conversation agent and the Fast Downward planner.

Encapsulates the closure preflight, the planner call and the conversion
of the resulting PDDL plan into TTS-ready navigation steps. Functions
here are stateless wrappers: they accept the agent (for shared lookups
and the converter handle) and return the new ``route_steps`` list, never
mutating agent state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from .closures import find_open_alternative, is_room_closed
from .plan_to_steps import apply_arrival_strict_photo, fd_plan_to_steps_room_level
from .planner_bridge import run_indoor_planner
from .text_formatting import BUILDING_FULL, BUILDING_NAMES, floor_text, nice_location_name

if TYPE_CHECKING:
    from ..conversation_agent import ConversationAgent
    from .context import ConversationContext


def compute_route(
    agent: "ConversationAgent", origin: Dict, destination: Dict
) -> Optional[List[Dict]]:
    """Build navigation steps for an (origin, destination) pair.

    A single Fast Downward call on ``domain_indoor.pddl`` resolves both
    intra- and inter-building routes. For cross-building pairs the
    converter emits rooms of both buildings plus ``conectado_exterior``
    edges between their entrances, so the resulting plan interleaves
    ``caminar`` / ``usar_ascensor`` / ``mover_exterior`` actions as
    needed.

    Returns ``None`` when the origin or destination is incomplete, when
    the destination is closed and no alternative exists, or when Fast
    Downward fails to find a plan.
    """
    o_bld = origin.get("building")
    o_flr = origin.get("floor")
    o_loc = origin.get("location_id")

    d_bld = destination.get("building")
    d_flr = destination.get("floor")
    d_loc = destination.get("location_id")

    if o_bld is None or o_flr is None or d_bld is None or d_flr is None:
        return None

    matching_ctx = _find_matching_ctx(agent, origin, destination)
    if matching_ctx:
        matching_ctx.pending_announcement = None
        matching_ctx.closure_blocked = False

    if d_loc:
        d_loc, d_flr = _apply_closure_preflight(
            agent, destination, d_bld, d_flr, d_loc, matching_ctx
        )
        if d_loc is None:
            return None

    goal_functional = destination.get("functional")
    ctx_hurry = matching_ctx.hurry_mode if matching_ctx else False

    if agent._hierarchical_converter is None or not o_loc:
        return None

    if not (d_loc or goal_functional):
        return None

    fd_actions = run_indoor_planner(
        planner=agent._planner,
        hierarchical_converter=agent._hierarchical_converter,
        pddl_dir=agent._pddl_dir,
        origin_building=o_bld,
        origin_room=o_loc, origin_floor=o_flr,
        dest_building=d_bld,
        dest_room=d_loc, dest_floor=d_flr,
        goal_functional=goal_functional,
        hurry_mode=ctx_hurry,
    )
    if not fd_actions:
        bname = BUILDING_NAMES.get(o_bld, str(o_bld))
        print(
            f"[Route] Planner did not return a plan for {bname} -> "
            f"{BUILDING_NAMES.get(d_bld, d_bld)} "
            "(check Docker, domain, and problem generation)."
        )
        return None

    steps = fd_plan_to_steps_room_level(
        fd_actions, origin, destination,
        places_locations=agent._locations,
        local_distance=agent._local_distance,
        local_hint=agent._local_hint,
    )
    if not steps:
        if o_bld == d_bld and o_flr == d_flr:
            steps = compute_same_floor(o_bld, o_flr)
        else:
            print(
                "[Route] Planner returned actions but they could not be "
                "converted to navigation steps."
            )
            return None

    print(f"[Route] Built {len(steps)} navigation steps from PDDL plan")
    return apply_arrival_strict_photo(steps, destination, agent._locations)


_GENERIC_FAILURE = "I couldn't compute a route. Please try a different destination."


def planner_failure_message(ctx: "ConversationContext") -> str:
    """User-facing error when :func:`compute_route` returns ``None``.

    Prefers a pending closure announcement (informative: ``"X is closed,
    no alternative"``) over the generic planner-failed line.
    """
    if ctx and ctx.pending_announcement:
        msg = ctx.pending_announcement
        ctx.pending_announcement = None
        ctx.closure_blocked = False
        return msg
    return _GENERIC_FAILURE


def compute_same_floor(bld: int, flr: int) -> List[Dict]:
    """Trivial fallback when origin and destination are on the same floor."""
    return [{
        "instruction": (
            f"Walk along {floor_text(flr)} in "
            f"{BUILDING_FULL.get(bld, 'the building')} "
            f"to reach your destination."
        ),
        "type": "local_walk",
        "verification": "voice",
        "expected_photo_type": None,
    }]


def _apply_closure_preflight(
    agent: "ConversationAgent",
    destination: Dict,
    d_bld: int,
    d_flr: int,
    d_loc: str,
    matching_ctx: Optional["ConversationContext"],
):
    """Substitute a closed destination with an open alternative when possible.

    Mutates ``destination`` in place when an alternative is picked, and
    parks the announcement on the owning context so the next reply can
    prepend it. Returns the (possibly updated) ``(d_loc, d_flr)`` pair,
    or ``(None, None)`` when no alternative exists.
    """
    closure = is_room_closed(agent._hierarchical_converter, d_bld, d_flr, d_loc)
    if not closure:
        return d_loc, d_flr

    alt = find_open_alternative(
        agent._hierarchical_converter,
        agent._locations,
        d_bld, d_flr, d_loc,
    )
    orig_name = nice_location_name(d_loc)
    reason = closure.get("reason") or "currently unavailable"

    if alt:
        destination["location_id"] = alt["location_id"]
        destination["floor"] = alt["floor"]
        destination.pop("functional", None)
        alt_name = nice_location_name(alt["location_id"])
        announcement = (
            f"{orig_name} is {reason}. "
            f"I'll guide you to {alt_name} instead."
        )
        if matching_ctx:
            matching_ctx.pending_announcement = announcement
        print(f"[Closure] {orig_name} closed ({reason}); redirecting to {alt_name}")
        return destination["location_id"], destination["floor"]

    announcement = f"{orig_name} is {reason}. Try a different destination."
    if matching_ctx:
        matching_ctx.pending_announcement = announcement
        matching_ctx.closure_blocked = True
    print(f"[Closure] {orig_name} closed ({reason}); no alternative found")
    return None, None


def _find_matching_ctx(
    agent: "ConversationAgent", origin: Dict, destination: Dict
) -> Optional["ConversationContext"]:
    """Locate the ConversationContext that owns this (origin, dest) pair."""
    for ctx in agent.contexts.values():
        if ctx.origin == origin and ctx.destination == destination:
            return ctx
    return None

"""
End-to-end test for the dynamic-closure feature.

Runs five demo-relevant scenarios through the full stack
(ConversationAgent -> HierarchicalPDDLConverter -> Fast Downward) and
prints the plan + the TTS the user would actually hear.

Scenario matrix:
  1. Baseline: nothing closed, Entrada -> aula_1_4 (elevator).
  2. Elevator floor 0 is CLOSED -> planner reroutes via stairs.
  3. Destination aula_1_4 is CLOSED -> agent substitutes aula_1_1.
  4. Floor 2 is fully closed (secretaria, sala_mentorias, despachos_eps,
     aula_2_1) -> no alternative -> agent explains impossibility.
  5. Baseline restored: the same first request yields the original plan,
     proving the system recovers.

The script toggles config/closed_rooms.json between scenarios and always
restores an empty closure list at the end.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from navigation.conversation_agent import ConversationAgent, ConversationState  # noqa: E402


CAMPUS_JSON = ROOT / "config" / "campus_graph.json"
CLOSED_JSON = ROOT / "config" / "closed_rooms.json"


def set_closed(entries):
    CLOSED_JSON.write_text(
        json.dumps({"closed": entries}, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def reset_closed():
    set_closed([])


def plan_and_print(agent, label, origin, destination):
    # Create a fresh context so contextual state does not leak
    session = f"test-{label}"
    ctx = agent.get_or_create_context(session)
    ctx.origin = dict(origin)
    ctx.destination = dict(destination)
    ctx.pending_announcement = None
    ctx.closure_blocked = False

    route = agent._compute_route(ctx.origin, ctx.destination)

    print(f"\n================ {label} ================")
    print(f"Request: {origin['location_id']} (floor {origin['floor']}) "
          f"-> {destination['location_id']} (floor {destination['floor']})")

    if route is None:
        print("Result: NO ROUTE")
        msg = agent._planner_failure_message(ctx)
        print(f"TTS: {msg}")
        return

    ann = ctx.pending_announcement
    print(f"Result: {len(route)} navigation steps  (destination now: "
          f"{ctx.destination['location_id']} floor {ctx.destination['floor']})")
    if ann:
        print(f"[Announcement] {ann}")
    print("TTS sequence:")
    for i, s in enumerate(route, 1):
        print(f"  {i}. {s['instruction']}")


def main():
    # Always start from a clean slate
    reset_closed()

    with CAMPUS_JSON.open("r", encoding="utf-8") as f:
        graph = json.load(f)
    agent = ConversationAgent(graph)

    entrada = {"building": 1, "floor": 0, "location_id": "entrada_principal"}
    aula_1_4 = {"building": 1, "floor": 1, "location_id": "aula_1_4"}
    secretaria = {"building": 1, "floor": 2, "location_id": "secretaria"}

    # ---------- 1. Baseline ----------
    plan_and_print(
        agent,
        "1. BASELINE — Entrada -> aula 1.4 (no closures, accessible)",
        entrada, aula_1_4,
    )

    # ---------- 2. Elevator ground-floor closed ----------
    set_closed([
        {"building": "G", "location_id": "ascensor", "floor": 0,
         "reason": "out of service for maintenance"},
    ])
    plan_and_print(
        agent,
        "2. ELEVATOR CLOSED — Entrada -> aula 1.4 (must take stairs)",
        entrada, aula_1_4,
    )

    # ---------- 3. Target classroom closed ----------
    set_closed([
        {"building": "G", "location_id": "aula_1_4",
         "reason": "occupied by a class in progress"},
    ])
    plan_and_print(
        agent,
        "3. TARGET CLASSROOM CLOSED — Entrada -> aula 1.4 (substitute 1.1)",
        entrada, aula_1_4,
    )

    # ---------- 4. Floor 2 offices closed but despachos (floor 1) still open:
    #    the alternative finder should pick despachos ----------
    set_closed([
        {"building": "G", "location_id": "secretaria",
         "reason": "closed for the day"},
        {"building": "G", "location_id": "sala_mentorias",
         "reason": "closed for the day"},
        {"building": "G", "location_id": "despachos_eps",
         "reason": "closed for the day"},
    ])
    plan_and_print(
        agent,
        "4. FLOOR 2 OFFICES CLOSED — Entrada -> secretaria (finds floor 1 office)",
        entrada, secretaria,
    )

    # ---------- 4b. Every office type closed: no alternative possible ----------
    set_closed([
        {"building": "G", "location_id": "secretaria",      "reason": "closed today"},
        {"building": "G", "location_id": "sala_mentorias", "reason": "closed today"},
        {"building": "G", "location_id": "despachos_eps",  "reason": "closed today"},
        {"building": "G", "location_id": "despachos",      "reason": "closed today"},
    ])
    plan_and_print(
        agent,
        "4b. ALL OFFICES CLOSED — Entrada -> secretaria (impossible, explains)",
        entrada, secretaria,
    )

    # ---------- 5. Baseline restored ----------
    reset_closed()
    plan_and_print(
        agent,
        "5. BASELINE RESTORED — Entrada -> aula 1.4 (back to normal)",
        entrada, aula_1_4,
    )

    reset_closed()
    print("\n(closed_rooms.json has been reset to empty.)")


if __name__ == "__main__":
    main()

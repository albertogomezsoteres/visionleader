"""Pre-compute reference plans for the end-to-end validation scenarios.

Runs Fast Downward standalone for the (origin, destination, hurry) tuple
declared by each scenario in ``scenarios.json`` and writes the result
to ``reference_plans/e2e_reference_plans.json``. The post-processing
script later compares the plan produced by the live integrated run
against this ground truth.

Requires the ``fast-downward:latest`` Docker image to be available.

Usage:
    python e2e_validation/scripts/precompute_reference_plans.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from navigation.agent.planner_bridge import run_indoor_planner  # noqa: E402
from navigation.fast_downward_client import FastDownwardPlanner  # noqa: E402
from navigation.hierarchical_pddl_converter import HierarchicalPDDLConverter  # noqa: E402


SCENARIOS_PATH = REPO_ROOT / "e2e_validation" / "scenarios.json"
OUTPUT_PATH = REPO_ROOT / "e2e_validation" / "reference_plans" / "e2e_reference_plans.json"
TOPOLOGY_PATH = REPO_ROOT / "config" / "campus_topology.json"
CLOSED_ROOMS_PATH = REPO_ROOT / "config" / "closed_rooms.json"
PDDL_DIR = REPO_ROOT / "pddl"


def main() -> int:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"]

    planner = FastDownwardPlanner()
    converter = HierarchicalPDDLConverter(
        json_path=str(TOPOLOGY_PATH),
        pddl_dir=str(PDDL_DIR),
        closed_rooms_path=str(CLOSED_ROOMS_PATH),
    )

    results = {}
    for sc in scenarios:
        sid = sc["scenario_id"]
        exp = sc["expected"]
        origin = exp["origin"]
        destination = exp["destination"]
        hurry = bool(exp.get("hurry_mode", False))

        print(f"\n=== {sid} — {sc['name']} ===")
        print(f"origin     : {origin}")
        print(f"destination: {destination}")
        print(f"hurry_mode : {hurry}")

        plan_result = run_indoor_planner(
            planner=planner,
            hierarchical_converter=converter,
            pddl_dir=PDDL_DIR,
            origin_building=origin["building"],
            origin_room=origin["location_id"],
            origin_floor=origin["floor"],
            dest_building=destination["building"],
            dest_room=destination["location_id"],
            dest_floor=destination["floor"],
            goal_functional=destination.get("functional"),
            hurry_mode=hurry,
        )

        if not plan_result:
            print(f"[{sid}] FAILED: planner did not return a plan")
            results[sid] = {
                "scenario_id": sid,
                "origin": origin,
                "destination": destination,
                "hurry_mode": hurry,
                "actions": [],
                "action_count": 0,
                "cost": 0,
                "success": False,
            }
            continue

        actions = plan_result["actions"]
        cost = plan_result.get("cost", 0)
        cleaned = [a.strip() for a in actions if a.strip()]
        print(f"[{sid}] OK: {len(cleaned)} actions, cost {cost}")
        for i, a in enumerate(cleaned, start=1):
            print(f"   {i}. {a}")
        results[sid] = {
            "scenario_id": sid,
            "origin": origin,
            "destination": destination,
            "hurry_mode": hurry,
            "actions": cleaned,
            "action_count": len(cleaned),
            "cost": cost,
            "success": True,
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"reference_plans": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    return 0 if all(r["success"] for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

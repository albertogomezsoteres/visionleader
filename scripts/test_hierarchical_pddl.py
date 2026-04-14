"""
Quick test script for the hierarchical PDDL planner (Building G).

Usage (with Docker Desktop running):

    python scripts/test_hierarchical_pddl.py

Runs three intra-Building-G plans through Fast Downward:
  1. Same floor   : entrada_principal -> aula_0_3
  2. Elevator     : entrada_principal -> aula_1_4 (accessible mode)
  3. Hurry/stairs : entrada_principal -> secretaria (modo_rapido)

Prints the generated plan and cost for each case.
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from navigation.fast_downward_client import FastDownwardPlanner
from navigation.pddl_converter import HierarchicalPDDLConverter


def run_case(label: str, conv: HierarchicalPDDLConverter, planner: FastDownwardPlanner, **kwargs):
    print(f"\n===== {label} =====")
    problem_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pddl", dir=str(ROOT / "pddl"), delete=False
        ) as f:
            problem_path = f.name
            conv.generate_building_problem(
                building_id=1,
                output_path=problem_path,
                **kwargs,
            )
        result = planner.plan(
            domain_path=str(conv.get_domain_path(1)),
            problem_path=problem_path,
        )
        if result.get("success"):
            print(f"Cost: {result.get('cost')}  Steps: {result.get('steps')}")
            for a in result.get("plan", []):
                print(f"  {a}")
        else:
            print(f"FAILED: {result.get('error')}")
            print(result.get("output", "")[:600])
    finally:
        if problem_path and Path(problem_path).exists():
            Path(problem_path).unlink(missing_ok=True)


def main():
    conv = HierarchicalPDDLConverter(
        json_path=str(ROOT / "config" / "campus_graph.json"),
        pddl_dir=str(ROOT / "pddl"),
    )
    planner = FastDownwardPlanner()

    run_case(
        "Same floor: entrada_principal -> aula_0_3",
        conv, planner,
        origin_room="entrada_principal", origin_floor=0,
        dest_room="aula_0_3", dest_floor=0,
        problem_name="test-same-floor",
    )
    run_case(
        "Elevator: entrada_principal -> aula_1_4 (accessible)",
        conv, planner,
        origin_room="entrada_principal", origin_floor=0,
        dest_room="aula_1_4", dest_floor=1,
        problem_name="test-elevator",
    )
    run_case(
        "Hurry/stairs: entrada_principal -> secretaria (hurry)",
        conv, planner,
        origin_room="entrada_principal", origin_floor=0,
        dest_room="secretaria", dest_floor=2,
        hurry_mode=True,
        problem_name="test-stairs-hurry",
    )


if __name__ == "__main__":
    main()

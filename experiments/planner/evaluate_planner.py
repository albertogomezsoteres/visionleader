"""Run the Fast Downward benchmark with three search configurations.

This script is the planner experiment itself: it generates the campus routing
problems, solves each one with every search configuration, and saves the raw
per-run metrics as a CSV plus a bar chart of search effort. Turning those
numbers into the written report lives elsewhere; here we only produce data.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


# === Paths and constants ===

# This file sits at experiments/planner/, so the repo root is two levels up.
# Everything the planner needs (the domain, the topology, the closures) is
# resolved relative to that root so the script runs from any working directory.
repoRoot = Path(__file__).resolve().parents[2]

from visionleader.navigation.hierarchical_pddl_converter import HierarchicalPDDLConverter
from visionleader.navigation.fast_downward_client import FastDownwardPlanner

topologyPath    = repoRoot / "config" / "campus_topology.json"
pddlDir         = repoRoot / "pddl"
domainPath      = pddlDir / "domain.pddl"
evalProblemsDir = pddlDir / "problems" / "evaluation"
outputDirectory = repoRoot / "experiments" / "planner" / "results"

# The actual search takes well under a second per problem, so this generous
# timeout is not about search time: it absorbs Docker container startup, which
# varies between runs, so a slow cold start is never mistaken for a failure.
perRunTimeoutSeconds = 300


# === Search configurations ===


@dataclass(frozen=True)
class SearchConfig:
    """One Fast Downward search configuration to evaluate."""
    key: str            # short id reused as a CSV column value
    searchExpr: str     # Fast Downward search string passed via --search
    algorithm: str      # human-readable algorithm name (e.g. "A*")
    heuristic: str      # human-readable heuristic name (e.g. "LM-Cut")
    optimal: bool       # True when this config returns optimal-cost plans

    @property
    def label(self) -> str:
        return f"{self.algorithm} + {self.heuristic}"


# Three configurations, chosen to bracket the trade-off the benchmark exists to
# show. A* with LM-Cut is the informed optimal planner we want to justify;
# blind A* is the optimal baseline that reveals how much the heuristic saves;
# lazy greedy with FF is satisficing, fast but with no optimality guarantee.
# We deliberately leave out h_max: in this domain it expands the same states as
# LM-Cut, so it would add a column without adding insight.
searchConfigs: list[SearchConfig] = [
    SearchConfig("astar_lmcut", "astar(lmcut())",    "A*",          "LM-Cut", optimal=True),
    SearchConfig("astar_blind", "astar(blind())",    "A*",          "blind",  optimal=True),
    SearchConfig("lazy_ff",     "lazy_greedy([ff()])", "Lazy greedy", "FF",    optimal=False),
]


# === Benchmark problems ===


@dataclass(frozen=True)
class Problem:
    """One planning problem to benchmark every configuration against."""
    key: str        # short id reused as a CSV column value and as the filename
    label: str      # human-readable description of the route
    category: str   # grouping bucket: intra-g, intra-cd, hybrid, special
    # converterArgs is forwarded verbatim to converter.generate_building_problem,
    # so its keys are that method's parameter names and stay snake_case.
    converterArgs: dict
    closures: list[dict] = field(default_factory=list)


# The suite is a minimal cover of the routing situations the assistant must
# handle, so the benchmark exercises every part of the domain rather than one
# easy case repeated. The four categories group them: routes inside building G,
# routes inside CD (including its two independent vertical cores), cross-building
# hybrid routes with an outdoor hop, and special cases (hurry mode and a closure
# that forces a replan). Labels are Spanish on purpose: they are the rows the
# downstream report renders verbatim.
problems: list[Problem] = [
    # Intra-G: same floor, one elevator hop, two elevator hops.
    Problem("g_same_floor",
            "G p0: classroom_g_0_1 → classroom_g_0_4 (same floor)", "intra-g",
            {"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
             "dest_room": "classroom_g_0_4", "dest_floor": 0}),
    Problem("g_one_floor",
            "G: entrance_2 p0 → classroom_g_1_4 p1", "intra-g",
            {"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
             "dest_room": "classroom_g_1_4", "dest_floor": 1}),
    Problem("g_two_floors",
            "G: classroom_g_0_1 p0 → classroom_g_2_1 p2", "intra-g",
            {"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
             "dest_room": "classroom_g_2_1", "dest_floor": 2}),

    # Intra-CD: single floor, two floors, and a route that crosses its two cores.
    Problem("cd_one_floor",
            "CD: entrance_cd_exterior → classroom_cd_2 (p1)", "intra-cd",
            {"origin_building": 2, "origin_room": "entrance_cd_exterior", "origin_floor": 0,
             "dest_room": "classroom_cd_2", "dest_floor": 1}),
    Problem("cd_two_floors",
            "CD: entrance_cd_exterior → classroom_cd_7 (p2)", "intra-cd",
            {"origin_building": 2, "origin_room": "entrance_cd_exterior", "origin_floor": 0,
             "dest_room": "classroom_cd_7", "dest_floor": 2}),
    Problem("cd_cross_cores",
            "CD: classroom_cd_1 (p1) → classroom_cd_8 (p2), crosses cores", "intra-cd",
            {"origin_building": 2, "origin_room": "classroom_cd_1", "origin_floor": 1,
             "dest_room": "classroom_cd_8", "dest_floor": 2}),

    # Hybrid: cross-building routes that interleave an indoor walk with an
    # outdoor hop between the two entrances.
    Problem("hybrid_noncanonical",
            "Hybrid: entrance_1 G p0 → classroom_cd_3 CD p1 (non-canonical entrance)", "hybrid",
            {"origin_building": 1, "origin_room": "entrance_1", "origin_floor": 0,
             "dest_building": 2, "dest_room": "classroom_cd_3", "dest_floor": 1}),
    Problem("hybrid_aula_p1",
            "Hybrid: classroom_g_1_4 (G p1) → classroom_cd_3 (CD p1), classroom to classroom", "hybrid",
            {"origin_building": 1, "origin_room": "classroom_g_1_4", "origin_floor": 1,
             "dest_building": 2, "dest_room": "classroom_cd_3", "dest_floor": 1}),
    Problem("hybrid_deep",
            "Hybrid deep: classroom_g_0_1 (G p0) → classroom_cd_8 (CD p2)", "hybrid",
            {"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
             "dest_building": 2, "dest_room": "classroom_cd_8", "dest_floor": 2}),

    # Special: hurry mode (which should flip the elevator/stairs balance) and a
    # closure that forces the planner to reroute around a blocked elevator.
    Problem("g_hurry",
            "G hurry_mode: entrance_2 p0 → classroom_g_1_4 p1", "special",
            {"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
             "dest_room": "classroom_g_1_4", "dest_floor": 1, "hurry_mode": True}),
    Problem("cd_cross_cores_hurry",
            "CD hurry: classroom_cd_1 (p1) → classroom_cd_8 (p2), opposite cores", "special",
            {"origin_building": 2, "origin_room": "classroom_cd_1", "origin_floor": 1,
             "dest_room": "classroom_cd_8", "dest_floor": 2, "hurry_mode": True}),
    Problem("hybrid_closure",
            "Hybrid+closure: entrance_2 G p0 → classroom_cd_8 CD p2 (elevator G p0 closed)", "special",
            {"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
             "dest_building": 2, "dest_room": "classroom_cd_8", "dest_floor": 2},
            closures=[{"building": "G", "location_id": "elevator", "floor": 0,
                       "reason": "benchmark: force cross rerouting"}]),
]


# === Per-run result and metrics ===


@dataclass
class RunResult:
    """Metrics from solving one problem with one configuration.

    These field names are also the CSV column names (see ``csvFields`` and
    ``asdict`` in ``writeCsv``), so they stay snake_case to keep the generated
    file's headers stable.
    """
    problem_key: str
    problem_label: str
    category: str
    config_key: str
    config_label: str
    optimal: bool
    success: bool
    cost: int | None = None
    steps: int | None = None
    expanded: int | None = None
    generated: int | None = None
    evaluated: int | None = None
    search_time_s: float | None = None
    total_time_s: float | None = None
    suboptimality_pct: float | None = None  # computed after every run finishes
    error: str | None = None


# Column order for the results CSV. Keeping this list next to RunResult makes
# adding or dropping a metric a single edit, and the strings stay snake_case
# because they are the literal headers written to disk.
csvFields: tuple[str, ...] = (
    "problem_key", "problem_label", "category",
    "config_key", "config_label", "optimal",
    "success", "cost", "steps",
    "expanded", "generated", "evaluated",
    "search_time_s", "total_time_s", "suboptimality_pct", "error",
)


def annotateSuboptimality(plannerResults: list[RunResult]) -> None:
    """Score how far each satisficing plan is from optimal.

    For every problem we take the cheapest cost any optimal config achieved as
    the reference. Optimal configs score 0 by definition; a satisficing config
    scores the percentage by which its cost exceeds that reference. If no
    optimal config managed to solve a problem we leave its satisficing runs
    unscored, since there is no fair baseline to measure them against.
    """
    cheapestOptimalCost: dict[str, int] = {}
    for result in plannerResults:
        if result.success and result.optimal and result.cost is not None:
            best = cheapestOptimalCost.get(result.problem_key)
            if best is None or result.cost < best:
                cheapestOptimalCost[result.problem_key] = result.cost

    for result in plannerResults:
        if not result.success or result.cost is None:
            continue
        if result.optimal:
            result.suboptimality_pct = 0.0
            continue
        reference = cheapestOptimalCost.get(result.problem_key)
        if reference:  # skips both None and 0, avoiding a divide-by-zero
            result.suboptimality_pct = round(100.0 * (result.cost - reference) / reference, 2)


# === Problem generation and planner execution ===


def materialiseProblems() -> dict[str, Path]:
    """Write the 12 problem .pddl files to disk and return their paths.

    The files land in pddl/problems/evaluation/ and are committed to git as the
    reproducibility artefact: anyone can open or re-run them without this script.
    A problem with closures bakes the blocked rooms straight into its generated
    ``(open ...)`` facts, so each file is self-contained.
    """
    evalProblemsDir.mkdir(parents=True, exist_ok=True)
    problemPaths: dict[str, Path] = {}
    for problem in problems:
        outPath = evalProblemsDir / f"problem_{problem.key}.pddl"
        outPath.write_text(_generateProblemText(problem), encoding="utf-8")
        problemPaths[problem.key] = outPath
    return problemPaths


def _generateProblemText(problem: Problem) -> str:
    """Generate the PDDL text for one problem, baking in any closures.

    Closures are passed to the converter through a throwaway JSON file with the
    same shape as config/closed_rooms.json, so the generated problem reflects
    the blocked rooms without us mutating the real closures file.
    """
    closuresTempPath: str | None = None
    if problem.closures:
        closuresFile = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"closed": problem.closures}, closuresFile)
        closuresFile.close()
        closuresTempPath = closuresFile.name
    try:
        converter = _makeConverter(closuresTempPath)
        return converter.generate_building_problem(problem_name=problem.key, **problem.converterArgs)
    finally:
        if closuresTempPath:
            os.unlink(closuresTempPath)


def _makeConverter(closuresPath: str | None) -> HierarchicalPDDLConverter:
    """Build the converter, optionally pointing it at a custom closures file."""
    # These keys are the converter constructor's parameter names, so they stay
    # snake_case to match its signature.
    converterArgs: dict = {"json_path": str(topologyPath), "pddl_dir": str(pddlDir)}
    if closuresPath:
        converterArgs["closed_rooms_path"] = closuresPath
    return HierarchicalPDDLConverter(**converterArgs)


def runOne(problem: Problem, searchConfig: SearchConfig,
           problemPath: Path, planner: FastDownwardPlanner) -> RunResult:
    """Solve one problem with one configuration and return its metrics.

    Fast Downward runs inside a Docker container that mounts pddlDir at /pddl
    and only looks for files at that mount root, not in sub-folders. The
    committed problem lives under pddl/problems/evaluation/, so we copy it to a
    temporary file at the top of pddlDir for the duration of the run and leave
    the original artefact untouched.
    """
    runtimeFile = tempfile.NamedTemporaryFile(suffix=".pddl", delete=False, dir=str(pddlDir))
    runtimeFile.close()
    shutil.copy(problemPath, runtimeFile.name)
    try:
        try:
            # search_config is the planner method's parameter name.
            stats = planner.plan(str(domainPath), runtimeFile.name,
                                 search_config=searchConfig.searchExpr)
        except Exception as exc:
            return _failure(problem, searchConfig, f"planner: {exc}")
        if not stats.get("success"):
            return _failure(problem, searchConfig, stats.get("error"), stats=stats)
        return _success(problem, searchConfig, stats)
    finally:
        os.unlink(runtimeFile.name)


def _success(problem: Problem, searchConfig: SearchConfig, stats: dict) -> RunResult:
    # The stats keys are whatever FastDownwardPlanner.plan returns, so they are
    # read by their snake_case names straight off that dict.
    return RunResult(
        problem_key=problem.key, problem_label=problem.label, category=problem.category,
        config_key=searchConfig.key, config_label=searchConfig.label, optimal=searchConfig.optimal,
        success=True,
        cost=stats.get("cost"), steps=stats.get("steps"),
        expanded=stats.get("expanded"), generated=stats.get("generated"),
        evaluated=stats.get("evaluated"),
        search_time_s=stats.get("search_time_s"), total_time_s=stats.get("total_time_s"),
    )


def _failure(problem: Problem, searchConfig: SearchConfig,
             error: str | None, stats: dict | None = None) -> RunResult:
    # A failed run still carries whatever partial counters the planner reported,
    # so a timeout or crash is distinguishable from a clean "no plan found".
    stats = stats or {}
    return RunResult(
        problem_key=problem.key, problem_label=problem.label, category=problem.category,
        config_key=searchConfig.key, config_label=searchConfig.label, optimal=searchConfig.optimal,
        success=False,
        expanded=stats.get("expanded"), generated=stats.get("generated"),
        evaluated=stats.get("evaluated"),
        search_time_s=stats.get("search_time_s"), total_time_s=stats.get("total_time_s"),
        error=error,
    )


# === Output: results CSV ===


def writeCsv(plannerResults: list[RunResult], path: Path) -> None:
    """Write every run as one row, in the column order declared by csvFields."""
    with path.open("w", newline="", encoding="utf-8") as csvFile:
        writer = csv.DictWriter(csvFile, fieldnames=csvFields)
        writer.writeheader()
        for result in plannerResults:
            row = asdict(result)
            writer.writerow({column: row.get(column) for column in csvFields})


# === Main entry point ===


def main() -> None:
    outputDirectory.mkdir(exist_ok=True)
    planner = FastDownwardPlanner(timeout=perRunTimeoutSeconds)

    print(f"Materialising {len(problems)} problem files to {evalProblemsDir}")
    problemPaths = materialiseProblems()
    for key, path in problemPaths.items():
        print(f"  {key:25s} -> {path.relative_to(repoRoot)}")

    # Solve every problem with every configuration, printing a one-line summary
    # per run so a long benchmark is followable in the terminal.
    totalRuns = len(problems) * len(searchConfigs)
    print(f"\nRunning {totalRuns} experiments ({len(problems)} problems × {len(searchConfigs)} configs)")
    plannerResults: list[RunResult] = []
    for problemIndex, problem in enumerate(problems, 1):
        for configIndex, searchConfig in enumerate(searchConfigs, 1):
            runIndex = (problemIndex - 1) * len(searchConfigs) + configIndex
            print(f"  [{runIndex:3d}/{totalRuns}] {problem.key:22s} "
                  f"{searchConfig.key:14s} ... ", end="", flush=True)
            result = runOne(problem, searchConfig, problemPaths[problem.key], planner)
            plannerResults.append(result)
            if result.success:
                expandedStr  = f"{result.expanded:>6}"       if result.expanded      is not None else "  --  "
                generatedStr = f"{result.generated:>6}"      if result.generated     is not None else "  --  "
                timeStr      = f"{result.search_time_s:.2f}" if result.search_time_s is not None else " -- "
                print(f"OK   cost={result.cost:>4} steps={result.steps:>3} "
                      f"exp={expandedStr} gen={generatedStr} time={timeStr}s")
            else:
                print(f"FAIL  {result.error}")

    # Suboptimality can only be computed once every run is in, since it compares
    # each satisficing plan against the best optimal cost found for its problem.
    annotateSuboptimality(plannerResults)

    csvPath = outputDirectory / "planner_evaluation.csv"
    writeCsv(plannerResults, csvPath)
    print(f"\nWrote {csvPath}")


if __name__ == "__main__":
    main()

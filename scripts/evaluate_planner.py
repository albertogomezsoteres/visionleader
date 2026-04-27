"""Benchmark Fast Downward on the UFV campus navigation domain.

The 12 problem .pddl files used by the experiment are materialised under
``pddl/problems/evaluation/`` (committed to git as the reproducibility
artefact). The script then runs every problem against every search
configuration and writes:

  * ``reports/planner_evaluation.md``  — Markdown report (per-problem plan
    + per-config stats table) ready to paste into the memoria.
  * ``reports/planner_evaluation.csv`` — raw per-run metrics.
  * ``reports/planner_evaluation_expanded.png`` — bar chart of expanded
    states per problem and config (skipped silently when matplotlib is
    not installed).

Run:
    python scripts/evaluate_planner.py

Requires Docker with the ``fast-downward`` image available locally; the
search itself runs inside the container via ``FastDownwardPlanner``.
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

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.navigation.hierarchical_pddl_converter import HierarchicalPDDLConverter
from src.navigation.fast_downward_client import FastDownwardPlanner

TOPOLOGY_PATH         = REPO / "config" / "campus_topology.json"
PDDL_DIR              = REPO / "pddl"
DOMAIN_PATH           = PDDL_DIR / "domain_indoor.pddl"
EVAL_PROBLEMS_DIR     = PDDL_DIR / "problems" / "evaluation"
OUTPUT_DIR            = REPO / "reports"

# Per-run timeout in seconds. Real search wall-clock for these problems is
# < 0.05 s; the slack covers Docker startup overhead and any transient
# cleanup contention from the planner client's fixed container name. Set
# generously so a Docker hiccup never gets confused with a planner failure.
PER_RUN_TIMEOUT_S = 300


# =========================================================================
# Search configurations to benchmark.
# =========================================================================


@dataclass(frozen=True)
class SearchConfig:
    """One Fast Downward search configuration to evaluate."""
    key: str            # short id used in CSV / plot column headers
    search_expr: str    # Fast Downward search string passed via --search
    algorithm: str      # human-readable algorithm name (e.g. "A*")
    heuristic: str      # human-readable heuristic name (e.g. "LM-Cut")
    optimal: bool       # True iff this config returns optimal-cost plans

    @property
    def label(self) -> str:
        return f"{self.algorithm} + {self.heuristic}"


# Three-way comparison: two optimal planners (LM-Cut as the informed choice,
# blind as the baseline) plus one satisficing planner to expose the
# optimality trade-off. h_max is omitted because it ties LM-Cut on expanded
# states in this domain and adds no distinguishing signal.
CONFIGS: list[SearchConfig] = [
    SearchConfig(
        key="astar_lmcut",
        search_expr="astar(lmcut())",
        algorithm="A*",
        heuristic="LM-Cut",
        optimal=True,
    ),
    SearchConfig(
        key="astar_blind",
        search_expr="astar(blind())",
        algorithm="A*",
        heuristic="blind",
        optimal=True,
    ),
    SearchConfig(
        key="lazy_ff",
        search_expr="lazy_greedy([ff()])",
        algorithm="Lazy greedy",
        heuristic="FF",
        optimal=False,
    ),
]

# The config whose plan is rendered in the per-problem section of the
# Markdown report. We pick the strongest informed optimal config so the
# displayed plan is both optimal and produced efficiently.
PLAN_DISPLAY_CONFIG_KEY = "astar_lmcut"


# =========================================================================
# Problem suite. Each entry becomes one row of the master table.
# =========================================================================


@dataclass(frozen=True)
class Problem:
    """One planning problem to benchmark every config against."""
    key: str             # short id used in CSV / plot column headers
    label: str           # human-readable description
    category: str        # grouping bucket (intra-g, intra-cd, hybrid, special)
    kwargs: dict         # forwarded verbatim to converter.generate_building_problem
    closures: list[dict] = field(default_factory=list)


PROBLEMS: list[Problem] = [
    # -- Intra-G, aulas (p0, p1, p2 — no ágora) --
    Problem(
        key="g_same_floor",
        label="G p0: classroom_g_0_1 → classroom_g_0_4 (misma planta)",
        category="intra-g",
        kwargs={"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
                "dest_room": "classroom_g_0_4", "dest_floor": 0},
    ),
    Problem(
        key="g_one_floor",
        label="G: entrance_2 p0 → classroom_g_1_4 p1",
        category="intra-g",
        kwargs={"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
                "dest_room": "classroom_g_1_4", "dest_floor": 1},
    ),
    Problem(
        key="g_two_floors",
        label="G: classroom_g_0_1 p0 → classroom_g_2_1 p2",
        category="intra-g",
        kwargs={"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
                "dest_room": "classroom_g_2_1", "dest_floor": 2},
    ),

    # -- Intra-CD, aulas (p0 entrance + p1/p2 aulas) --
    Problem(
        key="cd_one_floor",
        label="CD: entrance_cd_exterior → classroom_cd_2 (p1)",
        category="intra-cd",
        kwargs={"origin_building": 2, "origin_room": "entrance_cd_exterior", "origin_floor": 0,
                "dest_room": "classroom_cd_2", "dest_floor": 1},
    ),
    Problem(
        key="cd_two_floors",
        label="CD: entrance_cd_exterior → classroom_cd_7 (p2)",
        category="intra-cd",
        kwargs={"origin_building": 2, "origin_room": "entrance_cd_exterior", "origin_floor": 0,
                "dest_room": "classroom_cd_7", "dest_floor": 2},
    ),
    Problem(
        key="cd_cross_cores",
        label="CD: classroom_cd_1 (p1) → classroom_cd_8 (p2) — cruza cores",
        category="intra-cd",
        kwargs={"origin_building": 2, "origin_room": "classroom_cd_1", "origin_floor": 1,
                "dest_room": "classroom_cd_8", "dest_floor": 2},
    ),

    # -- Hybrid (cross-building, aulas a aulas) --
    Problem(
        key="hybrid_noncanonical",
        label="Hybrid: entrance_1 G p0 → classroom_cd_3 CD p1 (entrada no canónica)",
        category="hybrid",
        kwargs={"origin_building": 1, "origin_room": "entrance_1", "origin_floor": 0,
                "dest_building": 2,
                "dest_room": "classroom_cd_3", "dest_floor": 1},
    ),
    Problem(
        key="hybrid_aula_p1",
        label="Hybrid: classroom_g_1_4 (G p1) → classroom_cd_3 (CD p1) — aula↔aula",
        category="hybrid",
        kwargs={"origin_building": 1, "origin_room": "classroom_g_1_4", "origin_floor": 1,
                "dest_building": 2,
                "dest_room": "classroom_cd_3", "dest_floor": 1},
    ),
    Problem(
        key="hybrid_deep",
        label="Hybrid deep: classroom_g_0_1 (G p0) → classroom_cd_8 (CD p2)",
        category="hybrid",
        kwargs={"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
                "dest_building": 2,
                "dest_room": "classroom_cd_8", "dest_floor": 2},
    ),

    # -- Special (hurry mode + closure) --
    Problem(
        key="g_hurry",
        label="G hurry_mode: entrance_2 p0 → classroom_g_1_4 p1",
        category="special",
        kwargs={"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
                "dest_room": "classroom_g_1_4", "dest_floor": 1, "hurry_mode": True},
    ),
    Problem(
        key="cd_cross_cores_hurry",
        label="CD hurry: classroom_cd_1 (p1) → classroom_cd_8 (p2), cores opuestos",
        category="special",
        kwargs={"origin_building": 2, "origin_room": "classroom_cd_1", "origin_floor": 1,
                "dest_room": "classroom_cd_8", "dest_floor": 2, "hurry_mode": True},
    ),
    Problem(
        key="hybrid_closure",
        label="Hybrid+closure: entrance_2 G p0 → classroom_cd_8 CD p2 (elevator G p0 cerrado)",
        category="special",
        kwargs={"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
                "dest_building": 2,
                "dest_room": "classroom_cd_8", "dest_floor": 2},
        closures=[{"building": "G", "location_id": "elevator", "floor": 0,
                   "reason": "benchmark: forzar reruteo cruzado"}],
    ),
]


# =========================================================================
# Per-(problem, config) execution
# =========================================================================


@dataclass
class RunResult:
    """Outcome of one (problem, config) execution."""
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
    suboptimality_pct: float | None = None  # filled in post-run for non-optimal configs
    plan: list[str] = field(default_factory=list)
    error: str | None = None


# Single source of truth for the CSV column order. Keeps `write_csv` and
# the dataclass schema in sync — adding/removing a metric is a one-place
# change.
CSV_FIELDS: tuple[str, ...] = (
    "problem_key", "problem_label", "category",
    "config_key", "config_label", "optimal",
    "success", "cost", "steps",
    "expanded", "generated", "evaluated",
    "search_time_s", "total_time_s", "suboptimality_pct", "error",
)


def annotate_suboptimality(rows: list[RunResult]) -> None:
    """Compute `suboptimality_pct` for every successful non-optimal run.

    The reference cost per problem is the minimum cost reported by any
    optimal config that solved it. Optimal configs always get
    suboptimality_pct = 0. Non-optimal configs get
    100 * (cost − optimal_cost) / optimal_cost. If no optimal config solved
    a given problem, suboptimality stays as None for the non-optimal runs
    on that problem (we cannot fairly score them).
    """
    optimal_by_problem: dict[str, int] = {}
    for r in rows:
        if r.success and r.optimal and r.cost is not None:
            current = optimal_by_problem.get(r.problem_key)
            if current is None or r.cost < current:
                optimal_by_problem[r.problem_key] = r.cost

    for r in rows:
        if not r.success or r.cost is None:
            continue
        if r.optimal:
            r.suboptimality_pct = 0.0
            continue
        opt = optimal_by_problem.get(r.problem_key)
        if opt is None or opt == 0:
            continue
        r.suboptimality_pct = round(100.0 * (r.cost - opt) / opt, 2)


def materialise_problems() -> dict[str, Path]:
    """Generate the 12 problem .pddl files on disk and return their paths.

    Files land in ``pddl/problems/evaluation/problem_<key>.pddl`` and are
    committed to git as the reproducibility artefact: anyone can inspect
    or re-run them outside this script. Problems with closures bake the
    closure state into the generated `(open ...)` facts so the file is
    self-contained.
    """
    EVAL_PROBLEMS_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for problem in PROBLEMS:
        text = _generate_problem_text(problem)
        out = EVAL_PROBLEMS_DIR / f"problem_{problem.key}.pddl"
        out.write_text(text, encoding="utf-8")
        paths[problem.key] = out
    return paths


def _generate_problem_text(problem: Problem) -> str:
    """Generate the PDDL text for one problem, baking in any closures."""
    closures_tmp_path: str | None = None
    if problem.closures:
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"closed": problem.closures}, f)
        f.close()
        closures_tmp_path = f.name
    try:
        converter = _make_converter(closures_tmp_path)
        return converter.generate_building_problem(
            problem_name=problem.key, **problem.kwargs,
        )
    finally:
        if closures_tmp_path:
            os.unlink(closures_tmp_path)


def _make_converter(closures_path: str | None) -> HierarchicalPDDLConverter:
    """Construct the converter, optionally pointing it at a custom closures file."""
    kwargs: dict = {
        "json_path": str(TOPOLOGY_PATH),
        "pddl_dir":  str(PDDL_DIR),
    }
    if closures_path:
        kwargs["closed_rooms_path"] = closures_path
    return HierarchicalPDDLConverter(**kwargs)


def run_one(
    problem: Problem,
    config: SearchConfig,
    problem_path: Path,
    planner: FastDownwardPlanner,
) -> RunResult:
    """Run a single (problem, config) using the pre-materialised PDDL file.

    The planner's Docker container mounts PDDL_DIR at /pddl and expects
    files at that mount root, so the materialised file (which lives in a
    sub-directory) is copied to a tempname at PDDL_DIR top level for the
    duration of the run. The original under ``pddl/problems/evaluation/``
    is the artefact committed to git and is left untouched.
    """
    runtime = tempfile.NamedTemporaryFile(
        suffix=".pddl", delete=False, dir=str(PDDL_DIR),
    )
    runtime.close()
    shutil.copy(problem_path, runtime.name)
    try:
        try:
            stats = planner.plan(
                str(DOMAIN_PATH), runtime.name, search_config=config.search_expr,
            )
        except Exception as exc:
            return _failure(problem, config, f"planner: {exc}")
        if not stats.get("success"):
            return _failure(problem, config, stats.get("error"), stats=stats)
        return _success(problem, config, stats)
    finally:
        os.unlink(runtime.name)


def _success(problem: Problem, config: SearchConfig, stats: dict) -> RunResult:
    return RunResult(
        problem_key=problem.key,
        problem_label=problem.label,
        category=problem.category,
        config_key=config.key,
        config_label=config.label,
        optimal=config.optimal,
        success=True,
        cost=stats.get("cost"),
        steps=stats.get("steps"),
        expanded=stats.get("expanded"),
        generated=stats.get("generated"),
        evaluated=stats.get("evaluated"),
        search_time_s=stats.get("search_time_s"),
        total_time_s=stats.get("total_time_s"),
        plan=stats.get("plan") or [],
    )


def _failure(
    problem: Problem,
    config: SearchConfig,
    error: str | None,
    stats: dict | None = None,
) -> RunResult:
    s = stats or {}
    return RunResult(
        problem_key=problem.key,
        problem_label=problem.label,
        category=problem.category,
        config_key=config.key,
        config_label=config.label,
        optimal=config.optimal,
        success=False,
        expanded=s.get("expanded"),
        generated=s.get("generated"),
        evaluated=s.get("evaluated"),
        search_time_s=s.get("search_time_s"),
        total_time_s=s.get("total_time_s"),
        error=error,
    )


# =========================================================================
# Output writers
# =========================================================================


def write_csv(rows: list[RunResult], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            d = asdict(r)
            w.writerow({k: d.get(k) for k in CSV_FIELDS})


def _fmt(value, spec: str = "", na: str = "—") -> str:
    """Format a metric value for the Markdown table (NA-safe)."""
    if value is None:
        return na
    try:
        return format(value, spec) if spec else str(value)
    except (TypeError, ValueError):
        return str(value)


def write_markdown(
    rows: list[RunResult],
    plans_by_problem: dict[str, list[str]],
    path: Path,
) -> None:
    """Emit the human-readable report grouped by problem."""
    by_problem, problem_order = _group_by_problem(rows)
    display_config = next(c for c in CONFIGS if c.key == PLAN_DISPLAY_CONFIG_KEY)

    out: list[str] = []
    out.append("# Evaluación de Fast Downward sobre el dominio de navegación UFV\n")
    out.append(
        f"Se comparan {len(CONFIGS)} configuraciones de búsqueda sobre un "
        f"conjunto representativo de {len(PROBLEMS)} problemas. Las configuraciones "
        "óptimas garantizan coste mínimo; la satisficing (`lazy_greedy`) prioriza "
        "encontrar un plan rápido sin garantía de optimalidad."
    )
    out.append("")
    out.append("| Configuración | Algoritmo | Heurístico | Óptimo |")
    out.append("|---|---|---|---|")
    for c in CONFIGS:
        out.append(
            f"| `{c.search_expr}` | {c.algorithm} | {c.heuristic} | "
            f"{'✓' if c.optimal else '✗'} |"
        )
    out.append("")

    # Aggregate roll-up: totals across the problems each config solved.
    out.append("## Resumen agregado\n")
    out.append("Totales sumados sobre los problemas resueltos por cada configuración.\n")
    out.append("| Configuración | Resueltos | Σ Expanded | Σ Generated | Σ Search time (s) |")
    out.append("|---|---|---|---|---|")
    for c in CONFIGS:
        agg = _aggregate(rows, c.key)
        out.append(
            f"| {c.label} | {agg['solved']}/{len(PROBLEMS)} | "
            f"{agg['expanded']} | {agg['generated']} | "
            f"{agg['search_time_s']:.2f} |"
        )
    out.append("")

    # Suboptimality summary for non-optimal configs.
    out.append("## Suboptimalidad de configuraciones no-óptimas\n")
    out.append(
        "Para cada configuración satisficing, fracción de problemas en los "
        "que el coste del plan supera al óptimo (LM-Cut), con la desviación "
        "relativa media y máxima sobre los problemas resueltos.\n"
    )
    out.append("| Configuración | Subóptimos / Resueltos | Subopt. media | Subopt. máxima |")
    out.append("|---|---|---|---|")
    has_nonoptimal = False
    for c in CONFIGS:
        if c.optimal:
            continue
        has_nonoptimal = True
        sub = _suboptimality_summary(rows, c.key)
        out.append(
            f"| {c.label} | {sub['n_suboptimal']}/{sub['n_solved']} | "
            f"{_fmt(sub['mean_pct'], '.2f', na='—')}% | "
            f"{_fmt(sub['max_pct'], '.2f', na='—')}% |"
        )
    if not has_nonoptimal:
        out.append("| (sin configuraciones satisficing) | — | — | — |")
    out.append("")

    # Per-category breakdown.
    out.append("## Desglose por categoría\n")
    out.append(
        "Resultados agrupados por tipo de problema. Ayuda a localizar dónde "
        "cada configuración brilla o falla.\n"
    )
    out.append("| Categoría | n problemas | LM-Cut Σ Expanded | Greedy subóptimos | Greedy subopt. media |")
    out.append("|---|---|---|---|---|")
    categories = []
    seen = set()
    for p in PROBLEMS:
        if p.category not in seen:
            seen.add(p.category)
            categories.append(p.category)
    for cat in categories:
        cat_rows = [r for r in rows if r.category == cat]
        cat_n = len({r.problem_key for r in cat_rows})
        lmcut_exp = sum(
            int(r.expanded) for r in cat_rows
            if r.config_key == "astar_lmcut" and r.success and r.expanded is not None
        )
        greedy_rows = [r for r in cat_rows if r.config_key == "lazy_ff" and r.success]
        greedy_subopt = [r for r in greedy_rows
                         if r.suboptimality_pct is not None and r.suboptimality_pct > 0]
        mean_pct = (
            sum(r.suboptimality_pct for r in greedy_subopt) / len(greedy_subopt)
            if greedy_subopt else None
        )
        out.append(
            f"| {cat} | {cat_n} | {lmcut_exp} | "
            f"{len(greedy_subopt)}/{len(greedy_rows)} | "
            f"{_fmt(mean_pct, '.2f', na='—')}% |"
        )
    out.append("")

    # Per-problem detail.
    for prob_key in problem_order:
        prob_rows = by_problem[prob_key]
        prob = prob_rows[0]
        out.append(f"## {prob.problem_label}\n")
        out.append(f"Categoría: `{prob.category}`\n")

        plan = plans_by_problem.get(prob_key, [])
        if plan:
            caption = "Plan óptimo" if display_config.optimal else "Plan satisficing"
            out.append(f"**{caption}** ({display_config.label}):")
            out.append("```")
            for i, action in enumerate(plan, 1):
                out.append(f"  {i:2d}. {action}")
            out.append("```\n")

        out.append("| Configuración | Coste | Pasos | Expanded | Generated | Search (s) | Δ vs óptimo |")
        out.append("|---|---|---|---|---|---|---|")
        for r in prob_rows:
            if not r.success:
                out.append(
                    f"| {r.config_label} | — | — | — | — | "
                    f"FAIL: {(r.error or '')[:40]} | — |"
                )
                continue
            if r.optimal or r.suboptimality_pct == 0:
                delta = "—"
            else:
                delta = f"+{_fmt(r.suboptimality_pct, '.2f')}%"
            out.append(
                f"| {r.config_label} | {_fmt(r.cost)} | {_fmt(r.steps)} | "
                f"{_fmt(r.expanded)} | {_fmt(r.generated)} | "
                f"{_fmt(r.search_time_s, '.2f')} | {delta} |"
            )
        out.append("")

    path.write_text("\n".join(out), encoding="utf-8")


def _group_by_problem(
    rows: list[RunResult],
) -> tuple[dict[str, list[RunResult]], list[str]]:
    """Group rows by problem_key while preserving original order."""
    by_problem: dict[str, list[RunResult]] = {}
    order: list[str] = []
    for row in rows:
        if row.problem_key not in by_problem:
            order.append(row.problem_key)
            by_problem[row.problem_key] = []
        by_problem[row.problem_key].append(row)
    return by_problem, order


def _aggregate(rows: list[RunResult], config_key: str) -> dict:
    """Roll up successful runs of one config across all problems."""
    agg = {"solved": 0, "expanded": 0, "generated": 0, "search_time_s": 0.0}
    for r in rows:
        if r.config_key != config_key or not r.success:
            continue
        agg["solved"] += 1
        for k in ("expanded", "generated", "search_time_s"):
            v = getattr(r, k)
            if v is not None:
                agg[k] += float(v) if k == "search_time_s" else int(v)
    return agg


def _suboptimality_summary(rows: list[RunResult], config_key: str) -> dict:
    """For one non-optimal config, count how many resolved problems are
    suboptimal and compute the mean/max suboptimality percentage."""
    solved = [r for r in rows
              if r.config_key == config_key and r.success and r.suboptimality_pct is not None]
    suboptimal = [r for r in solved if r.suboptimality_pct > 0]
    return {
        "n_solved":      len(solved),
        "n_suboptimal":  len(suboptimal),
        "mean_pct":      sum(r.suboptimality_pct for r in suboptimal) / len(suboptimal)
                         if suboptimal else None,
        "max_pct":       max(r.suboptimality_pct for r in suboptimal) if suboptimal else None,
    }


def write_plot(rows: list[RunResult], path: Path) -> bool:
    """Bar chart of expanded states per problem, grouped by config.

    Failed runs are simply omitted (no fake bars). Returns True iff the
    chart was written; False if matplotlib is unavailable or no data
    survives.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    problems_in_order = _ordered_unique(r.problem_key for r in rows)
    configs_in_order  = _ordered_unique((r.config_key, r.config_label) for r in rows)

    data: dict[tuple[str, str], int] = {}
    for r in rows:
        if r.success and r.expanded is not None:
            data[(r.problem_key, r.config_key)] = r.expanded
    if not data:
        return False

    n_problems = len(problems_in_order)
    n_configs  = len(configs_in_order)
    bar_width  = 0.8 / n_configs

    fig, ax = plt.subplots(figsize=(max(14, n_problems * 1.3), 6))
    for i, (ckey, clabel) in enumerate(configs_in_order):
        xs, ys = [], []
        for j, p in enumerate(problems_in_order):
            v = data.get((p, ckey))
            if v is None:
                continue
            xs.append(j + (i - n_configs / 2 + 0.5) * bar_width)
            ys.append(v)
        ax.bar(xs, ys, bar_width, label=clabel)

    ax.set_xticks(range(n_problems))
    ax.set_xticklabels(problems_in_order, rotation=30, ha="right")
    ax.set_ylabel("Expanded states (log scale)")
    ax.set_yscale("log")
    ax.set_title("Fast Downward — Expanded states per problem, by configuration")
    ax.legend(loc="best")
    ax.grid(axis="y", alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def _ordered_unique(items):
    """Return items in first-seen order, preserving uniqueness."""
    seen = set()
    out = []
    for item in items:
        key = item[0] if isinstance(item, tuple) else item
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


# =========================================================================
# Entry point
# =========================================================================


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    planner = FastDownwardPlanner(timeout=PER_RUN_TIMEOUT_S)

    print(f"Materialising {len(PROBLEMS)} problem files to {EVAL_PROBLEMS_DIR}")
    problem_paths = materialise_problems()
    for key, path in problem_paths.items():
        print(f"  {key:25s} -> {path.relative_to(REPO)}")

    rows: list[RunResult] = []
    plans_by_problem: dict[str, list[str]] = {}

    total = len(PROBLEMS) * len(CONFIGS)
    print(f"\nRunning {total} experiments ({len(PROBLEMS)} problems × {len(CONFIGS)} configs)")

    for p_idx, problem in enumerate(PROBLEMS, 1):
        for c_idx, config in enumerate(CONFIGS, 1):
            run_idx = (p_idx - 1) * len(CONFIGS) + c_idx
            print(f"  [{run_idx:3d}/{total}] {problem.key:22s} "
                  f"{config.key:14s} ... ", end="", flush=True)
            row = run_one(problem, config, problem_paths[problem.key], planner)
            rows.append(row)
            if row.success:
                exp_s  = f"{row.expanded:>6}"      if row.expanded      is not None else "  --  "
                gen_s  = f"{row.generated:>6}"     if row.generated     is not None else "  --  "
                time_s = f"{row.search_time_s:.2f}" if row.search_time_s is not None else " -- "
                print(
                    f"OK   cost={row.cost:>4} steps={row.steps:>3} "
                    f"exp={exp_s} gen={gen_s} time={time_s}s"
                )
                if config.key == PLAN_DISPLAY_CONFIG_KEY:
                    plans_by_problem[problem.key] = row.plan
            else:
                print(f"FAIL  {row.error}")

    annotate_suboptimality(rows)

    md_path  = OUTPUT_DIR / "planner_evaluation.md"
    csv_path = OUTPUT_DIR / "planner_evaluation.csv"
    png_path = OUTPUT_DIR / "planner_evaluation_expanded.png"

    write_csv(rows, csv_path)
    write_markdown(rows, plans_by_problem, md_path)
    plotted = write_plot(rows, png_path)

    print("")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    if plotted:
        print(f"Wrote {png_path}")
    else:
        print("Skipped PNG chart (matplotlib not available or no data).")


if __name__ == "__main__":
    main()

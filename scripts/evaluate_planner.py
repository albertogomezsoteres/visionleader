"""Benchmark Fast Downward on the UFV campus navigation domain.

Runs a representative suite of problems (intra-G, intra-CD, hybrid, hurry,
closure) against several search configurations and writes:

  * ``reports/planner_evaluation.md``  — Markdown report ready to paste
    into the memoria (per-problem plan + per-config stats table).
  * ``reports/planner_evaluation.csv`` — raw per-run metrics.
  * ``reports/planner_evaluation_expanded.png`` — bar chart of expanded
    states per problem and config (if ``matplotlib`` is available).

Run:
    python scripts/evaluate_planner.py
"""

import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.navigation.hierarchical_pddl_converter import HierarchicalPDDLConverter
from src.navigation.fast_downward_client import FastDownwardPlanner

TOPOLOGY_PATH = REPO / "config" / "campus_topology.json"
PDDL_DIR = REPO / "pddl"
OUTPUT_DIR = REPO / "reports"

# Per-run timeout. Blind search on the hardest hybrid problems can expand
# hundreds of thousands of states; 90s is the safe ceiling.
PER_RUN_TIMEOUT = 90


# =========================================================================
# Search configurations to benchmark.
# =========================================================================
# Three-way comparison: two optimal planners (LM-Cut as the informed choice,
# blind as the baseline) plus one satisficing planner to expose the
# optimality trade-off. h_max is omitted because it ties LM-Cut on expanded
# states in this domain and adds no distinguishing signal.
CONFIGS: List[Dict] = [
    {"key": "astar_lmcut",
     "label": "A* + LM-Cut",
     "search": "astar(lmcut())",
     "optimal": True},
    {"key": "astar_blind",
     "label": "A* blind",
     "search": "astar(blind())",
     "optimal": True},
    {"key": "lazy_ff",
     "label": "Lazy greedy + FF",
     "search": "lazy_greedy([ff()])",
     "optimal": False},
]


# =========================================================================
# Problem suite. Each entry becomes one row of the master table.
# =========================================================================
PROBLEMS: List[Dict] = [
    # -- Intra-G, aulas (p0, p1, p2 — no ágora) --
    {
        "key": "g_same_floor",
        "label": "G p0: classroom_g_0_1 → classroom_g_0_4 (misma planta)",
        "category": "intra-g",
        "kwargs": {"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
                   "dest_room": "classroom_g_0_4", "dest_floor": 0},
    },
    {
        "key": "g_one_floor",
        "label": "G: entrance_2 p0 → classroom_g_1_4 p1",
        "category": "intra-g",
        "kwargs": {"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
                   "dest_room": "classroom_g_1_4", "dest_floor": 1},
    },
    {
        "key": "g_two_floors",
        "label": "G: classroom_g_0_1 p0 → classroom_g_2_1 p2",
        "category": "intra-g",
        "kwargs": {"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
                   "dest_room": "classroom_g_2_1", "dest_floor": 2},
    },
    # -- Intra-CD, aulas (p0 entrance + p1/p2 aulas) --
    {
        "key": "cd_one_floor",
        "label": "CD: entrance_cd_exterior → classroom_cd_2 p1",
        "category": "intra-cd",
        "kwargs": {"origin_building": 2, "origin_room": "entrance_cd_exterior", "origin_floor": 0,
                   "dest_room": "classroom_cd_2", "dest_floor": 1},
    },
    {
        "key": "cd_two_floors",
        "label": "CD: entrance_cd_exterior → classroom_cd_7 p2",
        "category": "intra-cd",
        "kwargs": {"origin_building": 2, "origin_room": "entrance_cd_exterior", "origin_floor": 0,
                   "dest_room": "classroom_cd_7", "dest_floor": 2},
    },
    {
        "key": "cd_cross_cores",
        "label": "CD: classroom_cd_1 p1 → classroom_cd_8 p2 (cross cores)",
        "category": "intra-cd",
        "kwargs": {"origin_building": 2, "origin_room": "classroom_cd_1", "origin_floor": 1,
                   "dest_room": "classroom_cd_8", "dest_floor": 2},
    },
    # -- Hybrid (cross-building, aulas a aulas) --
    {
        "key": "hybrid_noncanonical",
        "label": "Hybrid: entrance_1 G p0 → classroom_cd_3 CD p1 (no-canonical)",
        "category": "hybrid",
        "kwargs": {"origin_building": 1, "origin_room": "entrance_1", "origin_floor": 0,
                   "dest_building": 2,
                   "dest_room": "classroom_cd_3", "dest_floor": 1},
    },
    {
        "key": "hybrid_aula_p1",
        "label": "Hybrid: classroom_g_1_4 G p1 → classroom_cd_3 CD p1 (aula↔aula)",
        "category": "hybrid",
        "kwargs": {"origin_building": 1, "origin_room": "classroom_g_1_4", "origin_floor": 1,
                   "dest_building": 2,
                   "dest_room": "classroom_cd_3", "dest_floor": 1},
    },
    {
        "key": "hybrid_deep",
        "label": "Hybrid deep: classroom_g_0_1 G p0 → classroom_cd_8 CD p2",
        "category": "hybrid",
        "kwargs": {"origin_building": 1, "origin_room": "classroom_g_0_1", "origin_floor": 0,
                   "dest_building": 2,
                   "dest_room": "classroom_cd_8", "dest_floor": 2},
    },
    # -- Special (hurry mode + closure) --
    {
        "key": "g_hurry",
        "label": "G hurry_mode: entrance_2 p0 → classroom_g_1_4 p1",
        "category": "special",
        "kwargs": {"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
                   "dest_room": "classroom_g_1_4", "dest_floor": 1, "hurry_mode": True},
    },
    {
        "key": "hybrid_closure",
        "label": "Hybrid+closure: entrance_2 G p0 → classroom_cd_8 CD p2 (elevator G p0 cerrado)",
        "category": "special",
        "kwargs": {"origin_building": 1, "origin_room": "entrance_2", "origin_floor": 0,
                   "dest_building": 2,
                   "dest_room": "classroom_cd_8", "dest_floor": 2},
        "closures": [{"building": "G", "location_id": "elevator", "floor": 0,
                      "reason": "benchmark: forzar reruteo cruzado"}],
    },
]


def run_one(problem: Dict, config: Dict, planner: FastDownwardPlanner) -> Dict:
    """Run a single (problem, config) combination, return a row dict."""
    closures = problem.get("closures") or []

    closures_tmp: Optional[str] = None
    if closures:
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"closed": closures}, f)
        f.close()
        closures_tmp = f.name

    try:
        if closures_tmp:
            converter = HierarchicalPDDLConverter(
                json_path=str(TOPOLOGY_PATH),
                pddl_dir=str(PDDL_DIR),
                closed_rooms_path=closures_tmp,
            )
        else:
            converter = HierarchicalPDDLConverter(
                json_path=str(TOPOLOGY_PATH),
                pddl_dir=str(PDDL_DIR),
            )
        domain_path = str(converter.get_domain_path(1))

        try:
            problem_text = converter.generate_building_problem(
                problem_name=f"{problem['key']}_{config['key']}",
                **problem["kwargs"],
            )
        except Exception as exc:
            return _row(problem, config, success=False, error=f"generation: {exc}")

        # Problem file must live under the PDDL dir so Docker can mount it.
        problem_tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".pddl", delete=False, encoding="utf-8", dir=str(PDDL_DIR)
        )
        problem_tmp.write(problem_text)
        problem_tmp.close()
        try:
            result = planner.plan(
                domain_path, problem_tmp.name, search_config=config["search"]
            )
        finally:
            os.unlink(problem_tmp.name)

        if not result.get("success"):
            return _row(problem, config, success=False,
                        error=result.get("error"), stats=result)
        return _row(problem, config, success=True, stats=result)
    finally:
        if closures_tmp:
            os.unlink(closures_tmp)


def _row(problem: Dict, config: Dict, success: bool,
         error: Optional[str] = None, stats: Optional[Dict] = None) -> Dict:
    stats = stats or {}
    return {
        "problem_key":   problem["key"],
        "problem":       problem["label"],
        "category":      problem["category"],
        "config_key":    config["key"],
        "config":        config["label"],
        "optimal":       config["optimal"],
        "success":       success,
        "cost":          stats.get("cost") if success else None,
        "steps":         stats.get("steps") if success else None,
        "expanded":      stats.get("expanded"),
        "generated":     stats.get("generated"),
        "evaluated":     stats.get("evaluated"),
        "search_time_s": stats.get("search_time_s"),
        "total_time_s":  stats.get("total_time_s"),
        "plan":          stats.get("plan") if success else [],
        "error":         error,
    }


def write_csv(rows: List[Dict], path: Path):
    fields = ["problem_key", "problem", "category", "config_key", "config",
              "optimal", "success", "cost", "steps", "expanded", "generated",
              "evaluated", "search_time_s", "total_time_s", "error"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fields})


def _fmt(value, spec="", na="—"):
    if value is None:
        return na
    try:
        return format(value, spec) if spec else str(value)
    except (TypeError, ValueError):
        return str(value)


def write_markdown(rows: List[Dict],
                   plans_by_problem: Dict[str, List[str]],
                   path: Path):
    """Emit a Markdown report grouped by problem."""
    by_problem: Dict[str, List[Dict]] = {}
    order: List[str] = []
    for row in rows:
        if row["problem_key"] not in by_problem:
            order.append(row["problem_key"])
            by_problem[row["problem_key"]] = []
        by_problem[row["problem_key"]].append(row)

    out: List[str] = []
    out.append("# Evaluación de Fast Downward sobre el dominio de navegación UFV\n")
    out.append(
        "Este informe compara cuatro configuraciones de búsqueda sobre un "
        "conjunto representativo de problemas del dominio. Las tres primeras "
        "son óptimas (coste mínimo garantizado) y se diferencian por la "
        "fuerza del heurístico; la cuarta es satisficing (rápida pero "
        "sin garantía de optimalidad)."
    )
    out.append("")
    out.append("| Configuración | Algoritmo | Heurístico | Óptimo |")
    out.append("|---------------|-----------|------------|--------|")
    for c in CONFIGS:
        out.append(f"| `{c['search']}` | A* o lazy greedy | "
                   f"{c['label']} | {'✓' if c['optimal'] else '✗'} |")
    out.append("")

    # Aggregate summary table — rollup across all problems per config.
    agg: Dict[str, Dict[str, float]] = {}
    n_problems_ok: Dict[str, int] = {}
    for c in CONFIGS:
        agg[c["key"]] = {"expanded": 0, "generated": 0, "search_time_s": 0.0}
        n_problems_ok[c["key"]] = 0
    for row in rows:
        if not row["success"]:
            continue
        ck = row["config_key"]
        for metric in ("expanded", "generated", "search_time_s"):
            v = row.get(metric)
            if v is not None:
                agg[ck][metric] += float(v)
        n_problems_ok[ck] += 1

    out.append("## Resumen agregado\n")
    out.append("Totales sumados sobre los problemas resueltos por cada configuración.\n")
    out.append("| Configuración | Resueltos | Σ Expanded | Σ Generated | Σ Search time (s) |")
    out.append("|---------------|-----------|------------|-------------|-------------------|")
    for c in CONFIGS:
        a = agg[c["key"]]
        out.append(
            f"| {c['label']} | {n_problems_ok[c['key']]}/{len(PROBLEMS)} | "
            f"{int(a['expanded'])} | {int(a['generated'])} | "
            f"{a['search_time_s']:.2f} |"
        )
    out.append("")

    # Per-problem detail
    for prob_key in order:
        prob_rows = by_problem[prob_key]
        prob = prob_rows[0]
        out.append(f"## {prob['problem']}\n")
        out.append(f"Categoría: `{prob['category']}`\n")

        plan = plans_by_problem.get(prob_key, [])
        if plan:
            out.append("**Plan óptimo** (A* + LM-Cut):")
            out.append("```")
            for i, act in enumerate(plan, 1):
                out.append(f"  {i:2d}. {act}")
            out.append("```\n")

        out.append("| Configuración | Coste | Pasos | Expanded | Generated | Search (s) |")
        out.append("|---------------|-------|-------|----------|-----------|------------|")
        for r in prob_rows:
            if not r["success"]:
                out.append(
                    f"| {r['config']} | — | — | — | — | FAIL: "
                    f"{(r['error'] or '')[:40]} |"
                )
                continue
            out.append(
                f"| {r['config']} | {_fmt(r['cost'])} | {_fmt(r['steps'])} | "
                f"{_fmt(r['expanded'])} | {_fmt(r['generated'])} | "
                f"{_fmt(r['search_time_s'], '.2f')} |"
            )
        out.append("")

    path.write_text("\n".join(out), encoding="utf-8")


def write_plot(rows: List[Dict], path: Path) -> bool:
    """Bar chart of expanded states per problem, grouped by config."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    problems_in_order: List[str] = []
    seen = set()
    for r in rows:
        if r["problem_key"] not in seen:
            seen.add(r["problem_key"])
            problems_in_order.append(r["problem_key"])

    configs_in_order: List[tuple] = []
    seen = set()
    for r in rows:
        if r["config_key"] not in seen:
            seen.add(r["config_key"])
            configs_in_order.append((r["config_key"], r["config"]))

    data: Dict[tuple, int] = {}
    for r in rows:
        if r["success"] and r["expanded"] is not None:
            data[(r["problem_key"], r["config_key"])] = r["expanded"]
    if not data:
        return False

    n_problems = len(problems_in_order)
    n_configs = len(configs_in_order)

    fig, ax = plt.subplots(figsize=(max(14, n_problems * 1.3), 6))
    bar_width = 0.8 / n_configs
    for i, (ckey, clabel) in enumerate(configs_in_order):
        vals = [max(data.get((p, ckey), 0), 1) for p in problems_in_order]
        offsets = [j + (i - n_configs / 2 + 0.5) * bar_width for j in range(n_problems)]
        ax.bar(offsets, vals, bar_width, label=clabel)

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


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    planner = FastDownwardPlanner(timeout=PER_RUN_TIMEOUT)
    rows: List[Dict] = []
    plans_by_problem: Dict[str, List[str]] = {}

    total = len(PROBLEMS) * len(CONFIGS)
    print(f"Running {total} experiments ({len(PROBLEMS)} problems × {len(CONFIGS)} configs)")

    for p_idx, problem in enumerate(PROBLEMS, 1):
        for c_idx, config in enumerate(CONFIGS, 1):
            run_idx = (p_idx - 1) * len(CONFIGS) + c_idx
            print(f"  [{run_idx:3d}/{total}] {problem['key']:22s} "
                  f"{config['key']:14s} ... ", end="", flush=True)
            row = run_one(problem, config, planner)
            rows.append(row)
            if row["success"]:
                exp_s   = f"{row['expanded']:>6}"  if row["expanded"]      is not None else "  --  "
                gen_s   = f"{row['generated']:>6}" if row["generated"]     is not None else "  --  "
                time_s  = f"{row['search_time_s']:.2f}" if row["search_time_s"] is not None else " -- "
                print(
                    f"OK   cost={row['cost']:>4} steps={row['steps']:>3} "
                    f"exp={exp_s} gen={gen_s} time={time_s}s"
                )
                if config["key"] == "astar_lmcut":
                    plans_by_problem[problem["key"]] = row["plan"]
            else:
                print(f"FAIL  {row['error']}")

    md_path = OUTPUT_DIR / "planner_evaluation.md"
    csv_path = OUTPUT_DIR / "planner_evaluation.csv"
    png_path = OUTPUT_DIR / "planner_evaluation_expanded.png"

    write_csv(rows, csv_path)
    write_markdown(rows, plans_by_problem, md_path)
    ok_plot = write_plot(rows, png_path)

    print("")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    if ok_plot:
        print(f"Wrote {png_path}")
    else:
        print("Skipped PNG chart (matplotlib not available).")


if __name__ == "__main__":
    main()

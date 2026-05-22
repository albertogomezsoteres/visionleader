# Planner test set (campus routing problems)

A custom suite of 12 hand-authored PDDL problems used to benchmark the symbolic
planner (Fast Downward) on the routing situations the campus assistant must handle:
same-floor walks, single and multi floor moves, the two independent vertical cores
of building CD, cross-building routes with an outdoor hop, hurry mode, and a closure
that forces a replan.

## Where the problems live

The problem files stay next to the PDDL domain, in `pddl/problems/evaluation/`,
where `experiments/planner/evaluate_planner.py` reads and regenerates them. This
folder documents and indexes the suite: the manifest describes each problem and
`dataset_hashes.json` lets a held copy be verified byte for byte. Every problem is
solved against the shared domain `pddl/domain.pddl`.

## Contents

- `manifest.csv`: one row per problem.
- `dataset_hashes.json`: SHA-256 of each problem file.

## manifest.csv columns

| Column | Meaning |
|-|-|
| `problem_id` | Short identifier of the problem. |
| `filename` | Problem file under `pddl/problems/evaluation/`. |
| `category` | One of `intra-g`, `intra-cd`, `hybrid`, `special`. |
| `origin` | Start location, the `(at user X)` fact in `:init`. |
| `destination` | Goal location, the `(at user Y)` fact in `:goal`. |
| `description` | The routing situation the problem exercises. |

## Categories

- `intra-g`: routes inside building G (same floor, one floor, two floors).
- `intra-cd`: routes inside building CD, including its two independent vertical cores.
- `hybrid`: cross-building routes that mix indoor walks with an outdoor hop.
- `special`: hurry mode and a closure that forces a replan.

## Reproducibility

The suite is solved by `experiments/planner/evaluate_planner.py` against the LM-Cut
optimal search and two baselines. The 12 problems are fixed on disk so the benchmark
is reproducible, and the hashes here pin their exact bytes.

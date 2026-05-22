# Planner experiment

This benchmark validates the Fast Downward planner that computes the routes. It
confirms the planner solves every realistic campus route quickly, and it justifies
the chosen search configuration by comparing it against two baselines. It runs
locally in Docker.

## Test set

The 12 hand-written PDDL problems are in `pddl/problems/evaluation/` and described
in `data/planner/`. They cover the cases the assistant must handle: same-floor
walks, single and multi floor moves, the two separate elevator-and-stairs cores of
building CD, cross-building routes with an outdoor hop, hurry mode, and a closure
that forces a replan. Every problem is solved against the shared domain
`pddl/domain.pddl`.

## Search configurations

Each problem is solved with three Fast Downward configurations:

- `astar(lmcut())`: A* with the LM-Cut heuristic. Optimal, and the configuration
  used by the system.
- `astar(blind())`: A* with no heuristic. Also optimal, included as the worst case
  to measure how much search effort LM-Cut saves.
- `lazy_greedy([ff()])`: greedy search with the FF heuristic. Fast, but with no
  guarantee of an optimal plan.

## Run

```
python experiments/planner/evaluate_planner.py
```

It solves the 12 problems with the 3 configurations (36 runs) and writes the
per-run metrics to `experiments/planner/results/planner_evaluation.csv`. Requires
Docker with the `fast-downward` image available locally.

## Outcome

All three configurations solve all 12 problems. A* with LM-Cut expands 125 states
in total, about 75 times fewer than blind A* (9,433), and every plan is optimal.
Greedy search is comparably fast but returns a more costly plan on 4 of the 12
problems. LM-Cut is therefore the configuration used by the system.

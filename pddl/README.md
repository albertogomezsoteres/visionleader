# PDDL planning layer

This is the symbolic heart of the navigation system. The planner reads this model
and works out the route from one place to another across campus, room by room and
building to building, with a guarantee that the route it returns is the shortest
one under the cost model. Everything the planner needs is here: one domain file and
the problem files used to test it.

## Contents

| Path | What it is |
|-|-|
| `domain.pddl` | The `campus-navigation` domain: the types, predicates, actions and costs that describe how a person can move around. |
| `problems/examples/` | Two small problems written by hand, kept as easy-to-read examples of the format. |
| `problems/evaluation/` | The 12 problems used by the planner benchmark. |

When the app is running, the planner does not read these problem files. On each
request `HierarchicalPDDLConverter` builds a new problem on the fly and writes it to
a temporary file. The files here are for documentation, manual testing and the
benchmark.

## Domain

`domain.pddl` (`campus-navigation`) describes the whole campus with a single model:
moving room by room inside a building, plus the `outdoor_walk` action that crosses
from one building to another. It has two kinds of object, `person` and `location`,
and a single `user`. Whether a building has an elevator or stairs is stated in the
problem file rather than in the domain, so the same domain works for every building.

### Actions and costs

Each cost is roughly the seconds of effort the step takes. The planner adds them up
(`total-cost`) and looks for the cheapest route.

| Action | Cost | When it applies |
|-|-|-|
| `walk` | `(distance u1 u2)` | the two points share a hallway and the destination is open |
| `verify_elevator` | 5 | check the elevator from a photo before using it |
| `use_elevator` | 15 | move between floors, once the elevator has been checked |
| `validate_stairs` | 5 | check the stairs from a photo; required in both modes |
| `climb_stairs_accessible` | 30 | go up by stairs, normal mode |
| `descend_stairs_accessible` | 25 | go down by stairs, normal mode |
| `climb_stairs_fast` | 12 | go up by stairs, hurry mode |
| `descend_stairs_fast` | 8 | go down by stairs, hurry mode |
| `outdoor_walk` | `(distance_outdoor u1 u2)` | walk outdoors between two building entrances |

The costs are set on purpose: in normal mode the elevator comes out cheaper than
the stairs, but in hurry mode a short climb is cheaper by stairs. Either way the
user has to check the stairs from a photo before climbing, so that safety step is
never skipped; only the cost of the climb changes.

### Predicates and fluents

- `(at ?p ?u)`: where the user is.
- `(open ?u)`: whether the room is currently open. A room without this fact is treated as closed and the planner routes around it, which is how a live closure takes effect.
- `(is_elevator ?u)`, `(is_stairs ?u)`: what kind of point this is.
- `(elevator_verified ?u)`, `(stairs_verified ?u)`: set once a photo has confirmed the elevator or stairs, so the planner only uses them after a check.
- `(hurry_mode)`: a simple on/off flag; when it is set, the stair costs drop.
- Connections: `(hallway_connected …)`, `(elevator_connected …)`, `(stairs_up_connected …)`, `(stairs_down_connected …)`, `(outdoor_connected …)`.
- Numbers: `(total-cost)`, the value being minimised, and `(distance …)` / `(distance_outdoor …)`, the length in metres of each step.

## How problems are generated

`src/navigation/hierarchical_pddl_converter.py` builds a problem for every routing
request. It reads two files:

- `config/campus_topology.json`: the buildings, floors and rooms, the indoor links (`local_connections`) and the links between buildings (`connections`), each with its distance in metres.
- `config/closed_rooms.json`: the list of closed rooms, read again on every request, so closing a room reroutes the next route with no restart.

When the start and the destination are in different buildings, the converter
includes the rooms of both and the `(outdoor_connected …)` links between their
entrances, so a single planner call finds the whole route, door to door. Room names
that are unique across campus (`classroom_g_1_4`, `ai_lab`, `entrance_2`) are used
as they are; names that repeat between buildings (`elevator`, `stairs`, `bathroom`)
get a building-and-floor prefix (`elevator_g_f0`, `stairs_cd_fm1`) so two buildings
never clash in the same problem.

## Example problems

- `problems/examples/problem_g_intra_example.pddl`: inside one building, from `entrance_2` to `classroom_g_1_4` in building G.
- `problems/examples/problem_g_to_cd_example.pddl`: across buildings, from `classroom_g_1_4` (G) to the `gym` (CD), mixing an indoor walk with an outdoor hop.

The 12 problems in `problems/evaluation/` are the benchmark set: same-floor walks,
moves across one or more floors, building CD's two separate elevator-and-stairs
cores, cross-building routes, hurry mode and a closure that forces a replan. The
benchmark that runs them is in `experiments/planner/`.

## Run a problem manually

With the `fast-downward:latest` Docker image available locally, from the repository
root:

```bash
docker run --rm -v "$(pwd)/pddl:/pddl" fast-downward:latest \
  /pddl/domain.pddl /pddl/problems/examples/problem_g_intra_example.pddl
```

The search used is A* with the LM-Cut heuristic, which always returns the shortest
route.

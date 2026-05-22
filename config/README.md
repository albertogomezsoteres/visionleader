# Configuration

The JSON files the system reads at runtime, plus the catalogues the experiments use.
None of them is code: the behaviour of the planner and the assistant is driven by
their contents.

| File | Role | Read by |
|-|-|-|
| `campus_topology.json` | The campus graph: buildings, floors, rooms, edges and distances. | The PDDL problem generator and the planner. |
| `closed_rooms.json` | Which rooms are currently closed. | Every planning request. |
| `campus_places.json` | Display names, room types and hint text. | The spoken-step narration (TTS). |
| `prompts.json` | The catalogue of vision-language prompts. | The backend and the VLM experiments. |
| `models.json` | The catalogue of candidate vision models. | The VLM experiments only. |

## campus_topology.json

The authoritative campus graph and the most important file here. It declares the
buildings and floors, every location, the indoor edges (`local_connections`) and the
edges between buildings (`connections`), each with its distance in metres, plus the
`functional_locations` (cafeteria, gym, and so on). On every routing request the
problem generator reads this file to build the PDDL problem, so the planner reasons
over exactly this graph. It owns the topology and the metric distances; routing
decisions are made by the planner, never hard-coded elsewhere.

## closed_rooms.json

The live availability state: a list of rooms that are currently closed. It is read
again on every planning request, so editing it reroutes the next route with no
restart. This is what makes the dynamic replanning demo work. Rooms whose name
repeats between buildings (elevator, stairs, bathroom) need an explicit floor.

## campus_places.json

The display layer: human-readable names, room types and hint text. It is read while
turning a plan into spoken instructions, to make them clearer for the user. It is
never used for routing, so the topology and the wording stay separate concerns.

## prompts.json

The catalogue of prompts the vision-language model runs (room plates, directory
signs, elevator state, stair direction, and so on). It is the runtime catalogue read
by the backend. Each prompt turns an image into a PDDL atom or a
state value the planner can use.

## models.json

The catalogue of the candidate vision models (the PaliGemma 2 and Gemma 4 variants).
It is read only by the VLM experiment notebooks, which evaluate the listed models;
the assistant itself does not read this file.

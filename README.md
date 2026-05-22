# Neuro-Symbolic Campus Navigation System

**VisionLeader UFV** is an assistive indoor navigation system for visually impaired
users, developed as a final degree project (FDP) at Universidad Francisco de Vitoria.
It combines on-device **speech-to-text**, a **vision-language model** for reading
campus signage, and **automated planning** over a **PDDL** domain, coordinated by a
finite-state conversation agent. The user states a destination by voice; the system
transcribes it, grounds visual evidence from the camera into **symbolic predicates**,
and returns spoken, turn-by-turn directions to an optimal route.

## Architecture

The system is **neuro-symbolic**. Neural models handle the unstructured inputs they
are good at (noisy audio, campus photos), while a classical symbolic planner provides
the guarantees they cannot: optimality, completeness and explainability over a
structured world model. The neural components sit only at the perceptual edges of the
loop; the route and the dialogue state are reasoned about symbolically.

| Layer | Component | Where it runs |
|-|-|-|
| Speech recognition | On-device ASR: Whisper tiny (q5_0, whisper.cpp) | Android device |
| Perception | Vision-language model (Gemma 4 E4B-it) grounding signage into PDDL atoms | Colab GPU, served from `deploy/` |
| Reasoning | Automated planner: Fast Downward, A* with the LM-Cut heuristic | Docker |
| Knowledge | PDDL domain (`pddl/domain.pddl`) and campus graph (`config/campus_topology.json`) | loaded by the backend |
| Orchestration | Finite-state conversation agent | FastAPI backend |

The interface between the two paradigms is structured textual output: the
vision-language model emits PDDL atoms such as `(at user classroom_g_1_4)`, or a
discrete state label such as an elevator's open or closed status, in a closed
vocabulary defined by the campus topology and parsed deterministically. This forces
the neural side to commit to an unambiguous symbolic claim that the planner can act
on or reject. Two properties follow: the route is provably optimal under the metric
cost model (A* with the admissible LM-Cut heuristic), and the system adapts to live
state, since editing the room-availability file reroutes the next planning request
with no retraining and no restart.

## Pipeline (one turn)

1. The Android client records audio and runs **on-device ASR** (Whisper) to produce a transcript.
2. The transcript is posted to the FastAPI backend, where the **finite-state agent** updates the dialogue state and selects the next action.
3. When visual evidence is required, the client captures an image and the **vision-language model** grounds it into a symbolic predicate (a PDDL atom in the topology's vocabulary).
4. The agent generates a **PDDL problem** from the campus graph and the current state, and **Fast Downward** solves it (A* with LM-Cut) for an optimal route.
5. The plan is compacted into spoken instructions and returned for on-device text-to-speech.

## Documentation

Detailed docs are in [`docs/`](docs/):

- [Architecture](docs/architecture.md): components, technologies and the per-turn flow.
- [Setup](docs/setup.md): install and run the backend, vision model, planner and app.
- [Experiments](docs/experiments.md): how each component was chosen and validated.
- [Data](docs/data.md): the test sets, and what is kept local for privacy.
- [Reproducibility](docs/reproducibility.md): seeds, hardware and how to rerun.

## Repository layout

```text
tfg/
├── src/            Python backend: the FastAPI API and the navigation/planning logic
├── mobile_app/     Flutter client (Android)
├── pddl/           PDDL planning domain and the problem files
├── config/         Campus graph, room availability, model registry
├── experiments/    The experiments that selected each component (one folder each)
├── data/           The test sets the experiments consume
├── docs/           Detailed documentation (architecture, setup, experiments, ...)
├── deploy/         Colab notebook that serves the vision-language model over a tunnel
├── docker/         Fast Downward Docker image
├── scripts/        start_api, stop_api, close_room, regenerate_topology
├── requirements.txt
└── .env.example
```

Each of `experiments/`, `data/` and `pddl/` has its own README with the detail.

## Prerequisites

- Python 3.10 or newer
- Flutter SDK (the client targets Android)
- Docker, with the `fast-downward:latest` image, for the planner
- A Colab GPU runtime to serve the vision-language model

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in the values
```

The backend reads these from `.env`:

| Variable | Purpose |
|-|-|
| `COLAB_API_URL` | Base URL of the tunnel to the Colab vision server (no trailing slash). |
| `GOOGLE_MAPS_API_KEY` | Google Maps Directions key, used for the outdoor segment between buildings. |
| `TELEMETRY_JSONL_PATH` | Optional. Where to write the telemetry log read by the end-to-end validation. |

The Colab notebook uses its own secrets (`HF_TOKEN` for the gated Gemma model and
`NGROK_TOKEN` for the tunnel), set in Colab rather than in `.env`.

## Running

**Backend**

```bash
python scripts/start_api.py     # API on http://localhost:8000, OpenAPI docs at /docs
python scripts/stop_api.py      # stop it
```

**Vision-language model.** Open `deploy/colab_inference_server.ipynb` in Colab, run
the cells, and copy the printed tunnel URL into `.env` as `COLAB_API_URL`.

**Mobile client**

```bash
cd mobile_app
flutter pub get
flutter run
```

Point the client at the backend with `--dart-define=API_BASE_URL=http://<host>:8000`,
or edit `mobile_app/lib/core/app_config.dart`.

**Planner.** The backend invokes Fast Downward in Docker, so the `fast-downward:latest`
image must be available locally. Without it, routes that change floor or building
cannot be computed.

## Dynamic replanning (demo)

Room availability is part of the planning state, so closing a room reroutes the next
request with no restart:

```bash
python scripts/close_room.py close G elevator --floor 0
python scripts/close_room.py open  G elevator --floor 0
python scripts/close_room.py list
```

## Experiments and datasets

Every component was selected and validated through its own set of experiments
(speech recognition, vision-language grounding, planner search, and end-to-end
integration), and the assembled system was then validated end to end. See
`experiments/` for the protocols and results, and `data/` for the test sets.

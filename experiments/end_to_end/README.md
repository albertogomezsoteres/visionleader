# End-to-end validation

Each component of the system was tested on its own (see the other folders under
`experiments/`). This experiment checks them working together as one system: it
runs the whole assistant on a few scripted scenarios and confirms that the parts
connect correctly, from the spoken request to the door-to-door route, with no manual
help in between.

## The three scenarios

The three scenarios are a small set chosen so that, between them, they exercise the
VLM prompts the assistant uses while navigating (room plate, directory sign,
elevator state, stair direction, service plate), all three ways of moving (elevator,
stairs, and an outdoor walk between buildings), and the main branches of the
conversation.

| Scenario | Route | What it exercises |
|-|-|-|
| S1 | `entrance_2` (G) to the `cafeteria` (CD) | Voice origin and a spoken destination given by name, a cross-building route with an outdoor GPS leg, and arrival checked by a `service_plate` photo. |
| S2 | `classroom_g_0_1` to `classroom_g_1_4` (G) | Origin read from a room-plate photo (`room_plate`), an elevator checked mid-route (`elevator_state`), and arrival checked against the expected room code. |
| S3 | `directory_sign_g_0` to `classroom_g_1_5` (G) | Origin read from a directory sign (`directory_sign`), hurry mode set by voice (so the planner picks the stairs), the stairs checked mid-route (`stair_direction`), and arrival checked by room code. |

## How it is measured

The backend writes a line of structured telemetry for every event of a run (the
transcription, each VLM call, the planner result, every state change, the spoken
reply, and so on), tagged with the scenario and turn it belongs to, into a JSONL
log. That log is the record of the run.

- `scenarios.json` is the ground truth: for each turn it states what the user says, which keywords must be transcribed, which state change must happen, and which VLM prompt must run with which result.
- `reference_plans/` holds the optimal plan for each scenario, computed once in advance, so the route the assistant produces can be compared against it.
- `scripts/build_validation_csv.py` reads the log, scores it against the ground truth and the reference plans, and writes three CSVs (one row per turn, one per scenario, and one overall) along with the headline summary below.

## Run

```
python experiments/end_to_end/scripts/precompute_reference_plans.py
python experiments/end_to_end/scripts/build_validation_csv.py
```

The first computes the reference plans and needs Docker with the `fast-downward`
image. The second reads `logs/e2e_backend.jsonl` and writes the CSVs into
`results/`.

## Results

| Metric | Result |
|-|-|
| Scenarios completed | 3 / 3 |
| Validation checks passed | 14 / 14 |
| STT keyword accuracy | 11 / 11 |
| STT mean WER | 0.034 |
| FSM transitions correct | 16 / 16 |
| VLM format validity | 100% |
| VLM grounding accuracy | 100% |
| VLM verification checks passed | 7 / 7 |
| Planner solved | 3 / 3 |
| Routes matching the reference plan | 3 / 3 |
| Instructions delivered | 7 / 7 |
| Mean end-to-end latency per turn | 3552 ms |

All three scenarios complete door to door. The WER is not zero because Whisper adds
minor formatting (capitalisation, punctuation) that the keyword check ignores; every
keyword the planner relies on is transcribed correctly. The 22 PDDL actions across
the three routes are merged into 7 spoken steps, one per meaningful leg.

## Files

| Path | What it is |
|-|-|
| `scenarios.json` | The three scenarios and their ground truth. |
| `reference_plans/` | The optimal plan per scenario, precomputed. |
| `logs/e2e_backend.jsonl` | The saved telemetry log of the validation run. |
| `scripts/` | `precompute_reference_plans.py` and `build_validation_csv.py`. |
| `results/` | The three metric CSVs. |

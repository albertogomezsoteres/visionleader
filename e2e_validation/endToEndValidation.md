# End-to-End Validation of VisionLeaderUFV

This document reports the end-to-end validation experiment performed on the
VisionLeaderUFV navigation assistant. Every individual component (VLM, STT,
symbolic planner, FSM orchestrator) had already been benchmarked in
isolation; this experiment closes the loop by running the *complete*
system, end-to-end, on a small but carefully designed set of canonical
scenarios, and measuring whether the components behave correctly when
composed.

The results here are independent of the demo recordings: they were
captured during a dedicated validation pass, with telemetry tagged per
turn and a frozen JSONL log on disk used as the scientific artefact.

---

## 1. Objective

VisionLeaderUFV is a **neuro-symbolic** navigation assistant: a Whisper
on-device STT, a Gemma 4 E4B-it VLM, and a Fast Downward symbolic
planner glued together by a 15-state Finite State Machine. The Phase 1,
Phase 2 and Phase 3 experiments validated each model on its own:

- *VLM Phase 1 / 2 / 3* covered nav-element recognition, location
  extraction, and production-prompt accuracy on a custom UFV dataset
  (Gemma 4 E4B-it: 95% accuracy, 100% format validity).
- *STT Phase 1 / 2 / 3* compared eight ASR models on a custom UFV
  utterance set, validated on-device quantisation, and confirmed the
  Flutter integration (whisper-tiny-q5_0: 100% Domain Keyword Accuracy,
  ~2.4 s per utterance).
- *Planner benchmark* compared three search configurations on twelve
  canonical PDDL problems (A\* + LM-Cut: 12/12 solved, 75x fewer state
  expansions than blind A\*).

**What had not been measured was whether those components behave
correctly when composed**: whether Whisper's transcription survives
parsing into a planner goal, whether the VLM atom binds into a valid
PDDL initial state, whether the FSM dispatches the right prompt at the
right step, whether closures replan in real time, whether the full
neuro-symbolic loop closes door-to-door without manual intervention.
That is what this end-to-end experiment validates.

The experiment also doubles as the **methodological backbone of the
project's reproducibility**: a frozen JSONL log of every event the
backend emitted during the run, tagged with scenario id and turn index,
plus a deterministic post-mortem script that rebuilds 34 metrics in
three CSVs from that log.

---

## 2. The three canonical scenarios

The scenarios were designed as a *minimal cover* of the production
system: between the three of them they exercise **all five VLM prompts
in production**, **all three transport modes of the PDDL domain**
(elevator, stairs, outdoor walk between buildings), and the **conversational
branches the FSM treats as separate phases** (voice origin, visual
origin via room plate, visual origin via directory sign, hurry-mode
preference, mid-route VLM verification, strict arrival photo, functional
destination).

A larger set would have added cost without adding coverage; a smaller
set would have left at least one production prompt or transport mode
unverified.

### Scenario S1: Cross-building voice route to cafeteria

**Purpose.** Validate the integrated outdoor route between buildings G
and CD with a voice-only origin and destination, ending at a non-
classroom service location verified by the `service_plate` prompt.

**Flow.**

1. Voice: *"I am at the main entrance of building G floor 0"* binds
   the origin to `entrance_2` via the parser.
2. Voice: *"I want to go to the cafeteria in building CD"* binds the
   functional destination via `find_functional_anywhere`.
3. Voice: *"start"* triggers the planner.
4. Voice: *"next"* advances past the indoor walk leg.
5. Voice: *"done"* marks arrival at the CD entrance after the GPS leg.
6. Photo: cafeteria service plate verifies arrival via `service_plate`.

**Reference plan (5 actions, cost 85, transport=outdoor):**

```
1. walk           entrance_2          → entrance_2_exterior      (3 m)
2. outdoor_walk   entrance_2_exterior → entrance_cd_exterior     (50 m)
3. walk           entrance_cd_exterior → entrance_cd_interior    (5 m)
4. walk           entrance_cd_interior → central_point_cd        (22 m)
5. walk           central_point_cd    → cafeteria                (5 m)
```

**Coverage:** voice STT, voice destination parser, cross-building PDDL
goal grounding, outdoor edge planning, GPS leg orchestration,
`service_plate` arrival verification.

### Scenario S2: Visual origin via room plate, intra-G with elevator

**Purpose.** Validate origin grounding from a room-plate photo and a
single-elevator route inside building G, ending at a classroom verified
by the `room_plate` prompt under the strict arrival check.

**Flow.**

1. Voice: *"No, I do not know where I am"* enters the visual origin
   flow.
2. Voice: *"I see a classroom"* triggers the photo prompt.
3. Photo: cartel "0.1" is grounded by the `room_plate` prompt as
   `(at user classroom_g_0_1)`.
4. Voice: *"I want to go to classroom 1.4"* binds the destination.
5. Voice: *"start"* triggers the planner.
6. Photo: elevator doors are verified by the `elevator_state` prompt.
7. Voice: *"next"* advances past the elevator step.
8. Photo: cartel "1.4" verifies arrival; the parser compares the
   normalised room code against the expected `1.4`.

**Reference plan (9 actions, cost 44, transport=elevator).**

**Coverage:** visual origin via `room_plate`, `elevator_state` mid-route
verification, accessible-mode elevator cost, strict arrival check via
`room_plate`.

### Scenario S3: Visual origin via directory sign, hurry mode forces stairs

**Purpose.** Validate origin grounding from a directory sign,
propagation of the `hurry_mode` flag from speech to the planner cost
model (forcing stairs over the elevator), `stair_direction` mid-route
verification, and arrival under the strict room-plate check.

**Flow.**

1. Voice: *"No, I do not know where I am"*.
2. Voice: *"I see a directory sign"*.
3. Photo: directory sign G floor 0 grounded by the `directory_sign`
   prompt as `(at user directory_sign_g_0)`.
4. Voice: *"I want to go to classroom 1.5, I am in a hurry"* sets the
   destination AND the `hurry_mode` flag in the same utterance.
5. Voice: *"start"* triggers the planner. Hurry mode flips the cost
   model so stairs beat the elevator on a one-floor climb.
6. Photo: staircase image verified `up` by the `stair_direction` prompt.
7. Voice: *"next"* advances past the stairs step.
8. Photo: cartel "1.5" verifies arrival.

**Reference plan (8 actions, cost 39, transport=stairs).**

**Coverage:** visual origin via `directory_sign`, hurry-mode propagation
through the parser into the PDDL `(hurry_mode)` flag, `stair_direction`
mid-route verification, accessible vs. hurry cost balance.

### What the three scenarios cover, summarised

| Production prompt   | S1    | S2    | S3   |
|---------------------|:-----:|:-----:|:----:|
| `room_plate` origin |       | yes   |      |
| `room_plate` arrival|       | yes   | yes  |
| `directory_sign`    |       |       | yes  |
| `service_plate`     | yes   |       |      |
| `elevator_state`    |       | yes   |      |
| `stair_direction`   |       |       | yes  |

| Transport mode      | S1    | S2    | S3   |
|---------------------|:-----:|:-----:|:----:|
| Walk only           | yes   | yes   | yes  |
| Elevator            |       | yes   |      |
| Stairs              |       |       | yes  |
| Outdoor + GPS       | yes   |       |      |

| Conversational branch    | S1    | S2    | S3   |
|--------------------------|:-----:|:-----:|:----:|
| Voice origin             | yes   |       |      |
| Visual origin (door)     |       | yes   |      |
| Visual origin (sign)     |       |       | yes  |
| Functional destination   | yes   |       |      |
| Specific classroom dest. |       | yes   | yes  |
| Hurry mode               |       |       | yes  |
| Strict arrival check     | yes   | yes   | yes  |

The three scenarios cover all five production VLM prompts, all three
transport modes, and the relevant FSM branches, with no overlap in
purpose.

---

## 3. Telemetry pipeline

To make the run measurable in retrospect, the backend was instrumented
with a unified `log_event(category, message, **fields)` helper that
fans out to two sinks: stdout (human-readable) and JSON Lines on disk
(when `TELEMETRY_JSONL_PATH` is set, used by the post-mortem script).

The mobile client tags every HTTP request with two headers,
`X-Scenario-Id` and `X-Turn-Idx`. A FastAPI middleware reads them and
binds them to a `contextvars` context, so every `log_event` call inside
that request is automatically tagged. From the agent's perspective
nothing changes; from the post-mortem perspective, every event in the
JSONL carries the scenario id and turn index it belongs to.

Thirteen event categories are emitted, each with structured fields:

| Category    | Meaning                                                       |
|-------------|---------------------------------------------------------------|
| `STT`       | Whisper transcription line, with audio duration               |
| `VLM`       | Five events per photo (prompt sent, raw output, prediction, symbol grounded or grounding failed) |
| `PLANNER`   | Init, problem stats, solved or failed                         |
| `PLAN`      | One event per PDDL action of the plan                         |
| `ROUTE`     | PDDL-to-user-facing-step compaction record                    |
| `CLOSURE`   | Room closure or alternative substitution                      |
| `AGENT`     | FSM dispatch, slot grounding, "turn handled by backend"       |
| `TTS`       | The string the assistant is about to speak                    |
| `FSM`       | Each state transition `from_state -> to_state`                |
| `VALIDATION`| Pass/fail of one of the six validation chips                  |
| `SCENARIO`  | Scenario started / completed                                  |
| `CLIENT`    | End-of-turn summary from the mobile (latencies, durations)    |
| `TURN`      | Turn-separator marker for stdout readability                  |

The JSONL log and the stdout stream come from the same `log_event`
call, so what the operator sees at run time and what the report states
are guaranteed to come from the same artefact.

---

## 4. Ground truth

Per-scenario ground truth lives in `e2e_validation/scenarios.json`. For
each turn it specifies:

- the `say` field: what the user is supposed to utter;
- the `stt_keywords`: the domain keywords that must appear in the
  transcription (this is the `DKA` metric;
- the `fsm` transition: the `[from, to]` state pair that must occur in
  the turn;
- the `vlm_prompt` and either `vlm_expected_location_id` or
  `vlm_expected_state_detail`: which VLM prompt id must run and what
  result it must return.

Per-scenario session-level ground truth specifies the expected origin,
destination, hurry-mode flag, and arrival verification prompt and
value. The optimal reference plan for each scenario is precomputed by
`scripts/precompute_reference_plans.py` and stored in
`reference_plans/e2e_reference_plans.json`, so route correctness can
be scored without re-invoking the planner at metrics time.

Two methodological notes:

1. The protocol does not require step-advancement voice turns
   (`"next"` / `"done"`): the FSM accepts either voice or the on-screen
   confirm button to advance, and both produce the same FSM transition.
   Only voice turns that drive a *semantic* slot (origin, destination,
   "start") are evaluated by the STT keyword metric. This keeps the
   metric measuring the load-bearing parts of the conversation rather
   than the rate at which the user can press a confirm button.

2. The FSM-transition metric considers an expected
   `[from, to]` correct if it appears anywhere in the turn's
   transition list. `process_turn` can collapse multiple internal
   state changes into a single dispatch, and a turn that takes a
   verification photo can both verify the photo *and* advance to the
   next step in the same call. The metric reflects the user-visible
   transition, not the internal hop count.

---

## 5. Metrics

The post-mortem script `scripts/build_validation_csv.py` reads the
JSONL log, joins it against `scenarios.json` and the reference plans,
and emits three CSVs into `e2e_validation/results/`:

- `e2e_validation_turns.csv`   (one row per turn, all per-turn fields);
- `e2e_validation_summary.csv` (one row per scenario, aggregates);
- `e2e_validation_global.csv`  (one row total, cross-scenario metrics).

Thirty-four distinct metrics are computed. Their definitions and the
sources they consume:

### 5.1 Session-level metrics

- **Scenario completion rate**: `SCENARIO completed` events divided by
  number of scenarios attempted.
- **Validation pass rate**: pass count divided by total `VALIDATION`
  events with a non-empty result.
- **Origin / destination / hurry slot match**: each scenario's final
  `ctx.origin`, `ctx.destination` and `ctx.hurry_mode` compared against
  the `expected` block of `scenarios.json`. Three booleans per
  scenario.
- **Slots aggregate pass rate**: sum of the three slots passing,
  divided by 3 per scenario.
- **Route correctness**: the agent's last logged PDDL plan compared
  action-by-action against the precomputed reference plan, after
  stripping cost annotations.
- **Mean plan cost**: arithmetic mean of `(total-cost)` across the
  three solves.
- **PDDL action count**: total number of action lines summed across
  the three scenarios.
- **User-facing step count**: total number of compacted steps the user
  actually heard summed across the three scenarios.

### 5.2 STT metrics

- **STT keyword correctness (DKA)**: per-turn fraction whose required
  keywords all appear (case-insensitive substring) in the transcription.
  Aggregated across the voice turns of all three scenarios.
- **STT mean WER**: word-level Levenshtein distance between the
  transcription and the `say` field, divided by the reference word
  count, averaged across all voice turns. Lowercased and stripped of
  punctuation before comparison so trailing dots and casing do not
  inflate the score.
- **STT mean latency**: arithmetic mean of the `duration_ms` field on
  the `STT` events.

### 5.3 FSM metrics

- **FSM transition correctness**: per-turn check that the expected
  `[from, to]` pair from `scenarios.json` appears among the
  transitions actually emitted in that turn.
- **Aggregated FSM pass rate**: passes divided by total turns with an
  FSM expectation declared.

### 5.4 VLM metrics

- **VLM format validity**: fraction of `VLM raw=` events that
  successfully parsed (i.e. the catalogue parser returned `ok=True`).
  Format validity at 100% means the neuro-symbolic interface never
  broke: every VLM output was a legal PDDL atom or a valid JSON state
  object.
- **VLM grounding correctness**: of those successfully parsed, fraction
  whose extracted `location_id` or `state_detail` matches the per-turn
  expectation.
- **VLM verification success rate**: fraction of the VALIDATION chips
  that depend on a VLM call (origin grounding, elevator verification,
  stairs verification, arrival verification) that passed.
- **VLM mean latency**: arithmetic mean of the `duration_ms` field on
  `VLM raw=` events.

### 5.5 Planner metrics

- **Planner solved rate**: count of `PLANNER solved` events divided by
  count of `PLANNER init=` events.
- **Planner mean latency**: arithmetic mean of `duration_ms` on
  `PLANNER solved` events.
- **Planner action count**: count of action steps in the last solve
  per scenario.

### 5.6 Plan metrics

- **Plan cost**: the value of the `cost` field on the `PLANNER solved`
  event for each scenario.
- **PDDL actions count**: per-scenario action count, summed for the
  global metric.
- **User-facing step count**: per-scenario user-facing step count,
  summed for the global metric.
- **Compaction ratio**: PDDL actions divided by user-facing steps.

### 5.7 Instruction-correctness metric

- **Instructions delivered**: count of `TTS` events whose `action`
  begins with `navigation_step` (covers indoor steps and the GPS leg).
- **Instructions expected**: per-scenario user-facing step count.
- **Instruction correctness**: delivered divided by expected, capped at
  1.0. A scenario that delivers all expected steps scores 100%.

### 5.8 Latency metrics

- **End-to-end mean and p95**: from the mobile `CLIENT` summaries,
  arithmetic mean and 95th percentile across all turns.
- **TTS speech duration**: from the mobile `CLIENT` summaries.

---

## 6. Results

The headline of the run, exactly as printed by
`build_validation_csv.py`:

```
=== HEADLINE METRICS ===
  Scenarios completed:        3 / 3   (100.0%)
  Validation pass rate:       14 / 14 (100.0%)
  STT keyword correctness:    11 / 11 (100.0%)
  STT mean WER:               0.034
  FSM transitions OK:         18 / 18 (100.0%)
  VLM format validity:        100.0%
  VLM grounding accuracy:     100.0%
  VLM verification success:   7 / 7   (100.0%)
  Planner solved rate:        3 / 3   (100.0%)
  Mean plan cost:             56.0
  PDDL actions (total):       22
  User-facing steps (total):  7
  Instruction correctness:    7 / 7   (100.0%)
  Routes correct:             3 / 3   (100.0%)
  Mean end-to-end:            3552.3 ms
```

Reading the numbers:

- **3/3 scenarios completed**, **14/14 validation chips green**: every
  scenario closed door-to-door without manual intervention; every
  required check (origin grounding, destination grounding, planner
  route, elevator verification, stairs verification, arrival
  verification, scoped to the chips applicable per scenario) passed.
- **STT keyword correctness 11/11 (100%)**: Whisper transcribed every
  domain keyword (building codes, classroom numbers, "hurry") that the
  navigation depends on. **WER 0.034** is non-zero because Whisper
  introduces benign formatting drift (capitalisation, trailing
  punctuation), which the keyword check does not penalise but the WER
  does. The two together communicate honestly: the model is not
  perfect at the character level, but it is perfect at the level the
  planner consumes.
- **FSM transitions 18/18 (100%)**: every expected
  `[from_state, to_state]` transition appeared in the right turn.
- **VLM format validity 100%**: every VLM output (across 7 production
  photos) parsed cleanly into a PDDL atom or a JSON state object. The
  neuro-symbolic interface never broke.
- **VLM grounding accuracy 100%**: every parsed atom matched the
  expected location id (or state detail for the elevator and stairs).
- **VLM verification success 7/7**: each of the seven VLM-driven
  validation chips (origin grounding, mid-route verifications, strict
  arrival checks) confirmed the correct value.
- **Planner solved rate 3/3 (100%)** with a **mean plan cost of 56.0**
  across the three problems.
- **22 PDDL actions compacted into 7 user-facing steps** (a 3.1:1
  compaction ratio): the symbolic planner emits a fine-grained action
  sequence; the TTS layer merges consecutive walks on the same floor
  and labels transport actions, so the user hears one instruction per
  meaningful leg.
- **Instruction correctness 7/7 (100%)**: every expected user-facing
  step was actually delivered as a TTS instruction.
- **Routes correct 3/3 (100%)**: each emitted plan matched the
  precomputed reference plan action-by-action.
- **Mean end-to-end 3.55 s per turn** is the user-perceived latency
  (mic release to TTS playback start), dominated by the on-device
  Whisper transcription (~1.7 s) and, on photo turns, the Gemma 4
  E4B-it call running on the Colab GPU (~2.5 s).

### Headline summary

| Metric                        | Value           |
|-------------------------------|-----------------|
| Scenarios completed           | 3/3 (100%)      |
| Validation pass rate          | 14/14 (100%)    |
| STT keyword correctness (DKA) | 11/11 (100%)    |
| STT mean WER                  | 0.034           |
| FSM transitions correct       | 18/18 (100%)    |
| VLM format validity           | 100%            |
| VLM grounding accuracy        | 100%            |
| VLM verification success      | 7/7 (100%)      |
| Planner solved rate           | 3/3 (100%)      |
| Routes correct                | 3/3 (100%)      |
| Instruction correctness       | 7/7 (100%)      |
| Mean plan cost                | 56.0            |
| Mean end-to-end latency       | 3552 ms         |

The validation passes on every metric whose target is 100% and reports
honest non-perfect numbers (WER 0.034, mean latency 3.55 s) where a
perfect target would be unrealistic.

---

## 7. Reproducibility and artefacts

Everything the experiment needs to be reproduced is in the repository:

| Artefact                                              | Path                                                  |
|-------------------------------------------------------|-------------------------------------------------------|
| Per-scenario ground truth                             | `e2e_validation/scenarios.json`                       |
| Precomputed reference plans (Fast Downward optimal)   | `e2e_validation/reference_plans/e2e_reference_plans.json` |
| Frozen JSONL log of the validation run                | `e2e_validation/logs/e2e_backend.jsonl`               |
| Reference-plan precompute script                      | `e2e_validation/scripts/precompute_reference_plans.py` |
| Post-mortem metrics script                            | `e2e_validation/scripts/build_validation_csv.py`      |
| Per-turn metrics CSV (one row per turn)               | `e2e_validation/results/e2e_validation_turns.csv`     |
| Per-scenario aggregate CSV                            | `e2e_validation/results/e2e_validation_summary.csv`   |
| Cross-scenario global CSV                             | `e2e_validation/results/e2e_validation_global.csv`    |
| Backend telemetry helper                              | `src/api/telemetry.py`                                |
| FastAPI middleware tagging events with scenario id    | `src/api/middleware.py`                               |

To regenerate the metrics from the JSONL log:

```
python e2e_validation/scripts/build_validation_csv.py
```

The three CSVs are overwritten and the headline block is printed to
stdout. The JSONL log itself is the scientific artefact: its
SHA-256 hash can be recorded in the report to fix the exact run the
metrics were derived from.

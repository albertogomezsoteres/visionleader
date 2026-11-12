"""Post-process the end-to-end validation log into the three metric CSVs.

Reads the JSONL telemetry log of a validation run, groups the events by
scenario and turn, scores each turn against the ground truth in
``scenarios.json`` and the precomputed ``reference_plans``, and writes:

    e2e_validation_turns.csv     one row per turn
    e2e_validation_summary.csv   one row per scenario
    e2e_validation_global.csv    one row, cross-scenario totals

Usage:
    python experiments/end_to_end/scripts/build_validation_csv.py
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]  # experiments/end_to_end
REPO_ROOT = Path(__file__).resolve().parents[3]  # repository root, for tidy log paths

LOG_PATH = BASE / "logs" / "e2e_backend.jsonl"
SCENARIOS_PATH = BASE / "scenarios.json"
REFERENCE_PATH = BASE / "reference_plans" / "e2e_reference_plans.json"
RESULTS_DIR = BASE / "results"
TURNS_CSV = RESULTS_DIR / "e2e_validation_turns.csv"
SUMMARY_CSV = RESULTS_DIR / "e2e_validation_summary.csv"
GLOBAL_CSV = RESULTS_DIR / "e2e_validation_global.csv"

# === I/O helpers ===


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"[warn] log file not found: {path}")
        return []
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[warn] skipping malformed line: {e}")
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in columns})


# === Numeric helpers ===


def _safe_float(x: Any) -> float | None:
    """Parse to float, or None when the value is missing or non-numeric."""
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (p in 0..100) of a list of values."""
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def _pct(num: int, denom: int) -> str:
    """Format num / denom as a percentage string, empty when denom is 0."""
    if denom == 0:
        return ""
    return f"{(100.0 * num / denom):.1f}%"


def _wer(reference: str, hypothesis: str) -> float | None:
    """Word Error Rate via word-level Levenshtein distance.

    Returns ``edits / reference_word_count`` (so a result > 1.0 is possible
    when the hypothesis adds many extra words). Lowercases and strips
    common punctuation before comparing so trailing dots / commas don't
    inflate the score.
    """
    if not reference:
        return None
    import re as _re

    def _toks(s: str) -> list[str]:
        s = s.lower()
        s = _re.sub(r"[.,;:!?\"'()\[\]]", " ", s)
        return [w for w in s.split() if w]

    ref = _toks(reference)
    hyp = _toks(hypothesis or "")
    n, m = len(ref), len(hyp)
    if n == 0:
        return 0.0 if m == 0 else 1.0
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[n][m] / n


def _vlm_verification_applicable_checks(scenario: dict[str, Any]) -> set:
    """Return the set of VALIDATION check names that depend on a VLM call.

    arrival_verification is always VLM-driven (every scenario ends with
    a verification photo). origin_grounding is VLM-driven when the
    scenario uses a room_plate or directory_sign as the *first* prompt.
    The two mid-route chips depend on whether the scenario's plan uses
    the elevator or the stairs.
    """
    prompts = scenario.get("vlm_prompts_expected") or []
    checks = {"arrival_verification"}
    if prompts and prompts[0] in {"room_plate", "directory_sign"}:
        checks.add("origin_grounding")
    if "elevator_state" in prompts:
        checks.add("elevator_verification")
    if "stair_direction" in prompts:
        checks.add("stairs_verification")
    return checks


# === Event grouping ===


def _group_by_scenario_turn(
    events: list[dict[str, Any]],
) -> dict[str, dict[int, list[dict[str, Any]]]]:
    """Group events into ``{scenario_id: {turn_idx: [events]}}``."""
    out: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for ev in events:
        sc = ev.get("scenario_id")
        turn = ev.get("turn_idx")
        if sc is None or turn is None:
            continue
        out.setdefault(sc, {}).setdefault(int(turn), []).append(ev)
    return out


# === Per-turn analysis ===


def _summarise_turn(
    turn_events: list[dict[str, Any]],
    expected_turn: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reduce all events of a single turn to one CSV row.

    ``expected_turn`` is the matching entry from ``scenarios.json``'s
    ``turns[]``, used to score STT keyword correctness, FSM transition
    correctness, and the per-turn VLM expectation.
    """
    vlm_calls: list[dict[str, Any]] = []
    planner_total_ms: float | None = None
    planner_action_count: int | None = None
    backend_internal_ms: float | None = None
    stt_latency_ms: float | None = None
    stt_text: str | None = None
    tts_message: str | None = None
    tts_duration_ms: float | None = None
    end_to_end_ms: float | None = None
    fsm_transitions: list[tuple[str | None, str | None]] = []

    for ev in turn_events:
        cat = ev.get("category")
        msg = ev.get("message", "")
        dur = _safe_float(ev.get("duration_ms"))

        if cat == "STT":
            stt_text = ev.get("transcription") or stt_text
            if dur is not None:
                stt_latency_ms = dur
        elif cat == "VLM" and msg.startswith("raw=") and dur is not None:
            vlm_calls.append(
                {
                    "prompt_id": ev.get("prompt_id"),
                    "duration_ms": dur,
                    "raw_response": ev.get("raw_response"),
                }
            )
        elif cat == "VLM" and msg.startswith("symbol grounded:"):
            if vlm_calls:
                vlm_calls[-1]["parsed_ok"] = True
                vlm_calls[-1]["location_id"] = ev.get("location_id")
                vlm_calls[-1]["state_type"] = ev.get("state_type")
                vlm_calls[-1]["state_detail"] = ev.get("state_detail")
        elif cat == "VLM" and msg.startswith("symbol grounding FAILED"):
            if vlm_calls:
                vlm_calls[-1]["parsed_ok"] = False
        elif cat == "PLANNER" and msg.startswith("solved") and dur is not None:
            planner_total_ms = dur
            planner_action_count = ev.get("action_count")
        elif cat == "AGENT" and "turn handled" in msg and dur is not None:
            backend_internal_ms = dur
        elif cat == "TTS":
            tts_message = msg or tts_message
        elif cat == "FSM":
            # process_turn can emit multiple transitions for a single turn
            # (e.g. an elevator photo verifies the elevator AND auto-advances
            # to the next step). Collect all of them so the FSM expectation
            # in scenarios.json matches if it appears anywhere in the turn,
            # not just as the last hop.
            fsm_transitions.append((ev.get("from_state"), ev.get("to_state")))
        elif cat == "CLIENT":
            if "tts_duration_ms" in ev:
                tts_duration_ms = _safe_float(ev["tts_duration_ms"])
            if "end_to_end_ms" in ev:
                end_to_end_ms = _safe_float(ev["end_to_end_ms"])

    # STT keyword correctness
    keywords_expected: list[str] = (expected_turn or {}).get("stt_keywords") or []
    keywords_matched: list[str] = []
    keywords_missing: list[str] = []
    if keywords_expected and stt_text:
        low = stt_text.lower()
        for kw in keywords_expected:
            (keywords_matched if kw.lower() in low else keywords_missing).append(kw)
    stt_keywords_ok = bool(keywords_expected) and bool(stt_text) and not keywords_missing

    # FSM transition correctness
    # The expected transition matches if it appears anywhere in this turn's
    # transition list (process_turn may collapse multiple internal hops).
    expected_fsm: list[str] | None = (expected_turn or {}).get("fsm")
    if expected_fsm and len(expected_fsm) == 2:
        fsm_expected_from, fsm_expected_to = expected_fsm
        fsm_match = any(f == fsm_expected_from and t == fsm_expected_to for f, t in fsm_transitions)
    else:
        fsm_expected_from = fsm_expected_to = None
        fsm_match = None  # not applicable for turns without an FSM expectation
    # Last transition is what gets reported in the CSV row for human reading.
    fsm_from = fsm_transitions[-1][0] if fsm_transitions else None
    fsm_to = fsm_transitions[-1][1] if fsm_transitions else None

    # VLM expectation
    vlm_prompt_expected = (expected_turn or {}).get("vlm_prompt")
    vlm_loc_expected = (expected_turn or {}).get("vlm_expected_location_id")
    vlm_state_expected = (expected_turn or {}).get("vlm_expected_state_detail")
    vlm_grounding_ok: bool | None = None
    if vlm_prompt_expected and vlm_calls:
        # Pick the call whose prompt matches what was expected.
        match = next(
            (c for c in vlm_calls if c.get("prompt_id") == vlm_prompt_expected),
            vlm_calls[-1],
        )
        if not match.get("parsed_ok"):
            vlm_grounding_ok = False
        elif vlm_loc_expected is not None:
            vlm_grounding_ok = match.get("location_id") == vlm_loc_expected
        elif vlm_state_expected is not None:
            vlm_grounding_ok = match.get("state_detail") == vlm_state_expected
        else:
            # Open-class verification (e.g. elevator_state can be open OR
            # closed). Successful parse alone counts as correct.
            vlm_grounding_ok = True

    # Word Error Rate
    expected_say = (expected_turn or {}).get("say") or ""
    if (expected_turn or {}).get("input") == "voice" and stt_text and expected_say:
        wer_val = _wer(expected_say, stt_text)
    else:
        wer_val = None

    return {
        "stt_text": stt_text or "",
        "stt_latency_ms": stt_latency_ms,
        "stt_keywords_expected": "|".join(keywords_expected),
        "stt_keywords_matched": "|".join(keywords_matched),
        "stt_keywords_missing": "|".join(keywords_missing),
        "stt_keywords_ok": "" if not keywords_expected else int(stt_keywords_ok),
        "wer": "" if wer_val is None else round(wer_val, 3),
        "vlm_calls": len(vlm_calls),
        "vlm_total_ms": sum(c["duration_ms"] for c in vlm_calls) if vlm_calls else None,
        "vlm_max_ms": max((c["duration_ms"] for c in vlm_calls), default=None),
        "vlm_prompt_ids": "|".join(str(c.get("prompt_id") or "") for c in vlm_calls),
        "vlm_format_ok": (
            int(all(c.get("parsed_ok") is True for c in vlm_calls)) if vlm_calls else ""
        ),
        "vlm_grounding_ok": "" if vlm_grounding_ok is None else int(vlm_grounding_ok),
        "planner_total_ms": planner_total_ms,
        "planner_action_count": planner_action_count,
        "backend_internal_ms": backend_internal_ms,
        "tts_duration_ms": tts_duration_ms,
        "end_to_end_ms": end_to_end_ms,
        "fsm_expected_from": fsm_expected_from or "",
        "fsm_expected_to": fsm_expected_to or "",
        "fsm_actual_from": fsm_from or "",
        "fsm_actual_to": fsm_to or "",
        "fsm_match": "" if fsm_match is None else int(fsm_match),
        "tts_message": (tts_message or "")[:200],
    }


# === Per-scenario aggregation ===


def _final_state_for_scenario(
    turns: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Pick the latest TTS / PLAN events to recover the final ctx snapshot."""
    last_origin: dict | None = None
    last_destination: dict | None = None
    last_hurry: bool | None = None
    plan_actions: list[str] = []
    completed = False
    for turn_idx in sorted(turns.keys()):
        for ev in turns[turn_idx]:
            cat = ev.get("category")
            if cat == "TTS":
                if ev.get("origin"):
                    last_origin = ev["origin"]
                if ev.get("destination"):
                    last_destination = ev["destination"]
                if ev.get("hurry_mode") is not None:
                    last_hurry = ev["hurry_mode"]
            elif cat == "PLAN":
                action = ev.get("action") or ev.get("message", "")
                if action:
                    plan_actions.append(str(action))
            elif cat == "SCENARIO" and ev.get("status") == "completed":
                completed = True
    return {
        "origin": last_origin,
        "destination": last_destination,
        "hurry_mode": last_hurry,
        "plan_actions": plan_actions,
        "completed": completed,
    }


def _slot_match(observed: dict | None, expected: dict | None) -> bool:
    """True when observed and expected agree on building, floor and location_id."""
    if not observed or not expected:
        return False
    for k in ("building", "floor", "location_id"):
        if observed.get(k) != expected.get(k):
            return False
    return True


def _route_match(observed: list[str], reference: list[str]) -> bool:
    """Compare action sequences ignoring trailing cost annotations."""

    def _norm(seq):
        out = []
        for a in seq:
            a = a.strip()
            if not a:
                continue
            if a.endswith(")") and "(" in a:
                head, _, tail = a.rpartition("(")
                tail_no = tail.rstrip(")")
                if tail_no.isdigit():
                    a = head.strip()
            out.append(a)
        return out

    return _norm(observed) == _norm(reference)


def _count_validation_results(
    turn_events_all: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Count VALIDATION events as (pass, fail, total_applicable)."""
    p = f = 0
    for ev in turn_events_all:
        if ev.get("category") != "VALIDATION":
            continue
        r = ev.get("result")
        if r == "pass":
            p += 1
        elif r == "fail":
            f += 1
    return p, f, p + f


# === Main ===


def main() -> int:
    if not LOG_PATH.exists():
        print(f"No log file at {LOG_PATH}. Did you run a session with TELEMETRY_JSONL_PATH set?")
        return 1

    # Load the telemetry log and group its events by scenario and turn.
    events = _read_jsonl(LOG_PATH)
    grouped = _group_by_scenario_turn(events)
    if not grouped:
        print("No events with scenario_id and turn_idx found in the log.")
        return 1

    # Ground truth: per-scenario turns plus the precomputed optimal plans.
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"]
    scenarios_by_id = {s["scenario_id"]: s for s in scenarios}

    references: dict[str, dict[str, Any]] = {}
    if REFERENCE_PATH.exists():
        references = json.loads(REFERENCE_PATH.read_text(encoding="utf-8")).get(
            "reference_plans", {}
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    turn_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    # Cross-scenario accumulators for the global CSV.
    g_planner_attempts_total = 0
    g_planner_solves_total = 0
    g_plan_costs: list[int] = []
    g_pddl_actions_total = 0
    g_user_facing_steps_total = 0
    g_instructions_delivered_total = 0
    g_instructions_expected_total = 0
    g_vlm_verif_pass = 0
    g_vlm_verif_total = 0
    g_wer_values: list[float] = []
    g_user_turns_total = 0
    g_voice_turns_total = 0
    g_photo_turns_total = 0
    g_backend_turns_total = 0
    g_validation_pass = 0
    g_validation_total = 0
    g_stt_keywords_pass = 0
    g_stt_keywords_total = 0
    g_fsm_transitions_pass = 0
    g_fsm_transitions_total = 0
    g_vlm_calls_total = 0
    g_vlm_format_ok = 0
    g_vlm_grounding_ok = 0
    g_vlm_grounding_total = 0
    g_scenarios_completed = 0
    g_scenarios_total = len(scenarios)
    g_routes_correct = 0
    g_routes_scored = 0
    g_e2e_latencies: list[float] = []
    g_stt_latencies: list[float] = []
    g_vlm_latencies: list[float] = []
    g_planner_latencies: list[float] = []

    # One pass per scenario: per-turn rows first, then the scenario summary row.
    for sid in sorted(grouped.keys()):
        scenario = scenarios_by_id.get(sid, {})
        expected_turns_by_idx = {t["idx"]: t for t in (scenario.get("turns") or [])}
        turns = grouped[sid]

        # Per-scenario accumulators.
        e2e_per_turn: list[float] = []
        backend_per_turn: list[float] = []
        vlm_per_call: list[float] = []
        planner_per_call: list[float] = []
        stt_per_turn: list[float] = []
        wer_per_turn: list[float] = []
        voice_turns = photo_turns = 0
        stt_kw_pass = stt_kw_total = 0
        fsm_pass = fsm_total = 0
        vlm_format_pass = vlm_format_total = 0
        vlm_grounding_pass = vlm_grounding_total = 0

        # Build each turn row and fold its metrics into the per-scenario counters.
        for turn_idx in sorted(turns.keys()):
            row = _summarise_turn(turns[turn_idx], expected_turns_by_idx.get(turn_idx))
            row["scenario_id"] = sid
            row["turn_idx"] = turn_idx
            row["expected_input_type"] = expected_turns_by_idx.get(turn_idx, {}).get("input") or ""
            row["expected_say"] = expected_turns_by_idx.get(turn_idx, {}).get("say") or ""
            turn_rows.append(row)

            if row["expected_input_type"] == "voice":
                voice_turns += 1
            if row["expected_input_type"] == "photo":
                photo_turns += 1

            if row["end_to_end_ms"] is not None:
                e2e_per_turn.append(row["end_to_end_ms"])
            if row["backend_internal_ms"] is not None:
                backend_per_turn.append(row["backend_internal_ms"])
            if row["planner_total_ms"] is not None:
                planner_per_call.append(row["planner_total_ms"])
            if row["stt_latency_ms"] is not None:
                stt_per_turn.append(row["stt_latency_ms"])
            if row["vlm_total_ms"] is not None and row["vlm_calls"]:
                vlm_per_call.append(row["vlm_total_ms"] / row["vlm_calls"])
            if row["wer"] != "" and row["wer"] is not None:
                wer_per_turn.append(row["wer"])

            if row["stt_keywords_ok"] != "":
                stt_kw_total += 1
                if row["stt_keywords_ok"]:
                    stt_kw_pass += 1
            if row["fsm_match"] != "":
                fsm_total += 1
                if row["fsm_match"]:
                    fsm_pass += 1
            if row["vlm_format_ok"] != "":
                vlm_format_total += 1
                if row["vlm_format_ok"]:
                    vlm_format_pass += 1
            if row["vlm_grounding_ok"] != "":
                vlm_grounding_total += 1
                if row["vlm_grounding_ok"]:
                    vlm_grounding_pass += 1

        # Session-level scoring: slots, route vs reference plan, validation chips.
        final = _final_state_for_scenario(turns)
        expected_session = scenario.get("expected", {})
        ref_actions = references.get(sid, {}).get("actions", [])

        origin_ok = _slot_match(final["origin"], expected_session.get("origin"))
        destination_ok = _slot_match(final["destination"], expected_session.get("destination"))
        hurry_ok = bool(final.get("hurry_mode")) == bool(expected_session.get("hurry_mode"))
        slots_correct = int(origin_ok) + int(destination_ok) + int(hurry_ok)

        route_ok = _route_match(final["plan_actions"], ref_actions) if ref_actions else None
        if route_ok is not None:
            g_routes_scored += 1
            if route_ok:
                g_routes_correct += 1

        # Validation chip pass/fail across all events of this scenario.
        scenario_events = [ev for ts in turns.values() for ev in ts]
        v_pass, v_fail, v_total = _count_validation_results(scenario_events)
        backend_turn_count = sum(
            1
            for ev in scenario_events
            if ev.get("category") == "AGENT" and "turn handled" in ev.get("message", "")
        )

        scenario_completed = final["completed"]
        if scenario_completed:
            g_scenarios_completed += 1

        # Planner attempts/solves + last-plan stats
        planner_attempts = sum(
            1
            for ev in scenario_events
            if ev.get("category") == "PLANNER" and (ev.get("message") or "").startswith("init=")
        )
        planner_solves = sum(
            1
            for ev in scenario_events
            if ev.get("category") == "PLANNER" and (ev.get("message") or "").startswith("solved")
        )
        last_solved = next(
            (
                ev
                for ev in reversed(scenario_events)
                if ev.get("category") == "PLANNER"
                and (ev.get("message") or "").startswith("solved")
            ),
            None,
        )
        last_compacted = next(
            (
                ev
                for ev in reversed(scenario_events)
                if ev.get("category") == "ROUTE"
                and (ev.get("message") or "").startswith("compacted")
            ),
            None,
        )
        plan_cost_val = (last_solved or {}).get("cost")
        pddl_action_count_val = (last_solved or {}).get("action_count")
        user_facing_step_count_val = (last_compacted or {}).get("step_count")

        # Instruction correctness
        # Number of "deliver_step" TTS events in this scenario. The agent
        # uses two action tags for step deliveries: "navigation_step" for
        # the regular indoor steps and "navigation_step_outdoor" for the
        # GPS leg. Both count as a delivered instruction.
        instructions_delivered = sum(
            1
            for ev in scenario_events
            if ev.get("category") == "TTS"
            and (ev.get("action") or "").startswith("navigation_step")
        )
        instructions_expected = user_facing_step_count_val or 0
        if instructions_expected:
            instruction_correctness_val = min(1.0, instructions_delivered / instructions_expected)
        else:
            instruction_correctness_val = None

        # VLM verification subset of the validation chips
        vlm_checks = _vlm_verification_applicable_checks(scenario)
        vlm_verif_pass = sum(
            1
            for ev in scenario_events
            if ev.get("category") == "VALIDATION"
            and ev.get("check") in vlm_checks
            and ev.get("result") == "pass"
        )
        vlm_verif_total = sum(
            1
            for ev in scenario_events
            if ev.get("category") == "VALIDATION"
            and ev.get("check") in vlm_checks
            and ev.get("result") in ("pass", "fail")
        )

        # Assemble this scenario's summary row.
        summary_rows.append(
            {
                "scenario_id": sid,
                "scenario_name": scenario.get("name", ""),
                "completed": int(scenario_completed),
                "user_turns": len(turns),
                "voice_turns": voice_turns,
                "photo_turns": photo_turns,
                "backend_turns": backend_turn_count,
                # Validation chips
                "validation_pass": v_pass,
                "validation_fail": v_fail,
                "validation_total": v_total,
                "validation_pass_rate": _pct(v_pass, v_total),
                # STT
                "stt_keywords_pass": stt_kw_pass,
                "stt_keywords_total": stt_kw_total,
                "stt_keywords_pass_rate": _pct(stt_kw_pass, stt_kw_total),
                "stt_mean_ms": round(statistics.fmean(stt_per_turn), 1) if stt_per_turn else "",
                "stt_mean_wer": round(statistics.fmean(wer_per_turn), 3) if wer_per_turn else "",
                # FSM
                "fsm_transitions_pass": fsm_pass,
                "fsm_transitions_total": fsm_total,
                "fsm_transitions_pass_rate": _pct(fsm_pass, fsm_total),
                # Slots (session-level)
                "origin_match": int(origin_ok),
                "destination_match": int(destination_ok),
                "hurry_match": int(hurry_ok),
                "slots_correct": slots_correct,
                "slots_total": 3,
                "slots_pass_rate": _pct(slots_correct, 3),
                # VLM
                "vlm_calls_total": sum(
                    r["vlm_calls"] for r in turn_rows if r["scenario_id"] == sid
                ),
                "vlm_format_pass": vlm_format_pass,
                "vlm_format_total": vlm_format_total,
                "vlm_format_validity": _pct(vlm_format_pass, vlm_format_total),
                "vlm_grounding_pass": vlm_grounding_pass,
                "vlm_grounding_total": vlm_grounding_total,
                "vlm_grounding_correctness": _pct(vlm_grounding_pass, vlm_grounding_total),
                "vlm_verification_pass": vlm_verif_pass,
                "vlm_verification_total": vlm_verif_total,
                "vlm_verification_success_rate": _pct(vlm_verif_pass, vlm_verif_total),
                "vlm_mean_ms": round(statistics.fmean(vlm_per_call), 1) if vlm_per_call else "",
                # Planner
                "planner_calls_total": len(planner_per_call),
                "planner_attempts": planner_attempts,
                "planner_solves": planner_solves,
                "planner_solved_rate": _pct(planner_solves, planner_attempts),
                "plan_cost": plan_cost_val if plan_cost_val is not None else "",
                "pddl_action_count": pddl_action_count_val
                if pddl_action_count_val is not None
                else "",
                "user_facing_step_count": user_facing_step_count_val
                if user_facing_step_count_val is not None
                else "",
                "instructions_delivered": instructions_delivered,
                "instructions_expected": instructions_expected,
                "instruction_correctness": (
                    ""
                    if instruction_correctness_val is None
                    else f"{(100.0 * instruction_correctness_val):.1f}%"
                ),
                "planner_mean_ms": round(statistics.fmean(planner_per_call), 1)
                if planner_per_call
                else "",
                "route_correct": "" if route_ok is None else int(route_ok),
                # Latency
                "end_to_end_mean_ms": round(statistics.fmean(e2e_per_turn), 1)
                if e2e_per_turn
                else "",
                "end_to_end_p95_ms": round(_percentile(e2e_per_turn, 95), 1)
                if e2e_per_turn
                else "",
                "backend_mean_ms": round(statistics.fmean(backend_per_turn), 1)
                if backend_per_turn
                else "",
            }
        )

        # Roll into global accumulators.
        g_user_turns_total += len(turns)
        g_voice_turns_total += voice_turns
        g_photo_turns_total += photo_turns
        g_backend_turns_total += backend_turn_count
        g_validation_pass += v_pass
        g_validation_total += v_total
        g_stt_keywords_pass += stt_kw_pass
        g_stt_keywords_total += stt_kw_total
        g_fsm_transitions_pass += fsm_pass
        g_fsm_transitions_total += fsm_total
        g_vlm_calls_total += sum(r["vlm_calls"] for r in turn_rows if r["scenario_id"] == sid)
        g_vlm_format_ok += vlm_format_pass
        g_vlm_grounding_ok += vlm_grounding_pass
        g_vlm_grounding_total += vlm_grounding_total
        g_vlm_verif_pass += vlm_verif_pass
        g_vlm_verif_total += vlm_verif_total
        g_planner_attempts_total += planner_attempts
        g_planner_solves_total += planner_solves
        if plan_cost_val is not None:
            g_plan_costs.append(int(plan_cost_val))
        if pddl_action_count_val is not None:
            g_pddl_actions_total += int(pddl_action_count_val)
        if user_facing_step_count_val is not None:
            g_user_facing_steps_total += int(user_facing_step_count_val)
        g_instructions_delivered_total += instructions_delivered
        g_instructions_expected_total += instructions_expected
        g_wer_values.extend(wer_per_turn)
        g_e2e_latencies.extend(e2e_per_turn)
        g_stt_latencies.extend(stt_per_turn)
        g_vlm_latencies.extend(vlm_per_call)
        g_planner_latencies.extend(planner_per_call)

    # Assemble the single cross-scenario global row.
    global_row = {
        "scenarios_total": g_scenarios_total,
        "scenarios_completed": g_scenarios_completed,
        "scenario_completion_rate": _pct(g_scenarios_completed, g_scenarios_total),
        "user_turns_total": g_user_turns_total,
        "voice_turns_total": g_voice_turns_total,
        "photo_turns_total": g_photo_turns_total,
        "backend_turns_total": g_backend_turns_total,
        "validation_pass": g_validation_pass,
        "validation_total": g_validation_total,
        "validation_pass_rate": _pct(g_validation_pass, g_validation_total),
        "stt_keywords_pass": g_stt_keywords_pass,
        "stt_keywords_total": g_stt_keywords_total,
        "stt_keyword_correctness": _pct(g_stt_keywords_pass, g_stt_keywords_total),
        "stt_mean_wer": round(statistics.fmean(g_wer_values), 3) if g_wer_values else "",
        "stt_mean_ms": round(statistics.fmean(g_stt_latencies), 1) if g_stt_latencies else "",
        "fsm_transitions_pass": g_fsm_transitions_pass,
        "fsm_transitions_total": g_fsm_transitions_total,
        "fsm_transition_correctness": _pct(g_fsm_transitions_pass, g_fsm_transitions_total),
        "vlm_calls_total": g_vlm_calls_total,
        "vlm_format_validity": _pct(g_vlm_format_ok, g_vlm_calls_total),
        "vlm_grounding_correctness": _pct(g_vlm_grounding_ok, g_vlm_grounding_total),
        "vlm_verification_pass": g_vlm_verif_pass,
        "vlm_verification_total": g_vlm_verif_total,
        "vlm_verification_success_rate": _pct(g_vlm_verif_pass, g_vlm_verif_total),
        "vlm_mean_ms": round(statistics.fmean(g_vlm_latencies), 1) if g_vlm_latencies else "",
        "planner_calls_total": len(g_planner_latencies),
        "planner_attempts_total": g_planner_attempts_total,
        "planner_solves_total": g_planner_solves_total,
        "planner_solved_rate": _pct(g_planner_solves_total, g_planner_attempts_total),
        "plan_cost_mean": round(statistics.fmean(g_plan_costs), 1) if g_plan_costs else "",
        "pddl_actions_total": g_pddl_actions_total,
        "user_facing_steps_total": g_user_facing_steps_total,
        "instructions_delivered_total": g_instructions_delivered_total,
        "instructions_expected_total": g_instructions_expected_total,
        "instruction_correctness": _pct(
            g_instructions_delivered_total, g_instructions_expected_total
        ),
        "planner_mean_ms": round(statistics.fmean(g_planner_latencies), 1)
        if g_planner_latencies
        else "",
        "routes_correct": g_routes_correct,
        "routes_scored": g_routes_scored,
        "route_correctness": _pct(g_routes_correct, g_routes_scored),
        "end_to_end_mean_ms": round(statistics.fmean(g_e2e_latencies), 1)
        if g_e2e_latencies
        else "",
        "end_to_end_p95_ms": round(_percentile(g_e2e_latencies, 95), 1) if g_e2e_latencies else "",
    }

    # Write the three CSVs with an explicit, stable column order.
    _write_csv(
        TURNS_CSV,
        turn_rows,
        [
            "scenario_id",
            "turn_idx",
            "expected_input_type",
            "expected_say",
            "stt_text",
            "stt_latency_ms",
            "wer",
            "stt_keywords_expected",
            "stt_keywords_matched",
            "stt_keywords_missing",
            "stt_keywords_ok",
            "vlm_calls",
            "vlm_total_ms",
            "vlm_max_ms",
            "vlm_prompt_ids",
            "vlm_format_ok",
            "vlm_grounding_ok",
            "planner_total_ms",
            "planner_action_count",
            "backend_internal_ms",
            "tts_duration_ms",
            "end_to_end_ms",
            "fsm_expected_from",
            "fsm_expected_to",
            "fsm_actual_from",
            "fsm_actual_to",
            "fsm_match",
            "tts_message",
        ],
    )
    _write_csv(
        SUMMARY_CSV,
        summary_rows,
        [
            "scenario_id",
            "scenario_name",
            "completed",
            "user_turns",
            "voice_turns",
            "photo_turns",
            "backend_turns",
            "validation_pass",
            "validation_fail",
            "validation_total",
            "validation_pass_rate",
            "stt_keywords_pass",
            "stt_keywords_total",
            "stt_keywords_pass_rate",
            "stt_mean_ms",
            "stt_mean_wer",
            "fsm_transitions_pass",
            "fsm_transitions_total",
            "fsm_transitions_pass_rate",
            "origin_match",
            "destination_match",
            "hurry_match",
            "slots_correct",
            "slots_total",
            "slots_pass_rate",
            "vlm_calls_total",
            "vlm_format_pass",
            "vlm_format_total",
            "vlm_format_validity",
            "vlm_grounding_pass",
            "vlm_grounding_total",
            "vlm_grounding_correctness",
            "vlm_verification_pass",
            "vlm_verification_total",
            "vlm_verification_success_rate",
            "vlm_mean_ms",
            "planner_calls_total",
            "planner_attempts",
            "planner_solves",
            "planner_solved_rate",
            "plan_cost",
            "pddl_action_count",
            "user_facing_step_count",
            "instructions_delivered",
            "instructions_expected",
            "instruction_correctness",
            "planner_mean_ms",
            "route_correct",
            "end_to_end_mean_ms",
            "end_to_end_p95_ms",
            "backend_mean_ms",
        ],
    )
    _write_csv(GLOBAL_CSV, [global_row], list(global_row.keys()))

    print(f"Wrote {TURNS_CSV.relative_to(REPO_ROOT)} ({len(turn_rows)} rows)")
    print(f"Wrote {SUMMARY_CSV.relative_to(REPO_ROOT)} ({len(summary_rows)} rows)")
    print(f"Wrote {GLOBAL_CSV.relative_to(REPO_ROOT)} (1 row)")
    print()
    # Headline block: printed to stdout and pasted into the report.
    print("=== HEADLINE METRICS ===")
    print(
        f"  Scenarios completed:        {global_row['scenarios_completed']} / {global_row['scenarios_total']}  ({global_row['scenario_completion_rate']})"
    )
    print(
        f"  Validation pass rate:       {global_row['validation_pass']} / {global_row['validation_total']}  ({global_row['validation_pass_rate']})"
    )
    print(
        f"  STT keyword correctness:    {global_row['stt_keywords_pass']} / {global_row['stt_keywords_total']}  ({global_row['stt_keyword_correctness']})"
    )
    print(f"  STT mean WER:               {global_row['stt_mean_wer']}")
    print(
        f"  FSM transitions OK:         {global_row['fsm_transitions_pass']} / {global_row['fsm_transitions_total']}  ({global_row['fsm_transition_correctness']})"
    )
    print(f"  VLM format validity:        {global_row['vlm_format_validity']}")
    print(f"  VLM grounding accuracy:     {global_row['vlm_grounding_correctness']}")
    print(
        f"  VLM verification success:   {global_row['vlm_verification_pass']} / {global_row['vlm_verification_total']}  ({global_row['vlm_verification_success_rate']})"
    )
    print(
        f"  Planner solved rate:        {global_row['planner_solves_total']} / {global_row['planner_attempts_total']}  ({global_row['planner_solved_rate']})"
    )
    print(f"  Mean plan cost:             {global_row['plan_cost_mean']}")
    print(f"  PDDL actions (total):       {global_row['pddl_actions_total']}")
    print(f"  User-facing steps (total):  {global_row['user_facing_steps_total']}")
    print(
        f"  Instruction correctness:    {global_row['instructions_delivered_total']} / {global_row['instructions_expected_total']}  ({global_row['instruction_correctness']})"
    )
    print(
        f"  Routes correct:             {global_row['routes_correct']} / {global_row['routes_scored']}  ({global_row['route_correctness']})"
    )
    print(f"  Mean end-to-end:            {global_row['end_to_end_mean_ms']} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

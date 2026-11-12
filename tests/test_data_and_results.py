"""The committed datasets are consistent, and the reported numbers are backed by them.

Every headline figure in the README is recomputed here from the result CSVs,
so a figure in the docs cannot drift away from the data behind it.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pytest

from visionleader import paths
from visionleader.api.services import vlm_prompts

ROOT = paths.REPO_ROOT
DATA = ROOT / "data"
RESULTS = ROOT / "experiments"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- knowledge base ------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(p.name for p in paths.CONFIG_DIR.glob("*.json")))
def test_config_files_are_valid_json(name: str) -> None:
    json.loads((paths.CONFIG_DIR / name).read_text(encoding="utf-8"))


def test_vlm_location_vocabulary_exists_in_the_topology() -> None:
    """Every id the VLM may emit must be a node the planner knows about."""
    topology = paths.TOPOLOGY_PATH.read_text(encoding="utf-8")
    prompts = json.loads(paths.PROMPTS_PATH.read_text(encoding="utf-8"))["prompts"]
    for prompt_id in vlm_prompts.valid_prompt_ids():
        for location_id in prompts[prompt_id].get("valid_location_ids", []):
            if location_id == "unknown":  # explicit abstention label
                continue
            assert f'"{location_id}"' in topology, (prompt_id, location_id)


# --- datasets ----------------------------------------------------------------------


def _manifest_key(folder: str, row: dict[str, str]) -> str:
    # Images are hashed relative to their category folder.
    return f"{row['category']}/{row['filename']}" if folder == "vlm" else row["filename"]


@pytest.mark.parametrize("folder", ["stt", "vlm", "planner"])
def test_manifest_and_hash_file_describe_the_same_items(folder: str) -> None:
    manifest = {_manifest_key(folder, row) for row in read_csv(DATA / folder / "manifest.csv")}
    hashes = json.loads((DATA / folder / "dataset_hashes.json").read_text(encoding="utf-8"))
    assert hashes["algorithm"] == "sha256"
    assert manifest == set(hashes["files"])


def test_planner_problems_match_their_recorded_hashes() -> None:
    """The 12 problems on disk are the exact files that were benchmarked.

    The hashes were taken on a Windows checkout, so they cover CRLF line
    endings; git stores the files with LF.
    """
    hashes = json.loads((DATA / "planner" / "dataset_hashes.json").read_text(encoding="utf-8"))
    for name, expected in hashes["files"].items():
        raw = (ROOT / "pddl" / "problems" / "evaluation" / name).read_bytes()
        assert b"\r\n" not in raw
        assert hashlib.sha256(raw.replace(b"\n", b"\r\n")).hexdigest() == expected, name


def test_dataset_sizes() -> None:
    assert len(read_csv(DATA / "stt" / "manifest.csv")) == 30
    assert len(read_csv(DATA / "vlm" / "manifest.csv")) == 80
    assert len(read_csv(DATA / "planner" / "manifest.csv")) == 12


# --- reported results ----------------------------------------------------------------


def test_planner_headline_numbers() -> None:
    rows = read_csv(RESULTS / "planner" / "results" / "planner_evaluation.csv")
    by_config = defaultdict(list)
    for row in rows:
        by_config[row["config_key"]].append(row)

    assert all(len(runs) == 12 for runs in by_config.values())
    assert all(row["success"] == "True" for row in rows)

    expanded = {k: sum(int(r["expanded"]) for r in runs) for k, runs in by_config.items()}
    assert expanded["astar_lmcut"] == 125
    assert expanded["astar_blind"] == 9433
    assert round(expanded["astar_blind"] / expanded["astar_lmcut"]) == 75

    lmcut = {r["problem_key"]: int(r["cost"]) for r in by_config["astar_lmcut"]}
    blind = {r["problem_key"]: int(r["cost"]) for r in by_config["astar_blind"]}
    greedy = {r["problem_key"]: int(r["cost"]) for r in by_config["lazy_ff"]}
    assert lmcut == blind  # both optimal
    assert sum(greedy[k] > lmcut[k] for k in lmcut) == 4


def test_stt_choice_keeps_every_domain_keyword() -> None:
    server = {
        r["model"]: r
        for r in read_csv(
            RESULTS / "stt" / "phase1_server_benchmark" / "results" / "all_models_summary_wide.csv"
        )
    }
    whisper = [m for m in server if m.startswith("whisper-")]
    assert len(whisper) == 6
    assert all(float(server[m]["dka_with_prompt"]) == 100.0 for m in whisper)

    device = {
        r["model"]: r
        for r in read_csv(RESULTS / "stt" / "phase2_ondevice" / "results" / "fase2_summary.csv")
    }
    chosen = device["tiny-q5_0"]
    assert float(chosen["dka_pct"]) == 100.0
    assert 3000 < float(chosen["avg_latency_ms"]) < 3500  # "about 3 seconds"


def test_vlm_choice() -> None:
    phase1 = {
        r["model_id"]: float(r["overall_accuracy"])
        for r in read_csv(
            RESULTS / "vlm" / "phase1_state_recognition" / "results" / "all_models_summary.csv"
        )
    }
    assert len(phase1) == 7
    best = max(phase1.values())
    assert phase1["google/gemma-4-E4B-it"] == best == phase1["google/paligemma2-3b-mix-448"]

    phase2 = {
        r["model_id"]: float(r["overall_accuracy"])
        for r in read_csv(
            RESULTS / "vlm" / "phase2_location_extraction" / "results" / "all_models_summary.csv"
        )
    }
    assert phase2["google/gemma-4-E4B-it"] == 1.0
    assert round(phase2["google/paligemma2-3b-mix-448"], 2) == 0.74


@pytest.mark.parametrize(
    ("modality", "basic", "optimized"),
    [("text", 0.20, 0.84), ("vlm", 0.35, 0.96)],
)
def test_symbolic_grounding_prompt_gain(modality: str, basic: float, optimized: float) -> None:
    rows = {
        r["prompt_variant"]: float(r["exact_pddl_match"])
        for r in read_csv(
            RESULTS / "symbolic_grounding" / modality / "results" / "per_variant_summary.csv"
        )
    }
    assert round(rows["basic"], 2) == basic
    assert round(rows["optimized"], 2) == optimized


def test_end_to_end_validation_passes_every_check() -> None:
    (row,) = read_csv(RESULTS / "end_to_end" / "results" / "e2e_validation_global.csv")
    assert (row["scenarios_completed"], row["scenarios_total"]) == ("3", "3")
    assert row["validation_pass"] == row["validation_total"] == "14"
    for metric in (
        "stt_keyword_correctness",
        "fsm_transition_correctness",
        "vlm_grounding_correctness",
        "route_correctness",
        "instruction_correctness",
    ):
        assert row[metric] == "100.0%", metric

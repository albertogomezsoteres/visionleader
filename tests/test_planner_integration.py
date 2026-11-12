"""Re-solve the frozen benchmark with the real Fast Downward and compare to the CSV.

Needs Docker and the pinned image (``make planner-image``). Run with
``make test-planner``; CI builds the image and runs it on every push.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from visionleader import paths
from visionleader.navigation.fast_downward_client import FastDownwardPlanner

pytestmark = pytest.mark.planner

IMAGE = "fast-downward:latest"
EVAL_DIR = paths.PDDL_DIR / "problems" / "evaluation"
RESULTS = paths.REPO_ROOT / "experiments" / "planner" / "results" / "planner_evaluation.csv"
SEARCHES = {
    "astar_lmcut": "astar(lmcut())",
    "astar_blind": "astar(blind())",
    "lazy_ff": "lazy_greedy([ff()])",
}


def _image_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        out = subprocess.run(
            ["docker", "images", "-q", IMAGE], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and bool(out.stdout.strip())


if not _image_available():
    pytest.skip(f"Docker image {IMAGE} not available", allow_module_level=True)


def _recorded_runs() -> list[dict[str, str]]:
    with RESULTS.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize(
    "recorded",
    _recorded_runs(),
    ids=lambda r: f"{r['problem_key']}-{r['config_key']}",
)
def test_benchmark_run_reproduces_exactly(recorded: dict[str, str]) -> None:
    # Fast Downward only sees files at the root of the mounted pddl/ folder.
    source = EVAL_DIR / f"problem_{recorded['problem_key']}.pddl"
    with tempfile.NamedTemporaryFile(suffix=".pddl", dir=paths.PDDL_DIR, delete=False) as f:
        runtime = Path(f.name)
    try:
        shutil.copy(source, runtime)
        result = FastDownwardPlanner(timeout=300).plan(
            str(paths.DOMAIN_PATH), str(runtime), search_config=SEARCHES[recorded["config_key"]]
        )
    finally:
        runtime.unlink(missing_ok=True)

    assert result["success"], result.get("error")
    for field in ("cost", "steps", "expanded", "generated", "evaluated"):
        assert result[field] == int(recorded[field]), field

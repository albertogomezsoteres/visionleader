"""Parsing Fast Downward output and failing safely around the Docker call."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from conftest import FD_OUTPUT_G_ONE_FLOOR
from visionleader.navigation.agent.plan_to_steps import parse_fd_action
from visionleader.navigation.fast_downward_client import FastDownwardPlanner


def test_parses_a_real_solution() -> None:
    result = FastDownwardPlanner()._parse_plan(FD_OUTPUT_G_ONE_FLOOR)
    assert result["success"] is True
    assert result["error"] is None
    assert (result["cost"], result["steps"]) == (33, 6)
    assert result["plan"][0] == "walk user entrance_2 elevator_g_f0 (3)"
    assert result["plan"][-1] == "walk user bathroom_women_g_f1 classroom_g_1_4 (2)"
    assert len(result["plan"]) == result["steps"]
    assert result["expanded"] == 7
    assert result["generated"] == 23


def test_action_costs_add_up_to_the_plan_cost() -> None:
    result = FastDownwardPlanner()._parse_plan(FD_OUTPUT_G_ONE_FLOOR)
    costs = [int(line.rsplit("(", 1)[1].rstrip(")")) for line in result["plan"]]
    assert sum(costs) == result["cost"]


def test_unsolvable_output_is_a_clean_failure() -> None:
    output = "Search stopped without finding a solution.\nExpanded 0 state(s).\n"
    result = FastDownwardPlanner()._parse_plan(output)
    assert result["success"] is False
    assert result["plan"] == []
    assert result["error"] == "No solution found"


def test_missing_files_fail_before_docker_is_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_docker(*args, **kwargs):
        raise AssertionError("Docker must not be invoked")

    monkeypatch.setattr(subprocess, "run", no_docker)
    result = FastDownwardPlanner().plan(str(tmp_path / "domain.pddl"), str(tmp_path / "p.pddl"))
    assert result["success"] is False
    assert "Domain file not found" in result["error"]


def test_a_missing_docker_binary_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain, problem = tmp_path / "domain.pddl", tmp_path / "problem.pddl"
    domain.write_text("(define (domain d))")
    problem.write_text("(define (problem p))")

    def docker_not_installed(cmd, *args, **kwargs):
        if cmd[:2] == ["docker", "rm"]:
            raise FileNotFoundError("docker")
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", docker_not_installed)
    result = FastDownwardPlanner().plan(str(domain), str(problem))
    assert result["success"] is False
    assert "Error running Fast Downward" in result["error"]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "use_elevator user elevator_g_f0 elevator_g_f1 (15)",
            {"name": "use_elevator", "params": ["user", "elevator_g_f0", "elevator_g_f1"]},
        ),
        ("walk user a b", {"name": "walk", "params": ["user", "a", "b"]}),
        ("", None),
    ],
)
def test_parse_fd_action(line: str, expected: dict | None) -> None:
    assert parse_fd_action(line) == expected

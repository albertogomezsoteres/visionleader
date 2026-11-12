"""Shared fixtures: the real campus knowledge base and a planner stand-in.

The tests run against the committed config/ and pddl/ files, so a change to
the topology or the domain that breaks routing shows up here. Fast Downward
itself is replaced by ``FakePlanner`` (a recorded run of the real planner);
tests marked ``planner`` exercise the real binary through Docker.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from visionleader import paths
from visionleader.navigation.conversation_agent import ConversationAgent
from visionleader.navigation.fast_downward_client import FastDownwardPlanner
from visionleader.navigation.hierarchical_pddl_converter import HierarchicalPDDLConverter

FIXTURES = Path(__file__).parent / "fixtures"

# Real `fast-downward.py ... --search "astar(lmcut())"` output for
# pddl/problems/evaluation/problem_g_one_floor.pddl (entrance 2 -> classroom 1.4).
FD_OUTPUT_G_ONE_FLOOR = (FIXTURES / "fd_astar_lmcut_g_one_floor.txt").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _quiet_telemetry():
    """The agent narrates every turn on the terminal; keep test output clean."""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture(scope="session")
def topology() -> dict:
    return json.loads(paths.TOPOLOGY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def places() -> dict:
    return json.loads(paths.PLACES_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def no_closures(tmp_path: Path) -> Path:
    path = tmp_path / "closed_rooms.json"
    path.write_text(json.dumps({"closed": []}), encoding="utf-8")
    return path


@pytest.fixture
def converter(no_closures: Path) -> HierarchicalPDDLConverter:
    """Converter over the real topology with no rooms closed."""
    return HierarchicalPDDLConverter(
        json_path=str(paths.TOPOLOGY_PATH),
        pddl_dir=str(paths.PDDL_DIR),
        closed_rooms_path=str(no_closures),
    )


class FakePlanner:
    """Replays a recorded Fast Downward run and keeps the problems it was given."""

    def __init__(self, output: str = FD_OUTPUT_G_ONE_FLOOR) -> None:
        self.output = output
        self.problems: list[str] = []

    def plan(self, domain_path: str, problem_path: str, search_config: str = "") -> dict:
        self.problems.append(Path(problem_path).read_text(encoding="utf-8"))
        result = FastDownwardPlanner()._parse_plan(self.output)
        result["output"] = self.output
        return result


@pytest.fixture
def fake_planner() -> FakePlanner:
    return FakePlanner()


@pytest.fixture
def agent(topology: dict, places: dict, fake_planner: FakePlanner, converter) -> ConversationAgent:
    agent = ConversationAgent(topology, places)
    agent._planner = fake_planner
    agent._hierarchical_converter = converter
    return agent


@pytest.fixture
def room_lookup(agent: ConversationAgent) -> dict:
    return agent._room_lookup

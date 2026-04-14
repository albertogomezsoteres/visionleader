"""
Shared singletons used across routers and services.

Expensive resources (campus graph, planner, conversation agent) are loaded
once at startup and reused on every request.
"""

import os
import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from navigation.fast_downward_client import FastDownwardPlanner
from navigation.pddl_converter import (
    CampusGraphToPDDL,
    HierarchicalPDDLConverter,
)
from navigation.conversation_agent import ConversationAgent

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DOMAIN_PATH = BASE_DIR / "pddl" / "domain.pddl"
CAMPUS_JSON = BASE_DIR / "config" / "campus_graph.json"
PDDL_DIR = BASE_DIR / "pddl"

load_dotenv(BASE_DIR / ".env")

COLAB_API_URL: str = (os.getenv("COLAB_API_URL") or "").strip().rstrip("/")

planner = FastDownwardPlanner()
# Legacy floor-level converter (still used by /api/plan and the global domain)
converter = CampusGraphToPDDL(str(CAMPUS_JSON))
# Room-level hierarchical converter (building-specific domains)
hierarchical_converter = HierarchicalPDDLConverter(
    json_path=str(CAMPUS_JSON),
    pddl_dir=str(PDDL_DIR),
)

_campus_graph_data: Optional[dict] = None


def load_campus_graph() -> dict:
    """Load the campus JSON once and keep it in memory."""
    global _campus_graph_data
    if _campus_graph_data is None:
        with open(CAMPUS_JSON, "r", encoding="utf-8") as f:
            _campus_graph_data = json.load(f)
    return _campus_graph_data


_conversation_agent: Optional[ConversationAgent] = None


def get_conversation_agent() -> ConversationAgent:
    """Return the singleton ConversationAgent, creating it on first call."""
    global _conversation_agent
    if _conversation_agent is None:
        _conversation_agent = ConversationAgent(load_campus_graph())
    return _conversation_agent

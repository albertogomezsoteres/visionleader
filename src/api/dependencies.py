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
from navigation.hierarchical_pddl_converter import HierarchicalPDDLConverter
from navigation.conversation_agent import ConversationAgent

BASE_DIR       = Path(__file__).resolve().parent.parent.parent
DOMAIN_PATH    = BASE_DIR / "pddl" / "domain_indoor.pddl"
TOPOLOGY_JSON  = BASE_DIR / "config" / "campus_topology.json"
PLACES_JSON    = BASE_DIR / "config" / "campus_places.json"
PDDL_DIR       = BASE_DIR / "pddl"

load_dotenv(BASE_DIR / ".env")

COLAB_API_URL: str = (os.getenv("COLAB_API_URL") or "").strip().rstrip("/")

planner = FastDownwardPlanner()
hierarchical_converter = HierarchicalPDDLConverter(
    json_path=str(TOPOLOGY_JSON),
    pddl_dir=str(PDDL_DIR),
)

_topology_data: Optional[dict] = None
_places_data:   Optional[dict] = None


def load_topology() -> dict:
    """Load campus_topology.json once and keep it in memory."""
    global _topology_data
    if _topology_data is None:
        with open(TOPOLOGY_JSON, "r", encoding="utf-8") as f:
            _topology_data = json.load(f)
    return _topology_data


def load_places() -> dict:
    """Load campus_places.json once and keep it in memory."""
    global _places_data
    if _places_data is None:
        with open(PLACES_JSON, "r", encoding="utf-8") as f:
            _places_data = json.load(f)
    return _places_data


_conversation_agent: Optional[ConversationAgent] = None


def get_conversation_agent() -> ConversationAgent:
    """Return the singleton ConversationAgent, creating it on first call."""
    global _conversation_agent
    if _conversation_agent is None:
        _conversation_agent = ConversationAgent(load_topology(), load_places())
    return _conversation_agent

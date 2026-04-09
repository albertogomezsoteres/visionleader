"""
Shared state and singleton loaders used across routers and services.

We keep expensive resources (model weights, campus graph, planner) in
module-level singletons so they are loaded once and reused on every request.
"""

import os
import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from navigation.fast_downward_client import FastDownwardPlanner
from navigation.pddl_converter import CampusGraphToPDDL
from navigation.conversation_agent import ConversationAgent

# ── Paths ────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DOMAIN_PATH = BASE_DIR / "pddl" / "domain.pddl"
CAMPUS_JSON = BASE_DIR / "config" / "campus_graph.json"
PDDL_DIR = BASE_DIR / "pddl"

load_dotenv(BASE_DIR / ".env")

# ── Colab tunnel URL (empty string means "use local inference") ──────────

COLAB_API_URL: str = (os.getenv("COLAB_API_URL") or "").strip().rstrip("/")

# ── PDDL planner + converter (lightweight, created at import time) ───────

planner = FastDownwardPlanner()
converter = CampusGraphToPDDL(str(CAMPUS_JSON))

# ── Campus graph (loaded lazily, cached forever) ─────────────────────────

_campus_graph_data: Optional[dict] = None


def load_campus_graph() -> dict:
    """Load the campus JSON once and keep it in memory."""
    global _campus_graph_data
    if _campus_graph_data is None:
        with open(CAMPUS_JSON, "r", encoding="utf-8") as f:
            _campus_graph_data = json.load(f)
    return _campus_graph_data


# ── Conversation agent (one instance shared across sessions) ─────────────

_conversation_agent: Optional[ConversationAgent] = None


def get_conversation_agent() -> ConversationAgent:
    """Return the singleton ConversationAgent, creating it on first call."""
    global _conversation_agent
    if _conversation_agent is None:
        _conversation_agent = ConversationAgent(load_campus_graph())
    return _conversation_agent


# ── PaliGemma model (loaded lazily — heavy, only when needed) ────────────

_paligemma_model = None
_paligemma_processor = None


def load_paligemma_model():
    """Load PaliGemma weights once and keep them in GPU/CPU memory."""
    global _paligemma_model, _paligemma_processor
    if _paligemma_model is None or _paligemma_processor is None:
        from evaluation.model_loader import load_paligemma
        from huggingface_hub import login

        hf_token = (os.getenv("HF_TOKEN") or "").strip() or None
        if hf_token:
            try:
                login(token=hf_token)
                print("Authenticated with HuggingFace")
            except Exception as e:
                print(f"HuggingFace auth failed: {e}")
        else:
            print("No HF_TOKEN found — model may require authentication.")

        model_id = "google/paligemma2-3b-mix-224"
        print(f"Loading PaliGemma model: {model_id}")
        _paligemma_model, _paligemma_processor = load_paligemma(model_id, token=hf_token)
        print("PaliGemma model loaded successfully")

    return _paligemma_model, _paligemma_processor

"""Filesystem locations shared by the backend, the scripts and the experiments.

The knowledge base (PDDL domain, campus topology, prompts) lives at the
repository root rather than inside the package, so every module resolves it
through this file instead of walking ``__file__`` parents on its own.

Set ``VISIONLEADER_ROOT`` to point the backend at another checkout or at a
deployment directory with the same layout.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_root() -> Path:
    override = os.getenv("VISIONLEADER_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    # src/visionleader/paths.py -> repository root (editable installs, checkouts)
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "config").is_dir() and (candidate / "pddl").is_dir():
        return candidate
    return Path.cwd()


REPO_ROOT = _find_root()

CONFIG_DIR = REPO_ROOT / "config"
PDDL_DIR = REPO_ROOT / "pddl"

DOMAIN_PATH = PDDL_DIR / "domain.pddl"
TOPOLOGY_PATH = CONFIG_DIR / "campus_topology.json"
PLACES_PATH = CONFIG_DIR / "campus_places.json"
CLOSED_ROOMS_PATH = CONFIG_DIR / "closed_rooms.json"
PROMPTS_PATH = CONFIG_DIR / "prompts.json"
MODELS_PATH = CONFIG_DIR / "models.json"
ENV_FILE = REPO_ROOT / ".env"

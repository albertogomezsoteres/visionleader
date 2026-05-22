"""Boot the VisionLeader UFV backend with a clean, demo-grade terminal.

The structured ``[STT FLUTTER] / [VLM] / [PLANNER] / [TTS FLUTTER]`` events
emitted by ``api.telemetry`` are the live narration of every turn, so
this entry-point keeps the rest of the terminal quiet (uvicorn access
logs off, internal Python loggers at WARNING) and prints a tidy boot
banner with the operator-facing knobs at startup.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# Force UTF-8 stdout so the unicode characters in the banner (═ ─ ▸ ·)
# render reliably regardless of the platform's default codepage.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from colorama import Fore, Style, init as _colorama_init
    _colorama_init()
    _C_BOLD   = Style.BRIGHT
    _C_DIM    = Style.DIM
    _C_RESET  = Style.RESET_ALL
    _C_BLUE   = Fore.BLUE + Style.BRIGHT
    _C_GREEN  = Fore.GREEN
    _C_YELLOW = Fore.YELLOW
    _C_RED    = Fore.RED
    _C_GRAY   = Fore.LIGHTBLACK_EX
except Exception:
    _C_BOLD = _C_DIM = _C_RESET = ""
    _C_BLUE = _C_GREEN = _C_YELLOW = _C_RED = _C_GRAY = ""

# Project bootstrap
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root / "src"))

from api.app import app  # noqa: E402

# Logging config: keep the terminal clean. Only the structured telemetry
# events from api.telemetry should narrate the run.
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
for _name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
    logging.getLogger(_name).setLevel(logging.WARNING)


# ---- status helpers -------------------------------------------------------

def _status(text: str) -> str:
    """Colour-code a short status word (configured / ready / missing / …)."""
    low = text.lower()
    if low in ("ready", "configured", "ok"):
        return f"{_C_GREEN}{text}{_C_RESET}"
    if low in ("off", "none"):
        return f"{_C_GRAY}{text}{_C_RESET}"
    if "missing" in low or "unreachable" in low or low == "error":
        return f"{_C_YELLOW}{text}{_C_RESET}"
    return text


def _check_env(name: str) -> str:
    return "configured" if (os.getenv(name) or "").strip() else "missing"


def _check_docker_image(image: str) -> str:
    try:
        out = subprocess.run(
            ["docker", "images", "-q", image],
            capture_output=True, timeout=3, text=True,
        )
        return "ready" if out.stdout.strip() else "image missing"
    except FileNotFoundError:
        return "Docker unreachable"
    except subprocess.TimeoutExpired:
        return "Docker unreachable"
    except Exception:
        return "unknown"


def _check_file(rel: str) -> str:
    return "ok" if (project_root / rel).exists() else "missing"


def _closures_summary() -> str:
    closures_path = project_root / "config" / "closed_rooms.json"
    if not closures_path.exists():
        return "none"
    try:
        data = json.loads(closures_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"unreadable ({e})"
    entries = data.get("closed", []) or []
    if not entries:
        return "none"
    bits = []
    for entry in entries:
        bld = entry.get("building", "?")
        loc = entry.get("location_id", "?")
        floor = entry.get("floor")
        floor_txt = f" f{floor}" if floor is not None else ""
        bits.append(f"{bld}/{loc}{floor_txt}")
    return ", ".join(bits)


def _telemetry_status() -> str:
    raw = (os.getenv("TELEMETRY_JSONL_PATH") or "").strip()
    return raw if raw else "off"


# ---- banner ---------------------------------------------------------------

def _print_banner() -> None:
    width = 76
    rule = "═" * width
    print(f"{_C_BLUE}{rule}{_C_RESET}")
    print(
        f"  {_C_BOLD}VisionLeaderUFV{_C_RESET}"
        f"{_C_DIM}  ·  Campus Navigation Backend{_C_RESET}"
    )
    print(f"{_C_BLUE}{rule}{_C_RESET}")

    colab_status = _check_env("COLAB_API_URL")
    maps_status  = _check_env("GOOGLE_MAPS_API_KEY")
    fd_status    = _check_docker_image("fast-downward:latest")
    domain_status = _check_file("pddl/domain.pddl")
    topo_status   = _check_file("config/campus_topology.json")
    places_status = _check_file("config/campus_places.json")

    sections = [
        ("Endpoints", [
            ("API",        "http://localhost:8000",                                 None),
            ("Docs",       "http://localhost:8000/docs",                            None),
        ]),
        ("Models", [
            ("VLM",        "Gemma 4 E4B-it",          f"Colab · {_status(colab_status)}"),
            ("STT",        "Whisper Tiny Q5_0",       f"on-device · {_status('ready')}"),
            ("TTS",        "Flutter TTS",             f"on-device · {_status('ready')}"),
            ("Planner",    "Fast Downward A* + LM-Cut", f"Docker · {_status(fd_status)}"),
            ("Outdoor",    "Google Maps Directions",  f"{_status(maps_status)}"),
        ]),
        ("Knowledge", [
            ("Domain",     "pddl/domain.pddl",      _status(domain_status)),
            ("Topology",   "config/campus_topology.json",  _status(topo_status)),
            ("Places",     "config/campus_places.json",    _status(places_status)),
            ("Closures",   _closures_summary(),            None),
        ]),
        ("Telemetry", [
            ("Log",        _telemetry_status(),            None),
        ]),
    ]

    for title, rows in sections:
        print()
        print(f"  {_C_BOLD}{title}{_C_RESET}")
        for row in rows:
            label, value = row[0], row[1]
            tag = row[2] if len(row) > 2 else None
            line = f"  {_C_GRAY}▸{_C_RESET} {_C_YELLOW}{label:<10}{_C_RESET}  {value}"
            if tag:
                line += f"   {_C_GRAY}[{_C_RESET}{tag}{_C_GRAY}]{_C_RESET}"
            print(line)

    print()
    print(f"{_C_BLUE}{rule}{_C_RESET}")
    print(f"  {_C_DIM}Press Ctrl+C to stop the server.{_C_RESET}\n")


if __name__ == "__main__":
    _print_banner()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        access_log=False,
        log_level="warning",
    )

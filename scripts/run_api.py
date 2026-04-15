"""
Script para ejecutar la API de Planificacion.

Ejecutar: python scripts/run_api.py
"""

import json
import logging
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# Project bootstrap
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root / "src"))

from api.app import app  # noqa: E402

# Logging config: enable INFO globally so the planner bridge and the
# conversation agent emit live telemetry on the terminal during a demo.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet uvicorn access spam — keep it clean for the demo terminal.
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def _print_closure_state() -> None:
    """Print the current dynamic-availability state at boot, so the demo
    operator (and the tribunal) sees it without having to run a side query."""
    closures_path = project_root / "config" / "closed_rooms.json"
    if not closures_path.exists():
        print("[CLOSURES] config/closed_rooms.json not found - nothing closed.")
        return
    try:
        data = json.loads(closures_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[CLOSURES] could not read closed_rooms.json: {e}")
        return
    entries = data.get("closed", []) or []
    if not entries:
        print("[CLOSURES] no rooms currently closed.")
        return
    print(f"[CLOSURES] {len(entries)} room(s) currently closed:")
    for entry in entries:
        bld = entry.get("building", "?")
        loc = entry.get("location_id", "?")
        floor = entry.get("floor")
        reason = entry.get("reason") or "no reason given"
        floor_txt = f" floor {floor}" if floor is not None else ""
        print(f"   - {bld}/{loc}{floor_txt}: {reason}")


if __name__ == "__main__":
    print("=" * 60)
    print("Campus Navigation Planning API")
    print("=" * 60)
    print()
    _print_closure_state()
    print()
    print("Servidor iniciando en http://localhost:8000")
    print("Documentacion disponible en http://localhost:8000/docs")
    print()
    print("Presiona Ctrl+C para detener el servidor")
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )

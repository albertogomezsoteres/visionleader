"""
Quick CLI to toggle room closures for the live demo.

Edits config/closed_rooms.json. The PDDL converter reads the file on every
planning request, so closures take effect immediately without restarting
the API.

Usage:

    # Close a classroom (globally unique id, no floor needed)
    python scripts/close_room.py close G aula_1_4 --reason "class in session"

    # Close a shared-name id on a specific floor (elevator on floor 0)
    python scripts/close_room.py close G ascensor --floor 0 --reason "maintenance"

    # Reopen it
    python scripts/close_room.py open G ascensor --floor 0

    # List current closures
    python scripts/close_room.py list

    # Clear every closure at once
    python scripts/close_room.py reset
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLOSED_JSON = ROOT / "config" / "closed_rooms.json"


def _load() -> dict:
    with CLOSED_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with CLOSED_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")


def _matches(entry: dict, building: str, location_id: str, floor):
    if entry.get("building") != building:
        return False
    if entry.get("location_id") != location_id:
        return False
    if floor is None:
        return entry.get("floor") is None
    return entry.get("floor") == floor


def cmd_close(args) -> None:
    data = _load()
    closed = data.setdefault("closed", [])

    if any(_matches(e, args.building, args.location_id, args.floor) for e in closed):
        print(
            f"Already closed: {args.building}/{args.location_id}"
            f"{f' (floor {args.floor})' if args.floor is not None else ''}"
        )
        return

    entry = {
        "building": args.building,
        "location_id": args.location_id,
    }
    if args.floor is not None:
        entry["floor"] = args.floor
    if args.reason:
        entry["reason"] = args.reason

    closed.append(entry)
    _save(data)
    print(f"Closed: {entry}")


def cmd_open(args) -> None:
    data = _load()
    closed = data.setdefault("closed", [])
    before = len(closed)
    closed[:] = [
        e for e in closed
        if not _matches(e, args.building, args.location_id, args.floor)
    ]
    _save(data)
    removed = before - len(closed)
    if removed:
        print(
            f"Reopened {removed} entry: {args.building}/{args.location_id}"
            f"{f' (floor {args.floor})' if args.floor is not None else ''}"
        )
    else:
        print("No matching closure found.")


def cmd_list(_args) -> None:
    data = _load()
    closed = data.get("closed", [])
    if not closed:
        print("No rooms are currently closed.")
        return
    print(f"Currently closed ({len(closed)}):")
    for e in closed:
        floor = f"  floor={e.get('floor')}" if e.get('floor') is not None else ""
        reason = f"  ({e.get('reason')})" if e.get("reason") else ""
        print(f"  {e['building']} / {e['location_id']}{floor}{reason}")


def cmd_reset(_args) -> None:
    data = _load()
    n = len(data.get("closed", []))
    data["closed"] = []
    _save(data)
    print(f"Cleared {n} closure entries.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_close = sub.add_parser("close", help="close a room")
    p_close.add_argument("building", help="G | CD | H")
    p_close.add_argument("location_id", help="e.g. aula_1_4, ascensor, escaleras")
    p_close.add_argument("--floor", type=int, default=None,
                         help="floor, required only for ids shared across floors")
    p_close.add_argument("--reason", default="currently unavailable")
    p_close.set_defaults(func=cmd_close)

    p_open = sub.add_parser("open", help="reopen a closed room")
    p_open.add_argument("building")
    p_open.add_argument("location_id")
    p_open.add_argument("--floor", type=int, default=None)
    p_open.set_defaults(func=cmd_open)

    p_list = sub.add_parser("list", help="list current closures")
    p_list.set_defaults(func=cmd_list)

    p_reset = sub.add_parser("reset", help="clear every closure")
    p_reset.set_defaults(func=cmd_reset)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

"""Regenerate the G and CD sections of ``config/campus_topology.json``.

Source of truth is this script: edge distances are written in pasos,
converted to meters on the fly with the calibrated stride (0.75 m/paso),
rounded to the nearest integer (half up). Edits the topology file in place.

Run:
    python scripts/regenerate_g_cd_topology.py

Everything outside G and CD (other buildings, their local_connections, the
functional_locations map, etc.) is preserved as-is.
"""

import json
from pathlib import Path

TOPOLOGY = Path(__file__).resolve().parent.parent / "config" / "campus_topology.json"

STRIDE_M = 0.75


def m(pasos: float) -> int:
    """Convert pasos to meters, rounded half up to the nearest integer."""
    return int(pasos * STRIDE_M + 0.5)


# =========================================================================
# G — nodes per floor
# =========================================================================
G_LOCATIONS = {
    "-1": [  # ágora
        {"id": "entrance_agora_1",              "type": "entrance_interior"},
        {"id": "entrance_agora_1_exterior",     "type": "entrance_secondary"},
        {"id": "entrance_agora_2",              "type": "entrance_interior"},
        {"id": "entrance_agora_2_exterior",     "type": "entrance_secondary"},
        {"id": "classroom_agora_1",                  "type": "classroom"},
        {"id": "classroom_agora_2",                  "type": "classroom"},
        {"id": "classroom_agora_3",                  "type": "classroom"},
        {"id": "computer_lab",                  "type": "laboratory"},
        {"id": "electronics_lab",               "type": "laboratory"},
        {"id": "subtractive_manufacturing_lab", "type": "laboratory"},
        {"id": "directory_sign_g_agora",        "type": "directory_sign"},
        {"id": "stairs",                        "type": "stairs"},
        {"id": "elevator",                      "type": "elevator"},
        {"id": "bathroom_men",                  "type": "restroom"},
    ],
    "0": [
        {"id": "entrance_1",            "type": "entrance_interior"},
        {"id": "entrance_1_exterior",   "type": "entrance_secondary"},
        {"id": "entrance_2",            "type": "entrance_interior"},
        # entrance_2_exterior is the ONLY type="entrance" in G — canonical for
        # outdoor_connected. HierarchicalPDDLConverter._entrance_of picks this
        # one for cross-building edges.
        {"id": "entrance_2_exterior",   "type": "entrance"},
        {"id": "entrance_3",            "type": "entrance_interior"},
        {"id": "entrance_3_exterior",   "type": "entrance_secondary"},
        {"id": "lab_ia",                "type": "laboratory"},
        {"id": "classroom_0_1",         "type": "classroom"},
        {"id": "classroom_0_2",         "type": "classroom"},
        {"id": "classroom_0_3",         "type": "classroom"},
        {"id": "classroom_0_4",         "type": "classroom"},
        {"id": "directory_sign_g_0",    "type": "directory_sign"},
        {"id": "stairs",                "type": "stairs"},
        {"id": "elevator",              "type": "elevator"},
        {"id": "bathroom_men",          "type": "restroom"},
        {"id": "bathroom_women",        "type": "restroom"},
    ],
    "1": [
        {"id": "entrance_1_p1",       "type": "entrance_interior"},
        {"id": "entrance_2_p1",       "type": "entrance_interior"},
        {"id": "classroom_1_1",       "type": "classroom"},
        {"id": "classroom_1_2",       "type": "classroom"},
        {"id": "classroom_1_3",       "type": "classroom"},
        {"id": "classroom_1_4",       "type": "classroom"},
        {"id": "classroom_1_5",       "type": "classroom"},
        {"id": "classroom_1_6",       "type": "classroom"},
        {"id": "directory_sign_g_1",  "type": "directory_sign"},
        {"id": "stairs",              "type": "stairs"},
        {"id": "elevator",            "type": "elevator"},
        {"id": "bathroom_men",        "type": "restroom"},
        {"id": "bathroom_women",      "type": "restroom"},
    ],
    "2": [
        {"id": "exit_p2",             "type": "entrance_interior"},
        {"id": "classroom_2_1",       "type": "classroom"},
        {"id": "mentoring_room",      "type": "office"},
        {"id": "admin_office",        "type": "office"},
        {"id": "office_2_7",        "type": "office"},
        {"id": "directory_sign_g_2",  "type": "directory_sign"},
        {"id": "stairs",              "type": "stairs"},
        {"id": "elevator",            "type": "elevator"},
        {"id": "bathroom_men",        "type": "restroom"},
    ],
}

# G — edges (in pasos, bidirectional). Each tuple (a, b, pasos).
G_EDGES_AGORA = [
    # door pairs (exterior threshold ↔ interior threshold)
    ("entrance_agora_1", "entrance_agora_1_exterior", 3),
    ("entrance_agora_2", "entrance_agora_2_exterior", 3),
    # ala-A (entrance_1, aulas 2 y 3, directorio, núcleo vertical, baño)
    ("entrance_agora_1",       "classroom_agora_2",            8),
    ("entrance_agora_1",       "classroom_agora_3",            8),
    ("classroom_agora_2",           "classroom_agora_3",            5),
    ("classroom_agora_2",           "directory_sign_g_agora", 12),
    ("classroom_agora_3",           "directory_sign_g_agora", 12),
    ("stairs",                 "directory_sign_g_agora",  4),
    ("directory_sign_g_agora", "elevator",                4),
    ("elevator",               "bathroom_men",            2),
    # ala-B (entrance_2, aula_1, labs)
    ("entrance_agora_2", "classroom_agora_1",                  7),
    ("classroom_agora_1",     "computer_lab",                  6),
    ("computer_lab",     "entrance_agora_2",              9),
    ("computer_lab",     "electronics_lab",               2),
    ("electronics_lab",  "subtractive_manufacturing_lab", 2),
]

G_EDGES_P0 = [
    # door pairs
    ("entrance_1", "entrance_1_exterior", 4),
    ("entrance_2", "entrance_2_exterior", 4),
    ("entrance_3", "entrance_3_exterior", 4),
    # ala izquierda (lab_ia / 0.4 / baño fem)
    ("lab_ia",         "entrance_1",         7),
    ("entrance_1",     "classroom_0_4",      7),
    ("classroom_0_4",  "bathroom_women",     2),
    ("bathroom_women", "entrance_2",         5),
    ("bathroom_women", "directory_sign_g_0", 5),
    # hub central (entrance_2, directorio, núcleo vertical)
    ("entrance_2",         "directory_sign_g_0", 4),
    ("directory_sign_g_0", "stairs",             4),
    ("directory_sign_g_0", "elevator",           5),
    ("elevator",           "bathroom_men",       2),
    ("elevator",           "entrance_2",         4),
    # ala derecha (baño masc, 0.3, entrada 3, 0.1, 0.2)
    ("bathroom_men",  "classroom_0_3", 3),
    ("classroom_0_3", "entrance_3",    8),
    ("entrance_3",    "classroom_0_2", 5),
    ("entrance_3",    "classroom_0_1", 5),
    ("classroom_0_1", "classroom_0_2", 2),
]

G_EDGES_P1 = [
    # ala A (directorio, núcleo vertical, baño masc, aulas 1.1-1.3)
    ("stairs",                "directory_sign_g_1", 4),
    ("directory_sign_g_1",    "elevator",           4),
    ("elevator",              "bathroom_men",       2),
    ("bathroom_men",          "classroom_1_3",      4),
    ("classroom_1_3",         "entrance_2_p1",      7),
    ("entrance_2_p1",         "classroom_1_2",      4),
    ("classroom_1_2",         "classroom_1_1",      1),
    # ala B (baño fem, aulas 1.4-1.6)
    ("directory_sign_g_1", "bathroom_women", 6),
    ("bathroom_women",     "classroom_1_4",  3),
    ("classroom_1_4",      "entrance_1_p1",  8),
    ("entrance_1_p1",      "classroom_1_5",  4),
    ("entrance_1_p1",      "classroom_1_6",  4),
    ("classroom_1_5",      "classroom_1_6",  1),
]

G_EDGES_P2 = [
    ("stairs",               "directory_sign_g_2", 2),
    ("directory_sign_g_2",   "elevator",           6),
    ("elevator",             "bathroom_men",       2),
    ("bathroom_men",         "office_2_7",       3),
    ("office_2_7",         "mentoring_room",     8),
    ("mentoring_room",       "classroom_2_1",      2),
    ("exit_p2",              "classroom_2_1",      2),
    ("exit_p2",              "mentoring_room",     2),
    ("exit_p2",              "office_2_7",       8),
    ("elevator",             "admin_office",       5),
    ("directory_sign_g_2",   "admin_office",       4),
]


# =========================================================================
# CD — nodes per floor. Dual vertical cores (main + rear).
# =========================================================================
CD_LOCATIONS = {
    "-1": [
        {"id": "gym",           "type": "gym"},
        {"id": "pool",          "type": "pool"},
        {"id": "stairs",        "type": "stairs"},
        {"id": "elevator",      "type": "elevator"},
        {"id": "stairs_rear",   "type": "stairs"},
        {"id": "elevator_rear", "type": "elevator"},
    ],
    "0": [
        # entrance_cd_exterior = canonical for CD — used for outdoor edges.
        {"id": "entrance_cd_exterior",      "type": "entrance"},
        {"id": "entrance_cd_interior",      "type": "entrance_interior"},
        {"id": "back_entrance_cd_exterior", "type": "entrance_secondary"},
        {"id": "back_entrance_cd_interior", "type": "entrance_interior"},
        {"id": "central_point_cd",          "type": "hub"},
        {"id": "cafeteria",                 "type": "cafeteria"},
        {"id": "stairs",                    "type": "stairs"},
        {"id": "elevator",                  "type": "elevator"},
        {"id": "stairs_rear",               "type": "stairs"},
        {"id": "elevator_rear",             "type": "elevator"},
    ],
    "1": [
        {"id": "classroom_cd_1_1",     "type": "classroom"},
        {"id": "classroom_cd_1_2",     "type": "classroom"},
        {"id": "classroom_cd_1_3",     "type": "classroom"},
        {"id": "classroom_cd_1_4",     "type": "classroom"},
        {"id": "directory_sign_cd_1",  "type": "directory_sign"},
        {"id": "stairs",               "type": "stairs"},
        {"id": "elevator",             "type": "elevator"},
        {"id": "stairs_rear",          "type": "stairs"},
        {"id": "elevator_rear",        "type": "elevator"},
        {"id": "bathroom_men",         "type": "restroom"},
        {"id": "bathroom_women",       "type": "restroom"},
    ],
    "2": [
        {"id": "classroom_cd_2_5",     "type": "classroom"},
        {"id": "classroom_cd_2_6",     "type": "classroom"},
        {"id": "classroom_cd_2_7",     "type": "classroom"},
        {"id": "classroom_cd_2_8",     "type": "classroom"},
        {"id": "directory_sign_cd_2",  "type": "directory_sign"},
        {"id": "stairs",               "type": "stairs"},
        {"id": "elevator",             "type": "elevator"},
        {"id": "stairs_rear",          "type": "stairs"},
        {"id": "elevator_rear",        "type": "elevator"},
        {"id": "bathroom_men",         "type": "restroom"},
        {"id": "bathroom_women",       "type": "restroom"},
    ],
}

CD_EDGES_P_MINUS_1 = [
    ("stairs",        "gym",  15),
    ("elevator",      "gym",  15),
    ("stairs_rear",   "pool", 15),
    ("elevator_rear", "pool", 15),
]

CD_EDGES_P0 = [
    # front entrance + main core
    ("entrance_cd_exterior", "entrance_cd_interior",  6),
    ("entrance_cd_exterior", "stairs",               11),
    ("entrance_cd_exterior", "elevator",             11),
    ("stairs",               "elevator",              4),
    ("entrance_cd_interior", "central_point_cd",     29),
    # central pivot + cafeteria (reached from both entrances)
    ("central_point_cd", "cafeteria", 7),
    # back entrance + rear core
    ("back_entrance_cd_exterior", "back_entrance_cd_interior",  6),
    ("back_entrance_cd_exterior", "stairs_rear",               11),
    ("back_entrance_cd_exterior", "elevator_rear",             11),
    ("stairs_rear",               "elevator_rear",              4),
    ("back_entrance_cd_interior", "central_point_cd",          12),
]

CD_EDGES_P1 = [
    # lado main (con directorio)
    ("stairs",              "directory_sign_cd_1", 4),
    ("directory_sign_cd_1", "elevator",            2),
    ("elevator",            "bathroom_men",        3),
    # cadena de aulas cruzando el pasillo
    ("bathroom_men",     "classroom_cd_1_1", 10),
    ("classroom_cd_1_1", "classroom_cd_1_2", 10),
    ("classroom_cd_1_2", "classroom_cd_1_3", 10),
    ("classroom_cd_1_3", "classroom_cd_1_4", 10),
    # lado rear (sin directorio)
    ("classroom_cd_1_4", "bathroom_women",   3),
    ("bathroom_women",   "elevator_rear",    3),
    ("elevator_rear",    "stairs_rear",      4),
]

CD_EDGES_P2 = [
    ("stairs",              "directory_sign_cd_2", 4),
    ("directory_sign_cd_2", "elevator",            2),
    ("elevator",            "bathroom_men",        3),
    ("bathroom_men",     "classroom_cd_2_5", 10),
    ("classroom_cd_2_5", "classroom_cd_2_6", 10),
    ("classroom_cd_2_6", "classroom_cd_2_7", 10),
    ("classroom_cd_2_7", "classroom_cd_2_8", 10),
    ("classroom_cd_2_8", "bathroom_women",   3),
    ("bathroom_women",   "elevator_rear",    3),
    ("elevator_rear",    "stairs_rear",      4),
]


# =========================================================================
# Stub buildings (entrance-only, no interior topology).
# Each stub building has a single entrance node; a planner can route a user
# to the stub's entrance via outdoor_walk but cannot navigate inside.
# Detailed internal topology for these is left as future work.
# =========================================================================
STUB_BUILDINGS = {
    # building id -> (name as in JSON, canonical entrance id)
    3:  ("H",       "entrance_h"),
    4:  ("P",       "entrance_p"),
    5:  ("O",       "entrance_o"),
    6:  ("M",       "entrance_m"),
    7:  ("N",       "entrance_n"),
    8:  ("CSQ",     "entrance_csq"),
    9:  ("K",       "entrance_k"),
    10: ("CSC",     "entrance_csc"),
    11: ("C",       "entrance_c"),
    12: ("E",       "entrance_e"),
    13: ("CM",      "entrance_cm"),
    14: ("LCB",     "entrance_lcb"),
    15: ("Rodilla", "entrance_rodilla"),
    16: ("Chapel",  "entrance_chapel"),
}

# Fixed default outdoor distance (m) between buildings. Google Maps provides
# the actual metric path during navigation on the mobile app — this constant
# exists so the PDDL planner has a consistent cost signal for outdoor hops.
OUTDOOR_DISTANCE_M = 50


def make_local_conns(building: str, floor: int, edges_pasos):
    """Expand (a, b, pasos) tuples into two directed local_connections entries."""
    out = []
    for a, b, pasos in edges_pasos:
        dist = m(pasos)
        out.append({"building": building, "floor": floor, "from": a, "to": b, "distance_m": dist})
        out.append({"building": building, "floor": floor, "from": b, "to": a, "distance_m": dist})
    return out


def main():
    with TOPOLOGY.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # --- Building metadata ---------------------------------------------------
    # G: 4 floors, elevators+stairs.
    # CD: 4 floors, dual vertical cores (elevator/elevator_rear,
    # stairs/stairs_rear), pool on p-1.
    # Everything else: stub — floor 0 only, no elevator, no stairs inside
    # (the graph just stops at the entrance).
    for b in data["buildings"]:
        if b["id"] == 1:
            b["floors"] = [-1, 0, 1, 2]
            b["elevators"] = True
            b["stairs"] = True
        elif b["id"] == 2:
            b["floors"] = [-1, 0, 1, 2]
            b["elevators"] = True
            b["stairs"] = True
            b["pool_floor"] = -1
        elif b["id"] in STUB_BUILDINGS:
            b["floors"] = [0]
            b["elevators"] = False
            b["stairs"] = False

    # --- Location sets -------------------------------------------------------
    data["locations"]["G"] = G_LOCATIONS
    data["locations"]["CD"] = CD_LOCATIONS
    for bid, (name, entrance_id) in STUB_BUILDINGS.items():
        data["locations"][name] = {
            "0": [{"id": entrance_id, "type": "entrance"}]
        }

    # --- Local connections ---------------------------------------------------
    data["local_connections"] = [
        c for c in data["local_connections"]
        if c.get("building") in ("G", "CD")  # stubs have none
    ]
    # Drop G/CD entries and repopulate (we're the authoritative source).
    data["local_connections"] = [
        c for c in data["local_connections"] if c.get("building") not in ("G", "CD")
    ]
    data["local_connections"].extend(make_local_conns("G", -1, G_EDGES_AGORA))
    data["local_connections"].extend(make_local_conns("G",  0, G_EDGES_P0))
    data["local_connections"].extend(make_local_conns("G",  1, G_EDGES_P1))
    data["local_connections"].extend(make_local_conns("G",  2, G_EDGES_P2))
    data["local_connections"].extend(make_local_conns("CD", -1, CD_EDGES_P_MINUS_1))
    data["local_connections"].extend(make_local_conns("CD",  0, CD_EDGES_P0))
    data["local_connections"].extend(make_local_conns("CD",  1, CD_EDGES_P1))
    data["local_connections"].extend(make_local_conns("CD",  2, CD_EDGES_P2))

    # --- Outdoor connections (cross-building hallways) -----------------------
    # Authoritative rule:
    #   * G (1) ↔ CD (2)  — the main spine.
    #   * Each stub ↔ G  AND  each stub ↔ CD — every stub reachable from both.
    # All edges carry the default outdoor distance. Real metric comes from
    # Google Maps at runtime in the mobile app.
    outdoor: list = []

    def outdoor_pair(b1: int, b2: int):
        outdoor.append({
            "from": {"building": b1, "floor": 0},
            "to":   {"building": b2, "floor": 0},
            "type": "hallway",
            "distance_m": OUTDOOR_DISTANCE_M,
        })
        outdoor.append({
            "from": {"building": b2, "floor": 0},
            "to":   {"building": b1, "floor": 0},
            "type": "hallway",
            "distance_m": OUTDOOR_DISTANCE_M,
        })

    outdoor_pair(1, 2)  # G ↔ CD
    for bid in STUB_BUILDINGS:
        outdoor_pair(1, bid)   # G ↔ stub
        outdoor_pair(2, bid)   # CD ↔ stub

    data["connections"] = outdoor

    # --- Functional goals ----------------------------------------------------
    data["functional_locations"] = {
        "cafeteria": {"building": 2, "floor": 0},
        "gym":       {"building": 2, "floor": -1},
        "pool":      {"building": 2, "floor": -1},
    }

    with TOPOLOGY.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {TOPOLOGY}")


if __name__ == "__main__":
    main()

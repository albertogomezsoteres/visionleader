"""Small shared helpers used by both PDDL converters."""


def floor_str(floor: int) -> str:
    """Convert a floor number to a valid PDDL identifier (e.g. -1 -> planta_m1)."""
    if floor < 0:
        return f"planta_m{abs(floor)}"
    return f"planta_{floor}"

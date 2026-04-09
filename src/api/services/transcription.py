"""
Whisper post-processing: fix common transcription mistakes for campus terms.

Whisper often mishears domain-specific words (building names, "gym" → "jim",
floor numbers, room identifiers, etc.).  We apply regex-based corrections
using the campus graph as a vocabulary reference.
"""

import re
from typing import Optional

_WORD_FIXES: dict[str, str] = {
    "jim": "gym",
    "gim": "gym",
    "jimnasium": "gymnasium",
    "jym": "gym",
    "gymn": "gym",
    "caffeteria": "cafeteria",
    "kafoturia": "cafeteria",
    "cafeturia": "cafeteria",
    "cafetaria": "cafeteria",
    "kafeteria": "cafeteria",
    "cafateria": "cafeteria",
    "cafetiria": "cafeteria",
    "elevaor": "elevator",
    "elavator": "elevator",
    "elevater": "elevator",
    "staris": "stairs",
    "stares": "stairs",
    "stears": "stairs",
    "bilding": "building",
    "buidling": "building",
    "biulding": "building",
    "buiding": "building",
    "flor": "floor",
    "flore": "floor",
    "restrom": "restroom",
    "restrrom": "restroom",
    "batroom": "bathroom",
    "labratory": "laboratory",
    "laborotory": "laboratory",
    "labrotory": "laboratory",
    "secritary": "secretary",
    "secretery": "secretary",
    "secratary": "secretary",
    "classrom": "classroom",
    "clas room": "classroom",
    "clasroom": "classroom",
    "intrance": "entrance",
    "enterance": "entrance",
    "entrace": "entrance",
    "entrence": "entrance",
    "mentaring": "mentoring",
    "mentorig": "mentoring",
    "mentring": "mentoring",
}

_PHRASE_FIXES: list[tuple[str, str]] = [
    (r"\bbuilding\s+age\b", "building H"),
    (r"\bbuilding\s+a(?:ch|ge|sh)\b", "building H"),
    (r"\bbuilding\s+a\b(?!\w)", "building H"),
    (r"\bbuilding\s+(?:see|cee)\s*(?:dee|de)\b", "building CD"),
    (r"\bbuilding\s+si\s*di\b", "building CD"),
    (r"\bbuilding\s+gee\b", "building G"),
    (r"\broom\s+zero\s*(?:point|dot)\s*one\b", "room 0.1"),
    (r"\broom\s+zero\s*(?:point|dot)\s*three\b", "room 0.3"),
    (r"\broom\s+one\s*(?:point|dot)\s*one\b", "room 1.1"),
    (r"\broom\s+one\s*(?:point|dot)\s*four\b", "room 1.4"),
    (r"\broom\s+two\s*(?:point|dot)\s*one\b", "room 2.1"),
    (r"\bclassroom\s+zero\s*(?:point|dot)\s*one\b", "classroom 0.1"),
    (r"\bclassroom\s+zero\s*(?:point|dot)\s*three\b", "classroom 0.3"),
    (r"\bclassroom\s+one\s*(?:point|dot)\s*one\b", "classroom 1.1"),
    (r"\bclassroom\s+one\s*(?:point|dot)\s*four\b", "classroom 1.4"),
    (r"\bclassroom\s+two\s*(?:point|dot)\s*one\b", "classroom 2.1"),
    (r"\bi'?m lost\b", "I'm lost"),
    (r"\bi'?m in a(?:\s+big)? hurry\b", "I'm in a hurry"),
    (r"\bi'?m in a rush\b", "I'm in a hurry"),
    (r"\bi am lost\b", "I'm lost"),
]


def correct_whisper_transcription(text: str, campus_graph: dict) -> str:
    """Apply domain-aware corrections to raw Whisper output."""
    if not text:
        return text

    original_text = text

    for wrong, correct in _WORD_FIXES.items():
        text = re.sub(r"\b" + re.escape(wrong) + r"\b", correct, text, flags=re.IGNORECASE)

    for pattern, replacement in _PHRASE_FIXES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    if text != original_text:
        print(f"[CORRECTION] '{original_text}' -> '{text}'")

    return text.strip()

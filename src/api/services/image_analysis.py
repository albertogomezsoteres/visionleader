"""
Image analysis service — all PaliGemma-related logic lives here.

This module handles:
  - Parsing raw PaliGemma text into structured location data
  - Classifying image types (elevator, stairs, sign, door)
  - Running the multi-prompt analysis chain via Colab or locally
  - Generating clarification questions when info is incomplete

The routers call the high-level functions at the bottom of this file;
everything above is internal helpers.
"""

import io
import re
import json as _json
import requests
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from api.models import ImageAnalysisResponse
from api.dependencies import load_campus_graph, load_paligemma_model, COLAB_API_URL
from navigation.agents import Agent1_Identifier, CLASSIFIER_PROMPT


# ═══════════════════════════════════════════════════════════════════════════
# Small helpers
# ═══════════════════════════════════════════════════════════════════════════

def extract_floor_from_room_code(text: str) -> Optional[int]:
    """
    Try to pull a floor number out of a room code string.
    Examples: "Aula 2.1" → 2, "Lab 1.3" → 1, "Room 205" → 2
    """
    if not text or text.strip().lower() in ("none", "no", ""):
        return None
    text = text.strip()

    # "Aula 2.1", "Lab 1.3", "Despacho 205", etc.
    p1 = re.search(
        r"(?:aula|lab|laboratorio|despacho|room|clase|classroom|office|sala|seminar)\s*(\d+)[.\-]",
        text, re.IGNORECASE,
    )
    if p1:
        val = int(p1.group(1))
        if -1 <= val <= 4:
            return val

    # "X.Y" where X is a valid floor
    p2 = re.search(r"\b([0-4])\.\d+\b", text)
    if p2:
        return int(p2.group(1))

    # Three-digit code like "201" → hundreds digit is the floor
    p3 = re.search(r"\b(\d{3})\b", text)
    if p3:
        hundreds = int(p3.group(1)) // 100
        if 0 <= hundreds <= 4:
            return hundreds

    # Single digit
    p4 = re.search(r"\b([0-4])\b", text)
    if p4:
        return int(p4.group(1))

    return None


def parse_paligemma_json(response_text: str) -> dict:
    """Best-effort JSON extraction from a PaliGemma response."""
    _default = {
        "building_code": None, "floor": None, "confidence": "none",
        "visible_text": [], "landmarks": [],
        "reason": "JSON parse failed, raw: " + (response_text or "")[:100],
    }
    if not response_text:
        return _default
    try:
        result = _json.loads(response_text.strip())
        if isinstance(result, dict):
            return result
    except _json.JSONDecodeError:
        pass
    match = re.search(r"\{.*?\}", response_text, re.DOTALL)
    if match:
        try:
            result = _json.loads(match.group())
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return _default


def _normalize_image_type(raw: Optional[str]) -> Optional[str]:
    """Map the classifier output to one of: elevator, stairs, sign, door, other."""
    if not raw:
        return None
    r = raw.strip().lower()

    if r in ("elevator", "lift", "ascensor"):
        return "elevator"
    if r in ("stairs", "staircase", "escaleras", "escalera"):
        return "stairs"
    if r in ("sign", "directory", "cartel", "señal"):
        return "sign"
    if r in ("door", "puerta"):
        return "door"
    if r == "other":
        return "other"

    if any(w in r for w in ("elevator", "lift", "ascensor")):
        return "elevator"
    if any(w in r for w in ("stair", "escalera", "escaleras", "steps")):
        return "stairs"
    if any(w in r for w in ("directory", "cartel", "facilities", "floor plan", "sign")):
        return "sign"
    if "door" in r or "puerta" in r:
        return "door"

    return None


def _floor_text(floor: int) -> str:
    """Human-readable English floor name."""
    if floor == -1: return "the basement"
    if floor == 0:  return "the ground floor"
    if floor == 1:  return "the 1st floor"
    if floor == 2:  return "the 2nd floor"
    if floor == 3:  return "the 3rd floor"
    return f"floor {floor}"


def _parse_floor_direct(text: str) -> Optional[int]:
    """Quick extraction of a single floor number from a short string."""
    if not text:
        return None
    m = re.search(r"(?<!\d)(-?\d+)(?!\d)", text.strip())
    if m:
        val = int(m.group(1))
        if -5 <= val <= 10:
            return val
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Building + floor extraction from PaliGemma free-text responses
# ═══════════════════════════════════════════════════════════════════════════

def get_paligemma_prompts(campus_graph: Optional[dict] = None) -> list[str]:
    """Return the ordered prompt list from Agent1."""
    building_codes = ["G", "CD", "H"]
    return Agent1_Identifier.get_prompts(building_codes=building_codes)


def building_name(building_id: Optional[int], campus_graph: dict) -> str:
    """Short name for a building id (e.g. 'G', 'CD')."""
    if building_id is None:
        return "unknown"
    for b in campus_graph.get("buildings", []):
        if b.get("id") == building_id:
            return b.get("name", f"Building {building_id}")
    return f"Building {building_id}"


def parse_location_from_paligemma_response(response: str, campus_graph: dict) -> dict:
    """
    Extract building id and floor number from free-text PaliGemma output.
    We try many regex patterns because the model responds unpredictably.
    """
    result = {"building": None, "floor": None, "error": None}
    response_lower = response.lower()

    # Build lookup maps
    building_map: dict[str, int] = {}
    name_to_id: dict[str, int] = {}
    for b in campus_graph.get("buildings", []):
        bid = b.get("id")
        name = b.get("name", "").upper()
        full_name = b.get("full_name", "").lower()
        building_map[name] = bid
        name_to_id[name.lower()] = bid
        name_to_id[full_name] = bid
        if "politécnica" in full_name or "politecnica" in full_name:
            name_to_id["escuela politecnica"] = bid
            name_to_id["escuela politécnica"] = bid
            name_to_id["g"] = bid
        if "deportivo" in full_name:
            name_to_id["centro deportivo"] = bid

    building_found = None
    building_codes = ["G", "CD", "H"]

    # Compact pattern: "g0", "cd-1", "h2"
    _compact_code_map = {"G": 1, "CD": 2, "H": 3}
    for b in campus_graph.get("buildings", []):
        bname = b.get("name", "").upper()
        if bname in _compact_code_map and b.get("id") is not None:
            _compact_code_map[bname] = b["id"]

    compact_match = re.search(r"\b(eps|g|cd|h)(\s*-?\s*\d+)\b", response.strip(), re.IGNORECASE)
    if compact_match:
        compact_code = compact_match.group(1).upper()
        compact_floor_str = compact_match.group(2).replace(" ", "")
        try:
            compact_floor = int(compact_floor_str)
            if -1 <= compact_floor <= 4:
                building_id_compact = _compact_code_map.get(compact_code)
                if building_id_compact is not None:
                    result["building"] = building_id_compact
                    result["floor"] = compact_floor
                    return result
        except ValueError:
            pass

    # Very short response — might be just the building code
    response_stripped = response.strip()
    if len(response_stripped) <= 3:
        for code in building_codes:
            if response_stripped.upper() == code.upper():
                building_found = code.upper()
                break

    # Try regex patterns to find building code in longer text
    if not building_found:
        for code in building_codes:
            if len(code) == 1:
                pattern1 = r"(?:in\s+(?:the\s+)?)?(?:edificio|building)\s+" + re.escape(code) + r"\b"
                pattern1b = r"\b" + re.escape(code) + r"\s+(?:building|edificio)"
                pattern1c = r"(?<![a-zA-Z0-9])" + re.escape(code) + r"(?![a-zA-Z0-9])"
                pattern1d = r"(?:edificio|building)\s+" + re.escape(code) + r"\s*/\s*" + re.escape(code) + r"\s+(?:building|edificio)"
                pattern1f = r"(?:shows?|says?|displays?|indicates?)\s+(?:edificio|building)\s+" + re.escape(code) + r"\b"
                pattern2 = r"(?:on|in|at)?building\s+(?<![a-zA-Z0-9])" + re.escape(code) + r"(?![a-zA-Z0-9])"
                pattern3 = r"(?<![a-zA-Z0-9])" + re.escape(code) + r"(?![a-zA-Z0-9])\s*building"
                pattern4 = r"edificio\s+(?<![a-zA-Z0-9])" + re.escape(code) + r"(?![a-zA-Z0-9])"
                patterns = [pattern1, pattern2, pattern3, pattern4, pattern1b, pattern1d, pattern1f, pattern1c]
            else:
                pattern1 = r"\b" + re.escape(code) + r"\b"
                pattern2 = r"(?:on|in|at)?building\s*" + re.escape(code) + r"\b"
                pattern3 = r"\b" + re.escape(code) + r"\s*building"
                pattern4 = r"edificio\s+" + re.escape(code) + r"\b"
                patterns = [pattern1, pattern2, pattern3, pattern4]

            for pat in patterns:
                if pat and re.search(pat, response, re.IGNORECASE):
                    building_found = code.upper()
                    # Guard against false positives for single-letter codes
                    if code.upper() == "B" and "11" in response.lower():
                        building_found = None
                        continue
                    break
            if building_found:
                break

    # Fall back to full building names
    if not building_found:
        valid_codes_lower = {c.lower() for c in building_codes}
        for name, bid in name_to_id.items():
            if len(name) == 1 and name not in valid_codes_lower:
                continue
            if name in response_lower:
                for b in campus_graph.get("buildings", []):
                    if b.get("id") == bid:
                        building_found = b.get("name", "").upper()
                        break
                if building_found:
                    break

    if building_found:
        # Reject suspicious patterns like "11 building"
        if len(building_found) == 1 and re.search(r"\d+\s+building", response, re.IGNORECASE):
            building_found = None
        else:
            result["building"] = building_map.get(building_found)

    # Now look for the floor number
    floor_found = None
    floor_patterns = [
        r"(?:planta|piso|floor|nivel)\s*[:\-]?\s*(-?\d+)",
        r"(-?\d+)\s*(?:planta|piso|floor|nivel)",
        r"\b(-?\d+)\b",
    ]
    for pat in floor_patterns:
        matches = re.findall(pat, response, re.IGNORECASE)
        for m in matches:
            try:
                num = int(m)
                if num in [-1, 0, 1, 2]:
                    floor_found = num
                    break
            except ValueError:
                continue
        if floor_found is not None:
            break

    # Try word-based floor names
    if floor_found is None:
        word_to_num = {
            "primera": 1, "segunda": 2, "tercera": 3,
            "primero": 1, "segundo": 2, "tercero": 3,
            "sótano": -1, "sotano": -1, "planta baja": 0, "baja": 0,
            "agora": -1, "ágora": -1,
        }
        for word, num in word_to_num.items():
            if word in response_lower and num in [-1, 0, 1, 2]:
                floor_found = num
                break

    if floor_found is not None:
        result["floor"] = floor_found

    # Fill in a descriptive error when something is missing
    if result["building"] is None and result["floor"] is None:
        result["error"] = "Could not identify building or floor from the response"
    elif result["building"] is None:
        result["error"] = "Could not identify the building from the response"
    elif result["floor"] is None:
        result["error"] = "Could not identify the floor from the response"

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Clarification helpers (used when info is incomplete)
# ═══════════════════════════════════════════════════════════════════════════

def generate_clarification_question(
    building_id: Optional[int], floor: Optional[int], campus_graph: dict
) -> str:
    """Build a natural English question asking for the missing piece."""
    bname = None
    if building_id:
        for b in campus_graph.get("buildings", []):
            if b.get("id") == building_id:
                bname = b.get("name", f"Building {building_id}")
                if "Edificio" in bname:
                    bname = bname.replace("Edificio", "").strip()
                break

    if building_id and floor is None:
        if bname:
            return f"I can see you're in {bname}. Could you tell me which floor you're on?"
        return "I can see you're in a building, but I couldn't identify the floor. Which floor are you on?"
    if floor is not None and not building_id:
        ft = "ground floor" if floor == 0 else f"floor {floor}"
        return f"I can see you're on the {ft}, but I couldn't identify the building. Which building are you in?"
    return "I couldn't identify the location in the image. Could you tell me which building you see on the sign?"


def validate_user_response(user_response: str, campus_graph: dict) -> Tuple[bool, Optional[str]]:
    """Check if the user's text contains parseable location information."""
    rl = user_response.lower().strip()
    if len(rl) < 2:
        return False, "Sorry, I couldn't understand. Could you please repeat that?"

    # Known ASR artifacts
    for pat in [r"\bbuilding\s+age\b", r"\bonbuilding\b", r"\binbuilding\b"]:
        if re.search(pat, rl):
            return False, "Sorry, I couldn't understand clearly. Could you please repeat that more slowly?"

    parsed = parse_location_from_paligemma_response(user_response, campus_graph)
    if parsed.get("building") is None and parsed.get("floor") is None:
        kw = ["building", "edificio", "floor", "planta", "ground", "first", "second", "third", "h", "g", "cd"]
        if any(k in rl for k in kw):
            return False, "Sorry, I couldn't identify the building or floor clearly. Could you please repeat it?"
        if len(rl) > 10:
            return False, "Sorry, I couldn't identify the building or floor in your response. Could you please repeat it?"

    return True, None


# ═══════════════════════════════════════════════════════════════════════════
# Colab remote inference helper
# ═══════════════════════════════════════════════════════════════════════════

def _call_colab(
    colab_url: str,
    image_data: bytes,
    filename: str,
    content_type: str,
    prompt_text: str,
    *,
    skip_sorry_filter: bool = False,
    max_tokens: Optional[int] = None,
) -> Optional[str]:
    """Send a single prompt+image to the Colab endpoint and return the text (or None)."""
    if not prompt_text.strip().startswith("<image>"):
        prompt_text = "<image>\n" + prompt_text
    prompt_preview = re.sub(r"\s+", " ", prompt_text).strip()
    if len(prompt_preview) > 260:
        prompt_preview = prompt_preview[:260] + "..."
    print(f"[PALIGEMMA][PROMPT] {prompt_preview}")
    payload: dict = {"prompt": prompt_text}
    if max_tokens is not None:
        payload["max_tokens"] = str(max_tokens)
    try:
        resp = requests.post(
            f"{colab_url}/analyze",
            files={"file": (filename, image_data, content_type)},
            data=payload,
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[PALIGEMMA][ERROR] status={resp.status_code}")
            return None
        d = resp.json()
        raw = (d.get("response") or "").strip()
        print(f"[PALIGEMMA][RESPONSE] {raw!r}")
        if not d.get("success"):
            return None
        _invalid = {"none", "null", "n/a", "nothing", "unanswerable", "no", ""}
        if not raw or raw.lower() in _invalid or "unanswerable" in raw.lower():
            return None
        if not skip_sorry_filter and "sorry" in raw.lower():
            return None
        return raw
    except Exception as e:
        print(f"[PALIGEMMA][EXCEPTION] {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# High-level analysis entry points (called from routers)
# ═══════════════════════════════════════════════════════════════════════════

def analyze_image_via_colab(
    image_data: bytes,
    filename: str,
    content_type: str,
    campus_graph: dict,
    known_building: Optional[int],
    known_floor: Optional[int],
    colab_url: str,
) -> ImageAnalysisResponse:
    """
    Run the full multi-prompt analysis chain through the Colab tunnel.

    The chain works like this:
      1. Classify the image type (elevator / stairs / sign / door / other)
      2. Run type-specific prompts to extract location data
      3. If the sign prompt leaves gaps, try a cascade of fallback prompts
      4. Return structured result (or a clarification question)
    """
    prompts = get_paligemma_prompts(campus_graph)
    DEFAULT_MAX_TOKENS = 256

    def _colab(prompt, **kw):
        return _call_colab(colab_url, image_data, filename, content_type, prompt, **kw)

    # ── Step 0: classify the image ───────────────────────────────────────
    classifier_prompt = CLASSIFIER_PROMPT
    raw_type = _colab(classifier_prompt, skip_sorry_filter=True, max_tokens=64)
    image_type = _normalize_image_type(raw_type)
    print(f"\n--- CLASSIFIER ---  response={raw_type!r}  category={image_type!r}")

    # ── Elevator ─────────────────────────────────────────────────────────
    if image_type == "elevator":
        raw_elev = _colab(Agent1_Identifier.get_elevator_prompt(), skip_sorry_filter=True, max_tokens=DEFAULT_MAX_TOKENS)
        elevator_state = "open" if "open" in (raw_elev or "").lower() else "closed"
        effective_floor = known_floor

        if known_building is not None and effective_floor is not None:
            return ImageAnalysisResponse(
                success=True, raw_response=raw_elev or "", image_type="elevator",
                elevator_state=elevator_state, floor=effective_floor,
                needs_clarification=False, clarification_question=None,
            )

        # Build a descriptive clarification message
        oc = "open" if elevator_state == "open" else "closed"
        hint = "Directory signs are usually right next to the elevator and the stairs."
        if effective_floor is None and known_building is None:
            msg = f"In front of you there is an elevator with the doors {oc}. I still don't know your location. I need to know both your building and floor. {hint} You can also tell me by voice."
        elif known_floor is not None and known_building is None:
            msg = f"In front of you there is an elevator with the doors {oc}. I know you are on {_floor_text(known_floor)}, but I still need to know your building. {hint} You can also tell me by voice."
        else:
            msg = f"In front of you there is an elevator with the doors {oc}. I still need more information about your location. {hint} You can also tell me by voice."

        return ImageAnalysisResponse(
            success=False, raw_response=raw_elev or "", image_type="elevator",
            elevator_state=elevator_state, floor=effective_floor, building=known_building,
            needs_clarification=True, clarification_question=msg,
        )

    # ── Stairs ───────────────────────────────────────────────────────────
    if image_type == "stairs":
        raw_stairs = _colab(Agent1_Identifier.get_stairs_prompt(), skip_sorry_filter=True, max_tokens=8)
        r_st = (raw_stairs or "").lower()
        if "up" in r_st and "down" in r_st:
            direction = "both"
        elif "up" in r_st:
            direction = "up"
        elif "down" in r_st:
            direction = "down"
        else:
            direction = "both"
        raw_sf = _colab(Agent1_Identifier.get_stairs_floor_prompt(), skip_sorry_filter=True, max_tokens=8)
        floor_stairs = _parse_floor_direct(raw_sf) if raw_sf else None
        effective_floor = known_floor if known_floor is not None else floor_stairs
        return ImageAnalysisResponse(
            success=False, raw_response=raw_stairs or "", image_type="stairs",
            stairs_direction=direction, building=known_building, floor=effective_floor,
            needs_clarification=True, clarification_question="stairs",
        )

    # ── Door ─────────────────────────────────────────────────────────────
    if image_type == "door":
        raw_door = _colab(Agent1_Identifier.get_door_prompt(), skip_sorry_filter=True, max_tokens=DEFAULT_MAX_TOKENS)
        floor_from_door = extract_floor_from_room_code(raw_door or "")
        return ImageAnalysisResponse(
            success=True, raw_response=raw_door or "", floor=floor_from_door,
            image_type="door", needs_clarification=False, clarification_question=None,
            confidence="medium" if floor_from_door is not None else "none",
        )

    # ── Other (unrecognised) ─────────────────────────────────────────────
    if image_type == "other":
        return ImageAnalysisResponse(
            success=False, raw_response=raw_type or "", image_type="other",
            needs_clarification=True,
            clarification_question="I cannot identify the navigation element. Please take a photo of a directory sign.",
        )

    # ── Sign (or classifier returned None — we assume sign) ─────────────
    building_codes = ["G", "CD", "H"]
    sign_prompt = Agent1_Identifier.get_sign_prompt(building_codes)
    raw = _colab(sign_prompt, max_tokens=DEFAULT_MAX_TOKENS)
    print(f"--- SIGN ---  response={raw!r}")

    json_parsed = parse_paligemma_json(raw or "")
    agent1 = Agent1_Identifier.parse_response(raw or "", campus_graph)
    parsed = parse_location_from_paligemma_response(raw or "", campus_graph)

    building_id = agent1.get("building") or parsed.get("building")
    floor_num = agent1.get("floor") or parsed.get("floor")

    # UFV-only sign (no building code visible)
    if raw and "ufv" in raw.lower():
        building_id = None
        ufv_prompt = (
            "<image>\nLook at the top right corner of this sign. "
            "There is a large building letter (e.g. G, H, CD). "
            "Directly below that letter is the floor indicator. "
            "Reply with ONLY that number or word, nothing else."
        )
        raw_ufv = _colab(ufv_prompt, max_tokens=32)
        if raw_ufv:
            ufv_word = raw_ufv.strip().lower()
            if ufv_word in ("agora", "ágora"):
                floor_num = -1
            else:
                f_ufv = _parse_floor_direct(raw_ufv)
                if f_ufv is not None:
                    floor_num = f_ufv

    # Override with JSON-parsed values if available
    if json_parsed.get("building_code"):
        bc = json_parsed["building_code"].upper()
        for b in campus_graph.get("buildings", []):
            if b.get("name", "").upper() == bc:
                building_id = b["id"]
                break
    if json_parsed.get("floor") is not None:
        try:
            floor_num = int(json_parsed["floor"])
        except (ValueError, TypeError):
            pass

    landmarks = json_parsed.get("landmarks") or agent1.get("landmarks", [])
    resources = agent1.get("resources", [])

    # Confidence level
    json_conf = json_parsed.get("confidence")
    if json_conf and json_conf != "none":
        confidence = json_conf
    elif building_id is not None and floor_num is not None:
        confidence = "high"
    elif building_id is not None or floor_num is not None:
        confidence = "medium"
    else:
        confidence = "none"

    # ── Fallback prompts if floor is still unknown ───────────────────────
    if floor_num is None and len(prompts) > 1:
        raw2 = _colab(prompts[1], max_tokens=DEFAULT_MAX_TOKENS)
        if raw2:
            j2 = parse_paligemma_json(raw2)
            if j2.get("floor") is not None:
                try: floor_num = int(j2["floor"])
                except (ValueError, TypeError): pass
            if floor_num is None:
                p2 = parse_location_from_paligemma_response(raw2, campus_graph)
                floor_num = p2.get("floor") or _parse_floor_direct(raw2)

    if floor_num is None and len(prompts) > 2:
        raw3 = _colab(prompts[2], max_tokens=DEFAULT_MAX_TOKENS)
        floor_num = _parse_floor_direct(raw3)

    if floor_num is None and len(prompts) > 4:
        raw5 = _colab(prompts[4], max_tokens=DEFAULT_MAX_TOKENS)
        if raw5:
            f_room = extract_floor_from_room_code(raw5)
            if f_room is not None:
                floor_num = f_room
                if confidence == "none": confidence = "medium"

    if floor_num is None and len(prompts) > 5:
        raw6 = _colab(prompts[5], max_tokens=DEFAULT_MAX_TOKENS)
        if raw6:
            f_text = extract_floor_from_room_code(raw6)
            if f_text is not None:
                floor_num = f_text
                if confidence == "none": confidence = "medium"
            if floor_num is None:
                p6 = parse_location_from_paligemma_response(raw6, campus_graph)
                floor_num = p6.get("floor") or _parse_floor_direct(raw6)
                if floor_num is not None and confidence == "none": confidence = "medium"

    if floor_num is None and len(prompts) > 6:
        raw7 = _colab(prompts[6], max_tokens=DEFAULT_MAX_TOKENS)
        if raw7:
            f_dec = extract_floor_from_room_code(raw7)
            if f_dec is not None:
                floor_num = f_dec
                if confidence == "none": confidence = "medium"

    image_type = "sign"

    if building_id is not None and floor_num is not None:
        return ImageAnalysisResponse(
            success=True, building=building_id, floor=floor_num,
            raw_response=raw or "", needs_clarification=False, clarification_question=None,
            landmarks=landmarks or None, resources=resources or None,
            confidence=confidence, image_type=image_type,
        )

    question = generate_clarification_question(building_id, floor_num, campus_graph)
    return ImageAnalysisResponse(
        success=building_id is not None or floor_num is not None,
        building=building_id, floor=floor_num, raw_response=raw or "",
        needs_clarification=True, clarification_question=question,
        landmarks=landmarks or None, resources=resources or None,
        confidence=confidence, image_type=image_type,
    )


async def analyze_image_locally(
    image_data: bytes, campus_graph: dict, filename: str, content_type: str,
) -> ImageAnalysisResponse:
    """Fallback: run PaliGemma locally when Colab is unreachable."""
    try:
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        model, processor = load_paligemma_model()
        prompts = get_paligemma_prompts()
        from evaluation.inference import run_single_inference

        for idx, prompt in enumerate(prompts):
            try:
                prompt_preview = re.sub(r"\s+", " ", prompt).strip()
                if len(prompt_preview) > 260:
                    prompt_preview = prompt_preview[:260] + "..."
                print(f"[PALIGEMMA][LOCAL][PROMPT {idx + 1}/{len(prompts)}] {prompt_preview}")
                raw_response, _ = run_single_inference(
                    model=model, processor=processor, image=image,
                    question=prompt, max_new_tokens=100,
                )
                print(f"[PALIGEMMA][LOCAL][RESPONSE {idx + 1}/{len(prompts)}] {raw_response!r}")
                if "unanswerable" in raw_response.strip().lower():
                    continue
                parsed = parse_location_from_paligemma_response(raw_response, campus_graph)
                bid = parsed.get("building")
                fnum = parsed.get("floor")
                if bid is not None and fnum is not None:
                    return ImageAnalysisResponse(
                        success=True, building=bid, floor=fnum,
                        raw_response=raw_response, needs_clarification=False, clarification_question=None,
                    )
                if bid is not None or fnum is not None:
                    q = generate_clarification_question(bid, fnum, campus_graph)
                    return ImageAnalysisResponse(
                        success=False, building=bid, floor=fnum,
                        raw_response=raw_response, needs_clarification=True, clarification_question=q,
                    )
                if idx == len(prompts) - 1:
                    q = generate_clarification_question(None, None, campus_graph)
                    return ImageAnalysisResponse(
                        success=False, raw_response=raw_response,
                        needs_clarification=True, clarification_question=q,
                    )
            except Exception:
                if idx == len(prompts) - 1:
                    raise
                continue

        q = generate_clarification_question(None, None, campus_graph)
        return ImageAnalysisResponse(
            success=False, raw_response="", needs_clarification=True, clarification_question=q,
        )
    except Exception as e:
        return ImageAnalysisResponse(
            success=False, raw_response="",
            error=f"Error processing image locally: {e}",
            needs_clarification=False, clarification_question=None,
        )

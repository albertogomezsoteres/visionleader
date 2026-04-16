"""
Image analysis service: orchestrates the PaliGemma 2 vision pipeline.

Sits between the HTTP router and VisionAnalyzer. Sends the image to
the Colab GPU endpoint, runs the two-stage pipeline, and builds the
structured ImageAnalysisResponse returned to the app.
"""

import re
import time
import requests
from typing import Optional

from api.schemas import ImageAnalysisResponse
from api.services.vision_analyzer import VisionAnalyzer


def extractFloorFromRoomCode(roomCode: str) -> Optional[int]:
    """Infers the floor from a room code string.
    Room codes follow FLOOR.NUMBER format, so '1.4' -> floor 1."""
    if not roomCode:
        return None
    match = re.search(r"\b([0-4])\.\d+\b", roomCode)
    if match:
        return int(match.group(1))
    return None


def _callColab(
    colabUrl: str,
    imageData: bytes,
    filename: str,
    contentType: str,
    promptText: str,
    maxTokens: Optional[int] = None,
) -> Optional[str]:
    """Sends one prompt and image to the Colab endpoint and returns the response text.
    Returns None if the request failed or the response was empty."""
    if not promptText.strip().startswith("<image>"):
        promptText = "<image>\n" + promptText

    print(f"[PALIGEMMA][PROMPT] {re.sub(r'\\s+', ' ', promptText).strip()[:400]}")

    payload: dict = {"prompt": promptText}
    if maxTokens is not None:
        payload["max_tokens"] = str(maxTokens)

    started = time.time()
    try:
        response = requests.post(
            f"{colabUrl}/analyze",
            files={"file": (filename, imageData, contentType)},
            data=payload,
            timeout=30,
        )
        elapsed = time.time() - started

        if response.status_code != 200:
            print(f"[PALIGEMMA][ERROR] HTTP {response.status_code} ({elapsed:.2f}s)")
            return None

        responseData = response.json()
        rawText = (responseData.get("response") or "").strip()
        print(f"[PALIGEMMA][RESPONSE] {rawText!r}  ({elapsed:.2f}s)")

        if not responseData.get("success"):
            return None

        return rawText or None

    except Exception as error:
        elapsed = time.time() - started
        print(f"[PALIGEMMA][EXCEPTION] {error}  ({elapsed:.2f}s)")
        return None


def analyzeImageViaColab(
    imageData: bytes,
    filename: str,
    contentType: str,
    campusGraph: dict,
    knownBuilding: Optional[int],
    knownFloor: Optional[int],
    colabUrl: str,
) -> ImageAnalysisResponse:
    """Analyses a photo using PaliGemma 2 on Colab.

    Stage 1: classify the image type (sign, door, elevator, stairs, other).
    Stage 2: extract the relevant detail for that type.
    Maximum 2 model calls per photo."""

    def _query(prompt: str, maxTokens: Optional[int] = None) -> Optional[str]:
        return _callColab(colabUrl, imageData, filename, contentType, prompt, maxTokens)

    # Stage 1: classify
    classifierResponse = _query(VisionAnalyzer.getClassifierPrompt(), maxTokens=16)
    imageType = VisionAnalyzer.parseClassifier(classifierResponse)
    print(f"\n[CLASSIFIER] response={classifierResponse!r} type={imageType!r}")

    # Stage 2: type-specific extraction

    if imageType == "elevator":
        elevatorResponse = _query(VisionAnalyzer.getElevatorPrompt(), maxTokens=8)
        doorState = VisionAnalyzer.parseElevator(elevatorResponse or "")
        print(f"[ELEVATOR] doorState={doorState!r}")
        return ImageAnalysisResponse(
            success=knownBuilding is not None and knownFloor is not None,
            image_type="elevator",
            elevator_state=doorState,
            building=knownBuilding, floor=knownFloor,
            raw_response=elevatorResponse or "",
        )

    if imageType == "stairs":
        stairsResponse = _query(VisionAnalyzer.getStairsPrompt(), maxTokens=8)
        stairsDirection = VisionAnalyzer.parseStairs(stairsResponse or "")
        print(f"[STAIRS] direction={stairsDirection!r}")
        return ImageAnalysisResponse(
            success=False, image_type="stairs",
            stairs_direction=stairsDirection,
            building=knownBuilding, floor=knownFloor,
            raw_response=stairsResponse or "",
        )

    if imageType == "door":
        doorResponse = _query(VisionAnalyzer.getDoorPrompt(), maxTokens=16)
        roomCode = VisionAnalyzer.parseDoor(doorResponse or "")
        floorFromCode = extractFloorFromRoomCode(roomCode) if roomCode else None
        print(f"[DOOR] roomCode={roomCode!r} floor={floorFromCode!r}")
        return ImageAnalysisResponse(
            success=roomCode is not None,
            image_type="door",
            raw_response=doorResponse or "",
            floor=floorFromCode,
            building=knownBuilding,
        )

    if imageType == "other":
        return ImageAnalysisResponse(
            success=False, image_type="other",
            raw_response=classifierResponse or "",
        )

    # Sign: also the default when classifier returns an unrecognised response

    signResponse = _query(VisionAnalyzer.getSignPrompt(), maxTokens=32)
    print(f"[SIGN] response={signResponse!r}")

    parsedSign = VisionAnalyzer.parseSign(signResponse or "", campusGraph)

    # Prefer what the model found, fall back to what the app already knew
    buildingId = parsedSign["building"] if parsedSign["building"] is not None else knownBuilding
    floorNumber = parsedSign["floor"] if parsedSign["floor"] is not None else knownFloor

    # If the sign prompt extracted nothing useful (no building, no floor), the
    # image may be a door plate misclassified as 'sign'. Try the door prompt as
    # a fallback — this covers the common case where a small room-number plaque
    # triggers the sign branch.
    if buildingId is None and floorNumber is None:
        doorResponse = _query(VisionAnalyzer.getDoorPrompt(), maxTokens=16)
        roomCode = VisionAnalyzer.parseDoor(doorResponse or "")
        if roomCode:
            floorFromCode = extractFloorFromRoomCode(roomCode)
            print(f"[SIGN→DOOR fallback] roomCode={roomCode!r} floor={floorFromCode!r}")
            return ImageAnalysisResponse(
                success=True,
                image_type="door",
                raw_response=doorResponse or "",
                floor=floorFromCode,
                building=knownBuilding,
            )

    return ImageAnalysisResponse(
        success=buildingId is not None and floorNumber is not None,
        image_type="sign",
        building=buildingId, floor=floorNumber,
        raw_response=signResponse or "",
    )

"""
Visual analysis module for PaliGemma 2.

Implements a two-stage prompting pipeline per image:
  Stage 1: classify what type of navigation element is visible.
  Stage 2: extract the relevant detail for that element type.

Maximum 2 model calls per photo. Each parser normalises the model
response so callers always receive clean data regardless of minor
variations in the model output.
"""

from typing import Optional
import re


class VisionAnalyzer:
    """
    Builds prompts for PaliGemma 2 and parses its responses.

    All prompts list the valid options explicitly so the model picks
    from a known set rather than generating freely. This constrained
    approach improves reliability on a 3B parameter model.
    """

    # Prompts

    @staticmethod
    def getClassifierPrompt() -> str:
        """Stage 1 prompt. Uses PaliGemma's native 'answer' task prefix with
        inline descriptions so the model understands each category.
        Expected response: one word from {sign, door, elevator, stairs, other}."""
        return (
            "<image>\n"
            "answer with one word: is this a "
            "sign (large wall-mounted directory board or floor map), "
            "door (room door with a small number plate like 1.4), "
            "elevator (lift doors or interior), "
            "stairs (staircase), "
            "or other?"
        )

    @staticmethod
    def getSignPrompt() -> str:
        """Stage 2 prompt for directory signs. Uses native 'answer' prefix.
        Expected response format: 'BUILDING FLOOR', e.g. 'G 1', 'CD -1', 'H 0'."""
        return (
            "<image>\n"
            "answer what building letter and floor number does this directory sign show? "
            "Building: G, CD, or H. "
            "Floor: -1, 0, 1, or 2. "
            "Answer as two values like G 0, G 1, CD -1, H 1, or unknown."
        )

    @staticmethod
    def getDoorPrompt() -> str:
        """Stage 2 prompt for classroom doors. Uses native 'ocr' task prefix
        so PaliGemma extracts all visible text from the door plate.
        The existing parseDoor() parser then picks out the room code."""
        return "<image>\nocr"

    @staticmethod
    def getElevatorPrompt() -> str:
        """Stage 2 prompt for elevator images. Uses native 'answer' task prefix.
        Expected response: 'open' or 'closed'."""
        return "<image>\nanswer are the elevator doors open or closed?"

    @staticmethod
    def getStairsPrompt() -> str:
        """Stage 2 prompt for staircase images. Uses native 'answer' task prefix.
        Expected response: 'up', 'down', or 'both'."""
        return "<image>\nanswer from here can you go up, down, or both directions on these stairs?"

    # Parsers

    @staticmethod
    def parseClassifier(response: str) -> Optional[str]:
        """Parses the classifier response into a known category.
        Tries exact match first, then word-boundary search for verbose responses.
        Returns None if the response is empty or unrecognisable."""
        if not response:
            return None

        cleanedResponse = response.strip().lower()
        validCategories = ("elevator", "stairs", "sign", "door", "other")

        if cleanedResponse in validCategories:
            return cleanedResponse

        for category in validCategories:
            if re.search(rf"\b{category}\b", cleanedResponse):
                return category

        return None

    @staticmethod
    def parseSign(response: str, campusGraph: dict) -> dict:
        """Parses the sign response into a building ID and floor number.

        Handles format variations: 'G 1', 'G1', 'CD-1', 'CD 0'.
        CD is listed before G and H in the regex to prevent partial matches.
        Returns a dict with keys 'building' and 'floor', either can be None."""
        result: dict = {"building": None, "floor": None}

        if not response or "unknown" in response.strip().lower():
            return result

        buildingNameToId = {
            b["name"].upper(): b["id"]
            for b in campusGraph.get("buildings", [])
        }

        # Try to match building and floor together: 'G 1', 'G1', 'CD-1'
        fullMatch = re.search(r"\b(CD|G|H)\s*(-?\d+)\b", response, re.IGNORECASE)
        if fullMatch:
            buildingCode = fullMatch.group(1).upper()
            result["building"] = buildingNameToId.get(buildingCode)
            result["floor"] = int(fullMatch.group(2))
            return result

        # Partial match: building only
        buildingMatch = re.search(r"\b(CD|G|H)\b", response, re.IGNORECASE)
        if buildingMatch:
            result["building"] = buildingNameToId.get(buildingMatch.group(1).upper())

        # Partial match: floor only
        floorMatch = re.search(r"\b(-?\d+)\b", response)
        if floorMatch:
            floorValue = int(floorMatch.group(1))
            if -5 <= floorValue <= 5:
                result["floor"] = floorValue

        return result

    @staticmethod
    def parseDoor(response: str) -> Optional[str]:
        """Extracts and normalises the room code from a door image response.

        Handles variations the model might produce:
          '1.4'      -> returned as-is
          'Aula 1.4' -> extracts '1.4'
          '14'       -> inserted dot gives '1.4'
          '1.30'     -> trailing zero stripped gives '1.3'

        Returns the normalised room code, or None if nothing was found."""
        if not response or response.strip().lower() in ("none", "no", ""):
            return None

        # Look for a code that already has a dot: '1.4', '0.3', '1.30'
        dotPattern = re.search(r"\b(\d+\.\d+)\b", response)
        if dotPattern:
            rawCode = dotPattern.group(1)
            codeMatch = re.match(r"^(\d+)\.(\d+)$", rawCode)
            if codeMatch:
                floorPart = int(codeMatch.group(1))
                roomPart = codeMatch.group(2).rstrip("0") or "0"
                return f"{floorPart}.{roomPart}"
            return rawCode

        # Fallback: two-digit compact code like '14' -> '1.4'
        compactPattern = re.search(r"\b(\d{2})\b", response)
        if compactPattern:
            digits = compactPattern.group(1)
            return f"{digits[0]}.{digits[1]}"

        return None

    @staticmethod
    def parseElevator(response: str) -> str:
        """Returns 'open' or 'closed' based on the model response.
        Defaults to 'closed' when the response is empty or unclear."""
        if response and "open" in response.lower():
            return "open"
        return "closed"

    @staticmethod
    def parseStairs(response: str) -> str:
        """Returns 'up', 'down', or 'both' based on the model response.
        Defaults to 'both' when the response is empty or unclear."""
        if not response:
            return "both"

        cleaned = response.strip().lower()

        if "both" in cleaned:
            return "both"
        if "up" in cleaned:
            return "up"
        if "down" in cleaned:
            return "down"

        return "both"

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
        """Stage 1 prompt. Identifies the type of navigation element in the image.
        Expected response: one word from {sign, door, elevator, stairs, other}."""
        return (
            "<image>\n"
            "What type of navigation element is shown in this image?\n\n"
            "Options:\n"
            "- sign     : a directory board or information panel\n"
            "- door     : a room door with a number or label\n"
            "- elevator : elevator doors or elevator interior\n"
            "- stairs   : a staircase\n"
            "- other    : none of the above\n\n"
            "Answer with ONE word only."
        )

    @staticmethod
    def getSignPrompt() -> str:
        """Stage 2 prompt for directory signs.
        Expected response format: 'BUILDING FLOOR', e.g. 'G 1', 'CD -1', 'H 0'."""
        return (
            "<image>\n"
            "This is a campus directory sign. What building and floor does it show?\n\n"
            "Building options: G, CD, H\n"
            "Floor options: -1 (basement), 0 (ground floor), 1 (first floor), 2 (second floor)\n\n"
            "Answer format: BUILDING FLOOR\n"
            "Examples: G 0 | G 1 | G 2 | CD -1 | CD 0 | H 1\n\n"
            "If the sign is not readable, answer: unknown"
        )

    @staticmethod
    def getDoorPrompt() -> str:
        """Stage 2 prompt for classroom doors.
        Expected response: a room code like '1.4', or 'none' if not visible."""
        return (
            "<image>\n"
            "What is the room code or label written on this door?\n\n"
            "It could be a number code like: 0.1, 0.2, 0.3, 0.4, 0.5, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1\n"
            "Or a named room like: AI Lab, Laboratorio IA, I.A, Telefonica, Computer Lab, Laboratorio Informatica\n\n"
            "Write ONLY what you see on the door, for example: 1.4 or AI Lab\n"
            "If nothing is visible, write: none"
        )

    @staticmethod
    def getElevatorPrompt() -> str:
        """Stage 2 prompt for elevator images.
        Expected response: 'open' or 'closed'."""
        return (
            "<image>\n"
            "Look at the elevator doors in this image.\n\n"
            "Are the doors open or closed?\n\n"
            "Options: open / closed\n\n"
            "Answer with ONE word only."
        )

    @staticmethod
    def getStairsPrompt() -> str:
        """Stage 2 prompt for staircase images.
        Expected response: 'up', 'down', or 'both'."""
        return (
            "<image>\n"
            "You are standing in front of this staircase.\n\n"
            "From this position, which directions can you take?\n\n"
            "Options:\n"
            "- up   : stairs go upward from here\n"
            "- down : stairs go downward from here\n"
            "- both : stairs go in both directions\n\n"
            "Answer with ONE word only."
        )

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

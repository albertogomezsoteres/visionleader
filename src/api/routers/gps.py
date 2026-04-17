"""GPS route endpoint: walking directions between campus buildings via Google Maps."""

import os
import re

import requests
from fastapi import APIRouter

from api.schemas import GPSRouteRequest, GPSRouteResponse

router = APIRouter()

# Hard-coded GPS coordinates for the UFV campus buildings.
# Kept in sync with mobile_app/lib/core/building_locations.dart.
_BUILDING_GPS = {
    1:  {"lat": 40.441595,         "lng": -3.833650,          "name": "G"},
    2:  {"lat": 40.441412,         "lng": -3.833501,          "name": "CD"},
    3:  {"lat": 40.44188726971171, "lng": -3.834391097938894, "name": "H"},
    4:  {"lat": 40.44298858275285, "lng": -3.835530301598534, "name": "P"},
    5:  {"lat": 40.44316885736018, "lng": -3.835200228598359, "name": "O"},
    6:  {"lat": 40.44240864976504, "lng": -3.834946704494870, "name": "M"},
    7:  {"lat": 40.44220340611667, "lng": -3.835944009359643, "name": "N"},
    8:  {"lat": 40.44183583314631, "lng": -3.835627725992759, "name": "CSQ"},
    9:  {"lat": 40.44198871772325, "lng": -3.835362731820506, "name": "K"},
    10: {"lat": 40.44156909752000, "lng": -3.835700385685151, "name": "CSC"},
    11: {"lat": 40.44104538179100, "lng": -3.834678875834694, "name": "C"},
    12: {"lat": 40.43980926640134, "lng": -3.835392650504404, "name": "E"},
    13: {"lat": 40.43961734118567, "lng": -3.833708655238037, "name": "CM"},
    14: {"lat": 40.43988083159466, "lng": -3.833195763291739, "name": "LCB"},
    15: {"lat": 40.44074823643942, "lng": -3.833941069721472, "name": "Rodilla"},
    16: {"lat": 40.44072231214621, "lng": -3.833342641737906, "name": "Capilla"},
}


@router.post("/gps-route", response_model=GPSRouteResponse)
async def get_gps_route(request: GPSRouteRequest):
    """
    Proxy Google Maps Directions API so the mobile app avoids CORS issues.
    Returns walking steps from one building to another.
    """
    try:
        origin_gps = _BUILDING_GPS.get(request.from_building)
        goal_gps = _BUILDING_GPS.get(request.to_building)
        if not origin_gps or not goal_gps:
            return GPSRouteResponse(
                success=False,
                error=f"No GPS data for buildings {request.from_building} -> {request.to_building}",
            )

        maps_key = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
        if not maps_key:
            return GPSRouteResponse(
                success=False,
                error="GOOGLE_MAPS_API_KEY not configured. Add it to .env.",
            )

        origin = f"{origin_gps['lat']},{origin_gps['lng']}"
        dest = f"{goal_gps['lat']},{goal_gps['lng']}"
        url = (
            f"https://maps.googleapis.com/maps/api/directions/json?"
            f"origin={origin}&destination={dest}&key={maps_key}&mode=walking&language=en"
        )
        resp = requests.get(url, timeout=10)
        data = resp.json()

        if data.get("status") == "OK" and data.get("routes"):
            leg = data["routes"][0]["legs"][0]
            return GPSRouteResponse(
                success=True,
                distance=leg["distance"]["text"],
                duration=leg["duration"]["text"],
                steps=[
                    {
                        "instruction": re.sub(r"<[^>]+>", "", s["html_instructions"]),
                        "distance": s["distance"]["text"],
                        "duration": s["duration"]["text"],
                        "startLocation": s["start_location"],
                        "endLocation": s["end_location"],
                    }
                    for s in leg["steps"]
                ],
                polyline=data["routes"][0]["overview_polyline"]["points"],
            )

        return GPSRouteResponse(
            success=False,
            error=f"Directions API returned status: {data.get('status')}",
        )
    except Exception as e:
        return GPSRouteResponse(success=False, error=f"Error fetching GPS route: {e}")

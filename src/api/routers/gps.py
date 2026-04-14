"""GPS route endpoint: walking directions between campus buildings via Google Maps."""

import os
import re

import requests
from fastapi import APIRouter

from api.schemas import GPSRouteRequest, GPSRouteResponse

router = APIRouter()

# Hard-coded GPS coordinates for the UFV campus buildings
_BUILDING_GPS = {
    1: {"lat": 40.441595, "lng": -3.833650, "name": "G"},
    2: {"lat": 40.441412, "lng": -3.833501, "name": "CD"},
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

import logging
from dataclasses import dataclass
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RouteEstimate:
    distance_km: Decimal
    duration_min: int | None
    provider: str = "OPEN_ROUTE_SERVICE"


class OpenRouteServiceClient:
    """Async client for OpenRouteService routing and directions API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openrouteservice.org",
        timeout_seconds: float = 6.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def calculate_route(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        profile: str = "driving-car",
    ) -> RouteEstimate | None:
        if not self.is_configured:
            return None

        # Coordinates in GeoJSON/OpenRouteService are [longitude, latitude]
        coordinates = [
            [round(start_lng, 6), round(start_lat, 6)],
            [round(end_lng, 6), round(end_lat, 6)],
        ]
        url = f"{self.base_url}/v2/directions/{profile}"
        headers = {
            "Authorization": self.api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"coordinates": coordinates}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.warning(
                        "OpenRouteService returned status %s: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return None
                data = response.json()
        except Exception as exc:
            logger.warning("OpenRouteService request error: %s", exc)
            return None

        routes = data.get("routes", [])
        if not routes:
            return None

        summary = routes[0].get("summary", {})
        distance_meters = summary.get("distance")
        duration_seconds = summary.get("duration")

        if distance_meters is None:
            return None

        distance_km = Decimal(str(round(distance_meters / 1000.0, 2)))
        duration_min = max(1, round(duration_seconds / 60.0)) if duration_seconds is not None else None

        return RouteEstimate(
            distance_km=distance_km,
            duration_min=duration_min,
            provider="OPEN_ROUTE_SERVICE",
        )

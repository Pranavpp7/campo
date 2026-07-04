import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# City resolution via Open-Meteo's free geocoding API (no key needed).
# This replaces the old hardcoded VENUES dict of World Cup host cities —
# geocoding works for any competition's cities, which is what makes the
# weather and distance tools competition-agnostic.

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# City coordinates never change — cache for the process lifetime.
_cache: dict[str, dict | None] = {}
TTL_GEO = 7 * 24 * 3600

_expiry: dict[str, float] = {}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def _geocode(name: str) -> dict | None:
    response = requests.get(
        GEOCODE_URL,
        params={"name": name, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    return results[0] if results else None


def resolve_city(name: str) -> dict | None:
    """Resolve a city/place name to coordinates.

    Returns {"name", "lat", "lon", "country"} or None if nothing matches.
    Raises only on repeated network failure (callers turn that into an
    honest tool error message).
    """
    key = name.strip().lower()
    if not key:
        return None
    if key in _cache and time.time() < _expiry.get(key, 0):
        return _cache[key]

    hit = _geocode(name.strip())
    resolved = None
    if hit:
        resolved = {
            "name": hit.get("name", name),
            "lat": hit["latitude"],
            "lon": hit["longitude"],
            "country": hit.get("country", "Unknown"),
        }
    _cache[key] = resolved
    _expiry[key] = time.time() + TTL_GEO
    return resolved

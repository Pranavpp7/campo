import time
import requests
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ── World Cup 2026 venue coordinates ─────────────────────────────────────────
VENUES = {
    "new york": {"lat": 40.8135, "lon": -74.0745, "name": "MetLife Stadium, New York"},
    "los angeles": {"lat": 34.0141, "lon": -118.2879, "name": "SoFi Stadium, Los Angeles"},
    "dallas": {"lat": 32.7473, "lon": -97.0945, "name": "AT&T Stadium, Dallas"},
    "san francisco": {"lat": 37.4033, "lon": -121.9694, "name": "Levi's Stadium, San Francisco"},
    "miami": {"lat": 25.9580, "lon": -80.2389, "name": "Hard Rock Stadium, Miami"},
    "atlanta": {"lat": 33.7554, "lon": -84.4009, "name": "Mercedes-Benz Stadium, Atlanta"},
    "seattle": {"lat": 47.5952, "lon": -122.3316, "name": "Lumen Field, Seattle"},
    "houston": {"lat": 29.6847, "lon": -95.4107, "name": "NRG Stadium, Houston"},
    "kansas city": {"lat": 39.0489, "lon": -94.4839, "name": "Arrowhead Stadium, Kansas City"},
    "philadelphia": {"lat": 39.9008, "lon": -75.1675, "name": "Lincoln Financial Field, Philadelphia"},
    "boston": {"lat": 42.0909, "lon": -71.2643, "name": "Gillette Stadium, Boston"},
    "guadalajara": {"lat": 20.6597, "lon": -103.3496, "name": "Estadio Akron, Guadalajara"},
    "mexico city": {"lat": 19.3029, "lon": -99.1505, "name": "Estadio Azteca, Mexico City"},
    "monterrey": {"lat": 25.6693, "lon": -100.3098, "name": "Estadio BBVA, Monterrey"},
    "toronto": {"lat": 43.6333, "lon": -79.5890, "name": "BMO Field, Toronto"},
    "vancouver": {"lat": 49.2767, "lon": -123.1767, "name": "BC Place, Vancouver"},
}

# ── TTL Cache ─────────────────────────────────────────────────────────────────
_cache: dict = {}

def _get_cached(key: str):
    if key in _cache:
        if time.time() < _cache[key]["expires_at"]:
            return _cache[key]["data"]
    return None

def _set_cached(key: str, data, ttl_seconds: int):
    _cache[key] = {"data": data, "expires_at": time.time() + ttl_seconds}

TTL_WEATHER = 3 * 3600  # 3 hours

# ── Retry ─────────────────────────────────────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def _get_weather(lat: float, lon: float, date: str) -> dict:
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode",
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
            "start_date": date,
            "end_date": date,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()

# Weather code descriptions
WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail",
}

# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_venue_weather(city: str, date: str) -> str:
    """Get weather forecast for a World Cup 2026 venue on a specific date.

    Use this for Logistics planning (what to pack, travel conditions)
    and LocalPulse analysis (outdoor vs indoor considerations for businesses).

    Args:
        city: Host city name (e.g. "houston", "dallas", "miami", "toronto")
        date: Date in YYYY-MM-DD format (e.g. "2026-06-15")

    Returns:
        Weather forecast including temperature, precipitation, and conditions.
    """
    cache_key = f"weather_{city.lower()}_{date}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    venue = VENUES.get(city.lower())
    if not venue:
        available = ", ".join(VENUES.keys())
        return f"City '{city}' not found. Available venues: {available}"

    try:
        data = _get_weather(venue["lat"], venue["lon"], date)
        daily = data.get("daily", {})

        temp_max = daily.get("temperature_2m_max", [None])[0]
        temp_min = daily.get("temperature_2m_min", [None])[0]
        precip = daily.get("precipitation_probability_max", [None])[0]
        code = daily.get("weathercode", [0])[0]
        condition = WEATHER_CODES.get(code, "Unknown")

        output = (
            f"Weather for {venue['name']} on {date}:\n"
            f"Condition: {condition}\n"
            f"Temperature: {temp_min}°F - {temp_max}°F\n"
            f"Precipitation chance: {precip}%\n"
        )

        _set_cached(cache_key, output, TTL_WEATHER)
        return output

    except Exception as e:
        return f"Error fetching weather for {city} on {date}: {str(e)}"
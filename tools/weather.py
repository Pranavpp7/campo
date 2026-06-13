import time
import requests
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tools.venues import VENUES

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

        temp_max_list = daily.get("temperature_2m_max", [])
        temp_min_list = daily.get("temperature_2m_min", [])
        precip_list = daily.get("precipitation_probability_max", [])
        code_list = daily.get("weathercode", [])

        if not temp_max_list or not temp_min_list:
            output = (
                f"Forecast not yet available for {venue['name']} on {date} — "
                f"Open-Meteo forecasts only cover roughly 16 days ahead. "
                f"Try again closer to the date for an accurate forecast."
            )
            _set_cached(cache_key, output, TTL_WEATHER)
            return output

        temp_max = temp_max_list[0]
        temp_min = temp_min_list[0]
        precip = precip_list[0] if precip_list else None
        code = code_list[0] if code_list else None
        condition = WEATHER_CODES.get(code, "Unknown") if code is not None else "Unknown"

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
import math
from langchain_core.tools import tool
from tools.geo import resolve_city

EARTH_RADIUS_KM = 6371.0

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

@tool
def calculate_venue_distance(city_a: str, city_b: str) -> str:
    """Calculate the distance between two match cities and assess whether
    same-day travel between them is realistic.

    Use this for multi-match itinerary planning — checking whether a fan
    can realistically attend matches in two different cities close together
    in time. Works for any city — both are resolved by name.

    Args:
        city_a: City name (e.g. "Dallas", "Manchester")
        city_b: City name (e.g. "Atlanta", "London")

    Returns:
        Distance in km/miles and a same-day travel feasibility assessment.
    """
    try:
        a = resolve_city(city_a)
        b = resolve_city(city_b)
    except Exception as e:
        return f"Could not resolve cities: {e}"

    missing = [name for name, found in [(city_a, a), (city_b, b)] if not found]
    if missing:
        return (
            f"City name(s) not found: {', '.join(missing)}. "
            "Check the spelling or try the nearest major city."
        )

    if a["name"].lower() == b["name"].lower():
        return f"{a['name']} and {b['name']} are the same city."

    distance_km = _haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
    distance_miles = distance_km * 0.621371
    same_country = a["country"] == b["country"]

    if distance_km < 300:
        feasibility = "Drivable in a few hours — feasible for same-day travel."
    elif distance_km < 800:
        feasibility = "Feasible via a short flight, but tight — same-day travel needs careful timing."
    else:
        feasibility = "Not realistic for same-day travel — plan for an overnight stay or a rest day in between."

    border_note = ""
    if not same_country:
        border_note = (
            f"\nNote: {a['name']} is in {a['country']} and {b['name']} is in "
            f"{b['country']} — factor in border crossing, passport/visa "
            f"requirements, and customs/security wait times."
        )

    return (
        f"{a['name']} ({a['country']}) to {b['name']} ({b['country']}):\n"
        f"Straight-line distance: {distance_km:.0f} km ({distance_miles:.0f} miles)\n"
        f"Same-day feasibility: {feasibility}"
        f"{border_note}"
    )

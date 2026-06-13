"""Shared World Cup 2026 venue data — coordinates and metadata.

Used by tools/weather.py (forecast lookups) and tools/logistics.py
(venue-to-venue distance and travel feasibility).
"""

VENUES = {
    "new york": {"lat": 40.8135, "lon": -74.0745, "name": "MetLife Stadium, New York", "country": "USA"},
    "los angeles": {"lat": 34.0141, "lon": -118.2879, "name": "SoFi Stadium, Los Angeles", "country": "USA"},
    "dallas": {"lat": 32.7473, "lon": -97.0945, "name": "AT&T Stadium, Dallas", "country": "USA"},
    "san francisco": {"lat": 37.4033, "lon": -121.9694, "name": "Levi's Stadium, San Francisco", "country": "USA"},
    "miami": {"lat": 25.9580, "lon": -80.2389, "name": "Hard Rock Stadium, Miami", "country": "USA"},
    "atlanta": {"lat": 33.7554, "lon": -84.4009, "name": "Mercedes-Benz Stadium, Atlanta", "country": "USA"},
    "seattle": {"lat": 47.5952, "lon": -122.3316, "name": "Lumen Field, Seattle", "country": "USA"},
    "houston": {"lat": 29.6847, "lon": -95.4107, "name": "NRG Stadium, Houston", "country": "USA"},
    "kansas city": {"lat": 39.0489, "lon": -94.4839, "name": "Arrowhead Stadium, Kansas City", "country": "USA"},
    "philadelphia": {"lat": 39.9008, "lon": -75.1675, "name": "Lincoln Financial Field, Philadelphia", "country": "USA"},
    "boston": {"lat": 42.0909, "lon": -71.2643, "name": "Gillette Stadium, Boston", "country": "USA"},
    "guadalajara": {"lat": 20.6597, "lon": -103.3496, "name": "Estadio Akron, Guadalajara", "country": "Mexico"},
    "mexico city": {"lat": 19.3029, "lon": -99.1505, "name": "Estadio Azteca, Mexico City", "country": "Mexico"},
    "monterrey": {"lat": 25.6693, "lon": -100.3098, "name": "Estadio BBVA, Monterrey", "country": "Mexico"},
    "toronto": {"lat": 43.6333, "lon": -79.5890, "name": "BMO Field, Toronto", "country": "Canada"},
    "vancouver": {"lat": 49.2767, "lon": -123.1767, "name": "BC Place, Vancouver", "country": "Canada"},
}
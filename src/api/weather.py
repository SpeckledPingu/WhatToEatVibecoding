"""
weather.py — Client for the Open-Meteo weather API.

YOUR APP AS AN API CLIENT
Throughout this project, you've been building a REST API that OTHER programs call.
Now the roles are reversed: YOUR app is the CLIENT calling SOMEONE ELSE'S API.

    Your Streamlit app  →  Your FastAPI server  →  Open-Meteo API
         (client)              (server)               (server)

This is the same HTTP request/response pattern, but from the other side:
  - You build a URL with query parameters
  - You send an HTTP GET request to their server
  - They return JSON data
  - You parse and use that data

OPEN-METEO API
Open-Meteo is a free, open-source weather API that requires NO API key and NO
registration. It uses latitude/longitude coordinates to return weather data.

Example request:
    https://api.open-meteo.com/v1/forecast?latitude=40.71&longitude=-74.01&current=temperature_2m,weather_code&temperature_unit=fahrenheit

This returns JSON like:
    {
        "current": {
            "temperature_2m": 72.5,
            "weather_code": 3
        }
    }

WMO WEATHER CODES
The weather_code field uses the World Meteorological Organization (WMO) standard:
  0     = Clear sky
  1-3   = Partly cloudy
  45-48 = Fog
  51-57 = Drizzle
  61-67 = Rain
  71-77 = Snow
  80-82 = Rain showers
  95-99 = Thunderstorm
See: https://open-meteo.com/en/docs for the full list.

CONFIGURATION OVER CODE
Temperature thresholds, WMO code → condition mappings, and city coordinates are
all loaded from config/normalization_mappings.json. To change what counts as
"cold" weather or add a new city, edit the JSON config — no Python changes needed.

RUN IT (demo mode):
    uv run python -m src.api.weather
"""

import json
from functools import lru_cache
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Config file path — resolved relative to the project root
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "normalization_mappings.json"


@lru_cache(maxsize=1)
def load_config() -> dict:
    """
    Read and cache the normalization/weather configuration file.

    The weather_mapping and common_locations sections are defined alongside
    the food normalization rules in the same JSON config. This keeps ALL
    application configuration in one central location.
    """
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Load city coordinates from config — NOT hardcoded in Python
# ---------------------------------------------------------------------------
# Students add their own city by editing config/normalization_mappings.json
# under the "common_locations" key. The Python code here is generic — it
# reads whatever cities are in the config file.

def get_common_locations() -> dict:
    """
    Return the common city locations from the config file.

    Each city maps to {"latitude": float, "longitude": float}.
    Students can add their own city by editing the config JSON.
    Filters out the _description metadata key that's used for documentation.
    """
    config = load_config()
    locations = config.get("common_locations", {})
    # Filter out metadata keys (like _description) — only keep actual city entries
    return {k: v for k, v in locations.items() if isinstance(v, dict)}


# ---------------------------------------------------------------------------
# WMO weather code descriptions
# ---------------------------------------------------------------------------
# These human-readable labels explain what each WMO code means. Used to give
# users a friendly weather description like "partly cloudy" instead of "3".

WMO_DESCRIPTIONS = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def get_current_weather(
    latitude: float = 40.7128,
    longitude: float = -74.0060,
) -> dict:
    """
    Fetch current weather data from the Open-Meteo API.

    HOW THIS WORKS — STEP BY STEP:
    1. We build a URL with QUERY PARAMETERS — key=value pairs after the "?"
       Example: ?latitude=40.71&longitude=-74.01&current=temperature_2m,weather_code
       Query parameters tell the API WHAT data we want and WHERE we want it for.
    2. We send an HTTP GET request using httpx (similar to 'requests' library)
    3. The API returns JSON, which httpx parses into a Python dict
    4. We extract the fields we care about and return a clean result

    ERROR HANDLING FOR EXTERNAL SERVICES:
    When calling someone else's API, many things can go wrong:
      - Network issues: your internet is down, DNS fails, connection refused
      - Timeouts: the server is slow or overloaded (we set a 10-second timeout)
      - Server errors: the API returns 500 (their bug, not yours)
      - Bad data: the response format is unexpected
    We handle ALL of these gracefully and return a fallback dict so our app
    doesn't crash just because the weather API is having a bad day.

    API RATE LIMITING — BEING A GOOD API CITIZEN:
    Even though Open-Meteo is free, don't hammer their server with requests.
    Best practices:
      - Cache results (don't fetch weather every time a page loads)
      - Set reasonable timeouts (don't hold connections open forever)
      - Include a User-Agent header so they can contact you if needed
    Open-Meteo asks for < 10,000 requests/day for non-commercial use.

    Args:
        latitude: Geographic latitude (default: New York City)
        longitude: Geographic longitude (default: New York City)

    Returns:
        A dict with keys: temperature_f, weather_code, description.
        If the API fails, returns a fallback with None values and
        description="unavailable".
    """
    # The base URL is the API "endpoint" — the address of the service
    url = "https://api.open-meteo.com/v1/forecast"

    # Query parameters specify WHAT we want from the API:
    #   - latitude/longitude: WHERE to get weather for
    #   - current: WHICH current weather fields to include
    #   - temperature_unit: return Fahrenheit instead of Celsius
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code",
        "temperature_unit": "fahrenheit",
    }

    try:
        # httpx.get() sends an HTTP GET request — the most common type.
        # GET means "give me data" (as opposed to POST which means "here's data").
        # timeout=10 means "give up if the server doesn't respond within 10 seconds"
        response = httpx.get(url, params=params, timeout=10.0)

        # raise_for_status() throws an error if the HTTP status code indicates
        # failure (4xx = client error, 5xx = server error). This is the same
        # pattern used in our own API client (api_client.py).
        response.raise_for_status()

        # Parse the JSON response into a Python dict
        data = response.json()

        # Extract the fields we need from the nested response structure
        current = data.get("current", {})
        temp_f = current.get("temperature_2m")
        weather_code = current.get("weather_code")

        # Look up a human-readable description for the WMO weather code
        description = WMO_DESCRIPTIONS.get(weather_code, f"code {weather_code}")

        return {
            "temperature_f": temp_f,
            "weather_code": weather_code,
            "description": description,
        }

    except httpx.ConnectError:
        # Can't reach the server — network down, DNS failure, etc.
        return {"temperature_f": None, "weather_code": None, "description": "unavailable"}
    except httpx.TimeoutException:
        # Server took too long — they might be overloaded
        return {"temperature_f": None, "weather_code": None, "description": "unavailable"}
    except httpx.HTTPStatusError:
        # Server returned an error status (4xx or 5xx)
        return {"temperature_f": None, "weather_code": None, "description": "unavailable"}
    except Exception:
        # Catch-all for anything unexpected (bad JSON, network blip, etc.)
        return {"temperature_f": None, "weather_code": None, "description": "unavailable"}


def weather_to_recipe_tags(weather: dict) -> tuple[str | None, str | None]:
    """
    Map raw weather data to recipe tags (weather_temp, weather_condition).

    HOW THE CONFIG DRIVES THIS MAPPING:
    Instead of hardcoding "below 60°F = cold" in Python, we read the threshold
    and labels from config/normalization_mappings.json:

        "weather_mapping": {
            "temperature_threshold_f": 60,
            "temperature_labels": {
                "below_threshold": "cold",
                "at_or_above_threshold": "warm"
            },
            "wmo_code_to_condition": {
                "sunny": [0, 1, 2, 3],
                "cloudy": [4, 5, ..., 44],
                "rainy": [45, 46, ..., 99]
            }
        }

    CUSTOMIZING THE MAPPING:
    - Want 65°F as the cold/warm cutoff? Change temperature_threshold_f to 65
    - Want a "snowy" category? Add "snowy": [71, 73, 75, 77, 85, 86] to
      wmo_code_to_condition and remove those codes from "rainy"
    - All changes happen in the JSON config — no Python edits needed

    Args:
        weather: Dict from get_current_weather() with temperature_f and weather_code

    Returns:
        A tuple of (weather_temp, weather_condition), e.g. ("cold", "rainy").
        Returns (None, None) if weather data is unavailable.
    """
    temp_f = weather.get("temperature_f")
    weather_code = weather.get("weather_code")

    # If the weather API failed, we can't map anything — return None/None
    # so the recommendation engine knows to skip weather-based filtering
    if temp_f is None or weather_code is None:
        return (None, None)

    # Load mapping rules from the config file
    config = load_config()
    weather_mapping = config.get("weather_mapping", {})

    # --- Map temperature to a recipe tag ---
    # The config defines a threshold (default 60°F) and labels for above/below
    threshold = weather_mapping.get("temperature_threshold_f", 60)
    labels = weather_mapping.get("temperature_labels", {})

    if temp_f < threshold:
        weather_temp = labels.get("below_threshold", "cold")
    else:
        weather_temp = labels.get("at_or_above_threshold", "warm")

    # --- Map WMO weather code to a recipe condition ---
    # The config maps condition names to lists of WMO codes
    code_mapping = weather_mapping.get("wmo_code_to_condition", {})
    weather_condition = None

    for condition, codes in code_mapping.items():
        if weather_code in codes:
            weather_condition = condition
            break

    # If the code isn't in any mapping range, default to "cloudy" (safest guess)
    if weather_condition is None:
        weather_condition = "cloudy"

    return (weather_temp, weather_condition)


# ---------------------------------------------------------------------------
# Demo / standalone run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Weather API Client — Demo")
    print("=" * 60)

    # Show available locations from config
    locations = get_common_locations()
    print(f"\nCommon locations loaded from config: {len(locations)} cities")
    for city, coords in locations.items():
        print(f"  {city}: ({coords['latitude']}, {coords['longitude']})")

    # Fetch current weather for the default location (NYC)
    print("\n--- Fetching current weather for New York City ---")
    weather = get_current_weather()
    print(f"  Temperature: {weather['temperature_f']}°F")
    print(f"  Weather code: {weather['weather_code']}")
    print(f"  Description: {weather['description']}")

    # Map to recipe tags
    temp_tag, condition_tag = weather_to_recipe_tags(weather)
    print(f"\n  Recipe tags → weather_temp={temp_tag}, weather_condition={condition_tag}")

    # Try a few more cities
    for city in ["London", "Tokyo", "Miami"]:
        if city in locations:
            coords = locations[city]
            w = get_current_weather(coords["latitude"], coords["longitude"])
            t, c = weather_to_recipe_tags(w)
            print(f"\n  {city}: {w['temperature_f']}°F, {w['description']} → {t}/{c}")

    print("\n" + "=" * 60)
    print("Test curl commands for weather endpoints:")
    print("  curl http://localhost:8000/weather/current")
    print('  curl "http://localhost:8000/weather/current/New%20York"')
    print("  curl http://localhost:8000/weather/recommendations")
    print('  curl "http://localhost:8000/weather/recommendations/Seattle"')
    print("=" * 60)

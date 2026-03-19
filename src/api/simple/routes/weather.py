"""
weather.py — Weather and recommendation endpoints for the WhatToEat API.

WHAT THESE ENDPOINTS DO
These endpoints let the Streamlit app (or any HTTP client) access weather data
and weather-based recipe recommendations. They combine TWO data sources:
  1. External weather data from the Open-Meteo API (fetched in real time)
  2. Internal recipe matching data from our database

ENDPOINT DESIGN DECISIONS:
  - GET /weather/current — Raw weather data + recipe tag mapping
  - GET /weather/current/{city} — Convenience shortcut using city name
  - GET /weather/recommendations — Full recommendation engine results
  - GET /weather/recommendations/{city} — Convenience shortcut

All endpoints are GET (read-only) because they don't modify any data — they
just FETCH weather and READ from the database.

The {city} shortcut endpoints are a UX convenience — instead of looking up
coordinates, users can just say "New York". This is a common API pattern
for making endpoints more user-friendly.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from src.api.weather import (
    get_current_weather,
    weather_to_recipe_tags,
    get_common_locations,
)
from src.analytics.weather_recommendations import get_weather_recommendations

router = APIRouter()


# ==========================================================================
# GET /weather/current — Fetch current weather and map to recipe tags
# ==========================================================================
# This endpoint is the simplest: call the weather API, map the result to
# recipe tags, and return both. The client gets raw weather data AND the
# mapped tags in one call, so it can display "45°F, Rainy → cold + rainy".

@router.get("/current")
def current_weather(
    latitude: float = Query(
        default=40.7128,
        description="Geographic latitude (default: New York City)",
    ),
    longitude: float = Query(
        default=-74.0060,
        description="Geographic longitude (default: New York City)",
    ),
):
    """
    Get current weather data and the corresponding recipe tags.

    Returns the raw temperature and weather code from Open-Meteo,
    plus the mapped recipe tags (warm/cold + sunny/cloudy/rainy) that
    can be used to filter recipes.

    Query parameters:
      - latitude: Geographic latitude (default: NYC 40.7128)
      - longitude: Geographic longitude (default: NYC -74.0060)
    """
    weather = get_current_weather(latitude, longitude)
    weather_temp, weather_condition = weather_to_recipe_tags(weather)

    return {
        "weather": {
            "temperature_f": weather["temperature_f"],
            "weather_code": weather["weather_code"],
            "description": weather["description"],
        },
        "recipe_tags": {
            "weather_temp": weather_temp,
            "weather_condition": weather_condition,
        },
        "location": {
            "latitude": latitude,
            "longitude": longitude,
        },
    }


# ==========================================================================
# GET /weather/current/{city} — Weather by city name (convenience shortcut)
# ==========================================================================
# Instead of requiring latitude/longitude, let users pass a city name.
# The coordinates are looked up from the config file.
# Returns 404 if the city isn't in our list, with helpful suggestions.

@router.get("/current/{city}")
def current_weather_by_city(city: str):
    """
    Get current weather for a named city.

    City names are loaded from config/normalization_mappings.json under
    "common_locations". If the city isn't recognized, returns a 404 with
    the list of available cities.

    Path parameter:
      - city: City name (e.g., "New York", "London", "Tokyo")
    """
    locations = get_common_locations()

    # Case-insensitive lookup — try exact match first, then case-insensitive
    coords = locations.get(city)
    if coords is None:
        # Try case-insensitive match
        for name, c in locations.items():
            if name.lower() == city.lower():
                coords = c
                city = name  # Use the canonical name for the response
                break

    if coords is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"City '{city}' not found in configured locations.",
                "available_cities": list(locations.keys()),
                "tip": "Add your city to config/normalization_mappings.json under 'common_locations'.",
            },
        )

    weather = get_current_weather(coords["latitude"], coords["longitude"])
    weather_temp, weather_condition = weather_to_recipe_tags(weather)

    return {
        "city": city,
        "weather": {
            "temperature_f": weather["temperature_f"],
            "weather_code": weather["weather_code"],
            "description": weather["description"],
        },
        "recipe_tags": {
            "weather_temp": weather_temp,
            "weather_condition": weather_condition,
        },
        "location": {
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
        },
    }


# ==========================================================================
# GET /weather/recommendations — Weather-appropriate recipe recommendations
# ==========================================================================
# This is the main recommendation endpoint. It combines weather data with
# recipe matching data to suggest what to cook today.

@router.get("/recommendations")
def weather_recommendations(
    latitude: float = Query(
        default=40.7128,
        description="Geographic latitude (default: New York City)",
    ),
    longitude: float = Query(
        default=-74.0060,
        description="Geographic longitude (default: New York City)",
    ),
    include_almost: bool = Query(
        default=True,
        description="Include recipes that are 1-2 ingredients away from makeable",
    ),
    max_missing: int = Query(
        default=2,
        ge=0,
        le=10,
        description="Maximum missing ingredients for 'almost ready' category",
    ),
):
    """
    Get weather-appropriate recipe recommendations.

    Combines current weather, recipe weather tags, ingredient availability,
    and expiration urgency to suggest the best recipes for today.

    Recommendation tiers:
      - perfect_for_today: Fully makeable + matches weather
      - almost_ready: 1-2 ingredients away + matches weather
      - explore: Matches weather but needs more ingredients
      - use_it_up: Makeable recipes using soon-to-expire ingredients (any weather)
    """
    return get_weather_recommendations(
        latitude=latitude,
        longitude=longitude,
        include_almost=include_almost,
        max_missing=max_missing,
    )


# ==========================================================================
# GET /weather/recommendations/{city} — Recommendations by city name
# ==========================================================================

@router.get("/recommendations/{city}")
def weather_recommendations_by_city(
    city: str,
    include_almost: bool = Query(default=True),
    max_missing: int = Query(default=2, ge=0, le=10),
):
    """
    Get weather-appropriate recipe recommendations for a named city.

    Same as GET /weather/recommendations but uses a city name instead
    of latitude/longitude coordinates.
    """
    locations = get_common_locations()

    coords = locations.get(city)
    if coords is None:
        for name, c in locations.items():
            if name.lower() == city.lower():
                coords = c
                break

    if coords is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"City '{city}' not found in configured locations.",
                "available_cities": list(locations.keys()),
            },
        )

    return get_weather_recommendations(
        latitude=coords["latitude"],
        longitude=coords["longitude"],
        include_almost=include_almost,
        max_missing=max_missing,
    )

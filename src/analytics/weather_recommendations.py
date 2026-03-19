"""
weather_recommendations.py — Weather-based recipe recommendations.

RECOMMENDATION SYSTEMS 101
A recommendation system suggests items (recipes, in our case) based on signals:
  1. FILTER: Remove items that don't match criteria (weather tags, availability)
  2. SCORE: Assign a relevance score based on multiple factors
  3. RANK: Sort by score and present the best options first

Our signals:
  - Weather match: Does the recipe's weather tags match today's weather?
  - Availability: Can you actually make this recipe with what you have?
  - Expiration urgency: Does this recipe use ingredients that are about to expire?

COMBINING MULTIPLE SIGNALS
Real recommendation systems combine many weak signals into strong suggestions.
A recipe that matches the weather AND uses expiring ingredients AND is fully
makeable is a MUCH better recommendation than one that only matches weather.

This same pattern applies to many recommendation problems:
  - Movie recommendations: genre match + rating + friends' watches + time of day
  - Shopping: purchase history + browsing behavior + trending items + season
  - Music: genre + mood + time of day + listening history

RUN IT:
    uv run python -m src.analytics.weather_recommendations
"""

from datetime import date, timedelta

from sqlmodel import Session, select

from src.api.weather import get_current_weather, weather_to_recipe_tags, get_common_locations
from src.database import create_db_and_tables, get_engine
from src.models.recipe_matching import RecipeMatchSummary


def get_weather_recommendations(
    latitude: float = 40.7128,
    longitude: float = -74.0060,
    include_almost: bool = True,
    max_missing: int = 2,
) -> dict:
    """
    Get recipe recommendations based on current weather and inventory.

    THE RECOMMENDATION PIPELINE:
    Step 1: Get current weather from the Open-Meteo API
    Step 2: Map weather to recipe tags (warm/cold + sunny/cloudy/rainy)
    Step 3: Query RecipeMatchSummary for recipes matching those tags
    Step 4: Rank results by a combination of weather match, availability, and urgency

    RANKING TIERS (best to least):
    1. PERFECT: Fully makeable + weather match + uses expiring ingredients
    2. GREAT:   Fully makeable + weather match
    3. ALMOST:  1-2 missing ingredients + weather match
    4. EXPLORE: Weather match but many ingredients missing

    Args:
        latitude: Geographic latitude for weather lookup
        longitude: Geographic longitude for weather lookup
        include_almost: Whether to include "almost ready" recipes (1-2 missing)
        max_missing: Maximum missing ingredients for "almost ready" category

    Returns:
        A structured dict with weather info, ranked recommendations, and
        "use it up" suggestions for expiring ingredients.
    """
    # --- Step 1: Get current weather ---
    weather = get_current_weather(latitude, longitude)

    # --- Step 2: Map to recipe tags ---
    weather_temp, weather_condition = weather_to_recipe_tags(weather)

    # --- Step 3: Query the recipe match summary table ---
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        all_matches = session.exec(select(RecipeMatchSummary)).all()

    # --- Step 4: Filter and rank ---
    # Start with the weather result structure
    result = {
        "weather": {
            "temp_f": weather.get("temperature_f"),
            "description": weather.get("description"),
            "weather_code": weather.get("weather_code"),
            "recipe_temp": weather_temp,
            "recipe_condition": weather_condition,
        },
        "recommendations": {
            "perfect_for_today": [],
            "almost_ready": [],
            "explore": [],
        },
        "use_it_up": [],
    }

    # If weather data is unavailable, we can still return makeable recipes
    # without weather filtering — graceful degradation
    for match in all_matches:
        match_dict = {
            "recipe_id": match.recipe_id,
            "recipe_name": match.recipe_name,
            "total_ingredients": match.total_ingredients,
            "available_ingredients": match.available_ingredients,
            "missing_ingredients": match.missing_ingredients,
            "missing_ingredient_list": match.missing_ingredient_list or [],
            "is_fully_makeable": match.is_fully_makeable,
            "weather_temp": match.weather_temp,
            "weather_condition": match.weather_condition,
            "uses_expiring_ingredients": match.uses_expiring_ingredients,
            "expiring_ingredient_list": match.expiring_ingredient_list or [],
        }

        # Check weather match — both temp and condition should align
        # None tags on either side mean "matches anything" (no preference)
        temp_matches = (
            weather_temp is None
            or match.weather_temp is None
            or match.weather_temp == weather_temp
        )
        condition_matches = (
            weather_condition is None
            or match.weather_condition is None
            or match.weather_condition == weather_condition
        )
        weather_matches = temp_matches and condition_matches

        # "Use It Up" — any makeable recipe with expiring ingredients,
        # regardless of weather. These are always worth surfacing because
        # food waste prevention trumps weather preferences.
        if match.is_fully_makeable and match.uses_expiring_ingredients:
            result["use_it_up"].append(match_dict)

        # Now categorize by weather match + availability
        if weather_matches:
            if match.is_fully_makeable:
                result["recommendations"]["perfect_for_today"].append(match_dict)
            elif include_almost and match.missing_ingredients <= max_missing:
                result["recommendations"]["almost_ready"].append(match_dict)
            else:
                result["recommendations"]["explore"].append(match_dict)

    # Sort each tier: prioritize recipes using expiring ingredients first,
    # then by fewest missing ingredients (most accessible first)
    for tier in result["recommendations"].values():
        tier.sort(key=lambda r: (
            not r["uses_expiring_ingredients"],  # True first (uses expiring = top)
            r["missing_ingredients"],            # Fewest missing = top
        ))

    return result


# ---------------------------------------------------------------------------
# Standalone run — print a formatted recommendation report
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Weather-Based Recipe Recommendations")
    print("=" * 60)

    recs = get_weather_recommendations()

    # Weather info
    w = recs["weather"]
    print(f"\nCurrent Weather:")
    print(f"  Temperature: {w['temp_f']}°F")
    print(f"  Condition: {w['description']}")
    print(f"  Recipe tags: {w['recipe_temp']} / {w['recipe_condition']}")

    # Perfect for today
    perfect = recs["recommendations"]["perfect_for_today"]
    print(f"\n--- Perfect for Today ({len(perfect)} recipes) ---")
    for r in perfect:
        expiring = " [USES EXPIRING!]" if r["uses_expiring_ingredients"] else ""
        print(f"  {r['recipe_name']} ({r['available_ingredients']}/{r['total_ingredients']} ingredients){expiring}")

    # Almost ready
    almost = recs["recommendations"]["almost_ready"]
    print(f"\n--- Almost Ready ({len(almost)} recipes) ---")
    for r in almost:
        missing = ", ".join(r["missing_ingredient_list"])
        print(f"  {r['recipe_name']} — missing: {missing}")

    # Explore
    explore = recs["recommendations"]["explore"]
    print(f"\n--- Explore ({len(explore)} recipes) ---")
    for r in explore[:5]:  # Limit to top 5 for readability
        print(f"  {r['recipe_name']} — {r['missing_ingredients']} ingredients missing")

    # Use it up
    use_up = recs["use_it_up"]
    print(f"\n--- Use It Up ({len(use_up)} recipes with expiring ingredients) ---")
    for r in use_up:
        expiring = ", ".join(r["expiring_ingredient_list"])
        print(f"  {r['recipe_name']} — uses expiring: {expiring}")

    print("\n" + "=" * 60)

"""
weather_recommendations.py — Weather-based recipe recommendation page for Streamlit.

This page demonstrates how a frontend application can combine data from
multiple API endpoints to create a rich, contextual user experience:
  1. Fetch current weather (from the weather API endpoint)
  2. Get recommendations (from the recommendations API endpoint)
  3. Display results in an intuitive, visual layout

STREAMLIT PATTERNS USED HERE:
  - st.columns() for side-by-side layout
  - st.expander() for collapsible detail sections
  - st.selectbox() for dropdown selection
  - st.number_input() for coordinate entry
  - st.button() to trigger actions
  - st.metric() for prominent weather display
  - Conditional rendering: different UI based on data availability
"""

import streamlit as st

from src.app.api_client import WhatToEatAPI


def render(api: WhatToEatAPI):
    """Render the Weather Recommendations page."""
    st.header("Weather Recommendations")
    st.caption(
        "Get recipe suggestions based on today's weather. "
        "Hearty soups for cold rainy days, fresh salads for warm sunny ones."
    )

    # ------------------------------------------------------------------
    # Location selector
    # ------------------------------------------------------------------
    st.subheader("Select Your Location")

    # Fetch available cities from the weather API
    # We use a known city to discover the list — if the API returns an error,
    # we fall back to a hardcoded list of common cities
    location_method = st.radio(
        "Choose location method:",
        options=["Select a city", "Enter coordinates"],
        horizontal=True,
        label_visibility="collapsed",
    )

    latitude = None
    longitude = None
    city_name = None

    if location_method == "Select a city":
        # List of common cities — matches config/normalization_mappings.json
        cities = [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
            "Seattle", "Denver", "Atlanta", "Miami", "Boston",
            "London", "Tokyo", "Sydney", "Paris",
        ]
        city_name = st.selectbox("City", options=cities, index=0)
    else:
        col1, col2 = st.columns(2)
        with col1:
            latitude = st.number_input(
                "Latitude", value=40.7128, format="%.4f",
                help="e.g., 40.7128 for New York",
            )
        with col2:
            longitude = st.number_input(
                "Longitude", value=-74.0060, format="%.4f",
                help="e.g., -74.0060 for New York",
            )

    # ------------------------------------------------------------------
    # Fetch recommendations
    # ------------------------------------------------------------------
    if st.button("Get Recommendations", type="primary", use_container_width=True):
        with st.spinner("Fetching weather and recommendations..."):
            if city_name:
                result = api.get_weather_recommendations_by_city(city_name)
            else:
                result = api.get_weather_recommendations(
                    latitude=latitude, longitude=longitude,
                )

        if isinstance(result, dict) and "error" in result:
            st.error(result["error"])
            st.info(
                "Couldn't fetch weather data. Make sure the API server is "
                "running and you have an internet connection."
            )
            # Show fallback: all makeable recipes regardless of weather
            _render_fallback(api)
            return

        # Store in session state so it persists across re-runs
        st.session_state.weather_result = result

    # ------------------------------------------------------------------
    # Display results (from session state)
    # ------------------------------------------------------------------
    if "weather_result" not in st.session_state:
        st.info("Click 'Get Recommendations' to see weather-appropriate recipes.")
        return

    result = st.session_state.weather_result
    weather = result.get("weather", {})
    recommendations = result.get("recommendations", {})
    use_it_up = result.get("use_it_up", [])

    # --- Current weather display ---
    st.markdown("---")
    _render_weather_display(weather)

    # --- Recommendation sections ---
    st.markdown("---")

    # Perfect for today
    perfect = recommendations.get("perfect_for_today", [])
    _render_recipe_section(
        title=f"Perfect for Today ({len(perfect)})",
        recipes=perfect,
        description="Fully makeable recipes that match today's weather.",
        empty_message="No fully makeable recipes match today's weather.",
        color="green",
    )

    # Almost ready
    almost = recommendations.get("almost_ready", [])
    _render_recipe_section(
        title=f"Almost Ready ({len(almost)})",
        recipes=almost,
        description="Just 1-2 ingredients away from a weather-perfect meal.",
        empty_message="No almost-ready recipes match today's weather.",
        color="orange",
        show_missing=True,
    )

    # Explore
    explore = recommendations.get("explore", [])
    if explore:
        with st.expander(f"Explore ({len(explore)} more weather-matched recipes)"):
            st.caption("These match the weather but need more ingredients.")
            for r in explore[:10]:
                st.write(
                    f"**{r['recipe_name']}** — "
                    f"{r['missing_ingredients']} ingredients missing"
                )

    # --- Sidebar: Use It Up ---
    with st.sidebar:
        st.markdown("---")
        st.subheader("Use It Up!")
        st.caption("Recipes using soon-to-expire ingredients (any weather)")
        if use_it_up:
            for r in use_it_up:
                expiring = ", ".join(r.get("expiring_ingredient_list", []))
                st.write(f"**{r['recipe_name']}**")
                st.caption(f"Expiring: {expiring}")
        else:
            st.write("No expiring ingredients to use up.")


# ---------------------------------------------------------------------------
# Helper functions for rendering
# ---------------------------------------------------------------------------

def _render_weather_display(weather: dict):
    """Display current weather with visual indicators."""
    temp_f = weather.get("temp_f")
    description = weather.get("description", "unknown")
    recipe_temp = weather.get("recipe_temp", "unknown")
    recipe_condition = weather.get("recipe_condition", "unknown")

    # Choose emoji based on weather
    if temp_f is None:
        temp_emoji = "?"
    elif temp_f < 32:
        temp_emoji = "❄️"
    elif temp_f < 60:
        temp_emoji = "🌤️"
    else:
        temp_emoji = "☀️"

    condition_emoji = {
        "sunny": "☀️",
        "cloudy": "☁️",
        "rainy": "🌧️",
    }.get(recipe_condition, "🌡️")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Temperature",
            f"{temp_f}°F" if temp_f is not None else "N/A",
        )
    with col2:
        st.metric("Condition", f"{condition_emoji} {description}")
    with col3:
        st.metric("Mood", f"{temp_emoji} {recipe_temp} + {condition_emoji} {recipe_condition}")

    # Explanation of the mapping
    if recipe_temp and recipe_condition:
        st.caption(
            f"Today feels like: **{recipe_temp.title()} + {recipe_condition.title()}** "
            f"— suggesting {'hearty comfort food' if recipe_temp == 'cold' else 'light, refreshing dishes'}"
        )


def _render_recipe_section(
    title: str,
    recipes: list,
    description: str,
    empty_message: str,
    color: str,
    show_missing: bool = False,
):
    """Render a section of recipe recommendations."""
    st.subheader(title)
    st.caption(description)

    if not recipes:
        st.info(empty_message)
        return

    for r in recipes:
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                label = r["recipe_name"]
                if r.get("uses_expiring_ingredients"):
                    label += " ⚠️ uses expiring!"
                st.write(f"**{label}**")

                if show_missing and r.get("missing_ingredient_list"):
                    missing = ", ".join(r["missing_ingredient_list"])
                    st.caption(f"Missing: {missing}")

            with col2:
                avail = r.get("available_ingredients", 0)
                total = r.get("total_ingredients", 0)
                st.write(f"{avail}/{total} ingredients")


def _render_fallback(api: WhatToEatAPI):
    """
    Fallback when weather is unavailable: show all makeable recipes.

    This demonstrates GRACEFUL DEGRADATION — when an external service fails,
    we still show useful content instead of an empty page.
    """
    st.subheader("All Makeable Recipes")
    st.caption(
        "Couldn't fetch weather data. Here are all your makeable recipes instead:"
    )

    match_data = api.get_match_summary()
    if isinstance(match_data, dict) and "error" in match_data:
        st.error(match_data["error"])
        return

    if isinstance(match_data, list):
        makeable = [m for m in match_data if m.get("is_fully_makeable")]
        if makeable:
            for m in makeable:
                st.write(f"**{m['recipe_name']}** — {m['total_ingredients']} ingredients, all available")
        else:
            st.info("No fully makeable recipes found. Try running ingestion first.")

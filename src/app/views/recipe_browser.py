"""
recipe_browser.py — Browse and explore recipes with filters.

STREAMLIT LAYOUT CONCEPTS
  - st.columns() creates side-by-side columns for horizontal layouts
  - st.expander() creates a collapsible section — great for details-on-demand
  - st.container() groups elements together for visual organization
  - st.tabs() creates tabbed sections within a page

These layout tools let you build structured UIs without any HTML or CSS.
"""

import streamlit as st

from src.app.api_client import WhatToEatAPI


def render(api: WhatToEatAPI):
    """Render the Recipe Browser page."""
    st.header("📖 Recipe Browser")
    st.caption("Browse all recipes, search by name, and filter by weather tags.")

    # ------------------------------------------------------------------
    # Filters — displayed in a row using columns
    # ------------------------------------------------------------------
    # st.columns() divides the page width into equal (or custom-sized) columns.
    # Each column acts as an independent container for widgets.
    col1, col2, col3 = st.columns(3)

    with col1:
        search_text = st.text_input(
            "Search recipes",
            placeholder="Type a recipe name...",
            help="Searches recipe names (case-insensitive)",
        )

    with col2:
        weather_temp = st.selectbox(
            "Temperature",
            options=["All", "warm", "cold"],
            help="Filter by weather temperature tag",
        )

    with col3:
        weather_condition = st.selectbox(
            "Condition",
            options=["All", "sunny", "rainy", "cloudy"],
            help="Filter by weather condition tag",
        )

    # ------------------------------------------------------------------
    # Fetch recipes from the API with applied filters
    # ------------------------------------------------------------------
    result = api.list_recipes(
        search=search_text if search_text else None,
        weather_temp=weather_temp if weather_temp != "All" else None,
        weather_condition=weather_condition if weather_condition != "All" else None,
    )

    if isinstance(result, dict) and "error" in result:
        st.error(result["error"])
        return

    recipes = result.get("recipes", [])
    count = result.get("count", 0)

    # ------------------------------------------------------------------
    # Fetch matching data so we can show availability indicators
    # ------------------------------------------------------------------
    # We fetch the match summary once and build a lookup dict by recipe_id.
    # This is more efficient than calling the API for each recipe individually.
    match_data = api.get_match_summary()
    match_lookup = {}
    if isinstance(match_data, list):
        for m in match_data:
            match_lookup[m.get("recipe_id")] = m

    st.markdown(f"**{count} recipe{'s' if count != 1 else ''} found**")

    if not recipes:
        st.info("No recipes found. Try adjusting your filters or run ingestion from the Dashboard.")
        return

    # ------------------------------------------------------------------
    # Display recipes as expandable cards
    # ------------------------------------------------------------------
    for recipe in recipes:
        recipe_id = recipe.get("id")
        name = recipe.get("name", "Unnamed Recipe")
        description = recipe.get("description", "")
        weather_t = recipe.get("weather_temp")
        weather_c = recipe.get("weather_condition")
        prep = recipe.get("prep_time_minutes")
        cook = recipe.get("cook_time_minutes")
        servings = recipe.get("servings")

        # Build the availability indicator from match data
        match = match_lookup.get(recipe_id)
        if match:
            if match.get("is_fully_makeable"):
                status_badge = "🟢 Can Make"
            elif match.get("missing_ingredients", 99) <= 2:
                status_badge = "🟡 Almost"
            else:
                status_badge = "🔴 Can't Make"
        else:
            status_badge = "⚪ No match data"

        # Build a concise info line for the expander header
        info_parts = []
        if prep is not None:
            info_parts.append(f"Prep: {prep}m")
        if cook is not None:
            info_parts.append(f"Cook: {cook}m")
        if servings is not None:
            info_parts.append(f"Serves: {servings}")
        info_line = " | ".join(info_parts)

        # Each recipe is an expander — click to see full details
        with st.expander(f"{status_badge}  **{name}** — {info_line}"):
            # Description and weather badges
            if description:
                st.markdown(f"*{description}*")

            # Weather tags as colored badge text
            badges = []
            if weather_t:
                emoji = "🌡️" if weather_t == "warm" else "❄️"
                badges.append(f"{emoji} {weather_t.title()}")
            if weather_c:
                emoji_map = {"sunny": "☀️", "rainy": "🌧️", "cloudy": "☁️"}
                badges.append(f"{emoji_map.get(weather_c, '')} {weather_c.title()}")
            if badges:
                st.markdown(" &nbsp; ".join(badges))

            # Use tabs to organize detail sections
            if recipe.get("full_text_markdown"):
                tab_ingredients, tab_instructions, tab_full = st.tabs(
                    ["Ingredients", "Instructions", "Full Recipe"]
                )
            else:
                tab_ingredients, tab_instructions = st.tabs(
                    ["Ingredients", "Instructions"]
                )
                tab_full = None

            # --- Ingredients tab ---
            with tab_ingredients:
                ingredients = recipe.get("ingredients", [])
                if match and isinstance(match_data, list):
                    # Fetch ingredient-level detail for this recipe
                    ingredient_matches = api.get_recipe_match(recipe_id)
                    if isinstance(ingredient_matches, list):
                        # Build a lookup by ingredient name
                        ing_status = {
                            im.get("ingredient_name"): im
                            for im in ingredient_matches
                        }
                        for ing in ingredients:
                            ing_name = ing.get("name", "")
                            qty = ing.get("quantity", "")
                            unit = ing.get("unit", "")
                            status = ing_status.get(ing_name, {})
                            if status.get("is_available"):
                                st.markdown(f"- ✅ {qty} {unit} **{ing_name}**")
                            elif status.get("category_substitute_available"):
                                sub = status.get("substitute_item_name", "?")
                                st.markdown(
                                    f"- 🔄 {qty} {unit} **{ing_name}** "
                                    f"(substitute: {sub})"
                                )
                            else:
                                st.markdown(f"- ❌ {qty} {unit} **{ing_name}**")
                    else:
                        _render_plain_ingredients(ingredients)
                else:
                    _render_plain_ingredients(ingredients)

            # --- Instructions tab ---
            with tab_instructions:
                instructions = recipe.get("instructions", [])
                for i, step in enumerate(instructions, 1):
                    st.markdown(f"**Step {i}.** {step}")

            # --- Full Recipe tab (if markdown exists) ---
            if tab_full is not None:
                with tab_full:
                    st.markdown(recipe.get("full_text_markdown", ""))

            # Source info
            source = recipe.get("source")
            source_file = recipe.get("source_file", "")
            if source or source_file:
                st.caption(f"Source: {source or source_file}")


def _render_plain_ingredients(ingredients: list):
    """Render an ingredient list without availability data."""
    for ing in ingredients:
        name = ing.get("name", "")
        qty = ing.get("quantity", "")
        unit = ing.get("unit", "")
        st.markdown(f"- {qty} {unit} **{name}**")

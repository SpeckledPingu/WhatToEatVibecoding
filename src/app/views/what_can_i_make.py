"""
what_can_i_make.py — Find recipes based on what's in your inventory.

This page has three sections:
  1. Ready to Make — all ingredients available
  2. Almost Ready — missing only a few ingredients
  3. With Substitutions — missing ingredients have same-category swaps

Plus a shopping list generator that consolidates missing ingredients from
selected recipes.
"""

import streamlit as st

from src.app.api_client import WhatToEatAPI


def render(api: WhatToEatAPI):
    """Render the What Can I Make? page."""
    st.header("🍳 What Can I Make?")
    st.caption("Find recipes you can cook based on what's currently in your inventory.")

    # Three sections as tabs
    tab_ready, tab_almost, tab_subs = st.tabs([
        "Ready to Make",
        "Almost Ready",
        "With Substitutions",
    ])

    # ==================================================================
    # Tab 1: Ready to Make
    # ==================================================================
    with tab_ready:
        st.subheader("Recipes you can make right now")
        st.caption("All ingredients are currently in your active inventory.")

        makeable = api.get_makeable()

        if isinstance(makeable, dict) and "error" in makeable:
            st.error(makeable["error"])
        elif isinstance(makeable, list) and makeable:
            for recipe in makeable:
                _render_recipe_card(recipe, show_missing=False)
        else:
            st.info(
                "No recipes are fully makeable right now. "
                "Check the 'Almost Ready' tab, or add more items to your inventory."
            )

    # ==================================================================
    # Tab 2: Almost Ready
    # ==================================================================
    with tab_almost:
        st.subheader("Recipes you're close to making")

        max_missing = st.slider(
            "Show recipes missing up to N ingredients",
            min_value=1,
            max_value=5,
            value=2,
            key="almost_slider",
        )

        almost = api.get_almost_makeable(max_missing=max_missing)

        if isinstance(almost, dict) and "error" in almost:
            st.error(almost["error"])
        elif isinstance(almost, list) and almost:
            # Initialize shopping list selections in session state
            if "shopping_selections" not in st.session_state:
                st.session_state.shopping_selections = set()

            for recipe in almost:
                recipe_id = recipe.get("recipe_id")
                _render_recipe_card(recipe, show_missing=True)

                # Checkbox to add to shopping list
                key = f"shop_{recipe_id}"
                if st.checkbox(
                    f"Add to shopping list",
                    key=key,
                    value=recipe_id in st.session_state.shopping_selections,
                ):
                    st.session_state.shopping_selections.add(recipe_id)
                else:
                    st.session_state.shopping_selections.discard(recipe_id)

                st.markdown("---")

            # Shopping List Generator
            _render_shopping_list(api)
        else:
            st.info(f"No recipes found missing {max_missing} or fewer ingredients.")

    # ==================================================================
    # Tab 3: With Substitutions
    # ==================================================================
    with tab_subs:
        st.subheader("Recipes with possible substitutions")
        st.caption(
            "These recipes have missing ingredients, but you have a same-category "
            "substitute in stock. Category substitutions are approximate — mozzarella "
            "might work for cheddar, but parmesan might not."
        )

        subs = api.get_with_substitutions()

        if isinstance(subs, dict) and "error" in subs:
            st.error(subs["error"])
        elif isinstance(subs, list) and subs:
            for recipe in subs:
                name = recipe.get("recipe_name", "Unknown")
                missing = recipe.get("missing_ingredients", 0)
                subs_detail = recipe.get("substitute_details", [])

                with st.expander(f"**{name}** — {missing} missing, substitutes available"):
                    # Weather badges
                    _render_weather_badges(recipe)

                    # Show substitution details
                    if subs_detail:
                        st.markdown("**Suggested substitutions:**")
                        for sub in subs_detail:
                            if isinstance(sub, dict):
                                missing_name = sub.get("missing_ingredient", sub.get("ingredient_name", "?"))
                                sub_name = sub.get("substitute_name", sub.get("substitute_item_name", "?"))
                                st.markdown(f"- 🔄 **{missing_name}** → use **{sub_name}**")
                            elif isinstance(sub, str):
                                st.markdown(f"- 🔄 {sub}")
        else:
            st.info("No recipes with available substitutions found.")


def _render_recipe_card(recipe: dict, show_missing: bool = False):
    """Display a recipe match result as a card."""
    name = recipe.get("recipe_name", "Unknown")
    total = recipe.get("total_ingredients", 0)
    available = recipe.get("available_ingredients", 0)
    missing = recipe.get("missing_ingredients", 0)
    missing_list = recipe.get("missing_ingredient_list", [])
    uses_expiring = recipe.get("uses_expiring_ingredients", False)
    expiring_list = recipe.get("expiring_ingredient_list", [])

    # Header with availability count
    header = f"**{name}** — {available}/{total} ingredients available"
    if uses_expiring:
        header += " 🕐 **Use it up!**"

    with st.expander(header):
        _render_weather_badges(recipe)

        if uses_expiring and expiring_list:
            st.warning(
                "Uses expiring ingredients: " + ", ".join(
                    str(e) if isinstance(e, str) else e.get("ingredient_name", str(e))
                    for e in expiring_list
                )
            )

        if show_missing and missing_list:
            st.markdown(f"**Missing ({missing}):**")
            for item in missing_list:
                st.markdown(f"- ❌ {item}")


def _render_weather_badges(recipe: dict):
    """Display weather tag badges for a recipe."""
    weather_t = recipe.get("weather_temp")
    weather_c = recipe.get("weather_condition")
    badges = []
    if weather_t:
        emoji = "🌡️" if weather_t == "warm" else "❄️"
        badges.append(f"{emoji} {weather_t.title()}")
    if weather_c:
        emoji_map = {"sunny": "☀️", "rainy": "🌧️", "cloudy": "☁️"}
        badges.append(f"{emoji_map.get(weather_c, '')} {weather_c.title()}")
    if badges:
        st.markdown(" &nbsp; ".join(badges))


def _render_shopping_list(api: WhatToEatAPI):
    """Render the shopping list generator section."""
    st.markdown("---")
    st.subheader("🛒 Shopping List")

    selected = st.session_state.get("shopping_selections", set())

    if not selected:
        st.caption("Select recipes above using the checkboxes to generate a shopping list.")
        return

    st.markdown(f"**{len(selected)} recipe{'s' if len(selected) != 1 else ''} selected**")

    if st.button("Generate Shopping List", type="primary"):
        with st.spinner("Generating..."):
            result = api.get_shopping_list(list(selected))

        if isinstance(result, dict) and "error" in result:
            st.error(result["error"])
            return

        if isinstance(result, dict) and "items" in result:
            items = result.get("items", [])

            if not items:
                st.success("No items needed — you have everything!")
                return

            st.markdown(f"**{result.get('total_items', len(items))} items to buy:**")

            # Group items by category
            by_category = {}
            for item in items:
                cat = item.get("category", "other")
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(item)

            # Display grouped shopping list
            shopping_lines = []
            for cat in sorted(by_category.keys()):
                st.markdown(f"**{cat.title()}**")
                for item in by_category[cat]:
                    name = item.get("ingredient_name", "?")
                    needed_by = item.get("needed_by_recipes", "")
                    line = f"- [ ] {name}"
                    if needed_by:
                        line += f" *(for: {needed_by})*"
                    st.markdown(line)
                    shopping_lines.append(f"{name} ({cat})")

            # Copy to clipboard button
            clipboard_text = "\n".join(shopping_lines)
            st.text_area(
                "Copy this shopping list:",
                value=clipboard_text,
                height=100,
                help="Select all and copy (Ctrl+A, Ctrl+C) to save your shopping list.",
            )

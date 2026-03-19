"""
dashboard.py — Overview dashboard with summary metrics, charts, and quick actions.

STREAMLIT CHARTS
Streamlit has built-in charting via st.bar_chart(), st.line_chart(), etc., powered
by Altair under the hood. For more control, we use matplotlib and pass the figure
to st.pyplot(). Both approaches work — built-in charts are simpler, matplotlib
gives you full customization.

st.metric() is a special widget that displays a big number with an optional delta
(change indicator). It's perfect for KPI-style dashboard cards.
"""

import matplotlib.pyplot as plt
import streamlit as st

from src.app.api_client import WhatToEatAPI


def render(api: WhatToEatAPI):
    """Render the Dashboard page."""
    st.header("📊 Dashboard")
    st.caption("Overview of your recipes, inventory, and what you can cook.")

    # ------------------------------------------------------------------
    # Fetch data for the dashboard
    # ------------------------------------------------------------------
    summary = api.get_summary()
    recipes_result = api.list_recipes()
    match_data = api.get_match_summary()

    has_error = False
    if isinstance(summary, dict) and "error" in summary:
        st.error(summary["error"])
        has_error = True
    if isinstance(recipes_result, dict) and "error" in recipes_result:
        st.error(recipes_result["error"])
        has_error = True

    if has_error:
        st.info("Start the API server and run ingestion to see dashboard data.")
        _render_quick_actions(api)
        return

    # ------------------------------------------------------------------
    # Summary metrics row
    # ------------------------------------------------------------------
    total_recipes = recipes_result.get("count", 0) if isinstance(recipes_result, dict) else 0
    total_items = summary.get("total_items", 0) if isinstance(summary, dict) else 0
    expiring_7d = summary.get("expiring_within_7_days", 0) if isinstance(summary, dict) else 0

    # Count makeable recipes from match data
    makeable_count = 0
    if isinstance(match_data, list):
        makeable_count = sum(1 for m in match_data if m.get("is_fully_makeable"))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Recipes", total_recipes)
    with col2:
        st.metric("Inventory Items", total_items)
    with col3:
        st.metric("Makeable Recipes", f"{makeable_count} / {total_recipes}")
    with col4:
        st.metric("Expiring This Week", expiring_7d)

    st.markdown("---")

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------
    chart_col1, chart_col2 = st.columns(2)

    # --- Chart 1: Inventory by category (bar chart) ---
    with chart_col1:
        st.subheader("Inventory by Category")
        by_category = summary.get("by_category", {}) if isinstance(summary, dict) else {}

        if by_category:
            categories = sorted(by_category.keys())
            counts = [by_category[cat] for cat in categories]

            fig, ax = plt.subplots(figsize=(6, 4))
            bars = ax.barh(categories, counts, color="#4CAF50")
            ax.set_xlabel("Number of Items")
            ax.set_title("Items by Food Category")

            # Add count labels on each bar
            for bar, count in zip(bars, counts):
                ax.text(
                    bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                    str(count), va="center", fontsize=9,
                )

            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("No inventory data to chart.")

    # --- Chart 2: Recipe coverage (pie chart) ---
    with chart_col2:
        st.subheader("Recipe Coverage")

        if isinstance(match_data, list) and match_data:
            fully_makeable = sum(1 for m in match_data if m.get("is_fully_makeable"))
            almost = sum(
                1 for m in match_data
                if not m.get("is_fully_makeable") and m.get("missing_ingredients", 99) <= 2
            )
            cant_make = len(match_data) - fully_makeable - almost

            if fully_makeable or almost or cant_make:
                labels = []
                sizes = []
                colors = []

                if fully_makeable:
                    labels.append(f"Can Make ({fully_makeable})")
                    sizes.append(fully_makeable)
                    colors.append("#28a745")
                if almost:
                    labels.append(f"Almost ({almost})")
                    sizes.append(almost)
                    colors.append("#ffc107")
                if cant_make:
                    labels.append(f"Can't Make ({cant_make})")
                    sizes.append(cant_make)
                    colors.append("#dc3545")

                fig, ax = plt.subplots(figsize=(6, 4))
                ax.pie(
                    sizes, labels=labels, colors=colors,
                    autopct="%1.0f%%", startangle=90,
                )
                ax.set_title("Recipe Ingredient Availability")
                plt.tight_layout()
                st.pyplot(fig)
                plt.close(fig)
            else:
                st.info("No match data available.")
        else:
            st.info("No recipe match data. Run 'Refresh Matching' below.")

    # --- Chart 3: Expiration timeline ---
    st.subheader("Expiration Timeline (Next 14 Days)")

    expiring_items = api.get_expiring(days=14)

    if isinstance(expiring_items, list) and expiring_items:
        # Group items by expiration date
        from collections import Counter
        from datetime import date

        date_counts = Counter()
        for item in expiring_items:
            exp_date = item.get("expiration_date", "unknown")
            date_counts[exp_date] += 1

        sorted_dates = sorted(date_counts.keys())
        if sorted_dates:
            fig, ax = plt.subplots(figsize=(10, 3))
            ax.bar(sorted_dates, [date_counts[d] for d in sorted_dates], color="#ff6b6b")
            ax.set_xlabel("Expiration Date")
            ax.set_ylabel("Items")
            ax.set_title("Items Expiring Over the Next 2 Weeks")
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)
    else:
        st.info("No items expiring in the next 14 days.")

    # ------------------------------------------------------------------
    # Weather widget
    # ------------------------------------------------------------------
    st.markdown("---")
    _render_weather_widget(api)

    # ------------------------------------------------------------------
    # Quick actions
    # ------------------------------------------------------------------
    st.markdown("---")
    _render_quick_actions(api)


def _render_weather_widget(api: WhatToEatAPI):
    """Render a weather summary widget on the dashboard."""
    st.subheader("Today's Weather")

    weather_data = api.get_current_weather()

    if isinstance(weather_data, dict) and "error" in weather_data:
        st.info("Weather unavailable — start the API server to see weather data.")
        return

    weather = weather_data.get("weather", {})
    tags = weather_data.get("recipe_tags", {})
    temp_f = weather.get("temperature_f")
    description = weather.get("description", "unknown")
    recipe_temp = tags.get("weather_temp")
    recipe_condition = tags.get("weather_condition")

    # Weather display
    condition_emoji = {"sunny": "☀️", "cloudy": "☁️", "rainy": "🌧️"}.get(
        recipe_condition, "🌡️"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Temperature", f"{temp_f}°F" if temp_f is not None else "N/A")
    with col2:
        st.metric("Condition", f"{condition_emoji} {description}")
    with col3:
        # Count weather-appropriate makeable recipes
        recs = api.get_weather_recommendations()
        weather_makeable = 0
        if isinstance(recs, dict) and "recommendations" in recs:
            weather_makeable = len(recs["recommendations"].get("perfect_for_today", []))
        st.metric("Weather-Matched Recipes", weather_makeable)


def _render_quick_actions(api: WhatToEatAPI):
    """Render the quick action buttons section."""
    st.subheader("Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Refresh Inventory", use_container_width=True):
            with st.spinner("Rebuilding inventory..."):
                result = api.refresh_inventory()
            if isinstance(result, dict) and "error" in result:
                st.error(result["error"])
            else:
                st.success(result.get("message", "Done!") if isinstance(result, dict) else "Done!")
                st.rerun()

    with col2:
        if st.button("🔄 Refresh Matching", use_container_width=True):
            with st.spinner("Rebuilding recipe matching..."):
                result = api.refresh_matching()
            if isinstance(result, dict) and "error" in result:
                st.error(result["error"])
            else:
                st.success(result.get("message", "Done!") if isinstance(result, dict) else "Done!")
                st.rerun()

    with col3:
        if st.button("🚀 Run Full Ingestion", use_container_width=True):
            with st.spinner("Running full ingestion pipeline (this may take a moment)..."):
                result = api.ingest_all()
            if isinstance(result, dict) and "error" in result:
                st.error(result["error"])
            else:
                st.success(result.get("message", "Done!") if isinstance(result, dict) else "Done!")
                st.rerun()

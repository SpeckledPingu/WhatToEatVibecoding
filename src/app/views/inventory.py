"""
inventory.py — View and manage your food inventory.

DATA DISPLAY IN STREAMLIT
  - st.dataframe() renders a pandas DataFrame as an interactive, sortable table.
    Users can click column headers to sort, and Streamlit handles it automatically.
  - st.metric() shows a big number with an optional delta — great for dashboards.
  - Color coding helps users quickly scan for important information (like expiring
    items) without reading every row. We use pandas Styler for conditional formatting.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.app.api_client import WhatToEatAPI


def render(api: WhatToEatAPI):
    """Render the Inventory page."""
    st.header("📦 Inventory")
    st.caption("View your active food inventory, filter by category, and track expiration dates.")

    # ------------------------------------------------------------------
    # Summary cards at the top
    # ------------------------------------------------------------------
    summary = api.get_summary()

    if isinstance(summary, dict) and "error" in summary:
        st.error(summary["error"])
        return

    if isinstance(summary, dict) and "total_items" in summary:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Items", summary.get("total_items", 0))
        with col2:
            # Count categories
            by_cat = summary.get("by_category", {})
            st.metric("Categories", len(by_cat))
        with col3:
            st.metric("Expiring Soon (7d)", summary.get("expiring_within_7_days", 0))
        with col4:
            st.metric("Expired", summary.get("expired_count", 0))

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        # Build category options from the summary data
        categories = ["All"]
        if isinstance(summary, dict):
            by_cat = summary.get("by_category", {})
            categories += sorted(by_cat.keys())
        category_filter = st.selectbox("Category", options=categories)

    with col_f2:
        source_filter = st.selectbox("Source", options=["All", "receipt", "pantry"])

    with col_f3:
        expiry_filter = st.selectbox(
            "Expiration Status",
            options=["All", "Expiring Soon (7d)", "Expiring Very Soon (3d)", "Expired", "Good"],
        )

    # ------------------------------------------------------------------
    # Fetch inventory with filters
    # ------------------------------------------------------------------
    params = {}
    if category_filter != "All":
        params["category"] = category_filter
    if source_filter != "All":
        params["source"] = source_filter

    result = api.list_inventory(**params)

    if isinstance(result, dict) and "error" in result:
        st.error(result["error"])
        return

    items = result.get("items", []) if isinstance(result, dict) else []

    if not items:
        st.info("No inventory items found. Run ingestion from the Dashboard to load your data.")
        return

    # ------------------------------------------------------------------
    # Build a DataFrame for display
    # ------------------------------------------------------------------
    # Convert the API response into a pandas DataFrame — Streamlit's st.dataframe()
    # can render DataFrames as sortable, interactive tables automatically.
    rows = []
    today = date.today()

    for item in items:
        exp_date_str = item.get("expiration_date")
        exp_date = None
        if exp_date_str:
            try:
                exp_date = date.fromisoformat(exp_date_str)
            except (ValueError, TypeError):
                pass

        # Determine status based on expiration
        if item.get("is_expired") or (exp_date and exp_date < today):
            status = "Expired"
            days_left = 0 if not exp_date else (exp_date - today).days
        elif exp_date:
            days_left = (exp_date - today).days
            if days_left <= 3:
                status = "Expiring Very Soon"
            elif days_left <= 7:
                status = "Expiring Soon"
            else:
                status = "Good"
        else:
            status = "Good"
            days_left = None

        rows.append({
            "Item Name": item.get("item_name", ""),
            "Category": item.get("category", ""),
            "Quantity": item.get("quantity", 0),
            "Unit": item.get("unit", ""),
            "Source": item.get("source", ""),
            "Date Acquired": item.get("date_acquired", ""),
            "Expiration Date": exp_date_str or "N/A",
            "Status": status,
            "_days_left": days_left,
        })

    df = pd.DataFrame(rows)

    # Apply the expiration status filter
    if expiry_filter == "Expiring Soon (7d)":
        df = df[df["Status"].isin(["Expiring Soon", "Expiring Very Soon"])]
    elif expiry_filter == "Expiring Very Soon (3d)":
        df = df[df["Status"] == "Expiring Very Soon"]
    elif expiry_filter == "Expired":
        df = df[df["Status"] == "Expired"]
    elif expiry_filter == "Good":
        df = df[df["Status"] == "Good"]

    if df.empty:
        st.info("No items match the current filters.")
        return

    st.markdown(f"**Showing {len(df)} items**")

    # ------------------------------------------------------------------
    # Color-coded table display
    # ------------------------------------------------------------------
    # We use column_config to style the Status column with colored text.
    # Streamlit's st.dataframe supports pandas Styler for conditional formatting.

    # Drop the internal helper column before display
    display_df = df.drop(columns=["_days_left"])

    def color_status(val):
        """Return CSS color based on inventory status."""
        colors = {
            "Good": "color: #28a745",            # Green
            "Expiring Soon": "color: #ffc107",    # Yellow/amber
            "Expiring Very Soon": "color: #dc3545",  # Red
            "Expired": "color: #6c757d",          # Gray
        }
        return colors.get(val, "")

    # Apply styling to the Status column
    styled_df = display_df.style.map(color_status, subset=["Status"])

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
    )

    # ------------------------------------------------------------------
    # Refresh button
    # ------------------------------------------------------------------
    st.markdown("---")
    if st.button("🔄 Refresh Inventory", help="Rebuild the active inventory from source data"):
        with st.spinner("Rebuilding inventory..."):
            refresh_result = api.refresh_inventory()
        if isinstance(refresh_result, dict) and "error" in refresh_result:
            st.error(refresh_result["error"])
        elif isinstance(refresh_result, dict):
            st.success(refresh_result.get("message", "Inventory refreshed!"))
            st.rerun()

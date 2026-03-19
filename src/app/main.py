"""
main.py — The Streamlit web application for WhatToEat.

HOW STREAMLIT WORKS
Streamlit is fundamentally different from traditional web frameworks:
  - The ENTIRE script re-runs from top to bottom on EVERY user interaction
    (clicking a button, typing in a text box, selecting a dropdown, etc.)
  - This means variables are reset on every re-run — if you store something
    in a regular Python variable, it disappears the next time you click anything.
  - st.session_state is Streamlit's solution: it's a dictionary that PERSISTS
    across re-runs. Use it to remember things like the current page, API
    connection status, or data that was fetched.

HOW THE SIDEBAR NAVIGATION WORKS
We use st.session_state["current_page"] to track which page is active. The
sidebar shows radio buttons for page selection. When the user picks a different
page, the script re-runs, reads the new value from session_state, and calls
the corresponding page rendering function.

HOW TO RUN
    uv run streamlit run src/app/main.py
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Fix the import path so "from src.*" imports work.
#
# WHY IS THIS NEEDED?
# When you run `uv run streamlit run src/app/main.py`, Streamlit executes
# this file as a standalone script. Python adds the FILE's directory
# (src/app/) to sys.path, but NOT the project root. That means
# `from src.app.api_client import ...` fails because Python can't find
# a top-level "src" package.
#
# The fix: we figure out where the project root is (two levels up from this
# file: src/app/main.py → src/app → src → project root) and add it to
# sys.path if it's not already there. This makes all `from src.*` imports
# work exactly as they do when running via `uv run python -m src.app.main`.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st

from src.app.api_client import WhatToEatAPI
from src.app.views import recipe_browser, add_recipe, inventory, what_can_i_make, dashboard


# ==========================================================================
# Page configuration — must be the FIRST Streamlit command
# ==========================================================================
# set_page_config() configures the browser tab title, layout, and icon.
# It MUST be called before any other st.* command or Streamlit will throw an error.

st.set_page_config(
    page_title="WhatToEat",
    page_icon="🍽️",
    layout="wide",
)


# ==========================================================================
# Initialize session state — runs once, persists across re-runs
# ==========================================================================
# session_state is a dictionary attached to the user's browser session.
# We check if keys exist before setting defaults so we don't overwrite
# values the user has already set.

if "api_url" not in st.session_state:
    st.session_state.api_url = "http://localhost:8000"

if "api_connected" not in st.session_state:
    st.session_state.api_connected = False

if "current_page" not in st.session_state:
    st.session_state.current_page = "Recipe Browser"


# ==========================================================================
# Create the API client from the stored URL
# ==========================================================================
# This creates a new WhatToEatAPI instance on every re-run, but that's fine —
# it's lightweight (just stores the URL). The actual HTTP calls only happen
# when we call methods on it.

api = WhatToEatAPI(st.session_state.api_url)


# ==========================================================================
# Sidebar — Navigation and API configuration
# ==========================================================================

with st.sidebar:
    st.title("🍽️ WhatToEat")
    st.markdown("---")

    # Page navigation using radio buttons
    # The 'key' parameter ties this widget to session_state so its value persists
    page = st.radio(
        "Navigate",
        options=[
            "Recipe Browser",
            "Add Recipe",
            "Inventory",
            "What Can I Make?",
            "Dashboard",
        ],
        key="current_page",
        label_visibility="collapsed",
    )

    st.markdown("---")

    # API Configuration section at the bottom of the sidebar
    st.subheader("API Connection")

    # Text input for the API URL — lets users switch between the simple API
    # (port 8000) and the authenticated API (port 8001)
    new_url = st.text_input(
        "API URL",
        value=st.session_state.api_url,
        help="Default: http://localhost:8000 (simple API) or http://localhost:8001 (authenticated API)",
    )

    # Update the API URL if the user changed it
    if new_url != st.session_state.api_url:
        st.session_state.api_url = new_url
        st.session_state.api_connected = False
        api = WhatToEatAPI(new_url)

    # Test Connection button
    if st.button("Test Connection", use_container_width=True):
        with st.spinner("Connecting..."):
            result = api.test_connection()
            if result["status"] == "connected":
                st.session_state.api_connected = True
                st.success("Connected!")
            else:
                st.session_state.api_connected = False
                st.error(result["message"])

    # Show persistent connection status
    if st.session_state.api_connected:
        st.caption("🟢 Connected")
    else:
        st.caption("🔴 Not connected")


# ==========================================================================
# Main content — render the selected page
# ==========================================================================
# Each page is a function in its own module. We call the right one based
# on the current_page value in session_state.

if page == "Recipe Browser":
    recipe_browser.render(api)
elif page == "Add Recipe":
    add_recipe.render(api)
elif page == "Inventory":
    inventory.render(api)
elif page == "What Can I Make?":
    what_can_i_make.render(api)
elif page == "Dashboard":
    dashboard.render(api)

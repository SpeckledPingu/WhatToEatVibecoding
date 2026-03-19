"""
add_recipe.py — Add new recipes by pasting structured JSON and optional Markdown.

FORM VALIDATION AND DATA QUALITY
Why validate before submitting? Two reasons:
  1. User experience: Catching errors early (before the API call) gives instant
     feedback so the user can fix problems without waiting for a server response.
  2. Data quality: The recipe matching system depends on consistent data. If an
     ingredient has no category, or a category that doesn't match our config,
     the matching pipeline can't work correctly.

The API also validates (via Pydantic schemas), so we have TWO layers of defense:
  - Frontend validation: quick, user-friendly, catches obvious issues
  - Backend validation: authoritative, catches anything the frontend missed
"""

import json
from pathlib import Path

import streamlit as st

from src.app.api_client import WhatToEatAPI

# Valid categories from the config file — loaded once at module level
_CONFIG_PATH = Path("config/normalization_mappings.json")


def _load_valid_categories() -> list[str]:
    """Read the valid food categories from the normalization config."""
    try:
        config = json.loads(_CONFIG_PATH.read_text())
        return list(config.get("food_categories", {}).keys())
    except Exception:
        # Fallback if config can't be read
        return [
            "protein", "vegetable", "fruit", "dairy", "grain",
            "spice", "condiment", "beverage", "snack", "other",
        ]


def render(api: WhatToEatAPI):
    """Render the Add Recipe page."""
    st.header("➕ Add Recipe")
    st.caption(
        "Paste a recipe's structured JSON (from the extraction prompt) "
        "and optionally include the full recipe text in Markdown."
    )

    valid_categories = _load_valid_categories()

    # ==================================================================
    # Section 1: Structured Data (JSON) — required
    # ==================================================================
    st.subheader("1. Structured Recipe Data (JSON)")
    st.markdown(
        "Paste the JSON output from the recipe extraction prompt. "
        "See the collapsible example below for the expected format."
    )

    # Example JSON format (collapsible)
    with st.expander("Example JSON format"):
        st.code(
            json.dumps(
                {
                    "name": "Chicken Stir Fry",
                    "description": "A quick weeknight stir fry with vegetables",
                    "prep_time_minutes": 15,
                    "cook_time_minutes": 10,
                    "servings": 4,
                    "weather_temp": "warm",
                    "weather_condition": "sunny",
                    "ingredients": [
                        {"name": "chicken breast", "quantity": 1.5, "unit": "pounds", "category": "protein"},
                        {"name": "broccoli", "quantity": 2, "unit": "cups", "category": "vegetable"},
                        {"name": "soy sauce", "quantity": 3, "unit": "tablespoons", "category": "condiment"},
                    ],
                    "instructions": [
                        "Cut chicken into bite-sized pieces and season with salt.",
                        "Heat oil in a wok over high heat.",
                        "Stir-fry chicken until cooked through, about 5 minutes.",
                        "Add broccoli and soy sauce, cook 3 more minutes.",
                    ],
                    "tags": ["asian", "dinner", "quick"],
                    "source": "https://example.com/stir-fry",
                },
                indent=2,
            ),
            language="json",
        )
        st.caption(
            "Use the extraction prompt in `prompts/recipe_extraction.md` with a "
            "browser-connected AI to generate this JSON from any recipe webpage."
        )

    # JSON text area
    json_text = st.text_area(
        "Recipe JSON",
        height=300,
        placeholder='Paste your recipe JSON here...\n{\n  "name": "...",\n  "ingredients": [...],\n  "instructions": [...]\n}',
        key="recipe_json_input",
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    parsed_data = None
    validation_passed = False

    if json_text.strip():
        st.markdown("**Validation**")
        checks = []

        # Check 1: Is it valid JSON?
        try:
            parsed_data = json.loads(json_text)
            checks.append(("Valid JSON", True, None))
        except json.JSONDecodeError as e:
            checks.append(("Valid JSON", False, f"Parse error: {e}"))

        if parsed_data and isinstance(parsed_data, dict):
            # Check 2: Required fields
            has_name = bool(parsed_data.get("name"))
            checks.append(("Has 'name' field", has_name, None if has_name else "Recipe name is required"))

            has_ingredients = isinstance(parsed_data.get("ingredients"), list) and len(parsed_data.get("ingredients", [])) > 0
            checks.append((
                "Has 'ingredients' (non-empty list)",
                has_ingredients,
                None if has_ingredients else "At least one ingredient is required",
            ))

            has_instructions = isinstance(parsed_data.get("instructions"), list) and len(parsed_data.get("instructions", [])) > 0
            checks.append((
                "Has 'instructions' (non-empty list)",
                has_instructions,
                None if has_instructions else "At least one instruction step is required",
            ))

            # Check 3: Ingredient structure
            ingredients = parsed_data.get("ingredients", [])
            all_valid_structure = True
            all_valid_categories = True
            bad_categories = []

            for i, ing in enumerate(ingredients):
                if not isinstance(ing, dict):
                    all_valid_structure = False
                    continue
                for field in ("name", "quantity", "unit", "category"):
                    if field not in ing:
                        all_valid_structure = False

                cat = ing.get("category", "")
                if cat and cat not in valid_categories:
                    all_valid_categories = False
                    bad_categories.append(f"'{cat}' (ingredient: {ing.get('name', f'#{i+1}')})")

            checks.append((
                "Ingredients have name/quantity/unit/category",
                all_valid_structure,
                None if all_valid_structure else "Each ingredient needs: name, quantity, unit, category",
            ))

            checks.append((
                "Ingredient categories are valid",
                all_valid_categories,
                None if all_valid_categories else f"Invalid: {', '.join(bad_categories)}. Valid: {', '.join(valid_categories)}",
            ))

            # Check 4: Weather fields (warnings, not errors)
            has_weather_temp = bool(parsed_data.get("weather_temp"))
            has_weather_cond = bool(parsed_data.get("weather_condition"))

            if not has_weather_temp:
                checks.append(("weather_temp field", None, "Optional but recommended (warm/cold)"))
            else:
                checks.append(("weather_temp field", True, None))

            if not has_weather_cond:
                checks.append(("weather_condition field", None, "Optional but recommended (sunny/rainy/cloudy)"))
            else:
                checks.append(("weather_condition field", True, None))

        # Display validation results
        has_errors = False
        for label, passed, detail in checks:
            if passed is True:
                st.markdown(f"✅ {label}")
            elif passed is False:
                st.markdown(f"❌ {label}" + (f" — {detail}" if detail else ""))
                has_errors = True
            else:
                # Warning (None = optional)
                st.markdown(f"⚠️ {label}" + (f" — {detail}" if detail else ""))

        validation_passed = not has_errors and parsed_data is not None

        # Preview
        if parsed_data and validation_passed:
            with st.expander("Preview parsed recipe"):
                st.markdown(f"### {parsed_data.get('name', 'Untitled')}")
                if parsed_data.get("description"):
                    st.markdown(f"*{parsed_data['description']}*")

                info_parts = []
                if parsed_data.get("prep_time_minutes") is not None:
                    info_parts.append(f"Prep: {parsed_data['prep_time_minutes']}m")
                if parsed_data.get("cook_time_minutes") is not None:
                    info_parts.append(f"Cook: {parsed_data['cook_time_minutes']}m")
                if parsed_data.get("servings") is not None:
                    info_parts.append(f"Serves: {parsed_data['servings']}")
                if info_parts:
                    st.markdown(" | ".join(info_parts))

                st.markdown("**Ingredients:**")
                for ing in parsed_data.get("ingredients", []):
                    st.markdown(
                        f"- {ing.get('quantity', '')} {ing.get('unit', '')} "
                        f"**{ing.get('name', '')}** ({ing.get('category', '')})"
                    )

                st.markdown("**Instructions:**")
                for i, step in enumerate(parsed_data.get("instructions", []), 1):
                    st.markdown(f"{i}. {step}")

    # ==================================================================
    # Section 2: Full Recipe Text (Markdown) — optional
    # ==================================================================
    st.markdown("---")
    st.subheader("2. Full Recipe Text (Markdown) — Optional")
    st.markdown(
        "Paste the full human-readable recipe here. This is the complete recipe "
        "with tips, stories, and detailed descriptions — what you'd read on a "
        "recipe blog. Get it from your browser's markdown extension or paste "
        "the original text."
    )

    markdown_text = st.text_area(
        "Full Recipe Markdown",
        height=200,
        placeholder="# Recipe Name\n\nPaste the full recipe text here...",
        key="recipe_markdown_input",
    )

    # Preview the markdown
    if markdown_text.strip():
        with st.expander("Markdown Preview"):
            st.markdown(markdown_text)

    # ==================================================================
    # Submit
    # ==================================================================
    st.markdown("---")

    if st.button(
        "Submit Recipe",
        type="primary",
        use_container_width=True,
        disabled=not validation_passed,
    ):
        if parsed_data:
            # Add the markdown text if provided
            if markdown_text.strip():
                parsed_data["full_text_markdown"] = markdown_text.strip()

            with st.spinner("Submitting recipe..."):
                result = api.create_recipe(parsed_data)

            if isinstance(result, dict) and "error" in result:
                st.error(f"Failed to create recipe: {result['error']}")
            elif isinstance(result, dict) and result.get("id"):
                st.success(f"Recipe '{result.get('name')}' created with ID {result.get('id')}!")
                st.balloons()
                st.info("Switch to the Recipe Browser to view your new recipe.")
            else:
                st.warning("Unexpected response from API. Check the Recipe Browser to verify.")
        else:
            st.error("Please paste valid recipe JSON above first.")

    if not validation_passed and json_text.strip():
        st.caption("Fix the validation errors above to enable the Submit button.")
    elif not json_text.strip():
        st.caption("Paste recipe JSON above to get started.")

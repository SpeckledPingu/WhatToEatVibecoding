"""
api_client.py — A helper class that wraps all HTTP calls to the WhatToEat API.

WHAT IS AN API CLIENT?
An API client is a class that handles all the details of talking to a REST API:
  - Building the correct URLs
  - Sending the right HTTP method (GET, POST, PUT, DELETE)
  - Handling errors and returning user-friendly messages

WHY CENTRALIZE API CALLS?
Without a client, every page in our Streamlit app would need to:
  1. Know the full API URL for each endpoint
  2. Handle HTTP errors individually
  3. Parse the JSON response manually

This violates the DRY (Don't Repeat Yourself) principle. If we change the API URL
or add authentication headers, we'd need to update every single page. With a client,
we update ONE file.

HOW httpx WORKS
httpx is an HTTP library similar to the popular 'requests' library, but with async
support. The basic pattern is:
  - httpx.get(url)     → sends a GET request
  - httpx.post(url, json=data)  → sends a POST request with a JSON body
  - response.json()    → parses the JSON response into a Python dict
  - response.raise_for_status()  → raises an error if the HTTP status is 4xx/5xx
"""

from typing import Any, Optional

import httpx


class WhatToEatAPI:
    """
    Wraps all HTTP calls to the WhatToEat REST API.

    Usage:
        api = WhatToEatAPI("http://localhost:8000")
        recipes = api.list_recipes()
    """

    def __init__(self, base_url: str):
        """
        Initialize the API client with the base URL of the API server.

        Args:
            base_url: The root URL of the API, e.g. "http://localhost:8000".
                      No trailing slash needed.
        """
        # Strip any trailing slash to avoid double-slash URLs like
        # "http://localhost:8000//recipes"
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Internal helper — all API calls go through this method
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> dict | list | None:
        """
        Send an HTTP request and return the parsed JSON response.

        This is the single place where all HTTP communication happens.
        Every public method below calls _request(), which means:
          - Error handling is in one place
          - Logging / auth headers can be added once
          - URL construction is consistent

        Returns the parsed JSON (dict or list), or None if the request fails.
        On failure, returns a dict with an "error" key and a user-friendly message.
        """
        url = f"{self.base_url}{path}"

        try:
            # httpx.request() is the universal method — it handles GET, POST,
            # PUT, DELETE, etc. based on the 'method' argument.
            response = httpx.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                timeout=timeout,
            )

            # raise_for_status() throws an exception for HTTP 4xx/5xx errors.
            # This lets us catch API errors (like 404 Not Found) uniformly.
            response.raise_for_status()

            return response.json()

        except httpx.ConnectError:
            # The API server isn't running or the URL is wrong
            return {"error": f"Cannot connect to API at {self.base_url}. Is the server running?"}
        except httpx.TimeoutException:
            return {"error": "Request timed out. The API server may be overloaded."}
        except httpx.HTTPStatusError as e:
            # The server returned a 4xx or 5xx status code
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            return {"error": f"API error ({e.response.status_code}): {detail}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_connection(self) -> dict:
        """Ping the API root endpoint to check if the server is reachable."""
        result = self._request("GET", "/")
        if result and "error" not in result:
            return {"status": "connected", "message": result.get("message", "OK")}
        error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else "Unknown error"
        return {"status": "disconnected", "message": error_msg}

    # ==================================================================
    # Recipe methods
    # ==================================================================

    def list_recipes(
        self,
        search: Optional[str] = None,
        weather_temp: Optional[str] = None,
        weather_condition: Optional[str] = None,
    ) -> dict:
        """
        Get all recipes, optionally filtered by search text or weather tags.

        Returns a dict with 'count' and 'recipes' keys.
        """
        params = {}
        if search:
            params["search"] = search
        if weather_temp:
            params["weather_temp"] = weather_temp
        if weather_condition:
            params["weather_condition"] = weather_condition
        return self._request("GET", "/recipes", params=params)

    def get_recipe(self, recipe_id: int) -> dict:
        """Get a single recipe by its ID."""
        return self._request("GET", f"/recipes/{recipe_id}")

    def create_recipe(self, data: dict) -> dict:
        """
        Create a new recipe by sending JSON data to the API.

        Args:
            data: A dictionary matching the RecipeCreate schema — must include
                  'name', 'ingredients', and 'instructions' at minimum.
        """
        return self._request("POST", "/recipes", json_body=data)

    def update_recipe(self, recipe_id: int, data: dict) -> dict:
        """Update an existing recipe. Only included fields are changed."""
        return self._request("PUT", f"/recipes/{recipe_id}", json_body=data)

    def delete_recipe(self, recipe_id: int) -> dict:
        """Permanently delete a recipe by its ID."""
        return self._request("DELETE", f"/recipes/{recipe_id}")

    def get_makeable(self) -> list:
        """Get recipes where ALL ingredients are in stock."""
        return self._request("GET", "/recipes/makeable")

    def get_almost_makeable(self, max_missing: int = 2) -> list:
        """Get recipes missing up to max_missing ingredients."""
        return self._request("GET", "/recipes/almost-makeable", params={"max_missing": max_missing})

    def get_with_substitutions(self) -> list:
        """Get recipes where missing ingredients have same-category substitutes."""
        return self._request("GET", "/recipes/with-substitutions")

    # ==================================================================
    # Inventory methods
    # ==================================================================

    def list_inventory(
        self,
        category: Optional[str] = None,
        expiring_within_days: Optional[int] = None,
        source: Optional[str] = None,
    ) -> dict:
        """
        Get active inventory items with optional filters.

        Returns a dict with 'count', 'total_items', 'expired_count', and 'items'.
        """
        params = {}
        if category:
            params["category"] = category
        if expiring_within_days is not None:
            params["expiring_within_days"] = expiring_within_days
        if source:
            params["source"] = source
        return self._request("GET", "/inventory", params=params)

    def get_expiring(self, days: int = 7) -> list:
        """Get inventory items expiring within the specified number of days."""
        return self._request("GET", "/inventory/expiring", params={"days": days})

    def get_summary(self) -> dict:
        """Get inventory summary statistics (totals, by category, expiring counts)."""
        return self._request("GET", "/inventory/summary")

    def refresh_inventory(self) -> dict:
        """Rebuild the active inventory table from source data."""
        return self._request("POST", "/inventory/refresh")

    # ==================================================================
    # Matching methods
    # ==================================================================

    def get_match_summary(self) -> list:
        """Get the recipe match summary for all recipes."""
        return self._request("GET", "/matching/summary")

    def get_recipe_match(self, recipe_id: int) -> list:
        """Get ingredient-level match detail for a single recipe."""
        return self._request("GET", f"/matching/recipe/{recipe_id}")

    def get_shopping_list(self, recipe_ids: list[int]) -> dict:
        """
        Generate a consolidated shopping list for the given recipe IDs.

        Args:
            recipe_ids: List of recipe IDs to include in the shopping list.
        """
        # The API expects comma-separated IDs as a query parameter
        ids_str = ",".join(str(rid) for rid in recipe_ids)
        return self._request("GET", "/matching/shopping-list", params={"recipe_ids": ids_str})

    def refresh_matching(self) -> dict:
        """Rebuild the recipe matching tables."""
        return self._request("POST", "/matching/refresh")

    # ==================================================================
    # Ingestion methods
    # ==================================================================

    def ingest_all(self) -> dict:
        """Run the full ingestion pipeline (recipes, receipts, pantry, inventory, matching)."""
        return self._request("POST", "/ingest/all", timeout=120.0)

    def ingest_recipes(self) -> dict:
        """Ingest recipe files from data/recipes/json/."""
        return self._request("POST", "/ingest/recipes", timeout=60.0)

    def ingest_receipts(self) -> dict:
        """Ingest receipt CSV files from data/receipts/."""
        return self._request("POST", "/ingest/receipts", timeout=60.0)

    def ingest_pantry(self) -> dict:
        """Ingest pantry CSV files from data/pantry/."""
        return self._request("POST", "/ingest/pantry", timeout=60.0)

    # ==================================================================
    # Weather methods
    # ==================================================================

    def get_current_weather(
        self,
        latitude: float = 40.7128,
        longitude: float = -74.0060,
    ) -> dict:
        """Get current weather data and recipe tag mapping."""
        return self._request(
            "GET", "/weather/current",
            params={"latitude": latitude, "longitude": longitude},
        )

    def get_current_weather_by_city(self, city: str) -> dict:
        """Get current weather for a named city."""
        return self._request("GET", f"/weather/current/{city}")

    def get_weather_recommendations(
        self,
        latitude: float = 40.7128,
        longitude: float = -74.0060,
        include_almost: bool = True,
        max_missing: int = 2,
    ) -> dict:
        """Get weather-based recipe recommendations by coordinates."""
        return self._request(
            "GET", "/weather/recommendations",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "include_almost": include_almost,
                "max_missing": max_missing,
            },
        )

    def get_weather_recommendations_by_city(
        self,
        city: str,
        include_almost: bool = True,
        max_missing: int = 2,
    ) -> dict:
        """Get weather-based recipe recommendations for a named city."""
        return self._request(
            "GET", f"/weather/recommendations/{city}",
            params={
                "include_almost": include_almost,
                "max_missing": max_missing,
            },
        )

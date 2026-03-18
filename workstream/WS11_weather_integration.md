# Workstream 11: Weather Integration & Recommendations

Integrate a weather API to recommend recipes based on current weather conditions. This demonstrates how external APIs can enrich your application with real-time data from the internet.

## Context

Recipes in our database have `weather_temp` ("warm"/"cold") and `weather_condition` ("rainy"/"sunny"/"cloudy") fields. By fetching current weather data from a free API, we can suggest contextually appropriate recipes — hearty soups on cold rainy days, light salads on warm sunny days.

This workstream teaches:
- **Consuming external APIs** — your app as a CLIENT making requests to someone else's server
- **Data mapping** — translating external data formats into your internal categories
- **Error handling** — gracefully handling when external services are slow or unavailable
- **Combining data sources** — weather data + recipe data + inventory data for smart recommendations

## Instructions

1. **Set up the weather client** at `src/api/weather.py`:
   - Use the **Open-Meteo API** — it's free and requires NO API key or registration
   - Base URL: `https://api.open-meteo.com/v1/forecast`
   - Create a function `get_current_weather(latitude: float = 40.7128, longitude: float = -74.0060) -> dict`:
     - Default coordinates: New York City (students can change this)
     - Request current weather: temperature and weather code
     - Parse the response into a clean dict: `{"temperature_f": 72.0, "weather_code": 3, "description": "overcast"}`
     - Handle errors gracefully: network issues, API errors, timeouts
     - Return a fallback dict if the API fails: `{"temperature_f": None, "weather_code": None, "description": "unavailable"}`
   - Create a function `weather_to_recipe_tags(weather: dict) -> tuple[str | None, str | None]`:
     - **Read all mapping rules from `config/normalization_mappings.json`** under the `weather_mapping` section — do NOT hardcode thresholds or code ranges in Python
     - The config defines: temperature threshold (default 60°F), labels for above/below, and WMO weather code → condition mapping
     - If weather data is unavailable, return (None, None)
     - Include comments explaining how the config drives the mapping and how students can adjust the threshold or add new weather categories by editing the config file
   - **Load city coordinates from `config/normalization_mappings.json`** under `common_locations` — do NOT hardcode city data in Python:
     ```python
     # Load from config, not hardcoded:
     config = load_config()
     COMMON_LOCATIONS = config["common_locations"]
     # Students add their own city by editing config/normalization_mappings.json
     ```
   - Educational comments explaining:
     - How HTTP APIs work from the client perspective (URL + parameters → JSON response)
     - What query parameters are and how they're passed
     - Error handling patterns for external services (timeouts, retries, fallbacks)
     - API rate limiting and being a good API citizen (don't hammer the server)
     - The difference between YOUR API (server) and consuming SOMEONE ELSE'S API (client)

2. **Create weather-based recommendation logic** at `src/analytics/weather_recommendations.py`:
   - A function `get_weather_recommendations(latitude: float, longitude: float) -> dict`:
     - Step 1: Get current weather
     - Step 2: Map to recipe tags
     - Step 3: Query RecipeMatchSummary for recipes matching those tags
     - Step 4: Rank results:
       1. Fully makeable + weather match + uses expiring ingredients (BEST)
       2. Fully makeable + weather match (GREAT)
       3. Almost makeable (1-2 missing) + weather match (GOOD)
       4. Weather match but many missing ingredients (EXPLORE)
     - Return a structured result:
       ```python
       {
           "weather": {"temp_f": 45, "condition": "rainy", "recipe_temp": "cold", "recipe_condition": "rainy"},
           "recommendations": {
               "perfect_for_today": [...],  # makeable + weather match
               "almost_ready": [...],       # 1-2 missing + weather match
               "explore": [...]             # weather match, more ingredients needed
           },
           "use_it_up": [...]  # makeable recipes using expiring ingredients (any weather)
       }
       ```
   - Educational comments about:
     - Recommendation system basics (filter → score → rank)
     - How multiple signals (weather, availability, expiration) combine for better recommendations
     - How this pattern applies to other recommendation problems
   - Make runnable directly (prints a formatted recommendation)

3. **Add weather endpoints to the simple API** at `src/api/simple/routes/weather.py`:
   - `GET /weather/current` — Returns current weather and the mapped recipe tags
     - Query params: `latitude`, `longitude` (optional, with defaults)
     - Response includes raw weather data and the recipe tag mapping
   - `GET /weather/current/{city}` — Shortcut using a city name from COMMON_LOCATIONS
     - Returns 404 if city not recognized, with list of available cities
   - `GET /weather/recommendations` — Weather-appropriate recipe recommendations
     - Query params: `latitude`, `longitude`, `include_almost` (bool, default True), `max_missing` (int, default 2)
     - Returns the structured recommendations from step 2
   - `GET /weather/recommendations/{city}` — Shortcut with city name
   - Educational comments on each endpoint
   - Register this router in the simple API main.py

4. **Add the same weather endpoints to the authenticated API**:
   - Weather endpoints should be **public** (no auth required) — reading weather and recommendations is safe
   - Register in the authenticated API main.py

5. **Add a weather section to the Streamlit app** at `src/app/pages/weather_recommendations.py`:
   - **Location selector** at the top:
     - Dropdown of common cities from COMMON_LOCATIONS
     - OR manual latitude/longitude input
     - A "Get Recommendations" button
   - **Current weather display**:
     - Temperature with appropriate emoji (snowflake for cold, sun for warm)
     - Weather condition with emoji (rain cloud, sun, cloud)
     - The mapped recipe tags: "Today feels like: Cold + Rainy → suggesting hearty comfort food"
   - **Recommendation sections**:
     - "Perfect for Today" — makeable recipes matching the weather
     - "Almost Ready" — 1-2 ingredients away, with what's missing
     - "Explore" — weather-matched but need more ingredients
   - **"Use It Up" sidebar** — recipes using expiring ingredients regardless of weather
   - **Fallback display** — when weather data is unavailable: "Couldn't fetch weather data. Here are all your makeable recipes instead:"
   - Add this page to the sidebar navigation in `src/app/main.py`

6. **Update the Dashboard** (`src/app/pages/dashboard.py`):
   - Add a weather widget showing:
     - Current weather for the configured location
     - How many weather-appropriate recipes are makeable today
     - A "See Recommendations" link/button to the weather page

7. **Test the full integration**:
   - Start the API server
   - Start Streamlit
   - Verify weather data fetches correctly
   - Verify recommendations display and are contextually appropriate
   - Test the fallback behavior (disconnect from internet and see the graceful degradation)
   - Print test curl commands for the weather endpoints

8. **Create documentation** at `docs/guides/weather_api.md`:
   - How the Open-Meteo API works (free, no key needed, query parameters)
   - How to change your location (in the app or via API)
   - How weather maps to recipe tags (the mapping table)
   - How the recommendation ranking works
   - Ideas for using other weather APIs (OpenWeatherMap, WeatherAPI, etc.)
   - How to extend the weather categories (add "snowy", "windy", "humid")
   - Privacy note: your coordinates are sent to Open-Meteo's servers

## Things to Try After This Step

- Check the recommendations on a rainy day vs a sunny day — do they feel right?
- Change the location to a city with very different weather and see how recommendations change
- Modify the temperature threshold (60°F is the default split between warm/cold) — does a different value work better for your recipes?
- Add more weather condition mappings (snowy, windy, humid) and tag your recipes with them
- Ask Claude Code: "Add a weather forecast feature that recommends recipes for the next 3 days"
- Ask Claude Code: "Create a notebook that analyzes which weather categories have the most/fewest recipes — where should I add more recipes?"
- Try the app from different "locations" and think about how cuisine varies by climate
- Consider: how would you deploy this on a Raspberry Pi that shows today's cooking suggestions on a small screen?
- Ask Claude Code: "Add seasonal recipe recommendations — not just weather, but also time of year (summer BBQ, winter holidays)"
- Think about other external APIs that could enhance recommendations: time of day (breakfast vs dinner), holidays, local events

---

## Congratulations!

You've completed all 11 workstreams. You now have a fully functional application that:
- Ingests data from multiple formats (JSON, Markdown, CSV)
- Cleans and normalizes messy real-world data
- Stores everything in a relational database with proper keys and relationships
- Serves data through REST APIs (secured and unsecured)
- Displays an interactive web interface
- Generates analytics and visualizations
- Creates synthetic data for testing
- Integrates with external APIs for real-time recommendations

**What you've learned applies far beyond food:**
- Data ingestion pipelines work the same way for financial data, sensor data, social media, etc.
- Normalization and join keys are fundamental to any data integration project
- REST APIs and authentication are the backbone of the modern web
- The analytics patterns work with any pandas DataFrame, not just food data

**Keep building!** Some ideas:
- Deploy on a Raspberry Pi for a kitchen display
- Add a nutrition API to track macros
- Build a meal planning algorithm
- Create a recipe sharing feature with friends
- Add barcode scanning for receipts
- Connect to a smart home system to display on a screen

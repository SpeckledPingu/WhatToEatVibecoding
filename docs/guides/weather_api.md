# Weather API Integration Guide

## Overview

WhatToEat integrates with the [Open-Meteo API](https://open-meteo.com/) to fetch current weather data and recommend recipes based on weather conditions. This guide explains how the integration works and how to customize it.

## How Open-Meteo Works

Open-Meteo is a **free, open-source weather API** that requires:
- **No API key** — just send a request
- **No registration** — no account needed
- **No payment** — free for non-commercial use (< 10,000 requests/day)

### Making a Request

The API uses standard HTTP GET requests with query parameters:

```
https://api.open-meteo.com/v1/forecast?latitude=40.71&longitude=-74.01&current=temperature_2m,weather_code&temperature_unit=fahrenheit
```

| Parameter | Description |
|-----------|-------------|
| `latitude` | Geographic latitude (e.g., 40.7128 for NYC) |
| `longitude` | Geographic longitude (e.g., -74.0060 for NYC) |
| `current` | Which current weather fields to return |
| `temperature_unit` | `fahrenheit` or `celsius` |

### Response Format

```json
{
  "current": {
    "temperature_2m": 72.5,
    "weather_code": 3
  }
}
```

The `weather_code` uses the WMO (World Meteorological Organization) standard:
- **0**: Clear sky
- **1-3**: Partly cloudy to overcast
- **45-48**: Fog
- **51-57**: Drizzle
- **61-67**: Rain
- **71-77**: Snow
- **80-82**: Rain showers
- **95-99**: Thunderstorm

## Changing Your Location

### In the Streamlit App
1. Navigate to the **Weather Recommendations** page
2. Select a city from the dropdown, or enter custom latitude/longitude
3. Click **Get Recommendations**

### Via the API
```bash
# By coordinates
curl "http://localhost:8000/weather/current?latitude=47.61&longitude=-122.33"

# By city name
curl "http://localhost:8000/weather/current/Seattle"
```

### Adding Your Own City
Edit `config/normalization_mappings.json` and add to the `common_locations` section:

```json
"common_locations": {
    "My City": {"latitude": 12.3456, "longitude": -78.9012},
    ...
}
```

Find your coordinates at [latlong.net](https://www.latlong.net/).

## How Weather Maps to Recipe Tags

The mapping is defined in `config/normalization_mappings.json` under `weather_mapping`:

### Temperature Mapping

| Actual Temperature | Recipe Tag | Rule |
|-------------------|------------|------|
| Below 60°F | `cold` | Below `temperature_threshold_f` |
| 60°F and above | `warm` | At or above `temperature_threshold_f` |

To change the threshold, edit `temperature_threshold_f` in the config.

### Weather Condition Mapping

| WMO Codes | Recipe Tag | Weather Types |
|-----------|------------|---------------|
| 0-3 | `sunny` | Clear sky, partly cloudy |
| 4-44 | `cloudy` | Overcast, fog |
| 45-99 | `rainy` | Drizzle, rain, snow, thunderstorm |

## How Recommendations Work

The recommendation engine combines three signals:

1. **Weather match**: Does the recipe's `weather_temp` and `weather_condition` match today's weather?
2. **Ingredient availability**: Can you actually make this recipe with what you have?
3. **Expiration urgency**: Does this recipe use ingredients that are about to expire?

### Recommendation Tiers

| Tier | Criteria | Description |
|------|----------|-------------|
| **Perfect for Today** | Makeable + weather match | Everything you need, perfect for the weather |
| **Almost Ready** | 1-2 missing + weather match | A quick shopping trip away |
| **Explore** | Weather match, many missing | Inspiration for future cooking |
| **Use It Up** | Makeable + expiring ingredients | Any weather — reduce food waste |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /weather/current` | Current weather + recipe tags |
| `GET /weather/current/{city}` | Weather by city name |
| `GET /weather/recommendations` | Full recommendations |
| `GET /weather/recommendations/{city}` | Recommendations by city |

### Example API Calls

```bash
# Current weather for default location (NYC)
curl http://localhost:8000/weather/current

# Weather for a specific city
curl "http://localhost:8000/weather/current/Seattle"

# Full recommendations
curl http://localhost:8000/weather/recommendations

# Recommendations for a city, excluding "almost ready"
curl "http://localhost:8000/weather/recommendations/Chicago?include_almost=false"
```

## Extending Weather Categories

To add a new weather category like "snowy":

1. **Edit the config** (`config/normalization_mappings.json`):
   ```json
   "wmo_code_to_condition": {
       "sunny": [0, 1, 2, 3],
       "cloudy": [4, 5, ..., 44],
       "rainy": [45, ..., 70, 78, ..., 99],
       "snowy": [71, 73, 75, 77]
   }
   ```

2. **Tag your recipes** with `weather_condition: "snowy"` via the API or Streamlit app

3. The recommendation engine will automatically pick up the new category

## Using Other Weather APIs

While we use Open-Meteo for its simplicity, the same pattern works with other providers:

| API | Key Required? | Free Tier |
|-----|--------------|-----------|
| [Open-Meteo](https://open-meteo.com/) | No | 10,000 req/day |
| [OpenWeatherMap](https://openweathermap.org/) | Yes | 1,000 req/day |
| [WeatherAPI](https://www.weatherapi.com/) | Yes | 1,000,000 req/month |
| [Visual Crossing](https://www.visualcrossing.com/) | Yes | 1,000 req/day |

To switch providers, modify `src/api/weather.py`:
- Change the URL and query parameters
- Parse the new response format
- Map their weather codes to your categories in the config

## Privacy Note

When you use the weather feature, your coordinates (latitude/longitude) are sent to Open-Meteo's servers. Open-Meteo's [privacy policy](https://open-meteo.com/en/terms) states they do not track users or sell data. If privacy is a concern, you can:
- Use approximate coordinates (city center instead of exact location)
- Self-host Open-Meteo (it's open source)
- Use the city name endpoints which only send pre-configured coordinates

## Architecture

```
User clicks "Get Recommendations"
    ↓
Streamlit app → GET /weather/recommendations/Seattle
    ↓
FastAPI endpoint → calls get_weather_recommendations()
    ↓
Weather client → GET https://api.open-meteo.com/v1/forecast?...
    ↓
Maps weather → recipe tags (config-driven)
    ↓
Queries RecipeMatchSummary → filters + ranks
    ↓
Returns structured recommendations → Streamlit displays
```

## Files

| File | Purpose |
|------|---------|
| `src/api/weather.py` | Weather API client and mapping logic |
| `src/analytics/weather_recommendations.py` | Recommendation engine |
| `src/api/simple/routes/weather.py` | API endpoints (simple) |
| `src/api/authenticated/routes/weather.py` | API endpoints (authenticated) |
| `src/app/views/weather_recommendations.py` | Streamlit weather page |
| `config/normalization_mappings.json` | Weather mapping config |

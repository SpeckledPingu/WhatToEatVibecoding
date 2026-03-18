# Recipe Data Model

## Table: `recipe`

Stores structured recipe data ingested from JSON files, with optional full-text Markdown companions.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | Integer | Auto | Primary key, auto-incrementing |
| `name` | String | Yes | Recipe display name (indexed for fast lookups) |
| `description` | String | No | Brief summary of the dish |
| `ingredients` | JSON | Yes | List of ingredient objects (see structure below) |
| `instructions` | JSON | Yes | Ordered list of preparation step strings |
| `prep_time_minutes` | Integer | No | Minutes of active preparation |
| `cook_time_minutes` | Integer | No | Minutes of cooking time |
| `servings` | Integer | No | Number of portions the recipe makes |
| `weather_temp` | String | No | `"warm"` or `"cold"` for weather-based recommendations |
| `weather_condition` | String | No | `"rainy"`, `"sunny"`, or `"cloudy"` |
| `tags` | JSON | No | List of tag strings (e.g., `["breakfast", "vegetarian"]`) |
| `source` | String | No | URL or description of where the recipe came from |
| `source_format` | String | Yes | Always `"json"` — tracks how the structured data was parsed |
| `source_file` | String | Yes | Original filename for traceability (e.g., `"apple_cake.json"`) |
| `full_text_markdown` | Text | No | Full recipe text from a companion `.md` file, stored as-is |
| `created_at` | DateTime | Yes | UTC timestamp of when the record was ingested (auto-set) |

## JSON Field Structures

### `ingredients` — List of Ingredient Objects

Each ingredient is a JSON object with these keys:

```json
[
    {
        "name": "flour",
        "quantity": 2.5,
        "unit": "cups",
        "category": "grain"
    },
    {
        "name": "eggs",
        "quantity": 3,
        "unit": "whole",
        "category": "protein"
    },
    {
        "name": "salt",
        "quantity": 1,
        "unit": "teaspoons",
        "category": "spice"
    }
]
```

| Key | Type | Description |
|---|---|---|
| `name` | string | Ingredient name (e.g., "flour", "chicken breast") |
| `quantity` | number | Amount needed (can be decimal, e.g., 0.5) |
| `unit` | string | Measurement unit (e.g., "cups", "tablespoons", "whole", "ounces") |
| `category` | string | Standard food category from `config/normalization_mappings.json` |

Valid categories: `protein`, `vegetable`, `fruit`, `dairy`, `grain`, `spice`, `condiment`, `beverage`, `snack`, `other`

### `instructions` — Ordered List of Steps

```json
[
    "Preheat oven to 350°F.",
    "Mix dry ingredients in a large bowl.",
    "Add wet ingredients and stir until just combined.",
    "Bake for 25 minutes until golden."
]
```

## Example Records

### Apple Cake (with Markdown companion)

```json
{
    "id": 1,
    "name": "Apple Cake",
    "description": "A soft, moist cake that is a cross between a quick bread and a baked german apple pancake.",
    "ingredients": [
        {"name": "cooking spray", "quantity": 1, "unit": "cans", "category": "other"},
        {"name": "apple", "quantity": 4, "unit": "whole", "category": "fruit"},
        {"name": "sugar", "quantity": 5, "unit": "tablespoons", "category": "other"},
        {"name": "cinnamon", "quantity": 1, "unit": "tablespoons", "category": "spice"},
        {"name": "flour", "quantity": 11, "unit": "ounces", "category": "grain"},
        {"name": "egg", "quantity": 4, "unit": "whole", "category": "protein"}
    ],
    "instructions": ["Preheat oven to 350°F.", "Line the bottom of a tube pan...", "..."],
    "prep_time_minutes": 25,
    "cook_time_minutes": 90,
    "servings": 12,
    "weather_temp": "cold",
    "weather_condition": "rainy",
    "tags": ["dessert", "baking", "cake"],
    "source": "https://www.makebetterfood.com/recipes/apple-cake/",
    "source_format": "json",
    "source_file": "apple_cake.json",
    "full_text_markdown": "## Apple Cake\n\nThis recipe is a cross between...",
    "created_at": "2026-03-18T12:00:00Z"
}
```

### Overnight Oatmeal (no Markdown companion)

```json
{
    "id": 15,
    "name": "Overnight Oatmeal",
    "description": "This oatmeal parfait requires no cooking.",
    "ingredients": [
        {"name": "oats", "quantity": 0.67, "unit": "cups", "category": "grain"},
        {"name": "greek yogurt", "quantity": 0.67, "unit": "cups", "category": "dairy"},
        {"name": "water", "quantity": 0.67, "unit": "cups", "category": "beverage"},
        {"name": "vanilla extract", "quantity": 1.0, "unit": "teaspoons", "category": "other"}
    ],
    "instructions": ["Combine ingredients in a large mason jar.", "Cover tightly and shake.", "Set in fridge overnight.", "Enjoy!"],
    "prep_time_minutes": 5,
    "cook_time_minutes": 0,
    "servings": 2,
    "weather_temp": "warm",
    "weather_condition": "sunny",
    "tags": ["breakfast", "no-cook", "vegetarian"],
    "source": "https://www.makebetterfood.com/recipes/overnight-oatmeal/",
    "source_format": "json",
    "source_file": "overnight_oatmeal.json",
    "full_text_markdown": null,
    "created_at": "2026-03-18T12:00:00Z"
}
```

## Design Decisions

### Why JSON fields instead of separate tables?

Ingredients and instructions are always accessed together with their recipe — you'd never look up "step 3" without knowing which recipe it belongs to. Storing them as JSON inside the recipe row:
- Keeps related data together (one query gets everything)
- Avoids the complexity of junction tables and foreign keys for tightly-coupled data
- Makes it easy to preserve the exact structure from the source JSON files

The trade-off: you can't efficiently query across ingredients with SQL alone (e.g., "all recipes with garlic"). Workstream 05 addresses this by building a separate matching table that flattens ingredients out for cross-recipe queries.

### Why track source_format and source_file?

Data lineage (provenance) means knowing where each piece of data came from. If a recipe record looks wrong, `source_file` tells you exactly which JSON file to check. `source_format` confirms how the data was parsed, which matters when debugging ingestion issues.

### Why store full_text_markdown separately?

The JSON file provides clean, structured fields for querying and comparison. But original recipe pages often contain tips, variations, stories, and photos that don't fit neatly into structured fields. Storing the Markdown as-is preserves this context without polluting the structured data.

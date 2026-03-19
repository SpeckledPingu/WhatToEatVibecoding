"""
weather.py — Weather endpoints for the AUTHENTICATED WhatToEat API.

COMPARING THIS TO THE SIMPLE API (src/api/simple/routes/weather.py):
Weather endpoints are PUBLIC (no authentication required) in BOTH APIs.
Reading weather data and recommendations doesn't modify anything, so there's
no security reason to restrict access.

This means the authenticated version is IDENTICAL to the simple version —
we just reuse the same router. This is the simplest case: when an endpoint
doesn't need auth, the authenticated API looks exactly like the simple API.

WHY NOT REQUIRE AUTH?
Authentication protects WRITE operations (creating, updating, deleting data).
Weather endpoints only READ data — from an external API and from the database.
Making them public means:
  - No login friction for a read-only feature
  - Dashboard widgets can show weather without auth setup
  - Consistent with how GET endpoints work elsewhere in this API
"""

# We reuse the exact same router from the simple API since these endpoints
# are public (no auth required) in both versions. This avoids code duplication.
from src.api.simple.routes.weather import router  # noqa: F401

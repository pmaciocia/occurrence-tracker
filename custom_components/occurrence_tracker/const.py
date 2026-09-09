"""Constants for the Occurrence Tracker integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "occurrence_tracker"

SERVICE_RECORD: Final = "record"
SERVICE_REMOVE_LAST: Final = "remove_last"
SERVICE_CLEAR: Final = "clear"

ATTR_TIMESTAMP: Final = "timestamp"

# Monday-first, matching datetime.weekday().
WEEKDAY_NAMES: Final = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

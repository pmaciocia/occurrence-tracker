"""Constants for the Occurrence Tracker integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "occurrence_tracker"

CONF_STATISTIC_ID: Final = "statistic_id"

SERVICE_RECORD: Final = "record"
SERVICE_REMOVE_LAST: Final = "remove_last"
SERVICE_CLEAR: Final = "clear"
SERVICE_REBUILD_STATISTICS: Final = "rebuild_statistics"

ATTR_TIMESTAMP: Final = "timestamp"
ATTR_STATISTIC_ID: Final = "statistic_id"

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

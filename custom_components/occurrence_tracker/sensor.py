"""Sensors exposing the recorded occurrences and their distribution."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OccurrenceConfigEntry
from .const import ATTR_STATISTIC_ID, CONF_STATISTIC_ID, WEEKDAY_NAMES
from .entity import OccurrenceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OccurrenceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors for a config entry."""
    store = entry.runtime_data
    async_add_entities(
        [
            TotalSensor(entry, store),
            LastSensor(entry, store),
            ByHourSensor(entry, store),
            ByWeekdaySensor(entry, store),
        ]
    )


class TotalSensor(OccurrenceEntity, SensorEntity):
    """Running total of recorded occurrences.

    Deliberately carries no state_class. Long-term statistics for this tracker
    are written by the integration itself under the id in the ``statistic_id``
    attribute; letting the recorder compile a second series from this sensor's
    state transitions would put backfills on the wrong day and mis-count
    removals as meter resets.
    """

    _attr_name = "Total"
    _attr_icon = "mdi:counter"

    def __init__(self, entry, store) -> None:
        """Initialise the sensor."""
        super().__init__(entry, store, "total")
        self._statistic_id = entry.data.get(CONF_STATISTIC_ID)

    @property
    def native_value(self) -> int:
        """Return the number of recorded occurrences."""
        return self._store.total

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Point at the statistic that date-based charts should read."""
        return {ATTR_STATISTIC_ID: self._statistic_id}


class LastSensor(OccurrenceEntity, SensorEntity):
    """When the most recent occurrence was."""

    _attr_name = "Last"
    _attr_icon = "mdi:clock-time-eight-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry, store) -> None:
        """Initialise the sensor."""
        super().__init__(entry, store, "last")

    @property
    def native_value(self) -> datetime | None:
        """Return the most recent occurrence."""
        return self._store.last


class ByHourSensor(OccurrenceEntity, SensorEntity):
    """Distribution across the 24 hours of the day.

    The state is the busiest hour; the whole profile rides along as an
    attribute, shaped as an array of objects so a chart card can plot it
    directly.
    """

    _attr_name = "By hour"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, entry, store) -> None:
        """Initialise the sensor."""
        super().__init__(entry, store, "by_hour")

    @property
    def native_value(self) -> str | None:
        """Return the busiest hour of the day, or None with no data."""
        counts = self._store.by_hour
        if not any(counts):
            return None
        return f"{counts.index(max(counts)):02d}:00"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return the full hour-of-day profile."""
        counts = self._store.by_hour
        return {
            "profile": [
                {"hour": hour, "count": count} for hour, count in enumerate(counts)
            ],
            "counts": counts,
            "total": sum(counts),
        }


class ByWeekdaySensor(OccurrenceEntity, SensorEntity):
    """Distribution across the 7 days of the week."""

    _attr_name = "By weekday"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, entry, store) -> None:
        """Initialise the sensor."""
        super().__init__(entry, store, "by_weekday")

    @property
    def native_value(self) -> str | None:
        """Return the busiest day of the week, or None with no data."""
        counts = self._store.by_weekday
        if not any(counts):
            return None
        return WEEKDAY_NAMES[counts.index(max(counts))]

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return the full day-of-week profile, Monday first."""
        counts = self._store.by_weekday
        return {
            "profile": [
                {"day": index + 1, "name": WEEKDAY_NAMES[index], "count": count}
                for index, count in enumerate(counts)
            ],
            "counts": counts,
            "total": sum(counts),
        }

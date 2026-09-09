"""Persistent storage and bucketing for tracked occurrences.

The store keeps the raw timestamp of every occurrence rather than pre-aggregated
counters, and it keeps them for good. At the volumes this integration is built
for — a handful of events a week — the list stays tiny, and keeping the source
data means any bucketing can be recomputed later (two-hourly, weekday/weekend,
month of year) without having thrown anything away. The long-term statistics
this integration writes are a projection of this list, never a replacement for
it.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .rows import Row, build_rows, hour_floor

STORAGE_VERSION = 2
STORAGE_KEY_FORMAT = "occurrence_tracker.{}"


class StatisticsSink(Protocol):
    """What the store needs from whatever mirrors it into long-term statistics."""

    def async_write_from(self, rows: list[Row], hour: datetime) -> None:
        """Rewrite rows at or after ``hour``."""

    def async_rebuild(self, rows: list[Row]) -> None:
        """Clear and rewrite the whole series."""


class _OccurrenceStorage(Store[dict[str, Any]]):
    """The on-disk format, with migration from the v1 layout."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert v1's ISO-8601 strings to v2's epoch seconds.

        Floats keep the sub-second precision the strings carried, at roughly
        half the bytes and none of the string parsing on load.
        """
        if old_major_version == 1:
            converted: list[float] = []
            for raw in old_data.get("occurrences", []):
                when = dt_util.parse_datetime(raw) if isinstance(raw, str) else None
                if when is not None:
                    converted.append(dt_util.as_utc(when).timestamp())
            return {"occurrences": converted}
        return old_data


class OccurrenceStore:
    """Holds the occurrence timestamps for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialise the store for a config entry."""
        self._hass = hass
        self._store = _OccurrenceStorage(
            hass, STORAGE_VERSION, STORAGE_KEY_FORMAT.format(entry_id)
        )
        self._occurrences: list[datetime] = []
        self._listeners: list[Callable[[], None]] = []
        self.statistics: StatisticsSink | None = None

        # Derived views, recomputed lazily and dropped on every mutation. Each
        # is a full pass over the list; without the cache, one recorded press
        # would cost four such passes across the two profile sensors.
        self._rows: list[Row] | None = None
        self._by_hour: list[int] | None = None
        self._by_weekday: list[int] | None = None

    async def async_load(self) -> None:
        """Read the stored occurrences from disk."""
        data = await self._store.async_load() or {}
        parsed: list[datetime] = []
        for raw in data.get("occurrences", []):
            if isinstance(raw, (int, float)):
                parsed.append(dt_util.utc_from_timestamp(float(raw)))
        self._occurrences = sorted(parsed)
        self._invalidate()

    async def async_remove(self) -> None:
        """Delete the stored data entirely (config entry removal)."""
        await self._store.async_remove()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"occurrences": [when.timestamp() for when in self._occurrences]}
        )

    @callback
    def _invalidate(self) -> None:
        self._rows = None
        self._by_hour = None
        self._by_weekday = None

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Register an entity to be told when the occurrences change."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    @callback
    def _async_notify_listeners(self) -> None:
        for update_callback in self._listeners:
            update_callback()

    async def async_record(self, when: datetime | None = None) -> None:
        """Record one occurrence, defaulting to now.

        Timestamps are normalised to UTC on the way in. A naive datetime — which
        is what a service call passing a bare "2026-09-01 14:30:00" produces — is
        read as local time by dt_util.as_utc, which is what someone hand-entering
        a past occurrence means by it.
        """
        when = dt_util.utcnow() if when is None else dt_util.as_utc(when)
        bisect.insort(self._occurrences, when)
        self._invalidate()
        await self._async_save()
        if self.statistics is not None:
            self.statistics.async_write_from(self.rows, hour_floor(when))
        self._async_notify_listeners()

    async def async_remove_last(self) -> bool:
        """Drop the most recent occurrence. Returns False if there was none."""
        if not self._occurrences:
            return False
        self._occurrences.pop()
        self._invalidate()
        await self._async_save()
        if self.statistics is not None:
            self.statistics.async_rebuild(self.rows)
        self._async_notify_listeners()
        return True

    async def async_clear(self) -> None:
        """Forget every recorded occurrence."""
        self._occurrences = []
        self._invalidate()
        await self._async_save()
        if self.statistics is not None:
            self.statistics.async_rebuild(self.rows)
        self._async_notify_listeners()

    @callback
    def async_rebuild_statistics(self) -> None:
        """Force the statistics series back into line with the timestamps."""
        if self.statistics is not None:
            self.statistics.async_rebuild(self.rows)

    @property
    def total(self) -> int:
        """How many occurrences have been recorded."""
        return len(self._occurrences)

    @property
    def last(self) -> datetime | None:
        """The most recent occurrence, or None."""
        return self._occurrences[-1] if self._occurrences else None

    @property
    def rows(self) -> list[Row]:
        """The sparse statistics rows for the whole history."""
        if self._rows is None:
            self._rows = build_rows(self._occurrences)
        return self._rows

    @property
    def by_hour(self) -> list[int]:
        """Occurrence count per hour of day (0-23), in local time."""
        if self._by_hour is None:
            counts = [0] * 24
            for when in self._occurrences:
                counts[dt_util.as_local(when).hour] += 1
            self._by_hour = counts
        return self._by_hour

    @property
    def by_weekday(self) -> list[int]:
        """Occurrence count per day of week (Monday first), in local time."""
        if self._by_weekday is None:
            counts = [0] * 7
            for when in self._occurrences:
                counts[dt_util.as_local(when).weekday()] += 1
            self._by_weekday = counts
        return self._by_weekday

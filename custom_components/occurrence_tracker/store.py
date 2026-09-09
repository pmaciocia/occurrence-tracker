"""Persistent storage and bucketing for tracked occurrences.

The store keeps the raw timestamp of every occurrence rather than pre-aggregated
counters. At the volumes this integration is built for — a handful of events a
week — the list stays tiny, and keeping the source data means any bucketing can
be recomputed later (two-hourly, weekday/weekend, month of year) without having
thrown anything away.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

STORAGE_VERSION = 1
STORAGE_KEY_FORMAT = "occurrence_tracker.{}"


class OccurrenceStore:
    """Holds the occurrence timestamps for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialise the store for a config entry."""
        self._hass = hass
        self._store: Store[dict] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY_FORMAT.format(entry_id)
        )
        self._occurrences: list[datetime] = []
        self._listeners: list[Callable[[], None]] = []

    async def async_load(self) -> None:
        """Read the stored occurrences from disk."""
        data = await self._store.async_load() or {}
        parsed: list[datetime] = []
        for raw in data.get("occurrences", []):
            when = dt_util.parse_datetime(raw)
            if when is not None:
                parsed.append(dt_util.as_utc(when))
        self._occurrences = sorted(parsed)

    async def async_remove(self) -> None:
        """Delete the stored data entirely (config entry removal)."""
        await self._store.async_remove()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"occurrences": [when.isoformat() for when in self._occurrences]}
        )

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

        self._occurrences.append(when)
        self._occurrences.sort()
        await self._async_save()
        self._async_notify_listeners()

    async def async_remove_last(self) -> bool:
        """Drop the most recent occurrence. Returns False if there was none."""
        if not self._occurrences:
            return False
        self._occurrences.pop()
        await self._async_save()
        self._async_notify_listeners()
        return True

    async def async_clear(self) -> None:
        """Forget every recorded occurrence."""
        self._occurrences = []
        await self._async_save()
        self._async_notify_listeners()

    @property
    def total(self) -> int:
        """How many occurrences have been recorded."""
        return len(self._occurrences)

    @property
    def last(self) -> datetime | None:
        """The most recent occurrence, or None."""
        return self._occurrences[-1] if self._occurrences else None

    @property
    def by_hour(self) -> list[int]:
        """Occurrence count per hour of day (0-23), in local time."""
        counts = [0] * 24
        for when in self._occurrences:
            counts[dt_util.as_local(when).hour] += 1
        return counts

    @property
    def by_weekday(self) -> list[int]:
        """Occurrence count per day of week (Monday first), in local time."""
        counts = [0] * 7
        for when in self._occurrences:
            counts[dt_util.as_local(when).weekday()] += 1
        return counts

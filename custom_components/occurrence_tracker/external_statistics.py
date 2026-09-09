"""Writes the occurrence history into Home Assistant's long-term statistics.

Why external statistics rather than a ``total_increasing`` sensor: the recorder
compiles a sensor's statistics from its *state transitions*, and it cannot know
what a transition means. A backfilled occurrence changes the sensor's state now,
so the recorder books it now — on the wrong day. And ``total_increasing`` reads
any drop below 90% of the previous value as a meter reset and starts a fresh
cycle, so removing an occurrence never subtracts it and can double-count.

An external statistic (``occurrence_tracker:<name>``) has no sensor behind it.
The integration owns its rows outright and writes them from the stored
timestamps, so a backfill lands on the hour it happened and a removal is a
genuine correction.
"""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .rows import Row, rows_from

_LOGGER = logging.getLogger(__name__)


class OccurrenceStatistics:
    """The statistics sink for one tracker."""

    def __init__(self, hass: HomeAssistant, statistic_id: str, name: str) -> None:
        """Initialise the sink for a statistic id."""
        self._hass = hass
        self.statistic_id = statistic_id
        self._name = name

    def _metadata(self) -> StatisticMetaData:
        return StatisticMetaData(
            statistic_id=self.statistic_id,
            source=DOMAIN,
            name=self._name,
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            unit_of_measurement=None,
            unit_class=None,
        )

    @staticmethod
    def _to_data(rows: list[Row]) -> list[StatisticData]:
        # ``state`` mirrors the running total by convention (energy importers
        # put the meter reading there); ``sum`` is what the counts derive from.
        return [
            StatisticData(start=hour, state=float(total), sum=float(total))
            for hour, total in rows
        ]

    @callback
    def async_write_from(self, rows: list[Row], hour: datetime) -> None:
        """Rewrite every row at or after ``hour``.

        The normal path for a new occurrence: one row for a press now, or a
        stretch of rows for a backfill. Rows are upserted, so nothing older is
        touched.
        """
        affected = rows_from(rows, hour)
        if not affected:
            return
        async_add_external_statistics(self._hass, self._metadata(), self._to_data(affected))
        _LOGGER.debug("%s: wrote %d row(s) from %s", self.statistic_id, len(affected), hour)

    @callback
    def async_rebuild(self, rows: list[Row]) -> None:
        """Clear the series and write it in full.

        Upserts cannot delete, so any edit that can empty an hour — a removal —
        rebuilds from scratch. The clear and the import queue on the recorder in
        order, so there is no window where a reader sees half of each.
        """
        get_instance(self._hass).async_clear_statistics([self.statistic_id])
        if rows:
            async_add_external_statistics(self._hass, self._metadata(), self._to_data(rows))
        _LOGGER.debug("%s: rebuilt %d row(s)", self.statistic_id, len(rows))

    @callback
    def async_remove(self) -> None:
        """Delete the series entirely (config entry removal)."""
        get_instance(self._hass).async_clear_statistics([self.statistic_id])

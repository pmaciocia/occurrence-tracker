"""The Occurrence Tracker integration.

Records the times at which a recurring-but-rare event happens, and exposes the
resulting distribution across hour of day and day of week. Home Assistant's own
statistics can tell you how many times something happened in a window; nothing
in core folds those occurrences back onto a 24-hour or 7-day cycle, which is
what this integration is for.

The stored timestamps are the source of truth. They are also mirrored into a
long-term statistic (``occurrence_tracker:<name>``) so date-based charts can
read them, but that series is a projection: it is rebuilt from the timestamps,
never the other way round.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_STATISTIC_ID, DOMAIN
from .external_statistics import OccurrenceStatistics
from .rows import statistic_object_id
from .store import OccurrenceStore

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]

type OccurrenceConfigEntry = ConfigEntry[OccurrenceStore]


def _allocate_statistic_id(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Pick a statistic id from the entry title, avoiding other entries' ids.

    Fixed once and persisted on the entry, so renaming the tracker later never
    orphans its rows.
    """
    taken = {
        other.data.get(CONF_STATISTIC_ID)
        for other in hass.config_entries.async_entries(DOMAIN)
        if other.entry_id != entry.entry_id
    }
    base = f"{DOMAIN}:{statistic_object_id(entry.title)}"
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


async def async_setup_entry(hass: HomeAssistant, entry: OccurrenceConfigEntry) -> bool:
    """Set up an occurrence tracker from a config entry."""
    store = OccurrenceStore(hass, entry.entry_id)
    await store.async_load()

    statistic_id = entry.data.get(CONF_STATISTIC_ID)
    first_statistics_run = statistic_id is None
    if first_statistics_run:
        statistic_id = _allocate_statistic_id(hass, entry)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_STATISTIC_ID: statistic_id}
        )

    store.statistics = OccurrenceStatistics(hass, statistic_id, entry.title)
    if first_statistics_run:
        # Either a brand-new tracker (nothing to write) or an upgrade from a
        # version that kept timestamps but wrote no statistics: put every
        # existing occurrence onto the hour it happened.
        store.async_rebuild_statistics()

    entry.runtime_data = store
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OccurrenceConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the recorded occurrences and their statistics with the entry.

    Without this the stored timestamps would outlive the entry, orphaned in
    .storage, and the statistics rows would linger in the recorder forever.
    """
    await OccurrenceStore(hass, entry.entry_id).async_remove()
    if statistic_id := entry.data.get(CONF_STATISTIC_ID):
        OccurrenceStatistics(hass, statistic_id, entry.title).async_remove()

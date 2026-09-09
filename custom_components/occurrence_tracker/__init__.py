"""The Occurrence Tracker integration.

Records the times at which a recurring-but-rare event happens, and exposes the
resulting distribution across hour of day and day of week. Home Assistant's own
statistics can tell you how many times something happened in a window; nothing
in core folds those occurrences back onto a 24-hour or 7-day cycle, which is
what this integration is for.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .store import OccurrenceStore

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]

type OccurrenceConfigEntry = ConfigEntry[OccurrenceStore]


async def async_setup_entry(hass: HomeAssistant, entry: OccurrenceConfigEntry) -> bool:
    """Set up an occurrence tracker from a config entry."""
    store = OccurrenceStore(hass, entry.entry_id)
    await store.async_load()
    entry.runtime_data = store

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OccurrenceConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the recorded occurrences when the entry is deleted.

    Without this the stored timestamps would outlive the entry and be orphaned
    in .storage forever.
    """
    await OccurrenceStore(hass, entry.entry_id).async_remove()

"""Shared entity base for the Occurrence Tracker integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .store import OccurrenceStore


class OccurrenceEntity(Entity):
    """Base class: names itself off the device and follows the store."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, store: OccurrenceStore, key: str) -> None:
        """Initialise the entity."""
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Re-render whenever an occurrence is recorded or removed."""
        await super().async_added_to_hass()
        self.async_on_remove(self._store.async_add_listener(self.async_write_ha_state))

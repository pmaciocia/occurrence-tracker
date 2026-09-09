"""The button that records an occurrence, plus the entity services."""

from __future__ import annotations

from datetime import datetime

import voluptuous as vol

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OccurrenceConfigEntry
from .const import ATTR_TIMESTAMP, SERVICE_CLEAR, SERVICE_RECORD, SERVICE_REMOVE_LAST
from .entity import OccurrenceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OccurrenceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the record button and register the entity services."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RECORD,
        {vol.Optional(ATTR_TIMESTAMP): cv.datetime},
        "async_service_record",
    )
    platform.async_register_entity_service(
        SERVICE_REMOVE_LAST, None, "async_service_remove_last"
    )
    platform.async_register_entity_service(SERVICE_CLEAR, None, "async_service_clear")

    async_add_entities([RecordButton(entry, entry.runtime_data)])


class RecordButton(OccurrenceEntity, ButtonEntity):
    """Press to record that the tracked thing just happened."""

    _attr_name = "Record"
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, entry, store) -> None:
        """Initialise the button."""
        super().__init__(entry, store, "record")

    async def async_press(self) -> None:
        """Record an occurrence at the current time."""
        await self._store.async_record()

    async def async_service_record(self, timestamp: datetime | None = None) -> None:
        """Record an occurrence, optionally at a given past time.

        This is the backfill path: it lets a remembered occurrence be entered
        after the fact, and it lands in the right hour and weekday bucket.
        """
        await self._store.async_record(timestamp)

    async def async_service_remove_last(self) -> None:
        """Undo the most recent recorded occurrence."""
        await self._store.async_remove_last()

    async def async_service_clear(self) -> None:
        """Forget every recorded occurrence."""
        await self._store.async_clear()

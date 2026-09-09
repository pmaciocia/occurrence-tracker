"""Config flow for the Occurrence Tracker integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
)


class OccurrenceTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for a name and create the entry. There is nothing else to configure."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data={})

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA
        )

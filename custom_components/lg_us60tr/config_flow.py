from __future__ import annotations

import logging
import re
from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import (
    CONF_LAST_INPUT_SOURCE,
    CONF_POWERED,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import probe_soundbar

_LOGGER = logging.getLogger(__name__)


class LGUS60TRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure an LG soundbar through the Home Assistant UI."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        address: str | None = None

        if user_input is not None:
            try:
                address = _normalize_address(user_input[CONF_ADDRESS])
            except ValueError:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                _LOGGER.debug("Validating RFCOMM access to soundbar %s", address)
                try:
                    state = await self.hass.async_add_executor_job(
                        probe_soundbar, address
                    )
                except (OSError, TimeoutError) as error:
                    _LOGGER.warning(
                        "Unable to connect to soundbar %s: %s", address, error
                    )
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error while connecting to %s", address
                    )
                    errors["base"] = "unknown"
                else:
                    _LOGGER.info("Validated soundbar %s during config flow", address)
                    await self.async_set_unique_id(address.replace(":", "").lower())
                    self._abort_if_unique_id_configured()
                    options: dict[str, Any] = {CONF_POWERED: True}
                    if state.input_source is not None:
                        options[CONF_LAST_INPUT_SOURCE] = int(state.input_source)
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data={CONF_ADDRESS: address},
                        options=options,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=address or (user_input or {}).get(CONF_ADDRESS, ""),
                    ): str,
                }
            ),
            errors=errors,
        )


def _normalize_address(value: str) -> str:
    compact = value.strip().replace(":", "").replace("-", "")
    if re.fullmatch(r"[0-9A-Fa-f]{12}", compact) is None:
        raise ValueError("invalid Bluetooth address")
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2)).upper()

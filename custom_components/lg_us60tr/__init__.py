from __future__ import annotations

import logging
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import LGUS60TRCoordinator

_LOGGER = logging.getLogger(__name__)

LGUS60TRConfigEntry: TypeAlias = ConfigEntry[LGUS60TRCoordinator]

PLATFORMS = (Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SWITCH)


async def async_setup_entry(hass: HomeAssistant, entry: LGUS60TRConfigEntry) -> bool:
    """Set up an LG soundbar from a config entry."""
    _LOGGER.info("Setting up LG US60TR integration entry %s", entry.entry_id)
    coordinator = LGUS60TRCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("LG US60TR integration entry %s is ready", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LGUS60TRConfigEntry) -> bool:
    """Unload an LG soundbar config entry."""
    _LOGGER.info("Unloading LG US60TR integration entry %s", entry.entry_id)
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_shutdown()
    _LOGGER.info("LG US60TR integration entry %s unloaded", entry.entry_id)
    return True

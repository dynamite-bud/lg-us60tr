from __future__ import annotations

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LGUS60TRConfigEntry
from .entity import LGUS60TREntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LGUS60TRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the soundbar switch entities."""
    async_add_entities([LGUS60TRNightModeSwitch(entry)])


class LGUS60TRNightModeSwitch(LGUS60TREntity, SwitchEntity):
    """Control night mode."""

    _attr_translation_key = "night_mode"

    def __init__(self, entry: LGUS60TRConfigEntry) -> None:
        super().__init__(entry, "night_mode")

    @property
    @override
    def is_on(self) -> bool | None:
        return self.coordinator.data.night_mode

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_night_mode(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_night_mode(False)

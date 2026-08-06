from __future__ import annotations

from typing import override

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LGUS60TRConfigEntry
from .entity import LGUS60TREntity

NUMBER_DESCRIPTIONS = (
    NumberEntityDescription(
        key="woofer_level",
        translation_key="woofer_level",
        native_min_value=-15,
        native_max_value=6,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="center_level",
        translation_key="center_level",
        native_min_value=-6,
        native_max_value=6,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="rear_level",
        translation_key="rear_level",
        native_min_value=-6,
        native_max_value=6,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LGUS60TRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up soundbar channel-level entities."""
    async_add_entities(
        LGUS60TRLevelNumber(entry, description) for description in NUMBER_DESCRIPTIONS
    )


class LGUS60TRLevelNumber(LGUS60TREntity, NumberEntity):
    """Represent one bounded channel level."""

    entity_description: NumberEntityDescription

    def __init__(
        self,
        entry: LGUS60TRConfigEntry,
        description: NumberEntityDescription,
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        return getattr(self.coordinator.data, self.entity_description.key)

    @override
    async def async_set_native_value(self, value: float) -> None:
        setter = getattr(self.coordinator, f"async_set_{self.entity_description.key}")
        await setter(round(value))

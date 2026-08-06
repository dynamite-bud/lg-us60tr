from __future__ import annotations

from typing import ClassVar, override

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LGUS60TRConfigEntry
from .core import InputSource
from .entity import LGUS60TREntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LGUS60TRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the soundbar media player entity."""
    async_add_entities([LGUS60TRMediaPlayer(entry)])


class LGUS60TRMediaPlayer(LGUS60TREntity, MediaPlayerEntity):
    """Represent the soundbar's primary controls."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_source_list: ClassVar[list[str]] = [source.label for source in InputSource]
    _attr_volume_step = 0.01

    def __init__(self, entry: LGUS60TRConfigEntry) -> None:
        super().__init__(entry, "media_player")

    @property
    @override
    def state(self) -> MediaPlayerState:
        """Return the soundbar state while its control channel is connected."""
        return MediaPlayerState.ON

    @property
    @override
    def volume_level(self) -> float | None:
        volume = self.coordinator.data.volume
        return volume / 100 if volume is not None else None

    @property
    @override
    def source(self) -> str | None:
        source = self.coordinator.data.input_source
        return source.label if source is not None else None

    @property
    @override
    def sound_mode(self) -> str | None:
        mode = self.coordinator.data.sound_mode
        return mode.label if mode is not None else None

    @property
    @override
    def sound_mode_list(self) -> list[str]:
        return [mode.label for mode in self.coordinator.data.available_modes]

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        level = round(max(0.0, min(1.0, volume)) * 100)
        await self.coordinator.async_set_volume(level)

    @override
    async def async_select_source(self, source: str) -> None:
        await self.coordinator.async_set_input_source(source)

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        await self.coordinator.async_set_sound_mode(sound_mode)

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class InputSource(IntEnum):
    BLUETOOTH = 0x07
    USB = 0x40
    HDMI_IN = 0xC0
    OPTICAL_HDMI_ARC = 0xDF

    @property
    def label(self) -> str:
        return _INPUT_SOURCE_LABELS[self]

    @classmethod
    def from_name(cls, value: str) -> InputSource:
        normalized = " ".join(value.replace("_", " ").replace("-", " ").lower().split())
        for source, label in _INPUT_SOURCE_LABELS.items():
            if normalized in {
                source.name.lower().replace("_", " "),
                label.lower(),
            }:
                return source
        raise ValueError(
            f"unknown input source {value!r}; expected one of: "
            f"{', '.join(_INPUT_SOURCE_LABELS.values())}"
        )

    @classmethod
    def from_active_prefix(cls, prefix: int) -> InputSource | None:
        return _INPUT_SOURCE_BY_ACTIVE_PREFIX.get(prefix)


_INPUT_SOURCE_LABELS = {
    InputSource.BLUETOOTH: "Bluetooth",
    InputSource.USB: "USB",
    InputSource.HDMI_IN: "HDMI In",
    InputSource.OPTICAL_HDMI_ARC: "Optical / HDMI ARC",
}

_INPUT_SOURCE_BY_ACTIVE_PREFIX = {
    0x07: InputSource.BLUETOOTH,
    0x40: InputSource.USB,
    0xC0: InputSource.HDMI_IN,
    0xD0: InputSource.OPTICAL_HDMI_ARC,
}


class SoundMode(IntEnum):
    AI_SOUND_PRO = 0x90
    STANDARD = 0x02
    CINEMA = 0x55
    CLEAR_VOICE_PRO = 0x97
    SPORTS = 0x92
    MUSIC = 0x38
    GAME = 0x54
    BASS_BLAST = 0x37

    @property
    def label(self) -> str:
        return _SOUND_MODE_LABELS[self]

    @classmethod
    def from_name(cls, value: str) -> SoundMode:
        normalized = " ".join(value.replace("_", " ").replace("-", " ").lower().split())
        for mode, label in _SOUND_MODE_LABELS.items():
            if normalized in {label.lower(), mode.name.replace("_", " ").lower()}:
                return mode
        choices = ", ".join(mode.label for mode in cls)
        raise ValueError(f"unknown sound mode {value!r}; expected one of: {choices}")


_SOUND_MODE_LABELS = {
    SoundMode.AI_SOUND_PRO: "AI Sound Pro",
    SoundMode.STANDARD: "Standard",
    SoundMode.CINEMA: "Cinema",
    SoundMode.CLEAR_VOICE_PRO: "Clear Voice Pro",
    SoundMode.SPORTS: "Sports",
    SoundMode.MUSIC: "Music",
    SoundMode.GAME: "Game",
    SoundMode.BASS_BLAST: "Bass Blast",
}

SOUND_MODES_BY_DISPLAY_NAME = {mode.label.upper(): mode for mode in SoundMode}


@dataclass(frozen=True, slots=True)
class SoundbarState:
    connected: bool = False
    input_source: InputSource | None = None
    volume: int | None = None
    sound_mode: SoundMode | None = None
    woofer_level: int | None = None
    woofer_min: int = -15
    woofer_max: int = 6
    center_level: int | None = None
    center_min: int = -6
    center_max: int = 6
    rear_level: int | None = None
    rear_min: int = -6
    rear_max: int = 6
    night_mode: bool | None = None
    sound_mode_name: str | None = None
    control_prefix: int | None = None
    active_prefix: int | None = None
    available_modes: tuple[SoundMode, ...] = tuple(SoundMode)

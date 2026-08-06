from __future__ import annotations

from .protocol import Frame
from .state import InputSource, SoundMode

HANDSHAKE_START = Frame(0x00, 0x15)
INITIAL_CAPABILITY_QUERY = Frame(0x0D, 0x24, b"\x04")
HANDSHAKE_STAGE = Frame(0x00, 0x16)
SOUND_MODE_REGISTRATION = Frame(0x00, 0x17, b"\x1f")
PREFIX_QUERY = Frame(0x00, 0x0B)
SESSION_READY = Frame(0x00, 0x19)
POWER_OFF = Frame(0x00, 0x0A, b"\x00")
CONTROL_PREFIX = 0x07


def snapshot_query(prefix: int) -> Frame:
    return Frame(prefix, 0x03)


def input_source_command(source: InputSource) -> Frame:
    return Frame(0x00, 0x01, bytes((int(source),)))


def volume_command(prefix: int, volume: int) -> Frame:
    return Frame(prefix, 0x02, bytes((0x64, volume)))


def sound_mode_command(prefix: int, mode: SoundMode) -> Frame:
    return Frame(prefix, 0x1F, bytes((0x00, int(mode))))


def woofer_command(level: int | None = None) -> Frame:
    payload = b"" if level is None else int(level).to_bytes(1, "big", signed=True)
    return Frame(0x0D, 0x1B, payload)


def center_level_command(level: int | None = None) -> Frame:
    payload = b"" if level is None else int(level).to_bytes(1, "big", signed=True)
    return Frame(0x0D, 0x26, payload)


def rear_level_command(level: int | None = None) -> Frame:
    payload = b"" if level is None else int(level).to_bytes(1, "big", signed=True)
    return Frame(0x0D, 0x21, payload)


def night_mode_command(prefix: int, enabled: bool | None = None) -> Frame:
    payload = b"" if enabled is None else bytes((int(enabled),))
    return Frame(prefix, 0x4A, payload)

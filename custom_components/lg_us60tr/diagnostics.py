from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import LGUS60TRConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LGUS60TRConfigEntry
) -> dict[str, Any]:
    """Return privacy-safe diagnostics for one soundbar."""
    state = entry.runtime_data.data
    state_data = asdict(state) if state is not None else None
    if state_data is not None:
        state_data["input_source"] = (
            state.input_source.label if state.input_source is not None else None
        )
        state_data["sound_mode"] = (
            state.sound_mode.label if state.sound_mode is not None else None
        )
        state_data["available_modes"] = [mode.label for mode in state.available_modes]

    return {
        "entry": async_redact_data(dict(entry.data), {CONF_ADDRESS}),
        "rfcomm_channel": entry.runtime_data.channel,
        "state": state_data,
    }

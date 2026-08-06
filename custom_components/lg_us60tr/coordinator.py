from __future__ import annotations

import logging
import threading
from functools import partial
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_TIMEOUT,
    CONNECT_TIMEOUT,
    DEFAULT_CHANNELS,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .core import InputSource, SoundbarClient, SoundbarState, SoundMode
from .core.linux import LinuxRFCOMMTransport

_LOGGER = logging.getLogger(__name__)


class LGUS60TRCoordinator(DataUpdateCoordinator[SoundbarState]):
    """Own the soundbar connection and serialize its blocking SPP operations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.address: str = entry.data[CONF_ADDRESS]
        self._io_lock = threading.Lock()
        self._shutting_down = False
        self._client = SoundbarClient(
            LinuxRFCOMMTransport(self.address, DEFAULT_CHANNELS),
            listener=self._state_received,
        )
        _LOGGER.debug(
            "Created coordinator for %s with RFCOMM channels %s",
            self.address,
            DEFAULT_CHANNELS,
        )

    @property
    def channel(self) -> int | None:
        """Return the active RFCOMM channel."""
        return self._client.channel

    async def _async_update_data(self) -> SoundbarState:
        _LOGGER.debug("Refreshing soundbar state")
        previous_source = self.data.input_source if self.data is not None else None
        try:
            return await self.hass.async_add_executor_job(
                self._refresh, previous_source
            )
        except (OSError, TimeoutError) as error:
            _LOGGER.warning("Soundbar refresh failed: %s", error, exc_info=True)
            raise UpdateFailed(
                f"Unable to communicate with {self.address}: {error}"
            ) from error

    def _refresh(self, previous_source: InputSource | None = None) -> SoundbarState:
        with self._io_lock:
            try:
                if self._client.state.connected:
                    _LOGGER.debug("Querying state on the existing RFCOMM connection")
                    return self._client.query_state(timeout=COMMAND_TIMEOUT)
                _LOGGER.info("Opening RFCOMM connection to soundbar %s", self.address)
                return self._connect(previous_source)
            except (OSError, TimeoutError):
                _LOGGER.debug("Closing failed RFCOMM session", exc_info=True)
                self._client.close()
                raise

    async def async_set_volume(self, volume: int) -> None:
        await self._async_command("set_volume", volume)

    async def async_set_input_source(self, source: InputSource | str) -> None:
        await self._async_command("set_input_source", source)

    async def async_set_sound_mode(self, mode: SoundMode | str) -> None:
        await self._async_command("set_sound_mode", mode)

    async def async_set_woofer_level(self, level: int) -> None:
        await self._async_command("set_woofer_level", level)

    async def async_set_center_level(self, level: int) -> None:
        await self._async_command("set_center_level", level)

    async def async_set_rear_level(self, level: int) -> None:
        await self._async_command("set_rear_level", level)

    async def async_set_night_mode(self, enabled: bool) -> None:
        await self._async_command("set_night_mode", enabled)

    async def _async_command(self, method: str, *args: Any) -> None:
        _LOGGER.debug("Running soundbar command %s with arguments %r", method, args)
        previous_source = self.data.input_source if self.data is not None else None
        try:
            state = await self.hass.async_add_executor_job(
                partial(self._run_command, method, previous_source, *args)
            )
        except (OSError, TimeoutError) as error:
            _LOGGER.exception("Soundbar command %s failed", method)
            self.async_set_update_error(error)
            raise HomeAssistantError(
                f"Unable to send command to {self.address}: {error}"
            ) from error
        self.async_set_updated_data(state)
        _LOGGER.info("Soundbar command %s completed", method)

    def _run_command(
        self,
        method: str,
        previous_source: InputSource | None,
        *args: Any,
    ) -> SoundbarState:
        with self._io_lock:
            try:
                if not self._client.state.connected:
                    restore_source = (
                        None if method == "set_input_source" else previous_source
                    )
                    self._connect(restore_source)
                command = getattr(self._client, method)
                return command(*args, timeout=COMMAND_TIMEOUT)
            except (OSError, TimeoutError):
                self._client.close()
                raise

    def _connect(self, previous_source: InputSource | None) -> SoundbarState:
        state = self._client.connect(timeout=CONNECT_TIMEOUT)
        if (
            previous_source is None
            or previous_source is InputSource.BLUETOOTH
            or state.input_source is not InputSource.BLUETOOTH
        ):
            return state
        _LOGGER.info(
            "Soundbar wake selected Bluetooth; restoring previous input %s",
            previous_source.label,
        )
        return self._client.set_input_source(
            previous_source,
            timeout=COMMAND_TIMEOUT,
        )

    def _state_received(self, state: SoundbarState) -> None:
        _LOGGER.debug("Received pushed soundbar state: %s", state)
        if not self._shutting_down:
            self.hass.loop.call_soon_threadsafe(self._async_apply_state, state)

    @callback
    def _async_apply_state(self, state: SoundbarState) -> None:
        if not self._shutting_down:
            self.async_set_updated_data(state)

    async def async_shutdown(self) -> None:
        _LOGGER.info("Shutting down LG US60TR coordinator")
        self._shutting_down = True
        await self.hass.async_add_executor_job(self._close)

    def _close(self) -> None:
        with self._io_lock:
            self._client.close()


def probe_soundbar(address: str) -> SoundbarState:
    """Connect once during config flow validation and return the initial state."""
    _LOGGER.info("Probing soundbar %s over RFCOMM", address)
    client = SoundbarClient(LinuxRFCOMMTransport(address, DEFAULT_CHANNELS))
    try:
        state = client.connect(timeout=CONNECT_TIMEOUT)
        _LOGGER.info("Soundbar %s RFCOMM probe succeeded", address)
        return state
    finally:
        client.close()

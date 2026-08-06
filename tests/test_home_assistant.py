from collections.abc import Callable
from dataclasses import replace
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_us60tr.const import DOMAIN
from custom_components.lg_us60tr.core import InputSource, SoundbarState, SoundMode
from custom_components.lg_us60tr.diagnostics import async_get_config_entry_diagnostics

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

ADDRESS = "00:11:22:33:44:55"
TEST_STATE = SoundbarState(
    connected=True,
    input_source=InputSource.HDMI_IN,
    volume=25,
    sound_mode=SoundMode.CINEMA,
    woofer_level=2,
    center_level=-4,
    rear_level=4,
    night_mode=False,
    active_prefix=0xC0,
)


class FakeSoundbarClient:
    def __init__(
        self,
        transport: object,
        *,
        listener: Callable[[SoundbarState], None] | None = None,
    ) -> None:
        del transport
        self.state = SoundbarState()
        self.channel = 2
        self.listener = listener
        self.calls: list[tuple[str, object]] = []

    def _update(self, **changes: object) -> SoundbarState:
        self.state = replace(self.state, **changes)
        if self.listener is not None:
            self.listener(self.state)
        return self.state

    def connect(self, timeout: float) -> SoundbarState:
        self.calls.append(("connect", timeout))
        self.state = TEST_STATE
        if self.listener is not None:
            self.listener(self.state)
        return self.state

    def query_state(self, timeout: float) -> SoundbarState:
        self.calls.append(("query_state", timeout))
        return self.state

    def set_volume(self, volume: int, timeout: float) -> SoundbarState:
        self.calls.append(("set_volume", volume))
        return self._update(volume=volume)

    def set_input_source(self, source: str, timeout: float) -> SoundbarState:
        self.calls.append(("set_input_source", source))
        return self._update(input_source=InputSource.from_name(source))

    def set_sound_mode(self, mode: str, timeout: float) -> SoundbarState:
        self.calls.append(("set_sound_mode", mode))
        return self._update(sound_mode=SoundMode.from_name(mode))

    def set_woofer_level(self, level: int, timeout: float) -> SoundbarState:
        self.calls.append(("set_woofer_level", level))
        return self._update(woofer_level=level)

    def set_night_mode(self, enabled: bool, timeout: float) -> SoundbarState:
        self.calls.append(("set_night_mode", enabled))
        return self._update(night_mode=enabled)

    def close(self) -> None:
        self.calls.append(("close", True))
        self.state = replace(self.state, connected=False)


async def test_entities_expose_and_dispatch_soundbar_controls(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room soundbar",
        unique_id="001122334455",
        data={CONF_ADDRESS: ADDRESS},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.lg_us60tr.coordinator.SoundbarClient",
        FakeSoundbarClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    media_player_id = "media_player.living_room_soundbar"
    woofer_id = "number.living_room_soundbar_woofer_level"
    night_mode_id = "switch.living_room_soundbar_night_mode"

    media_player = hass.states.get(media_player_id)
    assert media_player is not None
    assert media_player.state == "on"
    assert media_player.attributes["volume_level"] == 0.25
    assert media_player.attributes["source"] == "HDMI In"
    assert media_player.attributes["sound_mode"] == "Cinema"
    assert media_player.attributes["source_list"] == [
        "Bluetooth",
        "USB",
        "HDMI In",
        "Optical / HDMI ARC",
    ]

    assert hass.states.get(woofer_id).state == "2"
    assert hass.states.get("number.living_room_soundbar_center_level").state == "-4"
    assert hass.states.get("number.living_room_soundbar_rear_level").state == "4"
    assert hass.states.get(night_mode_id).state == "off"

    client = entry.runtime_data._client

    await hass.services.async_call(
        "media_player",
        "volume_set",
        {"entity_id": media_player_id, "volume_level": 0.5},
        blocking=True,
    )
    assert ("set_volume", 50) in client.calls

    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": media_player_id, "source": "USB"},
        blocking=True,
    )
    assert ("set_input_source", "USB") in client.calls

    await hass.services.async_call(
        "media_player",
        "select_sound_mode",
        {"entity_id": media_player_id, "sound_mode": "Standard"},
        blocking=True,
    )
    assert ("set_sound_mode", "Standard") in client.calls

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": woofer_id, "value": 1},
        blocking=True,
    )
    assert ("set_woofer_level", 1) in client.calls

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": night_mode_id},
        blocking=True,
    )
    assert ("set_night_mode", True) in client.calls

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"][CONF_ADDRESS] != ADDRESS
    assert diagnostics["state"]["input_source"] == "USB"
    assert diagnostics["state"]["sound_mode"] == "Standard"

    assert await hass.config_entries.async_unload(entry.entry_id)

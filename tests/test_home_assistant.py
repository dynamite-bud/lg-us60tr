from collections.abc import Callable
from dataclasses import replace
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_us60tr.const import (
    CONF_LAST_INPUT_SOURCE,
    CONF_POWERED,
    DOMAIN,
)
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
ENTRY_OPTIONS = {
    CONF_LAST_INPUT_SOURCE: int(InputSource.HDMI_IN),
    CONF_POWERED: True,
}


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
        self.connect_state = TEST_STATE

    def _update(self, **changes: object) -> SoundbarState:
        self.connect_state = replace(self.connect_state, **changes)
        self.state = replace(self.connect_state, connected=True)
        if self.listener is not None:
            self.listener(self.state)
        return self.state

    def connect(self, timeout: float) -> SoundbarState:
        self.calls.append(("connect", timeout))
        self.state = replace(self.connect_state, connected=True)
        if self.listener is not None:
            self.listener(self.state)
        return self.state

    def query_state(self, timeout: float) -> SoundbarState:
        self.calls.append(("query_state", timeout))
        return self.state

    def set_volume(self, volume: int, timeout: float) -> SoundbarState:
        self.calls.append(("set_volume", volume))
        return self._update(volume=volume)

    def set_input_source(
        self, source: InputSource | str, timeout: float
    ) -> SoundbarState:
        self.calls.append(("set_input_source", source))
        resolved = InputSource.from_name(source) if isinstance(source, str) else source
        return self._update(input_source=resolved)

    def set_sound_mode(self, mode: str, timeout: float) -> SoundbarState:
        self.calls.append(("set_sound_mode", mode))
        return self._update(sound_mode=SoundMode.from_name(mode))

    def set_woofer_level(self, level: int, timeout: float) -> SoundbarState:
        self.calls.append(("set_woofer_level", level))
        return self._update(woofer_level=level)

    def set_night_mode(self, enabled: bool, timeout: float) -> SoundbarState:
        self.calls.append(("set_night_mode", enabled))
        return self._update(night_mode=enabled)

    def power_off(self, timeout: float) -> SoundbarState:
        self.calls.append(("power_off", timeout))
        return self.state

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
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.lg_us60tr.coordinator.SoundbarClient",
        FakeSoundbarClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    coordinator = entry.runtime_data
    client = coordinator._client
    assert client.calls == []
    assert coordinator.update_interval is None

    await coordinator.async_refresh()
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


async def test_reconnect_restores_input_selected_before_soundbar_wake(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room soundbar",
        unique_id="001122334455",
        data={CONF_ADDRESS: ADDRESS},
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.lg_us60tr.coordinator.SoundbarClient",
        FakeSoundbarClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    client = coordinator._client
    client.connect_state = replace(
        TEST_STATE,
        input_source=InputSource.BLUETOOTH,
        active_prefix=0x07,
    )
    client.state = replace(client.state, connected=False)

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert client.calls[-3:] == [
        ("connect", 8.0),
        ("set_input_source", InputSource.HDMI_IN),
        ("close", True),
    ]
    assert coordinator.data.input_source is InputSource.HDMI_IN
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_command_wake_restores_input_before_applying_control(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room soundbar",
        unique_id="001122334455",
        data={CONF_ADDRESS: ADDRESS},
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.lg_us60tr.coordinator.SoundbarClient",
        FakeSoundbarClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    client = coordinator._client
    client.connect_state = replace(
        TEST_STATE,
        input_source=InputSource.BLUETOOTH,
        active_prefix=0x07,
    )
    client.state = replace(client.state, connected=False)

    await coordinator.async_set_volume(25)

    assert client.calls[-4:] == [
        ("connect", 8.0),
        ("set_input_source", InputSource.HDMI_IN),
        ("set_volume", 25),
        ("close", True),
    ]
    assert coordinator.data.input_source is InputSource.HDMI_IN
    assert coordinator.data.volume == 25
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_explicit_source_command_skips_wake_restoration(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room soundbar",
        unique_id="001122334455",
        data={CONF_ADDRESS: ADDRESS},
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.lg_us60tr.coordinator.SoundbarClient",
        FakeSoundbarClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    client = coordinator._client
    client.connect_state = replace(
        TEST_STATE,
        input_source=InputSource.BLUETOOTH,
        active_prefix=0x07,
    )
    client.state = replace(client.state, connected=False)

    await coordinator.async_set_input_source("USB")

    assert client.calls[-3:] == [
        ("connect", 8.0),
        ("set_input_source", "USB"),
        ("close", True),
    ]
    assert coordinator.data.input_source is InputSource.USB
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_power_controls_are_on_demand_and_release_phone(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room soundbar",
        unique_id="001122334455",
        data={CONF_ADDRESS: ADDRESS},
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.lg_us60tr.coordinator.SoundbarClient",
        FakeSoundbarClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    client = coordinator._client
    media_player_id = "media_player.living_room_soundbar"

    await hass.services.async_call(
        "media_player",
        "turn_off",
        {"entity_id": media_player_id},
        blocking=True,
    )

    assert client.calls == [
        ("connect", 8.0),
        ("power_off", 3.0),
        ("close", True),
    ]
    assert coordinator.powered is False
    assert hass.states.get(media_player_id).state == "off"
    assert entry.options[CONF_POWERED] is False
    assert entry.options[CONF_LAST_INPUT_SOURCE] == int(InputSource.HDMI_IN)

    calls_after_power_off = list(client.calls)
    await coordinator.async_power_off()
    assert client.calls == calls_after_power_off

    client.connect_state = replace(
        TEST_STATE,
        input_source=InputSource.BLUETOOTH,
        active_prefix=0x07,
    )
    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": media_player_id},
        blocking=True,
    )

    assert client.calls[-3:] == [
        ("connect", 8.0),
        ("set_input_source", InputSource.HDMI_IN),
        ("close", True),
    ]
    assert coordinator.powered is True
    assert coordinator.data.input_source is InputSource.HDMI_IN
    assert hass.states.get(media_player_id).state == "on"
    assert entry.options[CONF_POWERED] is True
    assert await hass.config_entries.async_unload(entry.entry_id)

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.lg_us60tr.const import (
    CONF_LAST_INPUT_SOURCE,
    CONF_POWERED,
    DEFAULT_NAME,
    DOMAIN,
)
from custom_components.lg_us60tr.core import InputSource, SoundbarState

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_user_flow_creates_normalized_entry(hass: HomeAssistant) -> None:
    with (
        patch(
            "custom_components.lg_us60tr.config_flow.probe_soundbar",
            return_value=SoundbarState(
                connected=True,
                input_source=InputSource.HDMI_IN,
            ),
        ),
        patch(
            "custom_components.lg_us60tr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: "00-11-22-33-44-55"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {CONF_ADDRESS: "00:11:22:33:44:55"}
    assert result["result"].unique_id == "001122334455"
    assert result["result"].options == {
        CONF_LAST_INPUT_SOURCE: int(InputSource.HDMI_IN),
        CONF_POWERED: True,
    }


async def test_user_flow_rejects_invalid_address(hass: HomeAssistant) -> None:
    with patch("custom_components.lg_us60tr.config_flow.probe_soundbar") as probe:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: "not-a-bluetooth-address"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ADDRESS: "invalid_address"}
    probe.assert_not_called()


async def test_user_flow_retries_after_connection_failure(hass: HomeAssistant) -> None:
    with (
        patch(
            "custom_components.lg_us60tr.config_flow.probe_soundbar",
            side_effect=[
                OSError("RFCOMM unavailable"),
                SoundbarState(connected=True),
            ],
        ),
        patch(
            "custom_components.lg_us60tr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        flow_id = result["flow_id"]
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_ADDRESS: "00:11:22:33:44:55"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_ADDRESS: "68:52:10:77:2C:D1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: "68:52:10:77:2C:D1"}
    assert result["result"].options == {CONF_POWERED: True}

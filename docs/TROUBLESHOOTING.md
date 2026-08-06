# Deployment and troubleshooting

## Installation checklist

1. Install the repository through HACS or copy `custom_components/lg_us60tr` manually.
2. Restart Home Assistant.
3. Pair and trust the soundbar in the host's BlueZ database.
4. Restore the soundbar to the desired HDMI/ARC input after initial pairing.
5. Add **LG US60TR Soundbar** from **Settings → Devices & services** using its Bluetooth address.

The config flow performs a real RFCOMM probe. A successful form submission therefore proves that pairing, channel access, protocol handshake, and initial state retrieval all worked at that moment.

## Pairing on Home Assistant OS

Use the official Terminal & SSH app:

```text
bluetoothctl
power on
agent NoInputNoOutput
default-agent
scan on
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
scan off
devices Paired
quit
```

Initial pairing normally requires the soundbar's Bluetooth pairing function. Normal control does not. Avoid a later `bluetoothctl connect`: it may request audio profiles in addition to SPP. Let the integration open its RFCOMM socket directly.

## `cannot_connect` during setup

Check, in order:

1. The soundbar is powered on.
2. The address is the soundbar's Classic Bluetooth address, not an unrelated BLE advertisement.
3. `bluetoothctl devices Paired` lists that address.
4. The device is trusted (`bluetoothctl info XX:XX:XX:XX:XX:XX`).
5. ThinQ, a phone, the standalone CLI, or another Home Assistant instance is not holding the SPP session.
6. The Home Assistant Bluetooth adapter supports Classic Bluetooth/RFCOMM, not BLE only.
7. Restart the soundbar once after a failed or interrupted pairing attempt.

The transport tries channel 2 first and channel 1 second. Failures for both channels are included in debug logs.

## Entity becomes unavailable

The coordinator closes a failed session and reconnects on the next refresh. If it remains unavailable:

1. Close ThinQ on nearby phones.
2. Confirm the pairing still exists.
3. Reload the integration entry from **Settings → Devices & services**.
4. Power-cycle the soundbar only if the RFCOMM service remains wedged.
5. Collect diagnostics and debug logs before deleting/re-pairing the device.

## Enable debug logging

In **Developer tools → Actions**, run `logger.set_level` with:

```yaml
action: logger.set_level
data:
  custom_components.lg_us60tr: debug
```

Follow Core logs from the Terminal & SSH app:

```sh
ha core logs --follow
```

Useful messages include:

- RFCOMM channel attempts and selected channel
- Raw TX/RX bytes at debug level
- Decoded protocol major/minor/payload values
- State changes and pushed updates
- Command timeouts, disconnects, and reconnect attempts

Return logging to normal after diagnosis:

```yaml
action: logger.set_level
data:
  custom_components.lg_us60tr: warning
```

## Download diagnostics

Open the integration entry, select the menu, and download diagnostics. The report includes the selected RFCOMM channel and decoded state. The configured Bluetooth address is redacted.

## A command times out

- Same-value setters are handled as no-ops, but a changed value must still be confirmed by state traffic.
- A timeout usually means the soundbar closed the session, another controller took it, or the protocol handshake was interrupted.
- Do not increase the timeout first. Capture debug logs and verify the actual TX/RX sequence.
- Reloading the integration cleanly closes the old client before opening a new one.

## Source changes unexpectedly

On Linux/Home Assistant, the integration opens only an RFCOMM socket. If a reconnect wakes the soundbar on Bluetooth, the coordinator restores the last input it observed before completing the refresh or command. Explicit source selections bypass this restoration. A first connection with no previously observed source has nothing safe to restore.

On macOS, `IOBluetooth` was observed to establish A2DP alongside RFCOMM. A2DP can switch the soundbar to Bluetooth even when CoreAudio still outputs through another device. This is a platform/profile side effect; BLE is not an alternate control path for the tested soundbar.

## HACS does not show the integration

- Confirm the custom repository category is **Integration**.
- Confirm `hacs.json` and `custom_components/lg_us60tr/manifest.json` are present on the selected branch.
- Update/redownload the repository in HACS, then restart Home Assistant.
- Search for the display name **LG US60TR Soundbar**, not the domain name.

## Safe data to attach to an issue

- Home Assistant and HAOS versions
- Soundbar model and firmware version
- Whether pairing and trust succeed
- Redacted diagnostics
- Debug logs covering one connection or one isolated command
- A description of the physical display/source before and after the action

Remove Bluetooth addresses, phone serials, account identifiers, tokens, and full Android bugreports before publishing.

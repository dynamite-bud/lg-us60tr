# LG US60TR / US70TR Soundbar

Local control of LG US60TR/S70T-family soundbars over Bluetooth Classic RFCOMM/SPP. The repository contains a Home Assistant custom integration and the platform-neutral Python protocol client it uses.

The implementation is cloud-free: Home Assistant talks directly to the paired soundbar. It does not require the LG ThinQ app after initial Bluetooth pairing.

## Status

Working end to end on an **LG US70TR(D0)** with Home Assistant OS 18.2 / Core 2026.7.4 on Home Assistant Yellow. The project retains the `lg_us60tr` name from its original target; other family models have not yet been live-tested.

Verified controls:

- Input function: Bluetooth, USB, HDMI In, and Optical / HDMI ARC
- Volume: 0–100
- Sound mode: AI Sound Pro, Standard, Cinema, Clear Voice Pro, Sports, Music, Game, and Bass Blast
- Woofer level: -15…6
- Center level: -6…6
- Rear level: -6…6
- Night mode
- State refresh, pushed state changes, reconnect, availability, and privacy-safe diagnostics

There is no separately captured HDMI-CEC function. The fourth function exposed by the soundbar and ThinQ is **Optical / HDMI ARC**.

## How it works

```mermaid
flowchart LR
    HA[Home Assistant entities] --> C[DataUpdateCoordinator]
    C --> P[Soundbar protocol client]
    P --> R[Linux RFCOMM socket]
    R --> S[LG soundbar SPP channel 2]
```

The control transport is Bluetooth Classic SPP, not BLE. The packet protocol and every exposed command are capture-backed; guessed power, reset, pairing, firmware, demo, and factory commands are intentionally absent.

## Requirements

- Home Assistant 2026.7.4 or newer
- A Linux Home Assistant host with a Bluetooth adapter that supports Classic RFCOMM
- The soundbar paired and trusted by the host's BlueZ stack
- The soundbar's Bluetooth address

The integration first tries RFCOMM channel 2, then channel 1 as a fallback. Only one ThinQ/SPP controller should be active during setup.

## Install with HACS

1. In HACS, open **Integrations**, select the menu, then **Custom repositories**.
2. Add `https://github.com/dynamite-bud/lg-us60tr` with category **Integration**.
3. Install **LG US60TR Soundbar** and restart Home Assistant.
4. Pair the soundbar with the Home Assistant host as described below.
5. Open **Settings → Devices & services → Add integration**, search for **LG US60TR Soundbar**, and enter the Bluetooth address.

The repository layout and `hacs.json` are ready for HACS custom-repository installation. No Python package is downloaded at runtime; the complete protocol client and Linux transport are bundled under `custom_components/lg_us60tr/core`.

## Pair the soundbar with Home Assistant OS

Pairing is a one-time host operation. In the Terminal & SSH app, run:

```text
bluetoothctl
power on
agent NoInputNoOutput
default-agent
scan on
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
scan off
quit
```

Put the soundbar in Bluetooth pairing mode only for this initial pairing. Restore the desired HDMI/ARC input afterwards. Do not run `bluetoothctl connect` for normal use: the integration opens only its RFCOMM control channel and does not need an explicit A2DP connection.

List the saved address later with:

```sh
bluetoothctl devices Paired
```

## Home Assistant entities

| Entity | Capability |
|---|---|
| Media player | Source, volume, sound mode, availability |
| Woofer level | Integer slider, -15…6 |
| Center level | Integer slider, -6…6 |
| Rear level | Integer slider, -6…6 |
| Night mode | On/off switch |

All blocking Bluetooth work runs in Home Assistant's executor, while access to the single SPP session is serialized by the coordinator.

## Manual installation

Copy `custom_components/lg_us60tr` into the Home Assistant configuration directory:

```text
/config/custom_components/lg_us60tr
```

Restart Home Assistant, then add the integration through **Settings → Devices & services**.

## Standalone Python client

Python 3.11 or newer is required. Linux uses native `AF_BLUETOOTH` sockets; macOS installs PyObjC and uses `IOBluetooth`.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

lg-us60tr --address XX:XX:XX:XX:XX:XX state
lg-us60tr --address XX:XX:XX:XX:XX:XX volume 20
lg-us60tr --address XX:XX:XX:XX:XX:XX function "HDMI In"
lg-us60tr --address XX:XX:XX:XX:XX:XX mode Cinema
lg-us60tr --address XX:XX:XX:XX:XX:XX woofer 2
lg-us60tr --address XX:XX:XX:XX:XX:XX night off
```

On macOS, opening RFCOMM was observed to bring up A2DP as well, which can switch the soundbar to Bluetooth. Home Assistant/Linux is the recommended deployment target when preserving the current source matters.

## Documentation

- [Current status](docs/STATUS.md)
- [Protocol reference](docs/PROTOCOL.md)
- [Deployment and troubleshooting](docs/TROUBLESHOOTING.md)
- [Research evidence and capture index](research/README.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Safety and scope

The Home Assistant integration exposes only commands confirmed by ThinQ captures. The standalone CLI has a `raw` subcommand for protocol research; it is deliberately not exposed through Home Assistant or Assist. Do not send unknown commands to production hardware.

## License

[MIT](LICENSE)

# Research evidence

This directory is the local evidence workspace behind the implementation. Large captures, screenshots, APK material, and decompiled third-party source are intentionally ignored by Git so a HACS installation remains small and private device data is not published.

## Provenance

| Artifact | Value |
|---|---|
| ThinQ Android package | `com.lgeha.nuts` |
| ThinQ version | 5.1.32310 (`VERSION_CODE` 51002010) |
| ThinQ build timestamp | 2026-05-22 15:08:32 +0900 |
| Original base APK SHA-256 | `72d5ae917342d666c128fc2f9e357cead3277d75c34cfe5e1e93afe69fcdf521` |
| Original packaged web bundle SHA-256 | `177a1313efc467760e6ce78c3d65b1c78d466ba2661bd38f06833ea97d6ce0c5` |
| Decompiled with | JADX 1.5.6 |
| Packet analysis | TShark 4.6.7 |
| Tested product identity | LG US70TR(D0) |
| ThinQ product module | `GSB`, entry `GSB_CEN01_Main`, version 5002.38 |

The APK and generic `assets/www.zip` were removed after their hashes and relevant sources were recorded. The generic bundle does not contain the model-specific command table; ThinQ downloads that as the GSB module.

## Capture index

Local captures are under `research/captures/`.

| Prefix | Experiment | Retained evidence | Result |
|---:|---|---|---|
| 00 | Connected baseline | HCI log | Established SPP baseline |
| 01 | Physical volume 15→20 | HCI log | Identified pushed volume traffic |
| 02 | ThinQ volume 20→19 | HCI log, diagnostic screenshot | Mapped volume setter/confirmation |
| 03 | Woofer 0→1 | HCI log, before/after screenshots | Mapped signed woofer value |
| 04 | Woofer 1→2 | HCI log, before/after screenshots | Confirmed woofer mapping |
| 05 | Cinema→Standard | HCI log, before/selector/after screenshots | Mapped Standard value `02` |
| 06 | Standard→Cinema | HCI log, before/selector/after screenshots | Mapped Cinema value `55` |
| 07 | Night mode off→on | HCI log, before/after screenshots | Mapped boolean `01` |
| 08 | Night mode on→off | HCI log, before/after screenshots | Mapped boolean `00` |
| 09 | ThinQ reconnect | HCI logs, screenshots, one full bugreport ZIP | Mapped connection lifecycle and GSB metadata |
| 10 | Function switching | HCI log, HDMI/Bluetooth/USB/Optical screenshots | Mapped `00/01` source setters |

Redundant full Android bugreport ZIPs for 00–08, the failed 09 attempt, and 10 were removed after extracting their HCI logs. The successful `09-thinq-reconnect.zip` remains because its dumpstate contains the installed GSB module and product-page metadata that is not present in the HCI stream.

Useful packet views:

```sh
tshark -r research/captures/10-function-switches-btsnoop_hci.log \
  -Y 'btspp' \
  -T fields -e frame.number -e frame.time_relative -e _ws.col.Info

tshark -r research/captures/10-function-switches-btsnoop_hci.log \
  -Y 'btspp contains 41:54' -x
```

Do not inspect a binary btsnoop log as text. Filter SPP frames and correlate one isolated UI action with its before/after screenshot.

## ThinQ UI evidence

`research/ui/thinq-app/` contains the retained screenshots and Android UI hierarchy dumps used to identify the visible control names. They establish the user-facing modes and functions but are not packet evidence by themselves.

## Curated decompilation

The original 732 MB JADX tree was reduced to the source files relevant to interoperability under `research/decompiled/thinq-5.1.32310/`:

- `app/BuildConfig.java`: package version/build provenance
- `av/SppPacket.java`: frame layout and checksum
- `av/SppDeviceManager.java`: SPP lifecycle and JSON-to-frame dispatch
- `av/AvManager.java`: product routing and A2DP-triggered lifecycle
- `av/AVPluginCallBack.java`: web-to-native bridge surface
- `modules/`: GSB module request, cache, and persistence flow
- `soundbar/`: Bluetooth manager and soundbar BLE provisioning implementation
- `xboom/`: contrasting XBoom BLE implementation

The decompiled files are kept locally for interoperability research and are ignored by Git. They show that Bluetooth soundbar control routes through SPP, while the BLE paths belong to provisioning or other product families.

## Findings and confidence

### Directly observed

- SPP/RFCOMM carries the soundbar control protocol.
- The working tested channel is 2.
- Frames use `AT | major | minor | length | payload | checksum`.
- The command values documented in `docs/PROTOCOL.md` match isolated HCI captures.
- ThinQ can keep its control page open while the soundbar remains on HDMI/ARC.
- Home Assistant/Linux control works without a separately requested A2DP connection.

### Source-supported inference

ThinQ starts its Bluetooth-soundbar local-control lifecycle after Android reports A2DP connected, then opens SPP. macOS similarly initiated A2DP when its RFCOMM channel opened. The unwanted macOS input change is therefore attributed to the profile connection, not to a hidden BLE command.

### Not established

- Compatibility with every US60TR/S70T firmware or regional variant
- A distinct HDMI-CEC input command
- Safe power, mute, reset, firmware, demo, or factory commands
- BLE as an alternate control transport for this model

## Research rules

1. Isolate one user action per capture.
2. Preserve a before and after state.
3. Treat packet bytes as untrusted until both direction and behavior are established.
4. Add a protocol vector and a behavioral test for every promoted command.
5. Never expose raw or destructive command paths through Home Assistant or Assist.

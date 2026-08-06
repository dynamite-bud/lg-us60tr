# Protocol reference

This document records the capture-backed protocol implemented by `custom_components/lg_us60tr/core`. Values are hexadecimal unless stated otherwise.

## Transport

- Bluetooth Classic Serial Port Profile (SPP), UUID `0x1101`
- RFCOMM channel 2 on the tested LG US70TR(D0); channel 1 is a fallback
- Bidirectional byte stream with no application-level authentication, sequence number, or session ID
- Bluetooth pairing and trust are handled by the operating system

ThinQ's Bluetooth-soundbar path uses SPP. BLE/GATT traffic was not used for control in the Android captures. ThinQ has separate BLE implementations for soundbar Wi-Fi provisioning and XBoom products; those are not interchangeable with this SPP transport.

## Frame format

```text
41 54 | major | minor | payload_length | payload... | checksum
 A  T
```

The checksum is the 8-bit two's complement of the payload length plus every payload byte:

```python
checksum = (-(len(payload) + sum(payload))) & 0xFF
```

Example, select Bluetooth:

```text
41 54 00 01 01 07 f8
```

The parser accepts fragmented and concatenated frames, resynchronizes at `AT`, counts checksum failures, and discards malformed bytes without treating them as valid responses.

## Session initialization

The implemented handshake follows the captured ThinQ sequence:

| Order | Major/minor | Payload | Purpose |
|---:|---|---|---|
| 1 | `00/15` | — | Start handshake |
| 2 | `0d/24` | `04` | Initial capability query |
| 3 | `00/16` | — | Advance handshake |
| 4 | `00/17` | `1f` | Register sound-mode state |
| 5 | `00/0b` | — | Query active function prefix |
| 6 | `00/19` | — | Mark session ready |
| 7 | `07/03` | — | Query state snapshot |

Reconnects do not always announce the active prefix, so the client explicitly sends `00/0b` before completing initialization and before a full refresh.

## Prefix semantics

Two similarly named values have different roles:

- **Control prefix `07`**: stable major byte for volume, sound mode, snapshot, and night-mode commands on the tested firmware.
- **Active prefix**: value returned by `00/0b`; identifies the selected input function.

| Active prefix | Input source |
|---:|---|
| `07` | Bluetooth |
| `40` | USB |
| `c0` | HDMI In |
| `d0` | Optical / HDMI ARC |

The Optical / HDMI ARC setter uses `df`, while its active-prefix confirmation is `d0`. This asymmetry is present in the capture and is intentional.

## Commands

| Control | Major/minor | Payload |
|---|---|---|
| Select input | `00/01` | One function byte |
| Volume | `07/02` | `64`, then volume `00`–`64` |
| Sound mode | `07/1f` | `00`, then mode byte |
| Woofer level | `0d/1b` | Signed int8; empty payload queries |
| Center level | `0d/26` | Signed int8; empty payload queries |
| Rear level | `0d/21` | Signed int8; empty payload queries |
| Night mode | `07/4a` | `00` or `01`; empty payload queries |
| State snapshot | `07/03` | Empty |
| Active function | `00/0b` | Empty query; one-byte response |

### Input function values

| Function | Setter payload | Captured encoded frame |
|---|---:|---|
| Bluetooth | `07` | `415400010107f8` |
| USB | `40` | `415400010140bf` |
| HDMI In | `c0` | `4154000101c03f` |
| Optical / HDMI ARC | `df` | `4154000101df20` |

The older `00/07` family is query/state traffic, not the function setter. No separate HDMI-CEC setter was observed.

### Sound mode values

| Mode | Value |
|---|---:|
| AI Sound Pro | `90` |
| Standard | `02` |
| Cinema | `55` |
| Clear Voice Pro | `97` |
| Sports | `92` |
| Music | `38` |
| Game | `54` |
| Bass Blast | `37` |

The soundbar can emit a textual mode name in snapshot/registration traffic. Some snapshots report `RESERVED` immediately after a mode change; the client preserves the last recognized mode rather than replacing it with an unknown value.

## Response handling

- `00/0b`, one-byte payload: active prefix and input source
- Minor `03`, snapshot payload containing marker `64`: volume plus an optional ASCII sound-mode name
- Minor `02`, payload `64 <volume>`: volume update/confirmation
- Minor `1f`, payload `00 <mode>`: mode update; payload `05` plus mode bytes: available modes
- `0d/1b`, `0d/26`, and `0d/21`: signed woofer, center, and rear levels plus captured bounds
- Minor `4a`: night-mode state

The soundbar commonly confirms setters by echoing their resulting state. A same-value setter may produce no new notification, so the client treats an already-equal value as a successful no-op instead of waiting for an echo that will never arrive.

## Out of scope

Power, mute, pairing, firmware transfer, reset, demo, and factory operations are not mapped. Unknown frames must not be promoted to supported commands without an isolated capture and a behavioral test.

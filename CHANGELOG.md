# Changelog

## Unreleased

- Restore the last known input when a Home Assistant reconnect wakes the soundbar on Bluetooth; explicit source selections remain authoritative.
- Add regression coverage for refresh-driven wake, command-driven wake, and explicit source selection.

## 0.1.0 — 2026-08-06

Initial consolidated release.

- Reverse-engineered the local ThinQ SPP frame format, checksum, handshake, state queries, and confirmation behavior.
- Added typed control for input function, volume, eight sound modes, woofer, center, rear, and night mode.
- Added native Linux RFCOMM and macOS `IOBluetooth` transports behind one protocol client.
- Added a Home Assistant UI config flow, media player, three number entities, night-mode switch, reconnect handling, pushed state updates, diagnostics, and English translations.
- Captured and verified Bluetooth, USB, HDMI In, and Optical / HDMI ARC function switching.
- Verified the integration live on LG US70TR(D0) with Home Assistant OS 18.2 / Core 2026.7.4 on Home Assistant Yellow.
- Established that the tested soundbar uses Classic SPP control rather than BLE; documented the macOS A2DP source-switch side effect.
- Consolidated the implementation, research index, curated decompilation, captures, and deployment guidance into this repository.

The earlier exploratory workspace had no recoverable Git metadata at consolidation time. This release is the repository's provenance baseline; the dated research captures and this changelog preserve the preceding experimental sequence.

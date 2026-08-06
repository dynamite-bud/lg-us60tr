# Contributing

## Development setup

Python 3.11 or newer is required.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install pytest pytest-homeassistant-custom-component ruff build
```

Run the checks used by this repository:

```sh
pytest -q
ruff check custom_components tests
ruff format --check custom_components tests
python -m build
```

## Design constraints

- Keep the protocol/client layer platform-neutral.
- Keep Linux and macOS transports separate.
- Use native Linux RFCOMM sockets; do not add PyBluez.
- Do not replace macOS `IOBluetooth` with CoreBluetooth; CoreBluetooth cannot provide Classic SPP.
- Preserve the macOS main-thread run-loop behavior and native delegate-pointer copy.
- Serialize access to the one soundbar SPP session.
- Keep raw and destructive operations out of Home Assistant entities and Assist.
- Avoid cloud dependencies when the same state/control exists locally.

## Adding a command

A new command needs all of the following:

1. An isolated capture with known before/after behavior.
2. Direction, major/minor, payload, and confirmation response documented in `docs/PROTOCOL.md`.
3. A packet-level vector test.
4. A client behavior test that would fail for a plausible wrong value or wrong response.
5. A bounded typed API; no arbitrary bytes in Home Assistant.

Do not infer commands from adjacent values or UI order. Power, reset, pairing, firmware, demo, and factory operations require an especially strong safety case.

## Research artifacts

Put local HCI logs, screenshots, APKs, and decompiled files under `research/`. They are ignored by Git because they may contain device identifiers, personal data, large binaries, or third-party copyrighted material. Record only the necessary hashes, filenames, observations, and derived protocol facts in `research/README.md`.

## Home Assistant changes

- Exercise setup through a real config entry in tests.
- Verify every new entity command traverses the coordinator executor path.
- Preserve clean unload and reconnect behavior.
- Keep diagnostics privacy-safe.
- Update both `strings.json` and translations for user-visible text.

## Scope of compatibility claims

The only live-tested product is LG US70TR(D0). Describe other models as unverified until a contributor provides hardware-backed evidence.

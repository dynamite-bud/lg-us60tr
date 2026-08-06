# Current status

Last updated: 2026-08-06

## Deliverable

The Home Assistant custom integration is implemented, installed, and working on the live system. The standalone Python client, native Linux transport, macOS transport, protocol tests, Home Assistant tests, HACS metadata, and user documentation are in this repository.

Live Home Assistant verification covered:

- Successful paired RFCOMM connection to LG US70TR(D0)
- State reporting while the source was HDMI In
- Explicit switching through Bluetooth, USB, Optical / HDMI ARC, and back to HDMI In
- Volume and sound-mode control
- Woofer, center, and rear level entities
- Night mode off/on behavior
- Clean source restoration after testing

The latest user-visible entity state supplied during consolidation showed woofer `2`, center `-4`, rear `4`, and night mode `Off`.

## Architecture decisions

- Home Assistant/Linux is the primary target.
- Bluetooth Classic RFCOMM/SPP is the control transport.
- BLE is not used as a substitute transport for this model.
- The integration bundles its protocol client and has no runtime PyPI dependency.
- Only capture-confirmed safe controls are exposed.
- Raw command access remains standalone-CLI-only.
- Large/private research artifacts stay local under `research/` and are excluded from HACS/Git distribution.

## Known boundary

The LG US70TR(D0) is the only live-tested model. No independent HDMI-CEC setter was observed; the UI's fourth captured function is Optical / HDMI ARC. macOS can initiate A2DP while opening RFCOMM and may switch the soundbar to Bluetooth, so it is not the preferred always-on host.

## Distribution and optional future work

The canonical repository is `https://github.com/dynamite-bud/lg-us60tr`. It can be added to HACS as a custom repository in the **Integration** category.

The functional deliverable is complete. Optional follow-up work:

1. Submit the repository for inclusion in HACS defaults if broader distribution is wanted.
2. Collect hardware-backed compatibility reports for additional US60TR/S70T variants.

No temporary Home Assistant SSH key, API token, or deployment credential is retained by this workspace.

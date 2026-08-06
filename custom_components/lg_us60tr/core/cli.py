from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict

from .client import SoundbarClient
from .state import InputSource, SoundbarState, SoundMode
from .transport import RFCOMMTransport

LOG_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")


def _platform_transport(address: str, channels: tuple[int, ...]) -> RFCOMMTransport:
    if sys.platform == "darwin":
        from .macos import MacOSRFCOMMTransport

        return MacOSRFCOMMTransport(address, channels)
    if sys.platform == "linux":
        from .linux import LinuxRFCOMMTransport

        return LinuxRFCOMMTransport(address, channels)
    raise RuntimeError(f"unsupported Bluetooth platform: {sys.platform}")


def _state_json(state: SoundbarState, channel: int | None) -> str:
    data = asdict(state)
    data["sound_mode"] = (
        state.sound_mode.label if state.sound_mode is not None else None
    )
    data["input_source"] = (
        state.input_source.label if state.input_source is not None else None
    )
    data["available_modes"] = [mode.label for mode in state.available_modes]
    data["rfcomm_channel"] = channel
    return json.dumps(data, indent=2)


def _parse_hex_bytes(value: str) -> bytes:
    return bytes.fromhex(value.replace(" ", ""))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lg-us60tr")
    parser.add_argument(
        "--address",
        required=True,
        help="soundbar Bluetooth address (for example XX:XX:XX:XX:XX:XX)",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=LOG_LEVELS,
        default="WARNING",
        help="diagnostic logging threshold (default: WARNING)",
    )
    parser.add_argument(
        "--channels", default="2,1", help="RFCOMM channels in attempt order"
    )
    subcommands = parser.add_subparsers(dest="action", required=True)
    subcommands.add_parser("state")
    function = subcommands.add_parser(
        "function", help="switch the soundbar input function"
    )
    function.add_argument("value", choices=[source.label for source in InputSource])
    volume = subcommands.add_parser("volume")
    volume.add_argument("value", type=int)
    mode = subcommands.add_parser("mode")
    mode.add_argument("value", choices=[sound_mode.label for sound_mode in SoundMode])
    woofer = subcommands.add_parser("woofer")
    woofer.add_argument("value", type=int)
    center = subcommands.add_parser("center")
    center.add_argument("value", type=int)
    rear = subcommands.add_parser("rear")
    rear.add_argument("value", type=int)
    night = subcommands.add_parser("night")
    night.add_argument("value", choices=("on", "off"))
    raw = subcommands.add_parser("raw")
    raw.add_argument("major", type=lambda value: int(value, 0))
    raw.add_argument("minor", type=lambda value: int(value, 0))
    raw.add_argument("payload", nargs="?", default=b"", type=_parse_hex_bytes)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    channels = tuple(
        int(value.strip()) for value in args.channels.split(",") if value.strip()
    )
    transport = _platform_transport(args.address, channels)
    client = SoundbarClient(transport)
    try:
        client.connect()
        if args.action == "function":
            client.set_input_source(args.value)
        elif args.action == "volume":
            client.set_volume(args.value)
        elif args.action == "mode":
            client.set_sound_mode(args.value)
        elif args.action == "woofer":
            client.set_woofer_level(args.value)
        elif args.action == "center":
            client.set_center_level(args.value)
        elif args.action == "rear":
            client.set_rear_level(args.value)
        elif args.action == "night":
            client.set_night_mode(args.value == "on")
        elif args.action == "raw":
            client.send_command(args.major, args.minor, args.payload)
        print(_state_json(client.state, client.channel))
    finally:
        client.close()


if __name__ == "__main__":
    main()

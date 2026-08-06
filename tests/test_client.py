import queue
import unittest

from lg_us60tr import InputSource, SoundbarClient, SoundMode
from lg_us60tr.cli import build_parser
from lg_us60tr.protocol import Frame, decode_frame


class FakeTransport:
    def __init__(
        self,
        *,
        announce_prefix: bool = True,
        initial_mode: SoundMode | None = SoundMode.CINEMA,
        snapshot_name: bytes = b"CINEMA",
    ) -> None:
        self._connected = False
        self._incoming: queue.Queue[bytes | None] = queue.Queue()
        self.writes: list[Frame] = []
        self.announce_prefix = announce_prefix
        self.initial_mode = initial_mode
        self.snapshot_name = snapshot_name
        self.active_prefix = 0x07

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def channel(self) -> int | None:
        return 1 if self._connected else None

    def connect(self, timeout: float = 20.0) -> None:
        self._connected = True

    def service(self, timeout: float = 0.0) -> None:
        pass

    def read(self, timeout: float = 0.5) -> bytes:
        try:
            value = self._incoming.get(timeout=timeout)
        except queue.Empty:
            return b""
        return value or b""

    def write(self, data: bytes, timeout: float = 5.0) -> None:
        frame = decode_frame(data)
        self.writes.append(frame)
        response: Frame | None = None
        if frame.command == 0x0D24 and frame.payload == b"\x04":
            if self.announce_prefix:
                self._incoming.put(Frame(0x00, 0x0B, b"\x07").encode())
            self._incoming.put(
                Frame(0x07, 0x1F, bytes.fromhex("059002559792385437")).encode()
            )
            if self.initial_mode is not None:
                self._incoming.put(
                    Frame(0x07, 0x1F, bytes((0x00, int(self.initial_mode)))).encode()
                )
        elif frame.command == 0x000B:
            response = Frame(0x00, 0x0B, bytes((self.active_prefix,)))
        elif frame.command == 0x0001 and len(frame.payload) == 1:
            self.active_prefix = (
                0xD0
                if frame.payload[0] == InputSource.OPTICAL_HDMI_ARC
                else frame.payload[0]
            )
            response = Frame(0x00, 0x0B, bytes((self.active_prefix,)))
        elif frame.command == 0x0703:
            response = Frame(
                self.active_prefix,
                0x03,
                bytes.fromhex("ff10640500000000000000000000000000")
                + self.snapshot_name,
            )
        elif frame.command == 0x0D1B:
            response = Frame(
                0x0D,
                0x1B,
                frame.payload + b"\xf1\x06" if frame.payload else b"\x02\xf1\x06",
            )
        elif frame.command == 0x0D26:
            response = Frame(
                0x0D,
                0x26,
                frame.payload + b"\xfa\x06" if frame.payload else b"\xfc\xfa\x06",
            )
        elif frame.command == 0x0D21:
            response = Frame(
                0x0D,
                0x21,
                frame.payload + b"\xfa\x06" if frame.payload else b"\x04\xfa\x06",
            )
        elif frame.minor == 0x4A and frame.major == self.active_prefix:
            response = Frame(self.active_prefix, 0x4A, frame.payload or b"\x00")
        elif frame.minor == 0x02:
            response = Frame(self.active_prefix, 0x02, frame.payload)
        elif frame.minor == 0x1F:
            response = Frame(self.active_prefix, 0x1F, frame.payload)
        if response is not None:
            self._incoming.put(response.encode())

    def close(self) -> None:
        self._connected = False
        self._incoming.put(None)


class CLITests(unittest.TestCase):
    def test_log_level_flag_is_case_insensitive(self) -> None:
        for value, expected in (
            ("debug", "DEBUG"),
            ("INFO", "INFO"),
            ("Error", "ERROR"),
        ):
            with self.subTest(value=value):
                args = build_parser().parse_args(
                    [
                        "--address",
                        "00:11:22:33:44:55",
                        "--log-level",
                        value,
                        "state",
                    ]
                )
                self.assertEqual(args.log_level, expected)


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeTransport()
        self.client = SoundbarClient(self.transport)
        self.client.connect(timeout=1.0)

    def tearDown(self) -> None:
        self.client.close()

    def test_initial_state_query(self) -> None:
        state = self.client.state
        self.assertEqual(state.control_prefix, 0x07)
        self.assertEqual(state.active_prefix, 0x07)
        self.assertEqual(state.input_source, InputSource.BLUETOOTH)
        self.assertEqual(state.volume, 5)
        self.assertEqual(state.sound_mode, SoundMode.CINEMA)
        self.assertEqual(state.woofer_level, 2)
        self.assertEqual((state.woofer_min, state.woofer_max), (-15, 6))
        self.assertEqual(state.center_level, -4)
        self.assertEqual((state.center_min, state.center_max), (-6, 6))
        self.assertEqual(state.rear_level, 4)
        self.assertEqual((state.rear_min, state.rear_max), (-6, 6))
        self.assertFalse(state.night_mode)
        self.assertEqual(state.sound_mode_name, "CINEMA")
        self.assertEqual(state.available_modes, tuple(SoundMode))

    def test_connect_explicitly_queries_prefix_when_not_announced(self) -> None:
        transport = FakeTransport(announce_prefix=False)
        client = SoundbarClient(transport)
        try:
            state = client.connect(timeout=1.0)
            self.assertEqual(state.input_source, InputSource.BLUETOOTH)
            self.assertIn(Frame(0x00, 0x0B), transport.writes)
        finally:
            client.close()

    def test_typed_controls_match_capture_frames(self) -> None:
        self.client.set_volume(19, timeout=1.0)
        self.client.set_sound_mode("Standard", timeout=1.0)
        self.client.set_woofer_level(1, timeout=1.0)
        self.client.set_center_level(-3, timeout=1.0)
        self.client.set_rear_level(3, timeout=1.0)
        self.client.set_night_mode(True, timeout=1.0)
        encoded = [frame.encode().hex() for frame in self.transport.writes]
        self.assertIn("4154070202641387", encoded)
        self.assertIn("4154071f020002fc", encoded)
        self.assertIn("41540d1b0101fe", encoded)
        self.assertIn("41540d2601fd02", encoded)
        self.assertIn("41540d210103fc", encoded)
        self.assertIn("4154074a0101fe", encoded)

    def test_input_function_switches_match_captured_frames(self) -> None:
        expected = {
            InputSource.USB: "415400010140bf",
            InputSource.HDMI_IN: "4154000101c03f",
            InputSource.BLUETOOTH: "415400010107f8",
            InputSource.OPTICAL_HDMI_ARC: "4154000101df20",
        }
        for source, encoded in expected.items():
            with self.subTest(source=source):
                state = self.client.set_input_source(source, timeout=1.0)
                self.assertEqual(self.transport.writes[-1].encode().hex(), encoded)
                self.assertEqual(state.input_source, source)

        self.assertEqual(self.client.state.active_prefix, 0xD0)
        self.client.set_volume(19, timeout=1.0)
        self.assertEqual(self.transport.writes[-1], Frame(0x07, 0x02, b"\x64\x13"))

    def test_sound_mode_confirmation_accepts_active_hdmi_prefix(self) -> None:
        self.client.set_input_source(InputSource.HDMI_IN, timeout=1.0)
        state = self.client.set_sound_mode(SoundMode.STANDARD, timeout=1.0)
        self.assertEqual(state.sound_mode, SoundMode.STANDARD)
        self.assertEqual(self.transport.writes[-1], Frame(0x07, 0x1F, b"\x00\x02"))

    def test_same_value_controls_are_no_ops(self) -> None:
        before = len(self.transport.writes)
        self.client.set_input_source(InputSource.BLUETOOTH, timeout=1.0)
        self.client.set_volume(5, timeout=1.0)
        self.client.set_sound_mode(SoundMode.CINEMA, timeout=1.0)
        self.client.set_woofer_level(2, timeout=1.0)
        self.client.set_center_level(-4, timeout=1.0)
        self.client.set_rear_level(4, timeout=1.0)
        self.client.set_night_mode(False, timeout=1.0)
        self.assertEqual(len(self.transport.writes), before)

    def test_unknown_snapshot_mode_does_not_block_or_erase_mode(self) -> None:
        transport = FakeTransport(initial_mode=None, snapshot_name=b"RESERVED")
        client = SoundbarClient(transport)
        try:
            state = client.connect(timeout=1.0)
            self.assertIsNone(state.sound_mode)
            self.assertIsNone(state.sound_mode_name)

            state = client.set_sound_mode(SoundMode.STANDARD, timeout=1.0)
            self.assertEqual(state.sound_mode, SoundMode.STANDARD)
            state = client.query_state(timeout=1.0)
            self.assertEqual(state.sound_mode, SoundMode.STANDARD)
            self.assertEqual(state.sound_mode_name, "STANDARD")
        finally:
            client.close()

    def test_debug_logs_protocol_frames_and_state(self) -> None:
        with self.assertLogs("lg_us60tr.client", level="DEBUG") as captured:
            self.client.set_volume(19, timeout=1.0)

        messages = "\n".join(captured.output)
        self.assertIn(
            "Protocol TX major=0x07 minor=0x02 payload=64 13",
            messages,
        )
        self.assertIn(
            "Protocol RX major=0x07 minor=0x02 payload=64 13",
            messages,
        )
        self.assertIn("Soundbar state updated", messages)

    def test_invalid_values_are_rejected_before_write(self) -> None:
        before = len(self.transport.writes)
        with self.assertRaises(ValueError):
            self.client.set_volume(101)
        with self.assertRaises(ValueError):
            self.client.set_woofer_level(-16)
        with self.assertRaises(ValueError):
            self.client.set_center_level(-7)
        with self.assertRaises(ValueError):
            self.client.set_rear_level(7)
        with self.assertRaises(ValueError):
            self.client.set_sound_mode("Movie")
        with self.assertRaises(ValueError):
            self.client.set_input_source("Wi-Fi")
        self.assertEqual(len(self.transport.writes), before)


if __name__ == "__main__":
    unittest.main()

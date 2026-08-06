import unittest

from lg_us60tr.protocol import (
    ChecksumError,
    Frame,
    FrameParser,
    decode_frame,
    encode_frame,
)


class ProtocolTests(unittest.TestCase):
    def test_captured_control_vectors(self) -> None:
        vectors = {
            "function_bluetooth": (0x00, 0x01, b"\x07", "415400010107f8"),
            "function_usb": (0x00, 0x01, b"\x40", "415400010140bf"),
            "function_hdmi_in": (0x00, 0x01, b"\xc0", "4154000101c03f"),
            "function_optical_arc": (0x00, 0x01, b"\xdf", "4154000101df20"),
            "woofer_1": (0x0D, 0x1B, b"\x01", "41540d1b0101fe"),
            "woofer_2": (0x0D, 0x1B, b"\x02", "41540d1b0102fd"),
            "night_on": (0xC0, 0x4A, b"\x01", "4154c04a0101fe"),
            "night_off": (0xC0, 0x4A, b"\x00", "4154c04a0100ff"),
            "volume_19": (0x07, 0x02, b"\x64\x13", "4154070202641387"),
            "standard": (0x07, 0x1F, b"\x00\x02", "4154071f020002fc"),
            "cinema": (0x07, 0x1F, b"\x00\x55", "4154071f020055a9"),
        }
        for name, (major, minor, payload, expected_hex) in vectors.items():
            with self.subTest(name=name):
                encoded = encode_frame(major, minor, payload)
                self.assertEqual(encoded.hex(), expected_hex)
                self.assertEqual(decode_frame(encoded), Frame(major, minor, payload))

    def test_incremental_parser_handles_fragmentation_and_concatenation(self) -> None:
        parser = FrameParser()
        packet = bytes.fromhex("41540d1a000041540d1b000041540d1c0000")
        self.assertEqual(parser.feed(packet[:7]), (Frame(0x0D, 0x1A),))
        self.assertEqual(
            parser.feed(packet[7:]), (Frame(0x0D, 0x1B), Frame(0x0D, 0x1C))
        )

    def test_parser_resynchronizes_after_bad_checksum(self) -> None:
        parser = FrameParser()
        frames = parser.feed(
            bytes.fromhex("00ff41540d1b010100") + encode_frame(0x0D, 0x1B, b"\x02")
        )
        self.assertEqual(frames, (Frame(0x0D, 0x1B, b"\x02"),))
        self.assertEqual(parser.checksum_errors, 1)
        self.assertGreaterEqual(parser.discarded_bytes, 3)

    def test_strict_decoder_rejects_bad_checksum(self) -> None:
        with self.assertRaises(ChecksumError):
            decode_frame(bytes.fromhex("41540d1b010100"))


if __name__ == "__main__":
    unittest.main()

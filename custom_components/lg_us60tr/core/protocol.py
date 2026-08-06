from __future__ import annotations

from dataclasses import dataclass

MAGIC = b"AT"
MAX_PAYLOAD_LENGTH = 0xFF
MIN_FRAME_LENGTH = 6


class ProtocolError(ValueError):
    """The soundbar packet stream is malformed."""


class ChecksumError(ProtocolError):
    """A packet checksum does not match its payload."""


def payload_checksum(payload: bytes) -> int:
    """Return ThinQ's two's-complement checksum for a payload."""
    return (-(len(payload) + sum(payload))) & 0xFF


@dataclass(frozen=True, slots=True)
class Frame:
    major: int
    minor: int
    payload: bytes = b""

    def __post_init__(self) -> None:
        if not 0 <= self.major <= 0xFF:
            raise ValueError("major command must fit uint8")
        if not 0 <= self.minor <= 0xFF:
            raise ValueError("minor command must fit uint8")
        if len(self.payload) > MAX_PAYLOAD_LENGTH:
            raise ValueError("payload exceeds uint8 length")

    @property
    def command(self) -> int:
        return (self.major << 8) | self.minor

    def encode(self) -> bytes:
        payload = bytes(self.payload)
        return (
            MAGIC
            + bytes((self.major, self.minor, len(payload)))
            + payload
            + bytes((payload_checksum(payload),))
        )


def encode_frame(major: int, minor: int, payload: bytes = b"") -> bytes:
    return Frame(major, minor, bytes(payload)).encode()


def decode_frame(packet: bytes) -> Frame:
    packet = bytes(packet)
    if len(packet) < MIN_FRAME_LENGTH:
        raise ProtocolError("packet is shorter than six bytes")
    if packet[:2] != MAGIC:
        raise ProtocolError("packet does not start with AT")
    payload_length = packet[4]
    expected_length = MIN_FRAME_LENGTH + payload_length
    if len(packet) != expected_length:
        raise ProtocolError(
            f"packet length {len(packet)} does not match encoded length {expected_length}"
        )
    payload = packet[5 : 5 + payload_length]
    expected_checksum = payload_checksum(payload)
    if packet[-1] != expected_checksum:
        raise ChecksumError(
            f"checksum {packet[-1]:02x} does not match {expected_checksum:02x}"
        )
    return Frame(packet[2], packet[3], payload)


class FrameParser:
    """Incrementally parse concatenated or fragmented SPP packets."""

    __slots__ = ("_buffer", "checksum_errors", "discarded_bytes")

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.checksum_errors = 0
        self.discarded_bytes = 0

    def feed(self, data: bytes) -> tuple[Frame, ...]:
        if data:
            self._buffer.extend(data)
        frames: list[Frame] = []
        while True:
            magic_offset = self._buffer.find(MAGIC)
            if magic_offset < 0:
                keep = 1 if self._buffer.endswith(MAGIC[:1]) else 0
                self.discarded_bytes += len(self._buffer) - keep
                if keep:
                    del self._buffer[:-1]
                else:
                    self._buffer.clear()
                break
            if magic_offset:
                self.discarded_bytes += magic_offset
                del self._buffer[:magic_offset]
            if len(self._buffer) < 5:
                break
            packet_length = MIN_FRAME_LENGTH + self._buffer[4]
            if len(self._buffer) < packet_length:
                break
            packet = bytes(self._buffer[:packet_length])
            try:
                frame = decode_frame(packet)
            except ChecksumError:
                self.checksum_errors += 1
                self.discarded_bytes += 1
                del self._buffer[0]
                continue
            frames.append(frame)
            del self._buffer[:packet_length]
        return tuple(frames)

    def clear(self) -> None:
        self._buffer.clear()

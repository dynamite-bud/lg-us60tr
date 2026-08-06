import unittest
from contextlib import ExitStack
from unittest.mock import patch

from lg_us60tr.linux import LinuxRFCOMMTransport
from lg_us60tr.transport import SoundbarConnectionError, TransportDisconnected


class FakeSocket:
    def __init__(
        self,
        *,
        connect_error: OSError | None = None,
        incoming: list[bytes] | None = None,
    ) -> None:
        self.connect_error = connect_error
        self.incoming = list(incoming or [])
        self.address: tuple[str, int] | None = None
        self.timeout: float | None = None
        self.blocking: bool | None = None
        self.sent = bytearray()
        self.shutdown_mode: int | None = None
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def connect(self, address: tuple[str, int]) -> None:
        self.address = address
        if self.connect_error is not None:
            raise self.connect_error

    def setblocking(self, blocking: bool) -> None:
        self.blocking = blocking

    def recv(self, size: int) -> bytes:
        del size
        if self.closed:
            raise OSError(9, "Bad file descriptor")
        return self.incoming.pop(0)

    def send(self, data: memoryview) -> int:
        chunk = bytes(data[:2])
        self.sent.extend(chunk)
        return len(chunk)

    def shutdown(self, mode: int) -> None:
        self.shutdown_mode = mode

    def close(self) -> None:
        self.closed = True


class SocketFactory:
    def __init__(self, sockets: list[FakeSocket]) -> None:
        self.sockets = sockets
        self.calls: list[tuple[int, int, int]] = []

    def __call__(self, family: int, kind: int, protocol: int) -> FakeSocket:
        self.calls.append((family, kind, protocol))
        return self.sockets[len(self.calls) - 1]


class LinuxTransportTests(unittest.TestCase):
    def _patch_socket_api(
        self, factory: SocketFactory, *, readable: bool = True
    ) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(
            patch("lg_us60tr.linux.socket.AF_BLUETOOTH", 31, create=True)
        )
        stack.enter_context(
            patch("lg_us60tr.linux.socket.BTPROTO_RFCOMM", 3, create=True)
        )
        stack.enter_context(patch("lg_us60tr.linux.socket.socket", factory))

        def ready(
            readers: tuple[FakeSocket, ...],
            writers: tuple[FakeSocket, ...],
            errors: tuple[()],
            timeout: float,
        ):
            del errors, timeout
            return (list(readers) if readable else [], list(writers), [])

        stack.enter_context(patch("lg_us60tr.linux.select.select", ready))
        return stack

    def test_connect_tries_channels_in_order(self) -> None:
        refused = FakeSocket(connect_error=OSError("connection refused"))
        connected = FakeSocket()
        factory = SocketFactory([refused, connected])
        transport = LinuxRFCOMMTransport("00:11:22:33:44:55", (2, 1))

        with self._patch_socket_api(factory):
            transport.connect(timeout=2.0)
            self.assertTrue(transport.connected)
            self.assertEqual(transport.channel, 1)
            self.assertEqual(refused.address, ("00:11:22:33:44:55", 2))
            self.assertTrue(refused.closed)
            self.assertEqual(connected.address, ("00:11:22:33:44:55", 1))
            self.assertFalse(connected.blocking)
            transport.close()

        self.assertFalse(transport.connected)
        self.assertIsNone(transport.channel)
        self.assertTrue(connected.closed)

    def test_debug_logs_channel_fallback_and_packets(self) -> None:
        refused = FakeSocket(connect_error=OSError("connection refused"))
        connected = FakeSocket(incoming=[b"reply"])
        factory = SocketFactory([refused, connected])
        transport = LinuxRFCOMMTransport("00:11:22:33:44:55", (2, 1))

        with (
            self._patch_socket_api(factory),
            self.assertLogs("lg_us60tr.linux", level="DEBUG") as captured,
        ):
            transport.connect(timeout=2.0)
            transport.write(b"request", timeout=1.0)
            self.assertEqual(transport.read(timeout=1.0), b"reply")
            transport.close()

        messages = "\n".join(captured.output)
        self.assertIn("RFCOMM channel 2 connection", messages)
        self.assertIn("Connected to soundbar", messages)
        self.assertIn("RFCOMM TX: 72 65 71 75 65 73 74", messages)
        self.assertIn("RFCOMM RX: 72 65 70 6c 79", messages)

    def test_read_write_and_remote_disconnect(self) -> None:
        connected = FakeSocket(incoming=[b"reply", b""])
        factory = SocketFactory([connected])
        transport = LinuxRFCOMMTransport("00:11:22:33:44:55", (2,))

        with self._patch_socket_api(factory):
            transport.connect(timeout=2.0)
            transport.write(b"abcdef", timeout=1.0)
            self.assertEqual(connected.sent, b"abcdef")
            self.assertEqual(transport.read(timeout=1.0), b"reply")
            with self.assertRaisesRegex(TransportDisconnected, "peer closed"):
                transport.read(timeout=1.0)

        self.assertFalse(transport.connected)
        self.assertIsNone(transport.channel)
        self.assertTrue(connected.closed)

    def test_local_close_during_read_is_not_logged_as_transport_failure(self) -> None:
        connected = FakeSocket(incoming=[b""])
        factory = SocketFactory([connected])
        transport = LinuxRFCOMMTransport("00:11:22:33:44:55", (2,))

        with self._patch_socket_api(factory):
            transport.connect(timeout=2.0)

            def close_before_recv(*args: object) -> tuple[list[FakeSocket], list, list]:
                transport.close()
                return [connected], [], []

            with (
                patch("lg_us60tr.linux.select.select", close_before_recv),
                self.assertLogs("lg_us60tr.linux", level="DEBUG") as captured,
                self.assertRaisesRegex(TransportDisconnected, "channel closed"),
            ):
                transport.read(timeout=1.0)

        messages = "\n".join(captured.output)
        self.assertIn("read stopped after local close", messages)
        self.assertNotIn("ERROR", messages)

    def test_connection_failure_reports_each_channel(self) -> None:
        factory = SocketFactory(
            [
                FakeSocket(connect_error=OSError("first failed")),
                FakeSocket(connect_error=OSError("second failed")),
            ]
        )
        transport = LinuxRFCOMMTransport("00:11:22:33:44:55", (2, 1))

        with (
            self._patch_socket_api(factory),
            self.assertRaisesRegex(SoundbarConnectionError, "channel 2.*channel 1"),
        ):
            transport.connect(timeout=2.0)

        self.assertFalse(transport.connected)


if __name__ == "__main__":
    unittest.main()

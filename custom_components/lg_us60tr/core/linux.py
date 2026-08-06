from __future__ import annotations

import logging
import select
import socket
import threading
import time
from collections.abc import Iterable

from .transport import SoundbarConnectionError, TransportDisconnected, TransportError

_LOGGER = logging.getLogger(__name__)


class LinuxRFCOMMTransport:
    """Bluetooth Classic RFCOMM transport using Linux's native socket API."""

    def __init__(self, address: str, channels: Iterable[int] = (2, 1)) -> None:
        self.address = address
        self.channels = tuple(channels)
        if not self.channels:
            raise ValueError("at least one RFCOMM channel is required")
        if any(not 1 <= channel <= 30 for channel in self.channels):
            raise ValueError("RFCOMM channels must be in the range 1..30")
        self._socket: socket.socket | None = None
        self._channel: int | None = None
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._socket is not None

    @property
    def channel(self) -> int | None:
        with self._lock:
            return self._channel

    def connect(self, timeout: float = 20.0) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        _LOGGER.debug(
            "Connecting to soundbar %s over RFCOMM channels %s (timeout %.1fs)",
            self.address,
            self.channels,
            timeout,
        )
        try:
            address_family = socket.AF_BLUETOOTH
            protocol = socket.BTPROTO_RFCOMM
        except AttributeError as error:
            raise SoundbarConnectionError(
                "native Linux Bluetooth RFCOMM sockets are unavailable"
            ) from error

        deadline = time.monotonic() + timeout
        failures: list[str] = []
        with self._lock:
            if self._socket is not None:
                _LOGGER.debug(
                    "RFCOMM connection to %s is already open on channel %s",
                    self.address,
                    self._channel,
                )
                return
            for channel in self.channels:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    failures.append("connection deadline expired")
                    break
                _LOGGER.debug(
                    "Trying RFCOMM connection to %s on channel %s",
                    self.address,
                    channel,
                )
                candidate = socket.socket(address_family, socket.SOCK_STREAM, protocol)
                try:
                    candidate.settimeout(remaining)
                    candidate.connect((self.address, channel))
                    candidate.setblocking(False)
                except OSError as error:
                    candidate.close()
                    failures.append(f"channel {channel}: {error}")
                    _LOGGER.debug(
                        "RFCOMM channel %s connection to %s failed: %s",
                        channel,
                        self.address,
                        error,
                    )
                    continue
                self._socket = candidate
                self._channel = channel
                _LOGGER.info(
                    "Connected to soundbar %s on RFCOMM channel %s",
                    self.address,
                    channel,
                )
                return

        detail = "; ".join(failures) if failures else "no channels attempted"
        _LOGGER.error(
            "Unable to connect to soundbar %s over RFCOMM: %s",
            self.address,
            detail,
        )
        raise SoundbarConnectionError(
            f"could not connect to {self.address} over RFCOMM ({detail})"
        )

    def service(self, timeout: float = 0.0) -> None:
        del timeout

    def read(self, timeout: float = 0.5) -> bytes:
        candidate = self._connected_socket()
        try:
            readable, _, _ = select.select((candidate,), (), (), max(0.0, timeout))
            if not readable:
                return b""
            data = candidate.recv(4096)
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("RFCOMM RX: %s", data.hex(" "))
        except BlockingIOError:
            return b""
        except (OSError, ValueError) as error:
            was_connected = self._mark_disconnected(candidate)
            if was_connected:
                _LOGGER.exception("RFCOMM receive failed")
                message = "RFCOMM receive failed"
            else:
                _LOGGER.debug("RFCOMM read stopped after local close: %s", error)
                message = "RFCOMM channel closed"
            raise TransportDisconnected(message) from error
        if not data:
            was_connected = self._mark_disconnected(candidate)
            if was_connected:
                _LOGGER.warning("Soundbar closed the RFCOMM channel")
                raise TransportDisconnected("RFCOMM peer closed the channel")
            _LOGGER.debug("RFCOMM read stopped after local close")
            raise TransportDisconnected("RFCOMM channel closed")
        return data

    def write(self, data: bytes, timeout: float = 5.0) -> None:
        if not data:
            return
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("RFCOMM TX: %s", data.hex(" "))
        deadline = time.monotonic() + timeout
        remaining_data = memoryview(data)
        while remaining_data:
            candidate = self._connected_socket()
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                _LOGGER.error("RFCOMM write timed out")
                raise TransportError("RFCOMM write timed out")
            try:
                _, writable, _ = select.select((), (candidate,), (), remaining_time)
                if not writable:
                    _LOGGER.error("RFCOMM socket was not writable before timeout")
                    raise TransportError("RFCOMM write timed out")
                sent = candidate.send(remaining_data)
            except BlockingIOError:
                continue
            except TransportError:
                raise
            except (OSError, ValueError) as error:
                _LOGGER.exception("RFCOMM write failed")
                self._mark_disconnected(candidate)
                raise TransportDisconnected("RFCOMM write failed") from error
            if sent == 0:
                _LOGGER.warning("Soundbar closed the RFCOMM channel during a write")
                self._mark_disconnected(candidate)
                raise TransportDisconnected("RFCOMM peer closed the channel")
            remaining_data = remaining_data[sent:]

    def close(self) -> None:
        with self._lock:
            candidate = self._socket
            channel = self._channel
            self._socket = None
            self._channel = None
        if candidate is None:
            return
        _LOGGER.info(
            "Closing RFCOMM connection to %s on channel %s",
            self.address,
            channel,
        )
        try:
            candidate.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        candidate.close()

    def _connected_socket(self) -> socket.socket:
        with self._lock:
            candidate = self._socket
        if candidate is None:
            raise TransportDisconnected("RFCOMM channel is not open")
        return candidate

    def _mark_disconnected(self, candidate: socket.socket) -> bool:
        with self._lock:
            was_connected = self._socket is candidate
            if was_connected:
                self._socket = None
                self._channel = None
        candidate.close()
        return was_connected

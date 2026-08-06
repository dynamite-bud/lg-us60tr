from __future__ import annotations

from typing import Protocol, runtime_checkable


class TransportError(OSError):
    """Base error for an RFCOMM transport."""


class TransportDisconnected(TransportError):
    """The RFCOMM channel closed or is not open."""


class SoundbarConnectionError(TransportError):
    """No usable soundbar RFCOMM channel could be opened."""


class CommandTimeoutError(TimeoutError):
    """The soundbar did not confirm a command before its deadline."""


@runtime_checkable
class RFCOMMTransport(Protocol):
    @property
    def connected(self) -> bool: ...

    @property
    def channel(self) -> int | None: ...

    def connect(self, timeout: float = 20.0) -> None: ...
    def service(self, timeout: float = 0.0) -> None: ...

    def read(self, timeout: float = 0.5) -> bytes: ...

    def write(self, data: bytes, timeout: float = 5.0) -> None: ...

    def close(self) -> None: ...

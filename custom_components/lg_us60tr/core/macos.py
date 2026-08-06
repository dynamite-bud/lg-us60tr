from __future__ import annotations

import ctypes
import queue
import sys
import threading
from collections.abc import Iterable
from typing import Any

from .transport import SoundbarConnectionError, TransportDisconnected, TransportError

if sys.platform != "darwin":
    raise ImportError("lg_us60tr.macos is only available on macOS")

import IOBluetooth
import objc
from Foundation import NSDate, NSDefaultRunLoopMode, NSObject, NSRunLoop

objc.registerMetaDataForSelector(
    b"NSObject",
    b"rfcommChannelData:data:length:",
    {
        "arguments": {
            3: {"type": b"n^v", "c_array_length_in_arg": 4},
            4: {"type": b"Q"},
        }
    },
)


class _RFCOMMDelegate(
    NSObject,
    protocols=[objc.protocolNamed("IOBluetoothRFCOMMChannelDelegate")],
):
    transport: MacOSRFCOMMTransport | None = None

    def rfcommChannelData_data_length_(
        self, channel: Any, data: int, length: int
    ) -> None:
        transport = self.transport
        if transport is not None and data and length:
            transport._receive(ctypes.string_at(data, length))

    def rfcommChannelClosed_(self, channel: Any) -> None:
        transport = self.transport
        if transport is not None:
            transport._channel_closed()


class MacOSRFCOMMTransport:
    """Classic Bluetooth RFCOMM transport backed only by Apple's IOBluetooth."""

    def __init__(
        self,
        address: str,
        channels: Iterable[int] = (2, 1),
        *,
        receive_queue_size: int = 256,
    ) -> None:
        normalized_channels = tuple(dict.fromkeys(int(channel) for channel in channels))
        if not normalized_channels or any(
            not 1 <= channel <= 30 for channel in normalized_channels
        ):
            raise ValueError("RFCOMM channels must be in the range 1..30")
        self.address = address
        self.channels = normalized_channels
        self._incoming: queue.Queue[bytes | None] = queue.Queue(receive_queue_size)
        self._lock = threading.RLock()
        self._device: Any = None
        self._delegate: _RFCOMMDelegate | None = None
        self._rfcomm_channel: Any = None
        self._channel_id: int | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def channel(self) -> int | None:
        with self._lock:
            return self._channel_id

    def connect(self, timeout: float = 20.0) -> None:
        if self.connected:
            return
        if threading.current_thread() is not threading.main_thread():
            raise SoundbarConnectionError(
                "macOS IOBluetooth connections must be opened on the main thread"
            )
        self.close()
        self._clear_incoming()
        with objc.autorelease_pool():
            device = IOBluetooth.IOBluetoothDevice.deviceWithAddressString_(
                self.address
            )
            if device is None:
                raise SoundbarConnectionError(
                    f"macOS does not know Bluetooth device {self.address}"
                )
            if not device.isPaired():
                raise SoundbarConnectionError(
                    f"{device.name() or self.address} is not paired; pair it in macOS Bluetooth Settings first"
                )
            delegate = _RFCOMMDelegate.alloc().init()
            delegate.transport = self
            failures: list[str] = []
            for channel_id in self._candidate_channels(device):
                status, rfcomm_channel = (
                    device.openRFCOMMChannelSync_withChannelID_delegate_(
                        None, channel_id, delegate
                    )
                )
                if status == 0 and rfcomm_channel is not None:
                    with self._lock:
                        self._device = device
                        self._delegate = delegate
                        self._rfcomm_channel = rfcomm_channel
                        self._channel_id = channel_id
                        self._connected = True
                    return
                failures.append(
                    f"channel {channel_id}: 0x{int(status) & 0xFFFFFFFF:08x}"
                )
        details = ", ".join(failures) or "no cached SPP channels"
        raise SoundbarConnectionError(f"unable to open {self.address} ({details})")

    def service(self, timeout: float = 0.0) -> None:
        if threading.current_thread() is not threading.main_thread():
            raise TransportError(
                "macOS IOBluetooth events must be serviced on the main thread"
            )
        NSRunLoop.currentRunLoop().runMode_beforeDate_(
            NSDefaultRunLoopMode,
            NSDate.dateWithTimeIntervalSinceNow_(max(0.0, timeout)),
        )

    def read(self, timeout: float = 0.5) -> bytes:
        try:
            data = self._incoming.get(timeout=timeout)
        except queue.Empty:
            return b""
        if data is None:
            raise TransportDisconnected("RFCOMM channel closed")
        return data

    def write(self, data: bytes, timeout: float = 5.0) -> None:
        del timeout
        payload = bytes(data)
        with self._lock:
            if not self._connected or self._rfcomm_channel is None:
                raise TransportDisconnected("RFCOMM channel is not open")
            status = int(self._rfcomm_channel.writeSync_length_(payload, len(payload)))
        if status != 0:
            raise TransportError(
                f"IOBluetooth writeSync failed with IOReturn 0x{status & 0xFFFFFFFF:08x}"
            )

    def close(self) -> None:
        with self._lock:
            rfcomm_channel = self._rfcomm_channel
            delegate = self._delegate
            self._connected = False
            self._channel_id = None
            self._rfcomm_channel = None
            self._delegate = None
            self._device = None
        if delegate is not None:
            delegate.transport = None
        if rfcomm_channel is not None:
            rfcomm_channel.setDelegate_(None)
            rfcomm_channel.closeChannel()
        self._signal_closed()

    def _candidate_channels(self, device: Any) -> tuple[int, ...]:
        discovered: list[int] = []
        for service in device.services() or ():
            try:
                status, channel = service.getRFCOMMChannelID_(None)
                name = service.getServiceName() or ""
            except (AttributeError, TypeError, ValueError, objc.error):
                continue
            if status == 0 and channel and "SPP" in name.upper():
                discovered.append(int(channel))
        return tuple(dict.fromkeys((*self.channels, *discovered)))

    def _receive(self, data: bytes) -> None:
        if not data:
            return
        try:
            self._incoming.put_nowait(data)
        except queue.Full:
            self._incoming.get_nowait()
            self._incoming.put_nowait(data)

    def _channel_closed(self) -> None:
        with self._lock:
            self._connected = False
            self._channel_id = None
        self._signal_closed()

    def _signal_closed(self) -> None:
        try:
            self._incoming.put_nowait(None)
        except queue.Full:
            self._incoming.get_nowait()
            self._incoming.put_nowait(None)

    def _clear_incoming(self) -> None:
        while True:
            try:
                self._incoming.get_nowait()
            except queue.Empty:
                return

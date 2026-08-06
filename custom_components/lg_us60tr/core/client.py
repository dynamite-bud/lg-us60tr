from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from typing import Self

from .commands import (
    CONTROL_PREFIX,
    HANDSHAKE_STAGE,
    HANDSHAKE_START,
    INITIAL_CAPABILITY_QUERY,
    PREFIX_QUERY,
    SESSION_READY,
    SOUND_MODE_REGISTRATION,
    center_level_command,
    input_source_command,
    night_mode_command,
    rear_level_command,
    snapshot_query,
    sound_mode_command,
    volume_command,
    woofer_command,
)
from .protocol import Frame, FrameParser
from .state import SOUND_MODES_BY_DISPLAY_NAME, InputSource, SoundbarState, SoundMode
from .transport import CommandTimeoutError, RFCOMMTransport, TransportDisconnected

_LOGGER = logging.getLogger(__name__)

StateListener = Callable[[SoundbarState], None]

_LEVEL_RESPONSE_FIELDS = {
    0x0D1B: ("woofer_level", "woofer_min", "woofer_max", "woofer"),
    0x0D21: ("rear_level", "rear_min", "rear_max", "rear"),
    0x0D26: ("center_level", "center_min", "center_max", "center"),
}


def _signed_byte(value: int) -> int:
    return value - 256 if value >= 128 else value


class SoundbarClient:
    """Synchronous, thread-safe client for the ThinQ soundbar SPP protocol."""

    def __init__(
        self, transport: RFCOMMTransport, *, listener: StateListener | None = None
    ) -> None:
        self._transport = transport
        self._listener = listener
        self._parser = FrameParser()
        self._state = SoundbarState(control_prefix=CONTROL_PREFIX)
        self._condition = threading.Condition()
        self._observations: Counter[str] = Counter()
        self._reader_stop = threading.Event()
        self._reader: threading.Thread | None = None
        self._reader_error: BaseException | None = None

    @property
    def state(self) -> SoundbarState:
        with self._condition:
            return self._state

    @property
    def channel(self) -> int | None:
        return self._transport.channel

    def connect(self, timeout: float = 5.0) -> SoundbarState:
        _LOGGER.debug("Starting soundbar protocol session")
        self._transport.connect(timeout=timeout)
        self._set_state(connected=True)
        self._reader_stop.clear()
        self._reader_error = None
        self._reader = threading.Thread(
            target=self._read_loop, name="lg-us60tr-reader", daemon=True
        )
        self._reader.start()
        try:
            self.send_frame(HANDSHAKE_START)
            time.sleep(0.10)
            self.send_frame(INITIAL_CAPABILITY_QUERY)
            time.sleep(0.05)
            self.send_frame(HANDSHAKE_STAGE)
            self.send_frame(SOUND_MODE_REGISTRATION)
            # Reconnects do not always announce the active prefix. Query it
            # explicitly instead of depending on the initial capability burst.
            self.send_frame(PREFIX_QUERY)
            self._wait_for(lambda state: state.active_prefix is not None, timeout)
            self.send_frame(SESSION_READY)
            state = self.query_state(timeout=timeout)
            _LOGGER.info(
                "Soundbar protocol session ready on RFCOMM channel %s", self.channel
            )
            return state
        except BaseException:
            _LOGGER.exception("Soundbar protocol initialization failed")
            self.close()
            raise

    def close(self) -> None:
        _LOGGER.debug("Closing soundbar protocol session")
        self._reader_stop.set()
        self._transport.close()
        reader = self._reader
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=2.0)
        self._reader = None
        self._set_state(connected=False)

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def query_state(self, timeout: float = 3.0) -> SoundbarState:
        _LOGGER.debug("Querying complete soundbar state")
        prefix_seen = self._observation("prefix")
        self.send_frame(PREFIX_QUERY)
        self._wait_for(
            lambda state: (
                self._observation("prefix") > prefix_seen
                and state.active_prefix is not None
            ),
            timeout,
        )
        prefix = self._require_control_prefix()
        before = {
            name: self._observation(name)
            for name in ("volume", "woofer", "center", "rear", "night")
        }
        self.send_frame(snapshot_query(prefix))
        self.send_frame(woofer_command())
        self.send_frame(center_level_command())
        self.send_frame(rear_level_command())
        self.send_frame(night_mode_command(prefix))
        self._wait_for(
            lambda state: (
                all(self._observation(name) > count for name, count in before.items())
                and state.volume is not None
                and state.woofer_level is not None
                and state.center_level is not None
                and state.rear_level is not None
                and state.night_mode is not None
            ),
            timeout,
        )
        state = self.state
        _LOGGER.debug("Soundbar state query completed: %s", state)
        return state

    def set_input_source(
        self,
        source: InputSource | str,
        timeout: float = 3.0,
    ) -> SoundbarState:
        resolved = (
            InputSource.from_name(source)
            if isinstance(source, str)
            else InputSource(source)
        )
        if self.state.input_source == resolved:
            return self.state
        before = self._observation("input_source")
        self.send_frame(input_source_command(resolved))
        self._wait_for(
            lambda state: (
                self._observation("input_source") > before
                and state.input_source == resolved
            ),
            timeout,
        )
        return self.state

    def set_volume(self, volume: int, timeout: float = 3.0) -> SoundbarState:
        if not 0 <= volume <= 100:
            raise ValueError("volume must be in the range 0..100")
        if self.state.volume == volume:
            return self.state
        before = self._observation("volume")
        self.send_frame(volume_command(self._require_control_prefix(), volume))
        self._wait_for(
            lambda state: (
                self._observation("volume") > before and state.volume == volume
            ),
            timeout,
        )
        return self.state

    def set_sound_mode(
        self, mode: SoundMode | str, timeout: float = 3.0
    ) -> SoundbarState:
        resolved = (
            SoundMode.from_name(mode) if isinstance(mode, str) else SoundMode(mode)
        )
        if self.state.sound_mode == resolved:
            return self.state
        before = self._observation("mode")
        self.send_frame(sound_mode_command(self._require_control_prefix(), resolved))
        self._wait_for(
            lambda state: (
                self._observation("mode") > before and state.sound_mode == resolved
            ),
            timeout,
        )
        return self.state

    def set_woofer_level(self, level: int, timeout: float = 3.0) -> SoundbarState:
        state = self.state
        if not state.woofer_min <= level <= state.woofer_max:
            raise ValueError(
                f"woofer level must be in the range {state.woofer_min}..{state.woofer_max}"
            )
        if state.woofer_level == level:
            return state
        before = self._observation("woofer")
        self.send_frame(woofer_command(level))
        self._wait_for(
            lambda current: (
                self._observation("woofer") > before and current.woofer_level == level
            ),
            timeout,
        )
        return self.state

    def set_center_level(self, level: int, timeout: float = 3.0) -> SoundbarState:
        state = self.state
        if not state.center_min <= level <= state.center_max:
            raise ValueError(
                f"center level must be in the range {state.center_min}..{state.center_max}"
            )
        if state.center_level == level:
            return state
        before = self._observation("center")
        self.send_frame(center_level_command(level))
        self._wait_for(
            lambda current: (
                self._observation("center") > before and current.center_level == level
            ),
            timeout,
        )
        return self.state

    def set_rear_level(self, level: int, timeout: float = 3.0) -> SoundbarState:
        state = self.state
        if not state.rear_min <= level <= state.rear_max:
            raise ValueError(
                f"rear level must be in the range {state.rear_min}..{state.rear_max}"
            )
        if state.rear_level == level:
            return state
        before = self._observation("rear")
        self.send_frame(rear_level_command(level))
        self._wait_for(
            lambda current: (
                self._observation("rear") > before and current.rear_level == level
            ),
            timeout,
        )
        return self.state

    def set_night_mode(self, enabled: bool, timeout: float = 3.0) -> SoundbarState:
        if self.state.night_mode is enabled:
            return self.state
        before = self._observation("night")
        self.send_frame(night_mode_command(self._require_active_prefix(), enabled))
        self._wait_for(
            lambda state: (
                self._observation("night") > before and state.night_mode is enabled
            ),
            timeout,
        )
        return self.state

    def send_command(self, major: int, minor: int, payload: bytes = b"") -> None:
        """Send a raw research frame; typed integrations should not expose this method."""
        self.send_frame(Frame(major, minor, payload))

    def send_frame(self, frame: Frame) -> None:
        if not self._transport.connected:
            raise TransportDisconnected("soundbar is not connected")
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Protocol TX major=0x%02X minor=0x%02X payload=%s",
                frame.major,
                frame.minor,
                frame.payload.hex(" "),
            )
        self._transport.write(frame.encode())

    def _read_loop(self) -> None:
        try:
            while not self._reader_stop.is_set():
                data = self._transport.read(0.25)
                for frame in self._parser.feed(data):
                    self._handle_frame(frame)
        except TransportDisconnected as error:
            if self._reader_stop.is_set():
                _LOGGER.debug("Soundbar reader stopped: %s", error)
            else:
                _LOGGER.warning("Soundbar reader disconnected: %s", error)
        except Exception as error:
            # This thread boundary must relay unexpected parser/transport failures.
            _LOGGER.exception("Unexpected soundbar reader failure")
            self._reader_error = error
        finally:
            self._set_state(connected=False)

    def _handle_frame(self, frame: Frame) -> None:
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Protocol RX major=0x%02X minor=0x%02X payload=%s",
                frame.major,
                frame.minor,
                frame.payload.hex(" "),
            )
        payload = frame.payload
        updates: dict[str, object] = {}
        observed: set[str] = set()

        if frame.command == 0x000B and len(payload) == 1:
            active_prefix = payload[0]
            input_source = InputSource.from_active_prefix(active_prefix)
            updates["active_prefix"] = active_prefix
            updates["input_source"] = input_source
            observed.add("prefix")
            if input_source is not None:
                observed.add("input_source")
        elif frame.minor == 0x03 and len(payload) >= 4 and payload[2] == 0x64:
            updates["volume"] = payload[3]
            observed.add("volume")
            display_name = (
                payload[17:].rstrip(b"\x00").decode("ascii", errors="ignore").upper()
            )
            mode = SOUND_MODES_BY_DISPLAY_NAME.get(display_name)
            if mode is not None:
                updates["sound_mode_name"] = display_name
                updates["sound_mode"] = mode
                observed.add("mode")
        elif frame.minor == 0x02 and len(payload) == 2 and payload[0] == 0x64:
            updates["volume"] = payload[1]
            observed.add("volume")
        elif frame.minor == 0x1F and len(payload) > 1:
            if len(payload) == 2 and payload[0] == 0:
                try:
                    mode = SoundMode(payload[1])
                    updates["sound_mode"] = mode
                    updates["sound_mode_name"] = mode.label.upper()
                    observed.add("mode")
                except ValueError:
                    pass
            elif len(payload) == 9 and payload[0] == 0x05:
                modes = tuple(
                    mode
                    for code in payload[1:]
                    if (mode := SoundMode._value2member_map_.get(code))
                )
                if modes:
                    updates["available_modes"] = modes
                    observed.add("available_modes")
            else:
                raw_name = payload[1:].rstrip(b"\x00")
                if raw_name and all(0x20 <= byte <= 0x7E for byte in raw_name):
                    display_name = raw_name.decode("ascii").upper()
                    updates["sound_mode_name"] = display_name
                    mode = SOUND_MODES_BY_DISPLAY_NAME.get(display_name)
                    if mode is not None:
                        updates["sound_mode"] = mode
                        observed.add("mode")
        elif (
            payload
            and (level_fields := _LEVEL_RESPONSE_FIELDS.get(frame.command)) is not None
        ):
            level_field, min_field, max_field, observation = level_fields
            updates[level_field] = _signed_byte(payload[0])
            observed.add(observation)
            if len(payload) >= 3:
                updates[min_field] = _signed_byte(payload[1])
                updates[max_field] = _signed_byte(payload[2])
        elif frame.minor == 0x4A and len(payload) == 1:
            updates["night_mode"] = bool(payload[0])
            observed.add("night")

        if updates or observed:
            self._record(updates, observed)

    def _record(self, updates: dict[str, object], observed: set[str]) -> None:
        listener: StateListener | None = None
        new_state: SoundbarState
        with self._condition:
            for name in observed:
                self._observations[name] += 1
            new_state = replace(self._state, **updates) if updates else self._state
            changed = new_state != self._state
            if changed:
                self._state = new_state
                listener = self._listener
            self._condition.notify_all()
        if changed:
            _LOGGER.debug("Soundbar state updated: %s", new_state)
        if listener is not None:
            listener(new_state)

    def _set_state(self, **updates: object) -> None:
        self._record(updates, set())

    def _wait_for(
        self, predicate: Callable[[SoundbarState], bool], timeout: float
    ) -> None:
        deadline = time.monotonic() + timeout
        while True:
            with self._condition:
                if predicate(self._state):
                    return
                if self._reader_error is not None:
                    raise TransportDisconnected(
                        "soundbar reader stopped"
                    ) from self._reader_error
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _LOGGER.warning(
                        "Soundbar command confirmation timed out after %.1fs", timeout
                    )
                    raise CommandTimeoutError(
                        f"soundbar did not confirm command within {timeout:.1f}s"
                    )
            interval = min(remaining, 0.02)
            self._transport.service(interval)
            with self._condition:
                if predicate(self._state):
                    return
                self._condition.wait(
                    min(interval, max(0.0, deadline - time.monotonic()))
                )

    def _observation(self, name: str) -> int:
        return self._observations[name]

    def _require_control_prefix(self) -> int:
        prefix = self.state.control_prefix
        if prefix is None:
            raise CommandTimeoutError("soundbar did not provide a control prefix")
        return prefix

    def _require_active_prefix(self) -> int:
        prefix = self.state.active_prefix
        if prefix is None:
            raise CommandTimeoutError("soundbar did not provide an active prefix")
        return prefix

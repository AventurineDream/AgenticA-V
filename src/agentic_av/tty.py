"""Run the player in an alternate-screen TTY with no runtime dependencies.

The terminal is returned to its prior mode even when rendering or key handling
raises, and when SIGTERM asks the process to stop. Cleanup restores canonical
mode, echo, the cursor, and the primary screen, then puts the previous SIGTERM
handler back. This module is the sole terminal I/O boundary; paint remains pure.
Incomplete CSI sequences are held across reads; a lone Escape waits out a
short silence so a split arrow is not Escape plus a letter.
"""

from __future__ import annotations

import fcntl
import os
import select
import signal
import struct
import sys
import termios
import time
import tty
from collections.abc import Callable

from agentic_av.omarchy import load_omarchy
from agentic_av.paint import FrameRequest, compose, render_ansi
from agentic_av.palette import PaletteError
from agentic_av.session import Session

_ESC = "\x1b"
# 50 ms joins a CSI split across read(fd, 64) without making a lone Escape
# wait through the 250 ms idle poll. ncurses' 1 s ESCDELAY would feel stuck.
ESCAPE_HOLD_S = 0.05
_CSI = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end"}


def _take_one(text: str) -> tuple[str | None, int, bool]:
    """Take one action from the front of `text`.

    Returns:
        Key or None, characters consumed, and whether the remainder is an
        incomplete escape prefix that must be held.
    """
    char = text[0]
    if char == _ESC:
        if len(text) == 1 or (text[1] == "[" and not _csi_final(text)):
            return None, 0, True
        if text[1] != "[":
            return "esc", 1, False
        end = _csi_end(text)
        return _CSI.get(text[end], "unknown"), end + 1, False
    if char == "\x03":
        return "quit", 1, False
    if char in ("\r", "\n"):
        return "enter", 1, False
    if char in ("\x7f", "\x08"):
        return "backspace", 1, False
    if char.isprintable():
        return char, 1, False
    return None, 1, False


def _csi_end(text: str) -> int:
    """Return the index of the CSI final byte, or the length if it is absent."""
    end = 2
    while end < len(text) and not text[end].isalpha() and text[end] != "~":
        end += 1
    return end


def _csi_final(text: str) -> bool:
    """Report whether `text` contains a finished CSI sequence."""
    end = _csi_end(text)
    return end < len(text) and (text[end].isalpha() or text[end] == "~")


class KeyDecoder:
    """Join escape sequences split across raw ``read(fd, 64)`` calls.

    ``ESC [`` then ``C`` becomes ``right``. A lone Escape is emitted only after
    ``hold_s`` seconds of silence, so the gallery still closes.
    """

    def __init__(
        self, *, clock: Callable[[], float] | None = None, hold_s: float = ESCAPE_HOLD_S
    ) -> None:
        """Hold incomplete escapes until more bytes arrive or silence elapses.

        Args:
            clock: Monotonic time source in seconds. Tests inject this.
            hold_s: Silence, in seconds, before a lone Escape is emitted.
        """
        self._clock = clock or time.monotonic
        self._hold_s = hold_s
        self._pending = ""
        self._held_since: float | None = None

    def feed(self, data: bytes, *, now: float | None = None) -> list[str]:
        """Append one read and return actions that are now complete.

        Args:
            data: Next raw chunk. Empty input does not restart the silence timer.
            now: Optional monotonic time in seconds. Overrides `clock`.

        Returns:
            Named actions. An incomplete escape prefix is retained.
        """
        moment = self._moment(now)
        if data:
            self._pending += data.decode("utf-8", errors="ignore")
            # Silence is measured from the latest byte, not the first ESC.
            self._held_since = moment
        return self._take_complete()

    def flush(self, *, now: float | None = None) -> list[str]:
        """Emit a held Escape once `hold_s` has elapsed with no continuation.

        Args:
            now: Optional monotonic time in seconds. Overrides `clock`.

        Returns:
            ``['esc']`` after the hold, else an empty list. An unfinished CSI
            is dropped rather than replayed as digits, which would change themes.
        """
        moment = self._moment(now)
        if not self._pending or self._held_since is None:
            return []
        if moment - self._held_since < self._hold_s or not _take_one(self._pending)[2]:
            return []
        self._pending = ""
        self._held_since = None
        return ["esc"]

    def hold_remaining(self, *, now: float | None = None) -> float | None:
        """Return seconds until a held Escape should be flushed.

        Args:
            now: Optional monotonic time in seconds. Overrides `clock`.

        Returns:
            Remaining silence in seconds, or None when no escape prefix is held.
        """
        if self._held_since is None or not self._pending.startswith(_ESC):
            return None
        return max(0.0, self._hold_s - (self._moment(now) - self._held_since))

    def _moment(self, now: float | None) -> float:
        return self._clock() if now is None else now

    def _take_complete(self) -> list[str]:
        keys: list[str] = []
        while self._pending:
            key, consumed, incomplete = _take_one(self._pending)
            if incomplete:
                break
            if key is not None:
                keys.append(key)
            self._pending = self._pending[consumed:]
        if not self._pending:
            self._held_since = None
        return keys


def parse_keys(data: bytes) -> list[str]:
    """Parse a finished chunk into named actions.

    A trailing Escape is resolved immediately. Interactive reads must use
    `KeyDecoder` so a sequence split across ``read(fd, 64)`` is not treated
    as Escape plus the next chunk.

    Args:
        data: Bytes from one complete read, possibly containing several keys.

    Returns:
        Key names for letters, controls, and common CSI navigation keys.
    """
    decoder = KeyDecoder()
    keys = decoder.feed(data, now=0.0)
    keys.extend(decoder.flush(now=ESCAPE_HOLD_S))
    return keys


def _size(fd: int) -> tuple[int, int]:
    """Read current TTY rows and columns, with a usable fallback."""
    try:
        rows, columns, _, _ = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8))
        return max(1, columns), max(1, rows)
    except OSError:
        return 80, 24


def _terminal_frame(frame: str) -> str:
    """Convert the painter's LF rows to CRLF for raw-mode terminal output.

    `tty.setraw` disables OPOST, including ONLCR, so bare line feeds do not
    reset the column. Preview output remains LF-only.
    """
    return frame.replace("\n", "\r\n")


def _draw(session: Session, width: int, height: int) -> str:
    """Compose one full-screen frame from current session state.

    Still motion paints the held program. The playhead may already be in the
    next chapter; that position still drives the meter, not the picture.
    """
    position = session.playhead.position
    program_index, program = session.visual_program()
    # Commit once per frame. Scaling absolute position would rewind reduced motion.
    field_time = session.advance_visual_time()
    request = FrameRequest(
        show=session.show,
        palette=session.palette,
        themes=session.themes,
        width=width,
        height=height,
        position_s=position,
        playing=session.playhead.playing,
        rate=session.playhead.rate,
        program=program,
        program_index=program_index,
        theme_index=session.gallery_index,
        mode=session.mode,
        motion=session.motion,
        field_time_s=field_time,
        color_mode=session.color_mode,
        sync_note=session.omarchy_note,
    )
    return render_ansi(compose(request), session.color_mode)


def _set_theme(session: Session, theme_index: int) -> None:
    """Apply one built-in palette and clear any Omarchy status note.

    Args:
        session: Session whose palette and gallery selection are updated.
        theme_index: Built-in index. A negative index is no selection and is
            ignored so it cannot wrap onto the last palette.
    """
    count = len(session.themes)
    if count == 0 or theme_index < 0:
        return
    session.gallery_index = theme_index % count
    session.palette = session.themes[session.gallery_index]
    session.theme_id = session.palette.name
    session.omarchy_note = ""


def _step_gallery(session: Session, step: int) -> None:
    """Move gallery selection by one card, including from no selection.

    Args:
        session: Active session. A negative gallery index means nothing is selected.
        step: +1 toward the next built-in, -1 toward the previous.
    """
    count = len(session.themes)
    if count == 0:
        return
    if session.gallery_index < 0:
        session.gallery_index = 0 if step > 0 else count - 1
        return
    session.gallery_index = (session.gallery_index + step) % count


def _sync_omarchy(session: Session) -> None:
    """Refresh Omarchy colors, preserving the last good palette on failure."""
    try:
        current = load_omarchy()
    except PaletteError:
        session.omarchy_note = "unavailable"
        return
    session.omarchy = current
    session.palette = current.palette
    session.theme_id = "omarchy"
    session.omarchy_note = "ok"
    session.align_gallery_index()


def _handle(session: Session, key: str) -> bool:
    """Apply one key action; return False only when the player should quit.

    q and Ctrl-C quit from the stage, help, and the gallery. Esc returns to
    the stage and does not quit. Leaving the gallery restores the cycle index
    to the active palette, so a canceled card is not the next theme. Space in
    still mode toggles transport without replacing the held picture. A negative
    gallery index is no built-in selection: Enter leaves without applying a
    palette.

    Args:
        session: Active playback and display state.
        key: Action name from ``parse_keys``.

    Returns:
        False when the player should exit. True after any other action.
    """
    rates = (0.5, 1.0, 2.0)
    if key in ("q", "quit"):
        return False
    if key in ("esc", "backspace"):
        # Gallery browsing is not a theme change. A canceled card must not
        # become the index the next `t` cycles from.
        if session.mode == "gallery":
            session.align_gallery_index()
        session.mode = "play"
        return True
    if session.mode == "gallery":
        if key in ("j", "down", "right"):
            _step_gallery(session, 1)
        elif key in ("k", "up", "left"):
            _step_gallery(session, -1)
        elif key == "enter":
            if session.gallery_index >= 0:
                _set_theme(session, session.gallery_index)
            session.mode = "play"
        elif key == "o":
            _sync_omarchy(session)
            session.mode = "play"
        return True
    if key == " ":
        session.playhead.toggle()
    elif key == "left":
        session.seek_field(-5)
    elif key == "right":
        session.seek_field(5)
    elif key in ("j", "k"):
        session.seek_chapter(-1 if key == "j" else 1)
    elif key == "t":
        next_theme = 0 if session.gallery_index < 0 else session.gallery_index + 1
        _set_theme(session, next_theme)
    elif key == "T":
        session.mode = "gallery"
    elif key == "o":
        _sync_omarchy(session)
    elif key == "m":
        modes = ("full", "reduced", "still")
        nxt = modes[(modes.index(session.motion) + 1) % len(modes)]
        session.commit_motion(nxt)
    elif key == "?":
        session.mode = "help"
    elif key in ("[", "]"):
        index = min(range(len(rates)), key=lambda i: abs(rates[i] - session.playhead.rate))
        next_index = (index + (1 if key == "]" else -1)) % len(rates)
        session.playhead.set_rate(rates[next_index])
    elif key.isdigit() and key != "0":
        _set_theme(session, int(key) - 1)
    return True


class _PlayerTerminatedError(BaseException):
    """SIGTERM arrived while the terminal may be in raw mode.

    A ``BaseException``, not a failure: the name ends in Error so the naming
    lint accepts a class in the exception hierarchy. A broad ``except Exception``
    cannot swallow it and skip the restoration in ``run_player``.
    """


def _on_sigterm(_signum: int, _frame: object) -> None:
    """Unwind raw mode through ``run_player``'s finally block.

    The default SIGTERM action ends the process without running ``finally``,
    which leaves echo off, the cursor hidden, and the alternate screen up.
    """
    raise _PlayerTerminatedError


def run_player(session: Session, *, input_stream=None, output_stream=None) -> int:
    """Run the interactive player until Q or Ctrl-C, including from help and gallery.

    SIGTERM is catchable around raw mode so it also leaves through cleanup.
    Canonical mode, echo, the cursor, and the primary screen are restored,
    and the previous SIGTERM handler is put back afterward.

    Args:
        session: Prepared session with palette, show, and transport.
        input_stream: Optional TTY stream for isolated integration tests.
        output_stream: Optional TTY stream for isolated integration tests.

    Returns:
        Zero after orderly terminal restoration, including after SIGTERM.

    Raises:
        RuntimeError: Input or output is not an interactive terminal.
    """
    source = input_stream or sys.stdin
    target = output_stream or sys.stdout
    if not source.isatty() or not target.isatty():
        raise RuntimeError("interactive play needs a TTY; use `aav preview` for captured output")
    fd = source.fileno()
    original = termios.tcgetattr(fd)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    last_sync = 0.0
    decoder = KeyDecoder()
    try:
        # Before setraw: the default SIGTERM action would skip the finally below.
        signal.signal(signal.SIGTERM, _on_sigterm)
        tty.setraw(fd)
        target.write("\x1b[?1049h\x1b[?25l")
        target.flush()
        active = True
        while active:
            width, height = _size(fd)
            frame = _terminal_frame(_draw(session, width, height))
            target.write("\x1b[H" + frame + "\x1b[J")
            target.flush()
            now = time.monotonic()
            if session.theme_id == "omarchy" and now - last_sync >= 2:
                try:
                    current = load_omarchy()
                    if session.omarchy is None or current.generation != session.omarchy.generation:
                        session.omarchy = current
                        session.palette = current.palette
                    session.omarchy_note = "ok"
                except PaletteError:
                    session.omarchy_note = "unavailable"
                last_sync = now
            timeout = 1 / 12 if session.playhead.playing or session.mode != "play" else 0.25
            # Wake for a lone Escape before the frame poll, or a 250 ms idle
            # select would both delay Esc and flush a split CSI too early.
            remaining = decoder.hold_remaining()
            if remaining is not None:
                timeout = min(timeout, remaining)
            readable, _, _ = select.select([fd], [], [], timeout)
            keys = decoder.feed(os.read(fd, 64)) if readable else decoder.flush()
            for key in keys:
                if not _handle(session, key):
                    active = False
                    break
    except _PlayerTerminatedError:
        pass
    finally:
        # The handler raises. Ignore a second SIGTERM until the screen and
        # attributes are back, or that raise would skip the rest of cleanup.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, original)
            target.write("\x1b[0m\x1b[?25h\x1b[?1049l")
            target.flush()
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
    return 0

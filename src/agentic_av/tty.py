"""Run the player in an alternate-screen TTY with no runtime dependencies.

The terminal is returned to its prior mode even when rendering or key handling
raises. This module is the sole terminal I/O boundary; paint remains pure.
"""

from __future__ import annotations

import fcntl
import select
import struct
import sys
import termios
import time
import tty

from agentic_av.omarchy import load_omarchy
from agentic_av.paint import FrameRequest, compose, render_ansi
from agentic_av.palette import PaletteError
from agentic_av.session import Session

_ESC = "\x1b"


def parse_keys(data: bytes) -> list[str]:
    """Parse available raw terminal bytes into named actions.

    Args:
        data: Bytes read from a raw terminal, potentially containing multiple keys.

    Returns:
        Key names for letters, controls, and common CSI navigation keys.
    """
    text = data.decode("utf-8", errors="ignore")
    keys: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == _ESC:
            if index + 1 == len(text):
                keys.append("esc")
                break
            if text[index + 1] != "[":
                keys.append("esc")
                index += 1
                continue
            end = index + 2
            while end < len(text) and not text[end].isalpha() and text[end] != "~":
                end += 1
            if end >= len(text):
                keys.append("esc")
                break
            sequence = text[index + 2 : end + 1]
            keys.append(
                {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end"}.get(
                    sequence[-1], "unknown"
                )
            )
            index = end + 1
            continue
        if char == "\x03":
            keys.append("quit")
        elif char in ("\r", "\n"):
            keys.append("enter")
        elif char in ("\x7f", "\x08"):
            keys.append("backspace")
        elif char == "\x1b":
            keys.append("esc")
        elif char.isprintable():
            keys.append(char)
        index += 1
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
    """Compose one full-screen frame from current session state."""
    position = session.playhead.position
    program_index, program = session.show.program_at(position)
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
    the stage and does not quit. Space in still mode toggles transport without
    replacing the held picture. A negative gallery index is no built-in
    selection: Enter leaves without applying a palette.

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


def run_player(session: Session, *, input_stream=None, output_stream=None) -> int:
    """Run the interactive player until Q or Ctrl-C, including from help and gallery.

    Args:
        session: Prepared session with palette, show, and transport.
        input_stream: Optional TTY stream for isolated integration tests.
        output_stream: Optional TTY stream for isolated integration tests.

    Returns:
        Zero after orderly terminal restoration.

    Raises:
        RuntimeError: Input or output is not an interactive terminal.
    """
    source = input_stream or sys.stdin
    target = output_stream or sys.stdout
    if not source.isatty() or not target.isatty():
        raise RuntimeError("interactive play needs a TTY; use `aav preview` for captured output")
    fd = source.fileno()
    original = termios.tcgetattr(fd)
    last_sync = 0.0
    try:
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
            readable, _, _ = select.select([fd], [], [], timeout)
            if readable:
                data = __import__("os").read(fd, 64)
                for key in parse_keys(data):
                    if not _handle(session, key):
                        active = False
                        break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
        target.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        target.flush()
    return 0

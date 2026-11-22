"""Raw input parsing, terminal frames, player keys, and signal cleanup."""

import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

from clangor_visualis_machina.omarchy import OmarchyTheme
from clangor_visualis_machina.palette import builtin_palette, builtin_palettes, palette_from_omarchy
from clangor_visualis_machina.session import Session
from clangor_visualis_machina.show import Show
from clangor_visualis_machina.transport import Playhead
from clangor_visualis_machina.tty import ESCAPE_HOLD_S, KeyDecoder, _draw, _handle, _terminal_frame


def _keys(data: bytes) -> list[str]:
    """Decode one finished chunk, resolving a trailing Escape as the input loop does."""
    decoder = KeyDecoder()
    keys = decoder.feed(data, now=0.0)
    keys.extend(decoder.flush(now=ESCAPE_HOLD_S))
    return keys


def test_key_decoder_handles_navigation_and_multiple_actions() -> None:
    assert _keys(b" \x1b[D\x1b[Ct?q\x03") == [" ", "left", "right", "t", "?", "q", "quit"]
    assert _keys(b"\x1b[A\x1b[B\r") == ["up", "down", "enter"]
    assert _keys(b"\x1b") == ["esc"]


def test_split_csi_resolves_to_navigation_not_escape() -> None:
    """ESC [ then C across reads is right, not Escape plus a printable C."""
    clock = {"now": 0.0}
    decoder = KeyDecoder(clock=lambda: clock["now"])
    assert decoder.feed(b"\x1b[") == []
    clock["now"] += 0.01
    assert decoder.feed(b"C") == ["right"]
    assert decoder.feed(b"\x1b") == []
    assert decoder.feed(b"[C") == ["right"]


def test_standalone_escape_waits_for_silence() -> None:
    """A lone Escape is held until the silence timeout, then does not swallow the next key."""
    clock = {"now": 0.0}
    decoder = KeyDecoder(clock=lambda: clock["now"])
    assert decoder.feed(b"\x1b") == []
    clock["now"] = ESCAPE_HOLD_S - 0.001
    assert decoder.flush() == []
    clock["now"] = ESCAPE_HOLD_S
    assert decoder.flush() == ["esc"]
    assert decoder.feed(b"C") == ["C"]


def test_tty_frame_uses_carriage_return_line_feeds() -> None:
    assert _terminal_frame("first\nsecond\n") == "first\r\nsecond\r\n"


class _Clock:
    """Deterministic monotonic clock for key-action tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        """Return injected monotonic time in seconds."""
        return self.now


def _live_palette():
    return palette_from_omarchy(
        {"background": "#111111", "foreground": "#eeeeee", "accent": "#336699"},
        "live",
    )


def _session(
    *,
    name: str = "tungsten",
    palette=None,
    theme_id: str | None = None,
    motion: str = "full",
    duration: float = 96.0,
    programs: tuple[str, ...] = ("garden", "aperture"),
    position: float = 0.0,
    playing: bool = False,
    field_time: float | None = None,
):
    show = Show("Reel", "study", duration, 0, programs)
    clock = _Clock()
    head = Playhead(duration, position_s=position, playing=playing, _clock=clock)
    chosen = palette if palette is not None else builtin_palette(name)
    session = Session(
        show,
        head,
        chosen,
        theme_id or name,
        builtin_palettes(),
        "none",
        motion,
        field_time_s=position if field_time is None else field_time,
        motion_anchor_s=position,
    )
    return session, head, clock


def test_quit_leaves_help_and_gallery_while_esc_returns() -> None:
    """Q and Ctrl-C exit overlays; Esc returns to the stage."""
    session, _, _ = _session()
    session.mode = "help"
    assert _handle(session, "q") is False
    session.mode = "gallery"
    assert _keys(b"\x03") == ["quit"]
    assert _handle(session, "quit") is False
    session.mode = "help"
    assert _handle(session, "esc") is True
    assert session.mode == "play"
    session.mode = "gallery"
    assert _handle(session, "esc") is True
    assert session.mode == "play"
    session.mode = "help"
    assert _handle(session, "backspace") is True
    assert session.mode == "play"
    assert _handle(session, "q") is False


def test_gallery_index_follows_builtin_and_live_palette() -> None:
    """The first theme key continues from the active built-in, or starts at the first."""
    themes = builtin_palettes()
    session, _, _ = _session(name="phosphor")
    phosphor = next(i for i, theme in enumerate(themes) if theme.name == "phosphor")
    assert session.gallery_index == phosphor
    assert _handle(session, "t") is True
    assert session.palette.name == "broadcast"
    live, _, _ = _session(palette=_live_palette(), theme_id="omarchy")
    assert live.gallery_index == -1
    assert _handle(live, "t") is True
    assert live.palette.name == "tungsten"
    assert live.gallery_index == 0
    assert _handle(live, "9") is True
    assert live.palette.name == "void"


def test_gallery_enter_without_selection_keeps_live_palette() -> None:
    """Enter must not wrap a missing selection onto the last built-in."""
    live = _live_palette()
    session, _, _ = _session(palette=live, theme_id="omarchy")
    session.mode = "gallery"
    assert session.gallery_index == -1
    assert _handle(session, "enter") is True
    assert session.palette.name == live.name
    assert session.theme_id == "omarchy"
    assert session.mode == "play"
    assert session.palette.name != builtin_palettes()[-1].name


def test_gallery_navigation_selects_from_no_builtin() -> None:
    """Down from no selection starts at the first card; up starts at the last."""
    session, _, _ = _session(palette=_live_palette(), theme_id="omarchy")
    session.mode = "gallery"
    assert _handle(session, "down") is True
    assert session.gallery_index == 0
    assert _handle(session, "enter") is True
    assert session.palette.name == "tungsten"
    assert session.mode == "play"
    session, _, _ = _session(palette=_live_palette(), theme_id="omarchy")
    session.mode = "gallery"
    assert _handle(session, "k") is True
    assert session.gallery_index == len(session.themes) - 1
    assert _handle(session, "enter") is True
    assert session.palette.name == "void"
    session.mode = "gallery"
    session.gallery_index = len(session.themes) - 1
    assert _handle(session, "j") is True
    assert session.gallery_index == 0


def test_omarchy_sync_clears_builtin_selection(monkeypatch) -> None:
    """After a live sync, the next theme key starts at the first built-in."""
    live = _live_palette()
    theme = OmarchyTheme(live, "live", Path("colors.toml"), "1")
    monkeypatch.setattr("clangor_visualis_machina.tty.load_omarchy", lambda: theme)
    session, _, _ = _session(name="carbon")
    carbon = next(i for i, item in enumerate(session.themes) if item.name == "carbon")
    assert session.gallery_index == carbon
    assert _handle(session, "o") is True
    assert session.gallery_index == -1
    assert session.theme_id == "omarchy"
    assert session.palette.name == live.name
    assert _handle(session, "t") is True
    assert session.palette.name == "tungsten"


def test_still_space_keeps_held_picture_while_seeks_update_it() -> None:
    """Pause and resume must not replace a still picture with the playhead."""
    session, head, clock = _session(
        motion="still",
        position=1.0,
        playing=True,
        programs=("garden",),
    )
    clock.now = 6.0
    assert abs(head.position - 7.0) < 1e-6
    assert _handle(session, " ") is True
    assert head.playing is False
    assert abs(session.field_time_s - 1.0) < 1e-6
    assert _handle(session, " ") is True
    assert head.playing is True
    assert abs(session.field_time_s - 1.0) < 1e-6
    assert _handle(session, "right") is True
    assert abs(session.field_time_s - head.position) < 1e-6
    assert abs(head.position - 12.0) < 1e-6
    assert _handle(session, "k") is True
    assert head.position == 0
    assert abs(session.field_time_s - head.position) < 1e-6


def test_short_show_seeks_keep_direction() -> None:
    """Right and left keep their direction when the show is ten seconds or shorter."""
    session, head, _ = _session(duration=10.0, position=6.0, programs=("garden",))
    assert _handle(session, "right") is True
    assert abs(head.position - 1.0) < 1e-6
    assert abs(session.field_time_s - 11.0) < 1e-6
    session, head, _ = _session(duration=10.0, position=1.0, programs=("garden",))
    assert _handle(session, "left") is True
    assert abs(head.position - 6.0) < 1e-6
    assert abs(session.field_time_s - (1.0 - 5.0)) < 1e-6
    session, head, _ = _session(duration=96.0, position=10.0)
    assert _handle(session, "right") is True
    assert abs(session.field_time_s - 15.0) < 1e-6
    assert _handle(session, "left") is True
    assert abs(session.field_time_s - 10.0) < 1e-6


def test_one_program_chapter_keys_follow_direction() -> None:
    """Next moves forward and previous backward even when both land on the only start."""
    session, head, _ = _session(duration=8.0, position=5.0, programs=("garden",))
    assert _handle(session, "k") is True
    assert head.position == 0
    assert abs(session.field_time_s - 8.0) < 1e-6
    session, head, _ = _session(duration=8.0, position=5.0, programs=("garden",))
    assert _handle(session, "j") is True
    assert head.position == 0
    assert abs(session.field_time_s - 0.0) < 1e-6
    session, head, _ = _session(duration=8.0, position=1.0, programs=("garden", "aperture"))
    assert _handle(session, "j") is True
    assert abs(head.position - 4.0) < 1e-6
    assert session.field_time_s < 1.0


def _crossed_still():
    """Start in aperture and let transport enter garden while still."""
    session, head, clock = _session(
        motion="still",
        position=12.0,
        playing=True,
        duration=20.0,
        programs=("garden", "aperture"),
    )
    clock.now = 10.0
    return session, head


def test_still_holds_program_across_a_chapter_until_seek() -> None:
    """Still freezes the selected program when transport crosses a chapter.

    The frame stays on Iris Study after the playhead enters garden. Leaving
    still follows the playhead. An explicit seek, then a chapter skip, updates
    the held program.
    """
    session, head = _crossed_still()
    assert abs(head.position - 2.0) < 1e-6
    assert session.show.program_at(head.position) == (0, "garden")
    held = _draw(session, 80, 24)
    assert "02  Iris Study" in held
    assert "Signal Garden" not in held
    assert abs(session.field_time_s - 12.0) < 1e-6

    resumed, resumed_head = _crossed_still()
    assert abs(resumed_head.position - 2.0) < 1e-6
    assert _handle(resumed, "m") is True
    assert resumed.motion == "full"
    resumed_frame = _draw(resumed, 80, 24)
    assert "01  Signal Garden" in resumed_frame
    assert "Iris Study" not in resumed_frame

    assert _handle(session, "right") is True
    assert abs(head.position - 7.0) < 1e-6
    updated = _draw(session, 80, 24)
    assert "01  Signal Garden" in updated
    assert "Iris Study" not in updated
    assert _handle(session, "k") is True
    assert abs(head.position - 10.0) < 1e-6
    chapter = _draw(session, 80, 24)
    assert "02  Iris Study" in chapter
    assert "Signal Garden" not in chapter


def test_gallery_cancel_cycles_from_the_active_palette() -> None:
    """Escape drops a gallery browse; the next theme key uses the stage palette."""
    session, _, _ = _session(name="tungsten")
    assert session.palette.name == "tungsten"
    assert session.gallery_index == 0
    assert _handle(session, "T") is True
    assert session.mode == "gallery"
    assert _handle(session, "down") is True
    assert session.gallery_index == 1
    assert session.palette.name == "tungsten"
    assert _handle(session, "esc") is True
    assert session.mode == "play"
    assert session.palette.name == "tungsten"
    assert session.gallery_index == 0
    assert _handle(session, "t") is True
    assert session.palette.name == "phosphor"


def _read_pty(master: int, sink: bytearray, *, wait_s: float) -> None:
    """Append bytes available on the PTY master within `wait_s` seconds."""
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        readable, _, _ = select.select([master], [], [], min(0.05, remaining))
        if not readable:
            return
        try:
            chunk = os.read(master, 65536)
        except OSError:
            return
        if not chunk:
            return
        sink.extend(chunk)


def _pty_failure(proc: subprocess.Popen[bytes], output: bytearray, detail: str) -> str:
    """Stop a hung player and format stderr plus the PTY tail for an assertion."""
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=2)
    err = proc.stderr.read() if proc.stderr is not None else b""
    return f"{detail}; code={proc.returncode} stderr={err!r} tail={bytes(output[-400:])!r}"


def test_sigterm_restores_the_terminal() -> None:
    """SIGTERM during playback exits through raw-mode cleanup.

    The waits are bounded. After the process exits, canonical mode and echo
    are back, and the cursor and primary-screen sequences were written.
    """
    master, slave = pty.openpty()
    proc = None
    output = bytearray()
    try:
        original = termios.tcgetattr(slave)[3]
        assert original & termios.ICANON
        assert original & termios.ECHO
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        src = str(root / "src")
        env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "clangor_visualis_machina",
                "play",
                "--theme",
                "tungsten",
                "--no-color",
            ],
            stdin=slave,
            stdout=slave,
            stderr=subprocess.PIPE,
            env=env,
            cwd=root,
            close_fds=True,
        )
        deadline = time.monotonic() + 5
        saw_raw = False
        while time.monotonic() < deadline:
            # Drain so a full PTY buffer cannot block the player's restore write.
            _read_pty(master, output, wait_s=0.05)
            if proc.poll() is not None:
                break
            flags = termios.tcgetattr(slave)[3]
            if not (flags & termios.ICANON) and not (flags & termios.ECHO):
                saw_raw = True
                break
        if not saw_raw:
            raise AssertionError(_pty_failure(proc, output, "player never entered raw mode"))
        proc.send_signal(signal.SIGTERM)
        exit_deadline = time.monotonic() + 5
        while proc.poll() is None and time.monotonic() < exit_deadline:
            _read_pty(master, output, wait_s=0.05)
        if proc.poll() is None:
            raise AssertionError(_pty_failure(proc, output, "SIGTERM did not stop the player"))
        _read_pty(master, output, wait_s=0.2)
        flags = termios.tcgetattr(slave)[3]
        detail = _pty_failure(proc, output, "terminal was not restored")
        assert proc.returncode == 0, detail
        assert flags & termios.ICANON, detail
        assert flags & termios.ECHO, detail
        assert flags == original, detail
        assert b"\x1b[?25h" in output, detail
        assert b"\x1b[?1049l" in output, detail
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        if proc is not None and proc.stderr is not None:
            proc.stderr.close()
        os.close(master)
        os.close(slave)

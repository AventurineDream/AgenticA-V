"""Exercise native mosaic bytes over a real PTY without media tools.

The fake controller and synthetic features isolate playback from audio hardware;
real raw-mode entry, UTF-8 output, key delivery, and terminal restoration remain.
"""

import fcntl
import os
import pty
import signal
import struct
import termios
import threading
from pathlib import Path

import numpy as np
import pytest

from agentic_av.catalog import Album, CatalogEntry, Track
from agentic_av.library import _TTY
from agentic_av.native import NativeAlbum, TrackData, play_native
from agentic_av.palette import builtin_palettes
from agentic_av.tty import _PlayerTerminatedError
from agentic_av.viz.audio import analyze


@pytest.mark.parametrize("terminate", [False, True], ids=["quit", "sigterm"])
def test_native_frame_over_pty_restores_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminate: bool
) -> None:
    """Render real Stage output before q/SIGTERM and restore canonical mode/echo."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 16, 60, 0, 0))
    original = termios.tcgetattr(slave)
    track = Track(number=1, title="PTY movement", start_s=0)
    album = Album(
        artist="Test",
        band="Test",
        title="PTY album",
        duration_s=60,
        asset="nurse-log-ground-moves-anyway.html.gz",
        tracks=(track,),
    )
    entry = CatalogEntry(album, track)
    extracted = NativeAlbum((TrackData(tmp_path / "fake.mp3", scene="root"),), "forest")
    features = analyze(np.zeros((2205, 2), dtype=np.float32))
    monkeypatch.setattr("agentic_av.native.extract_album", lambda *_args: extracted)
    monkeypatch.setattr("agentic_av.native.load_features", lambda *_args: features)
    closed = threading.Event()

    class Player:
        def get(self, _name):
            return 0.1

        def close(self):
            closed.set()

    output = bytearray()
    rendered = threading.Event()

    def drain():
        while True:
            try:
                output.extend(os.read(master, 65536))
            except OSError:
                return
            if not rendered.is_set() and b"\x1b[?2026l" in output:
                rendered.set()
                if terminate:
                    os.kill(os.getpid(), signal.SIGTERM)
                else:
                    os.write(master, b"q")

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    timed_out = threading.Event()

    def rescue():
        timed_out.set()
        os.write(master, b"q")

    watchdog = threading.Timer(5, rescue)
    watchdog.start()
    try:
        with (
            open(slave, "rb", buffering=0, closefd=False) as source,
            open(slave, "w", encoding="utf-8", closefd=False) as target,
        ):
            terminal = _TTY(source, target)
            terminal.enter()
            try:
                if terminate:
                    with pytest.raises(_PlayerTerminatedError):
                        play_native(
                            entry,
                            [entry],
                            builtin_palettes()[0],
                            "none",
                            glyphs="half",
                            input_stream=source,
                            output_stream=target,
                            player_factory=lambda *_args: Player(),
                        )
                else:
                    assert (
                        play_native(
                            entry,
                            [entry],
                            builtin_palettes()[0],
                            "none",
                            glyphs="half",
                            input_stream=source,
                            output_stream=target,
                            player_factory=lambda *_args: Player(),
                        )
                        == "quit"
                    )
            finally:
                terminal.leave()
            assert termios.tcgetattr(slave) == original
    finally:
        watchdog.cancel()
        os.close(slave)
        reader.join(timeout=2)
        os.close(master)
    assert rendered.is_set() and not timed_out.is_set()
    assert closed.is_set()
    assert b"\x1b[?2026h" in output
    assert b"\x1b[?25h" in output
    assert b"q back" in output

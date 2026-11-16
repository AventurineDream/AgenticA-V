"""Tests for native album playback: extraction, frames, players, and the loop.

The bundled archives are 70-112 MB of HTML, so tests build tiny synthetic
`.html.gz` documents in each album's shape and pass them as `source`. A fake
player stands in for mpv/ffplay, and a pipe stands in for the TTY, so
`play_native` never touches real audio or the terminal. Every loop run has a
watchdog, so a regression that stops a key from landing fails instead of
hanging the suite.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from agentic_av.catalog import Album, CatalogEntry, Track
from agentic_av.library import AlbumError
from agentic_av.native import (
    Ffplay,
    Mpv,
    NativeError,
    _player_for,
    _scene_rows,
    _status_line,
    extract_album,
    play_native,
)
from agentic_av.paint import render_ansi
from agentic_av.palette import builtin_palettes
from agentic_av.scenes import FAMILIES, EventIndex, normalize_events
from agentic_av.tty import _PlayerTerminatedError

FOREST = "nurse-log-ground-moves-anyway.html.gz"
AQUATIC = "drowning-collective-are-we-fish.html.gz"
COUPON = "coupon-seance-saturn.html.gz"
ROOMS = "quiet-machinery-atlas-unlit-rooms.html.gz"

# Distinct payloads prove each movement gets its own file.
NAMES = (b"ONE", b"TWO", b"THREE")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _gz(html: str) -> bytes:
    return gzip.compress(html.encode("utf-8"))


def _forest_html(count: int = 2) -> str:
    """Nurse-Log shape: `window.NURSE_LOG_ALBUM` with a data URI per track."""
    scenes = ("root", "rain", "spiral")
    tracks = [
        {
            "number": index + 1,
            "scene": scenes[index],
            "events": [["harp", 0.0, 1.0, 60, 0.5, 0.0]] if index == 0 else [],
            "audio": f"data:audio/mpeg;base64,{_b64(NAMES[index])}",
        }
        for index in range(count)
    ]
    return f"<script>window.NURSE_LOG_ALBUM={json.dumps({'tracks': tracks})};</script>"


def _aquatic_html() -> str:
    """Drowning shape: track `audio` paths keyed into `band02-assets`."""
    events = {"tracks": [{"audio": "../audio/mix.mp3"}, {"audio": "../track-02/audio/mix.mp3"}]}
    assets = {
        "../audio/mix.mp3": f"data:audio/mpeg;base64,{_b64(b'ONE')}",
        "../track-02/audio/mix.mp3": f"data:audio/mpeg;base64,{_b64(b'TWO')}",
    }
    return (
        f"<script>window.BAND02_VISUAL_EVENTS={json.dumps(events)};</script>"
        f'<script type="application/json" id="band02-assets">{json.dumps(assets)}</script>'
    )


def _coupon_html() -> str:
    """Coupon shape: one album `<audio>` and a `const tracks=[...]` literal."""
    return (
        f'<audio id="audio" src="data:audio/mpeg;base64,{_b64(b"ONE")}"></audio>'
        "<script>const tracks=["
        "{start:0,title:'Customs',text:'01'},"
        "{start:77.5,title:'Rosin',text:'02'},"
        "{start:150,title:'Grid',text:'03'}"
        "];</script>"
    )


def _album(asset: str, starts: tuple[float, ...], duration_s: float) -> Album:
    return Album(
        artist="Test Band",
        band="Test Band",
        title="Test Album",
        duration_s=duration_s,
        asset=asset,
        tracks=tuple(
            Track(number=index + 1, title=f"Movement {index + 1}", start_s=start)
            for index, start in enumerate(starts)
        ),
    )


COUPON_ALBUM = _album(COUPON, (0.0, 77.5, 150.0), 200.0)
FOREST_ALBUM = _album(FOREST, (0.0, 60.0, 120.0), 180.0)


# --- extraction ------------------------------------------------------------


def test_per_movement_audio_gets_its_own_file(tmp_path: Path) -> None:
    """Nurse Log inlines one MP3 per movement; each plays from zero."""
    native = extract_album(FOREST, tmp_path, _gz(_forest_html()))
    assert native.family == "forest"
    assert [t.audio.read_bytes() for t in native.tracks] == [b"ONE", b"TWO"]
    assert [t.offset_s for t in native.tracks] == [0.0, 0.0]
    assert [t.scene for t in native.tracks] == ["root", "rain"]
    assert native.tracks[0].events[0][:4] == ["harp", 0.0, 1.0, 0.5]


def test_drowning_audio_resolves_through_asset_manifest(tmp_path: Path) -> None:
    native = extract_album(AQUATIC, tmp_path, _gz(_aquatic_html()))
    assert native.family == "aquatic"
    assert [t.audio.read_bytes() for t in native.tracks] == [b"ONE", b"TWO"]
    # The archive names no scenes; the original player's order applies.
    assert native.tracks[0].scene == "tidal seed"


def test_coupon_movements_share_one_mix_at_their_start(tmp_path: Path) -> None:
    native = extract_album(COUPON, tmp_path, _gz(_coupon_html()))
    assert len({t.audio for t in native.tracks}) == 1
    assert native.tracks[0].audio.read_bytes() == b"ONE"
    assert [t.offset_s for t in native.tracks] == [0.0, 77.5, 150.0]
    assert [t.scene for t in native.tracks] == ["arrival", "friction", "commerce"]


def test_repeat_plays_read_the_score_cache_not_the_archive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _gz(_forest_html())
    first = extract_album(FOREST, tmp_path, source)

    def no_decompress(_data: bytes) -> bytes:
        raise AssertionError("archive decompressed on a warm cache")

    monkeypatch.setattr("agentic_av.native.gzip.decompress", no_decompress)
    assert extract_album(FOREST, tmp_path, source) == first


def test_missing_cached_audio_forces_a_fresh_extraction(tmp_path: Path) -> None:
    source = _gz(_forest_html())
    first = extract_album(FOREST, tmp_path, source)
    first.tracks[1].audio.unlink()
    again = extract_album(FOREST, tmp_path, source)
    assert again.tracks[1].audio.read_bytes() == b"TWO"


def test_extraction_rejects_assets_outside_the_catalog(tmp_path: Path) -> None:
    with pytest.raises(AlbumError):
        extract_album("not-in-catalog.html.gz", tmp_path, _gz("<html></html>"))


@pytest.mark.parametrize(
    "html",
    [
        "<html></html>",
        '<script>window.QUIET_MACHINERY={"tracks":[{"scene":"void"}]};</script>',
    ],
    ids=["no-track-data", "movement-without-audio"],
)
def test_extraction_fails_cleanly_without_data_or_audio(tmp_path: Path, html: str) -> None:
    with pytest.raises(NativeError):
        extract_album(ROOMS, tmp_path, _gz(html))


# --- frames ------------------------------------------------------------------


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("mode", ["truecolor", "256", "none"])
def test_scene_frames_fill_the_grid_in_every_color_mode(family: str, mode: str) -> None:
    events = EventIndex.build(normalize_events({"bass": [[0.0, 2.0, 30, 0.8, 0.0, 0]]}))
    rows = _scene_rows(40, 10, family, "", 1.0, events)
    assert len(rows) == 10
    assert all(len(row) == 40 for row in rows)
    # Blank cells once carried an empty fg that the 256/truecolor paths rejected.
    assert len(render_ansi(rows, mode).split("\n")) == 10


def test_status_line_keeps_clock_and_way_out_at_80_columns() -> None:
    title = "Mall Cop on the Astral Plane Has Opinions About Saturn"
    line = _status_line(80, "PLAYING", "0:12 / 1:56", title, "Orbital traffic", "full", "")
    assert len(line) <= 80
    assert line.startswith(" PLAYING  0:12 / 1:56")
    assert line.rstrip().endswith("q back")
    noted = _status_line(80, "PAUSED", "0:12 / 1:56", title, "x", "still", "ffplay cannot seek")
    assert "0:12 / 1:56" in noted and "ffplay cannot seek" in noted and "q back" in noted
    assert "q back" in _status_line(12, "PLAYING", "0:12 / 1:56", title, "x", "full", "")


# --- playback loop -------------------------------------------------------------


class FakePlayer:
    """Stand-in for mpv: `time-pos` is the clock; records seeks and close."""

    def __init__(self, media: Path, offset: float, *, late_s: float, tick_s: float) -> None:
        self.media = media
        self.offset = offset
        self.time_pos = offset + late_s
        self.tick_s = tick_s
        self.seeks: list[float] = []
        self.closed = False

    def get(self, name: str) -> Any:
        """Report `time-pos` like mpv IPC, advancing `tick_s` per read."""
        if name != "time-pos":
            return None
        value = self.time_pos
        self.time_pos += self.tick_s
        return value

    def seek(self, seconds: float) -> None:
        """Record an absolute seek and jump the clock there."""
        self.seeks.append(seconds)
        self.time_pos = seconds

    def set_pause(self, paused: bool) -> None:
        """Pausing is not simulated."""

    def close(self) -> None:
        """Mark the player stopped."""
        self.closed = True


class _Pipe:
    """Readable fd with `fileno`, standing in for the TTY input."""

    def __init__(self, fd: int) -> None:
        self.fd = fd

    def fileno(self) -> int:
        return self.fd


class _Sink:
    """Output that keeps frames and can queue a key after the Nth frame."""

    def __init__(self, write_fd: int, quit_after: int | None) -> None:
        self.frames: list[str] = []
        self.write_fd = write_fd
        self.quit_after = quit_after

    def write(self, text: str) -> int:
        self.frames.append(text)
        # The first write is the loading line, not a playback frame.
        if self.quit_after is not None and len(self.frames) - 1 == self.quit_after:
            os.write(self.write_fd, b"q")
        return len(text)

    def flush(self) -> None:
        pass


def _play(
    tmp_path: Path,
    html: str,
    number: int,
    album: Album,
    keys: bytes,
    *,
    after_switch: bytes = b"",
    quit_after_frames: int | None = None,
    motion: str = "full",
    late_s: float = 0.0,
    tick_s: float = 0.0,
) -> tuple[list[FakePlayer], list[str]]:
    """Run `play_native` on a pipe preloaded with `keys`.

    `after_switch` is written when the second player starts: a quit in the
    same read as a track key returns before the switch. `late_s` starts only
    the first player that far into its movement. Returns the players and
    the frames written after the loading line.
    """
    entries = [CatalogEntry(album, track) for track in album.tracks]
    players: list[FakePlayer] = []
    read_fd, write_fd = os.pipe()
    os.write(write_fd, keys)
    sink = _Sink(write_fd, quit_after_frames)
    timed_out = threading.Event()

    def rescue() -> None:
        timed_out.set()
        os.write(write_fd, b"q")

    def factory(media: Path, offset: float) -> FakePlayer:
        late = late_s if not players else 0.0
        players.append(FakePlayer(media, offset, late_s=late, tick_s=tick_s))
        if len(players) == 2 and after_switch:
            os.write(write_fd, after_switch)
        return players[-1]

    watchdog = threading.Timer(5.0, rescue)
    watchdog.start()
    try:
        result = play_native(
            entries[number - 1],
            entries,
            builtin_palettes()[0],
            "none",
            motion=motion,
            input_stream=_Pipe(read_fd),
            output_stream=sink,
            cache_home=tmp_path,
            source=_gz(html),
            player_factory=factory,
        )
    finally:
        watchdog.cancel()
        os.close(read_fd)
        os.close(write_fd)
    assert not timed_out.is_set(), "playback ignored its keys; the watchdog quit it"
    assert result == "quit"
    return players, sink.frames[1:]


def test_playback_starts_the_selected_movement_and_q_stops_it(tmp_path: Path) -> None:
    players, _ = _play(tmp_path, _coupon_html(), 2, COUPON_ALBUM, b"q")
    assert [p.offset for p in players] == [77.5]
    assert players[0].closed


def test_seeks_are_relative_to_the_movement_in_a_shared_mix(tmp_path: Path) -> None:
    """Two arrows in one read both count, from movement 2's start at 77.5 s."""
    players, _ = _play(
        tmp_path, _coupon_html(), 2, COUPON_ALBUM, b"\x1b[C\x1b[C", quit_after_frames=2
    )
    assert players[0].seeks[:2] == [87.5, 97.5]


def test_n_and_p_step_through_per_movement_files(tmp_path: Path) -> None:
    forward, _ = _play(tmp_path, _forest_html(3), 2, FOREST_ALBUM, b"n", after_switch=b"q")
    back, _ = _play(tmp_path, _forest_html(3), 2, FOREST_ALBUM, b"p", after_switch=b"q")
    assert [p.media.read_bytes() for p in forward] == [b"TWO", b"THREE"]
    assert [p.media.read_bytes() for p in back] == [b"TWO", b"ONE"]
    assert all(p.closed for p in forward + back)


def test_p_at_a_movement_end_goes_back_not_forward(tmp_path: Path) -> None:
    """Auto-advance must not override a key the listener pressed."""
    players, _ = _play(
        tmp_path, _forest_html(3), 2, FOREST_ALBUM, b"p", after_switch=b"q", late_s=1000.0
    )
    assert [p.media.read_bytes() for p in players] == [b"TWO", b"ONE"]


def test_previous_movement_is_not_skipped_by_a_stale_position(tmp_path: Path) -> None:
    """`p` from Coupon's second movement lands on the first and stays there.

    The second movement's clock reads 77.5 s into the shared mix, exactly the
    first movement's length; judging the new movement by it would skip on.
    """
    players, _ = _play(tmp_path, _coupon_html(), 2, COUPON_ALBUM, b"p", after_switch=b"q")
    assert [p.offset for p in players] == [77.5, 0.0]


def _scene_part(frame: str) -> list[str]:
    """Frame lines without the status row, whose clock always moves."""
    return frame.split("\n")[:-1]


@pytest.mark.parametrize(
    ("motion", "keys", "held"),
    [("full", b"", False), ("still", b"", True), ("full", b"m", True)],
    ids=["full-moves", "still-holds", "m-holds"],
)
def test_motion_modes_hold_or_move_the_picture(
    tmp_path: Path, motion: str, keys: bytes, held: bool
) -> None:
    _, frames = _play(
        tmp_path,
        _forest_html(),
        1,
        FOREST_ALBUM,
        keys,
        quit_after_frames=3,
        motion=motion,
        tick_s=7.0,
    )
    assert (_scene_part(frames[1]) == _scene_part(frames[2])) is held


# --- players -----------------------------------------------------------------


def _spawn_sleeper(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.Popen[bytes]]:
    """Make the players launch `sleep 30` instead of mpv/ffplay."""
    real = subprocess.Popen
    spawned: list[subprocess.Popen[bytes]] = []

    def fake(_args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        spawned.append(real(["sleep", "30"], **kwargs))
        return spawned[-1]

    monkeypatch.setattr("agentic_av.native.subprocess.Popen", fake)
    return spawned


def _state(pid: int) -> str:
    """Linux process state letter from /proc (T = stopped)."""
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="needs Linux /proc")
def test_ffplay_pause_stops_the_audio_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ffplay has no pause input here, so pause must stop the process itself."""
    spawned = _spawn_sleeper(monkeypatch)
    player = Ffplay(tmp_path / "a.mp3", 0.0)
    pid = spawned[0].pid
    try:
        player.set_pause(True)
        deadline = time.monotonic() + 2.0
        while _state(pid) != "T" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert _state(pid) == "T"
        player.set_pause(False)
        deadline = time.monotonic() + 2.0
        while _state(pid) == "T" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert _state(pid) != "T"
        player.set_pause(True)
    finally:
        player.close()
    # A stopped child still ends on SIGTERM rather than waiting out the kill.
    assert spawned[0].returncode == -signal.SIGTERM


def test_sigterm_during_mpv_startup_leaves_no_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spawned = _spawn_sleeper(monkeypatch)
    real_sleep = time.sleep
    fired: list[bool] = []

    def interrupted(seconds: float) -> None:
        # The first wait for mpv's socket is where SIGTERM lands; later
        # sleeps (subprocess's own waits) must behave normally.
        if not fired:
            fired.append(True)
            raise _PlayerTerminatedError
        real_sleep(seconds)

    monkeypatch.setattr("agentic_av.native.time.sleep", interrupted)
    with pytest.raises(_PlayerTerminatedError):
        Mpv(tmp_path / "a.mp3", 0.0)
    assert spawned[0].poll() is not None


def test_missing_players_raise_a_listener_facing_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("agentic_av.native._mpv_available", lambda: False)
    monkeypatch.setattr("agentic_av.native._ffplay_available", lambda: False)
    with pytest.raises(NativeError, match="install mpv or ffplay"):
        _player_for(tmp_path / "a.mp3", 0.0)

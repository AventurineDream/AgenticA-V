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
import dataclasses
import gzip
import json
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pyte
import pytest

from agentic_av.catalog import ALBUMS, Album, CatalogEntry, Track
from agentic_av.library import AlbumError
from agentic_av.native import (
    Ffplay,
    Mpv,
    NativeError,
    _layout,
    _player_for,
    _status_line,
    _write_output,
    extract_album,
    movement_signals,
    play_native,
)
from agentic_av.palette import builtin_palettes
from agentic_av.tty import _PlayerTerminatedError
from agentic_av.viz.audio import AudioError, Segment, analyze
from agentic_av.viz.cover import ArtworkError
from agentic_av.viz.score import NOTE

FOREST = "nurse-log-ground-moves-anyway.html.gz"
AQUATIC = "drowning-collective-are-we-fish.html.gz"
COUPON = "coupon-seance-saturn.html.gz"
ROOMS = "quiet-machinery-atlas-unlit-rooms.html.gz"
POCKET = "nurse-log-the-forest-has-a-pocket.html.gz"

# Distinct payloads prove each movement gets its own file.
NAMES = (b"ONE", b"TWO", b"THREE")


@pytest.fixture(autouse=True)
def _synthetic_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep playback tests independent of ffmpeg and actual audio payloads."""
    features = analyze(np.zeros((2205, 2), dtype=np.float32))
    monkeypatch.setattr("agentic_av.native.load_features", lambda *_args: features)


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
            "sections": [{"name": "Ground", "start": 0, "end": 60, "intensity": 0.5}],
            "audio": f"data:audio/mpeg;base64,{_b64(NAMES[index])}",
        }
        for index in range(count)
    ]
    return f"<script>window.NURSE_LOG_ALBUM={json.dumps({'tracks': tracks})};</script>"


def _pocket_html(count: int = 2) -> str:
    """Pocket-album shape: `window.NL2_ALBUM` with one inline MP3 per track."""
    scenes = ("root", "rain", "spiral")
    tracks = [
        {
            "number": index + 1,
            "scene": scenes[index],
            "bpm": 88,
            "meter": "5/4" if index == 1 else "4/4",
            "color": ["#091c18", "#497453", "#d0b575"],
            "duration": 60,
            "events": [
                {
                    "part": "harp",
                    "kind": "note",
                    "time": 2,
                    "duration": 1,
                    "midi": 72,
                    "velocity": 0.5,
                    "pan": -0.2,
                    "voice": "held-center",
                },
            ],
            "audio": f"data:audio/mpeg;base64,{_b64(NAMES[index])}",
        }
        for index in range(count)
    ]
    album = {"band": "Nurse Log", "tracks": tracks}
    return f"<script>window.NL2_ALBUM={json.dumps(album)};</script>"


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
    assert native.tracks[0].score["events"]["harp"][0][:5] == [0, 1, 60, 0.5, 0]


def test_pocket_album_reads_its_own_window_and_normalizes_rows(tmp_path: Path) -> None:
    """The sixth album reads `window.NL2_ALBUM`, keeps its own family and pocket rows."""
    native = extract_album(POCKET, tmp_path, _gz(_pocket_html()))
    assert native.family == "pocket"
    assert [t.audio.read_bytes() for t in native.tracks] == [b"ONE", b"TWO"]
    assert [t.scene for t in native.tracks] == ["root", "rain"]
    assert native.tracks[0].score["palette"] == ["#091c18", "#497453", "#d0b575"]
    assert native.tracks[1].score["bpm"] == 88
    assert native.tracks[1].score["meter"] == [5, 4]
    assert native.tracks[0].score["events"]["harp"][0][:5] == [2, 1, 72, 0.5, -0.2]


def test_drowning_audio_resolves_through_asset_manifest(tmp_path: Path) -> None:
    native = extract_album(AQUATIC, tmp_path, _gz(_aquatic_html()))
    assert native.family == "aquatic"
    assert [t.audio.read_bytes() for t in native.tracks] == [b"ONE", b"TWO"]
    assert native.tracks[0].scene == "kindness"


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
    assert first.tracks[0].score["events"]["harp"]


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


def test_status_line_keeps_clock_and_way_out_at_80_columns() -> None:
    title = "Mall Cop on the Astral Plane Has Opinions About Saturn"
    line = _status_line(80, "PLAYING", "0:12 / 1:56", title, "Orbital traffic", "full", "")
    assert len(line) <= 80
    assert line.startswith(" PLAYING  0:12 / 1:56")
    assert line.rstrip().endswith("q back")
    noted = _status_line(80, "PAUSED", "0:12 / 1:56", title, "x", "still", "ffplay cannot seek")
    assert "0:12 / 1:56" in noted and "ffplay cannot seek" in noted and "q back" in noted
    assert "q back" in _status_line(12, "PLAYING", "0:12 / 1:56", title, "x", "full", "")


def test_a_long_note_gives_way_before_the_clock() -> None:
    note = "ffplay cannot seek; choose another movement"
    line = _status_line(60, "PAUSED", "0:12 / 1:56", "Rain Has Teeth", "rain", "full", note)
    assert len(line) <= 60
    assert line.startswith(" PAUSED  0:12 / 1:56")
    assert line.rstrip().endswith("q back")


# --- playback loop -------------------------------------------------------------


class FakePlayer:
    """Stand-in for mpv: `time-pos` is the clock; records seeks and close."""

    def __init__(
        self,
        media: Path,
        offset: float,
        *,
        late_s: float,
        tick_s: float,
        exit_code: int | None = None,
    ) -> None:
        self.media = media
        self.offset = offset
        self.time_pos = offset + late_s
        self.tick_s = tick_s
        self.seeks: list[float] = []
        self.closed = False
        self.proc = None if exit_code is None else SimpleNamespace(poll=lambda: exit_code)

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
    """Output that keeps frames and queues scripted keys after given frames."""

    def __init__(
        self,
        write_fd: int,
        script: dict[int, Any],
        loading_seen: threading.Event | None = None,
    ) -> None:
        self.frames: list[str] = []
        self.write_fd = write_fd
        self.script = script
        self.loading_seen = loading_seen
        self.loading_count = 0

    def write(self, text: str) -> int:
        self.frames.append(text)
        assert isinstance(text, str)
        if self.loading_seen is not None and "Listening…" in text:
            self.loading_count += 1
            if self.loading_count >= 2:
                self.loading_seen.set()
        # The first write is the loading line, not a playback frame.
        keys = self.script.get(len(self.frames) - 1)
        if callable(keys):
            keys(self.write_fd)
        elif keys:
            os.write(self.write_fd, keys)
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
    keys_after_frames: dict[int, Any] | None = None,
    motion: str = "full",
    late_s: float = 0.0,
    tick_s: float = 0.0,
    glyphs: str = "half",
    color_mode: str = "none",
    player_exit_code: int | None = None,
    loading_seen: threading.Event | None = None,
) -> tuple[list[FakePlayer], list[str]]:
    """Run `play_native` on a pipe preloaded with `keys`.

    `after_switch` is written when the second player starts: a quit in the
    same read as a track key returns before the switch. `keys_after_frames`
    maps a playback frame number (from 1) to keys queued once it is drawn.
    `late_s` starts only the first player that far into its movement.
    Returns the players and the frames written after the loading line.
    """
    entries = [CatalogEntry(album, track) for track in album.tracks]
    players: list[FakePlayer] = []
    read_fd, write_fd = os.pipe()
    os.write(write_fd, keys)
    script = dict(keys_after_frames or {})
    if quit_after_frames is not None:
        script[quit_after_frames] = script.get(quit_after_frames, b"") + b"q"
    sink = _Sink(write_fd, script, loading_seen)
    timed_out = threading.Event()

    def rescue() -> None:
        timed_out.set()
        os.write(write_fd, b"q")

    def factory(media: Path, offset: float) -> FakePlayer:
        late = late_s if not players else 0.0
        players.append(
            FakePlayer(media, offset, late_s=late, tick_s=tick_s, exit_code=player_exit_code)
        )
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
            color_mode,
            motion=motion,
            input_stream=_Pipe(read_fd),
            output_stream=sink,
            glyphs=glyphs,
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


def test_p_holds_when_the_new_movement_clock_is_stale(tmp_path: Path) -> None:
    """A fresh movement's stale clock must not end it at once (issue #7).

    After `p` opens the previous movement, the new player's first position
    reading can still carry the previous movement's clock (mpv seek
    settling). If that stale reading is already past the new movement's end,
    judging the new movement by it would auto-advance immediately, and
    repeated advances wrap to track 1. The player must hold the new movement
    while the seek settles.
    """
    entries = [CatalogEntry(COUPON_ALBUM, track) for track in COUPON_ALBUM.tracks]
    players: list[FakePlayer] = []
    read_fd, write_fd = os.pipe()
    # `p` after a few frames, then `q` soon after so the run ends inside the
    # settle window.
    sink = _Sink(write_fd, {4: b"p", 7: b"q"})
    timed_out = threading.Event()

    def rescue() -> None:
        timed_out.set()
        os.write(write_fd, b"q")

    def factory(media: Path, offset: float) -> FakePlayer:
        # First player: movement 2 (offset 77.5), honest clock. Second
        # player: movement 1 (offset 0) whose clock reports 1000 s, far past
        # movement 1's 77.5 s length, as a not-yet-settled seek would.
        late = 1000.0 if players else 0.0
        players.append(FakePlayer(media, offset, late_s=late, tick_s=0.0))
        return players[-1]

    watchdog = threading.Timer(5.0, rescue)
    watchdog.start()
    try:
        result = play_native(
            entries[1],
            entries,
            builtin_palettes()[0],
            "none",
            motion="full",
            input_stream=_Pipe(read_fd),
            output_stream=sink,
            glyphs="half",
            cache_home=tmp_path,
            source=_gz(_coupon_html()),
            player_factory=factory,
        )
    finally:
        watchdog.cancel()
        os.close(read_fd)
        os.close(write_fd)
    assert not timed_out.is_set(), "playback ignored its keys; the watchdog quit it"
    assert result == "quit"
    # Movement 2, then movement 1, and it stays there: the stale clock must
    # not auto-advance it onward (which would wrap back toward track 1).
    assert [p.offset for p in players] == [77.5, 0.0]


def _pictures(frames: list[str]) -> list[tuple[str, ...]]:
    """Interpret cursor writes into the consumer's canvas, retaining skipped rows."""
    grid = [[" "] * 80 for _ in range(24)]
    pictures = []
    token = re.compile(r"\x1b\[([0-9;?]*)([A-Za-z])|([^\x1b]+)")
    for frame in frames:
        row = col = 0
        for match in token.finditer(frame):
            if match[2] == "H":
                fields = match[1].split(";")
                row = int(fields[0] or 1) - 1
                col = int(fields[1] or 1) - 1 if len(fields) > 1 else 0
            elif match[3]:
                for char in match[3]:
                    if char == "\r":
                        col = 0
                    elif char == "\n":
                        row += 1
                    elif 0 <= row < 24 and 0 <= col < 80:
                        grid[row][col] = char
                        col += 1
        pictures.append(tuple("".join(line) for line in grid[:-2]))
    return pictures


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
    pictures = _pictures(frames)
    assert (pictures[1] == pictures[2]) is held


def test_leaving_still_rejoins_the_audio_clock(tmp_path: Path) -> None:
    """Hold for two frames, release: frame 4 matches plain full motion's."""
    _, plain = _play(
        tmp_path, _forest_html(), 1, FOREST_ALBUM, b"", quit_after_frames=4, tick_s=7.0
    )
    _, toggled = _play(
        tmp_path,
        _forest_html(),
        1,
        FOREST_ALBUM,
        b"",
        keys_after_frames={1: b"m", 3: b"m", 4: b"q"},
        tick_s=7.0,
    )
    held = _pictures(toggled)
    assert held[1] == held[2]
    assert held[3] == _pictures(plain)[3]
    assert held[3] != held[2]


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


def test_nonzero_audio_process_exit_is_reported_before_auto_advance(tmp_path: Path) -> None:
    """A failed player reports an error instead of silently cycling the album."""
    with pytest.raises(NativeError, match="audio player exited with status 1"):
        _play(
            tmp_path,
            _forest_html(),
            1,
            FOREST_ALBUM,
            b"",
            player_exit_code=1,
        )


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


def test_movement_signals_share_analysis_and_cache_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One mix is analyzed with all movement hints; views reset the time base."""
    import numpy as np

    from agentic_av.native import NativeAlbum, TrackData

    audio = tmp_path / "mix.mp3"
    native = NativeAlbum(
        (
            TrackData(audio, 0, score={"bpm": 120, "duration": 1}),
            TrackData(audio, 1, score={"bpm": 150, "duration": 2}),
        ),
        "coupon",
    )
    analyzed = analyze(np.zeros((3 * 22050, 2), dtype=np.float32))
    calls = []

    def load(path, segments):
        calls.append((path, segments))
        return analyzed

    monkeypatch.setattr("agentic_av.native.load_features", load)
    first = movement_signals(native, 0)
    second = movement_signals(native, 1)
    assert movement_signals(native, 1) is second
    assert first[0].duration_s == 1
    assert second[0].duration_s == 2
    assert second[0].sample(0).travel == 0
    assert second[1].bpm == 150
    assert calls == [(audio, [Segment(0, 1, 120), Segment(1, 3, 150)])]
    assert second[1].recent("unknown", 0, 1).dtype == NOTE


def test_movement_signals_cache_audio_error_without_losing_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agentic_av.native import NativeAlbum, TrackData

    calls = []

    def fail(path, segments):
        calls.append(path)
        raise AudioError("ffmpeg missing")

    monkeypatch.setattr("agentic_av.native.load_features", fail)
    native = NativeAlbum((TrackData(tmp_path / "audio.mp3", score={"bpm": 84}),), "aquatic")
    features, score = movement_signals(native, 0)
    assert features is None and score.bpm == 84
    assert movement_signals(native, 0) == (features, score)
    assert len(calls) == 1


def test_frames_are_single_sync_wrapped_writes_without_canvas_clear(tmp_path: Path) -> None:
    """Incremental canvas rows and transport arrive inside one synchronized write."""
    _, frames = _play(
        tmp_path, _forest_html(), 1, FOREST_ALBUM, b"", quit_after_frames=3, tick_s=0.1
    )
    for frame in frames:
        assert frame.startswith("\x1b[?2026h")
        assert frame.endswith("\x1b[?2026l")
        assert frame.count("\x1b[?2026h") == 1
        assert "\x1b[J" not in frame and "\x1b[2J" not in frame
        assert not re.search(r"\x1b\[[0-9;]*m", frame)


def test_pause_holds_display_even_if_player_clock_advances(tmp_path: Path) -> None:
    """Hold the last pixels, rather than merely freezing geometric tau."""
    _, frames = _play(
        tmp_path,
        _forest_html(),
        1,
        FOREST_ALBUM,
        b" ",
        quit_after_frames=3,
        tick_s=7,
    )
    pictures = _pictures(frames)
    assert pictures[0] == pictures[1] == pictures[2]
    assert "PAUSED" in frames[1]


def test_paused_tier_redraw_reuses_the_captured_visual_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held tier change redraws at the displayed instant, not before its visual lead."""
    from agentic_av import native

    real_stage = native.Stage
    clocks: list[tuple[float, float]] = []

    class RecordingStage:
        def __init__(self, *args, **kwargs):
            self.stage = real_stage(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.stage, name)

        def frame(self, t, tau, *, motion):
            clocks.append((t, tau))
            return self.stage.frame(t, tau, motion=motion)

    monkeypatch.setattr(native, "Stage", RecordingStage)
    _play(
        tmp_path,
        _forest_html(),
        1,
        FOREST_ALBUM,
        b"",
        keys_after_frames={1: b" ", 2: b"g"},
        quit_after_frames=4,
        tick_s=0.5,
    )
    assert len(clocks) == 2
    assert clocks[0] == clocks[1]


def test_g_cycles_tier_and_explicit_tier_overrides_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual consumer sees the tier selection and its runtime replacement."""
    monkeypatch.setenv("AAV_GLYPHS", "invalid-but-ignored-by-explicit")
    _, frames = _play(
        tmp_path,
        _forest_html(),
        1,
        FOREST_ALBUM,
        b"g",
        quit_after_frames=2,
        glyphs="half",
    )
    assert "half" in frames[0]
    assert "braille" in frames[1]
    assert _pictures(frames)[0] != _pictures(frames)[1]


def test_auto_tier_honors_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Native auto selects AAV_GLYPHS before consulting the terminal hint."""
    monkeypatch.setenv("AAV_GLYPHS", "ascii")
    _, frames = _play(tmp_path, _forest_html(), 1, FOREST_ALBUM, b"q", glyphs="auto")
    assert "ascii" in frames[0]


def test_analysis_failure_is_visible_and_audio_still_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A quiet scene is an explicit degraded mode, not fabricated live analysis."""

    def fail(*_args):
        raise AudioError("ffmpeg unavailable")

    monkeypatch.setattr("agentic_av.native.load_features", fail)
    players, frames = _play(tmp_path, _forest_html(), 1, FOREST_ALBUM, b"q")
    assert players[0].closed
    assert "analysis unavailable" in frames[0]
    assert any(char.strip() for row in _pictures(frames)[0] for char in row)


def test_output_boundary_writes_utf8_bytes_to_binary_buffer() -> None:
    """Text streams decode explicitly; a real TextIOWrapper uses its byte buffer."""
    import io

    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="utf-8")
    payload = "─ mosaic".encode()
    _write_output(stream, payload)
    assert buffer.getvalue() == payload


def test_output_boundary_rejects_short_writes() -> None:
    """Transport errors must propagate instead of silently losing half a frame."""

    class Short:
        def write(self, value):
            return len(value) - 1

        def flush(self):
            pass

    with pytest.raises(OSError, match="short terminal"):
        _write_output(Short(), b"frame")


def test_analysis_is_single_flight_across_simultaneous_movements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A next-movement prefetch and foreground open share one cache publication."""
    from agentic_av.native import NativeAlbum, TrackData

    entered = threading.Event()
    release = threading.Event()
    features = analyze(np.zeros((2205, 2), dtype=np.float32))
    calls = []

    def load(*_args):
        calls.append(True)
        entered.set()
        assert release.wait(2)
        return features

    monkeypatch.setattr("agentic_av.native.load_features", load)
    album = NativeAlbum((TrackData(tmp_path / "mix.mp3"),) * 2, "coupon")
    first = threading.Thread(target=movement_signals, args=(album, 0))
    second = threading.Thread(target=movement_signals, args=(album, 1))
    first.start()
    assert entered.wait(2)
    second.start()
    release.set()
    first.join(2)
    second.join(2)
    assert not first.is_alive() and not second.is_alive()
    assert len(calls) == 1


def test_seeking_updates_a_held_picture(tmp_path: Path) -> None:
    """Still mode holds between seeks, but a successful seek captures a new instant."""
    _, frames = _play(
        tmp_path,
        _forest_html(),
        1,
        FOREST_ALBUM,
        b"",
        keys_after_frames={1: b"\x1b[C", 3: b"q"},
        motion="still",
    )
    pictures = _pictures(frames)
    assert pictures[0] != pictures[1]
    assert pictures[1] == pictures[2]


def test_large_terminal_applies_tier_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The native caller budgets the actual canvas, not just the detection default."""
    monkeypatch.setattr("agentic_av.native._size", lambda _fd: (300, 80))
    _, frames = _play(tmp_path, _forest_html(), 1, FOREST_ALBUM, b"q", glyphs="octant")
    assert "quadrant" in frames[0]


@pytest.mark.parametrize("size", [(1, 1), (12, 4), (40, 10)])
@pytest.mark.parametrize("mode", ["truecolor", "256", "none"])
def test_small_terminal_frames_keep_exit_and_valid_color_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: tuple[int, int], mode: str
) -> None:
    """Native output remains drawable across short/narrow grids and color modes."""
    monkeypatch.setattr("agentic_av.native._size", lambda _fd: size)
    _, frames = _play(tmp_path, _forest_html(), 1, FOREST_ALBUM, b"q", color_mode=mode)
    assert frames[0].startswith("\x1b[?2026h")
    assert frames[0].endswith("\x1b[?2026l")
    if size[0] >= 12:
        assert "q back" in frames[0]
    if mode == "none":
        assert not re.search(r"\x1b\[[0-9;]*m", frames[0])


def test_background_analysis_never_delays_quit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The next movement can remain in analysis after the audio controller closes."""
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    features = analyze(np.zeros((2205, 2), dtype=np.float32))
    calls = []

    def load(*_args):
        calls.append(True)
        if len(calls) > 1:
            started.set()
            assert release.wait(3)
            finished.set()
        return features

    monkeypatch.setattr("agentic_av.native.load_features", load)
    try:
        players, _ = _play(tmp_path, _forest_html(), 1, FOREST_ALBUM, b"", quit_after_frames=2)
        assert started.wait(1)
        assert players[0].closed
        assert not finished.is_set()
    finally:
        release.set()
        assert finished.wait(2)


def test_quit_remains_responsive_while_foreground_analysis_waits_for_prefetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cold-cache n press still accepts q while serialized analysis is busy."""
    prefetch_waiting = threading.Event()
    loading_line = threading.Event()
    release = threading.Event()
    prefetch_timed_out = threading.Event()
    calls = []
    features = analyze(np.zeros((2205, 2), dtype=np.float32))

    def load(*_args):
        calls.append(True)
        if len(calls) == 2:
            prefetch_waiting.set()
            if not release.wait(2):
                prefetch_timed_out.set()
        return features

    monkeypatch.setattr("agentic_av.native.load_features", load)

    def switch_then_quit(write_fd):
        os.write(write_fd, b"n")

        def quit_when_loading_line():
            if prefetch_waiting.wait(2):
                loading_line.wait(0.5)
                os.write(write_fd, b"q")

        threading.Thread(target=quit_when_loading_line, daemon=True).start()

    start = time.monotonic()
    try:
        players, _ = _play(
            tmp_path,
            _forest_html(),
            1,
            FOREST_ALBUM,
            b"",
            keys_after_frames={1: switch_then_quit},
            loading_seen=loading_line,
        )
        elapsed = time.monotonic() - start
    finally:
        release.set()
        deadline = time.monotonic() + 2
        while (
            any(
                thread.name in {"aav-analysis", "aav-current-analysis"} and thread.is_alive()
                for thread in threading.enumerate()
            )
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
    assert prefetch_waiting.is_set()
    assert loading_line.is_set()
    assert elapsed < 1.0
    assert not prefetch_timed_out.is_set()
    assert players[0].closed


def test_section_and_hairline_are_visible_in_transport(tmp_path: Path) -> None:
    """The source score reaches listener-visible section text and progress ticks."""
    _, frames = _play(tmp_path, _forest_html(), 1, FOREST_ALBUM, b"q")
    assert "Ground" in frames[0]
    assert "\x1b[23;1H" in frames[0]
    assert "│" in frames[0] and "─" in frames[0]


@pytest.mark.parametrize(
    ("motion", "cost_s", "expected_s"),
    [("full", 0.01, 1 / 30 - 0.01), ("still", 0.01, 0.19), ("full", 0.1, 0)],
)
def test_frame_deadlines_drop_slow_work_without_queued_catchup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    motion: str,
    cost_s: float,
    expected_s: float,
) -> None:
    """Each loop subtracts only this frame's measured cost from its own cadence."""
    from types import SimpleNamespace

    ticks = iter(index * cost_s for index in range(20))
    monkeypatch.setattr("agentic_av.native.time", SimpleNamespace(monotonic=lambda: next(ticks)))
    import select

    real_select = select.select
    waits = []

    def observe(read, write, error, timeout):
        waits.append(timeout)
        return real_select(read, write, error, timeout)

    monkeypatch.setattr("agentic_av.native.select.select", observe)
    _play(
        tmp_path,
        _forest_html(),
        1,
        FOREST_ALBUM,
        b"",
        quit_after_frames=2,
        motion=motion,
        tick_s=0.1,
    )
    assert waits == pytest.approx([expected_s, expected_s])


# --- album cover panel ---------------------------------------------------------

_SYNC_MARK = re.compile(r"\x1b\[\?2026[hl]")
_SGR_SEQUENCE = re.compile(r"\x1b\[[0-9;]*m")
_CATALOG_POCKET = next(album for album in ALBUMS if album.asset == POCKET)
# The catalog's A-02 record lists six movements; the playback harness replays two, so the
# real cover rides on a two-movement album.
POCKET_ALBUM = dataclasses.replace(_album(POCKET, (0.0, 60.0), 120.0), cover=_CATALOG_POCKET.cover)


def _replay(frames: list[str], width: int, height: int) -> pyte.Screen:
    """Feed the frames, in order, to a terminal of the given size."""
    screen = pyte.Screen(width, height)
    stream = pyte.Stream(screen)
    for frame in frames:
        stream.feed(_SYNC_MARK.sub("", frame))
    return screen


def _painted(screen: pyte.Screen, rows: range, cols: range) -> int:
    """Count cells in the box that show a glyph or carry a color."""
    return sum(
        1
        for row in rows
        for col in cols
        if screen.buffer[row][col].data != " "
        or screen.buffer[row][col].fg != "default"
        or screen.buffer[row][col].bg != "default"
    )


def _glyphs(screen: pyte.Screen, rows: range, cols: range) -> str:
    """Return the characters in the box, row by row."""
    return "".join(screen.buffer[row][col].data for row in rows for col in cols)


def test_a02_shows_its_cover_left_of_the_stage_in_color(tmp_path: Path) -> None:
    _, frames = _play(
        tmp_path, _pocket_html(2), 1, POCKET_ALBUM, b"", quit_after_frames=2, color_mode="truecolor"
    )
    screen = _replay(frames, 80, 24)
    # A 32x16 panel centered on the 22 canvas rows: rows 4-19, columns 1-32 (one-based).
    assert _painted(screen, range(3, 19), range(0, 32)) == 32 * 16
    assert _painted(screen, range(0, 3), range(0, 32)) == 0
    assert _painted(screen, range(19, 22), range(0, 32)) == 0
    # The two-column gap is erased; the stage keeps its 46 columns on the right.
    assert _painted(screen, range(0, 22), range(32, 34)) == 0
    assert _painted(screen, range(0, 22), range(34, 80)) == 22 * 46
    assert "PLAYING" in screen.display[23]


def test_a02_cover_is_glyphs_only_without_color(tmp_path: Path) -> None:
    _, frames = _play(tmp_path, _pocket_html(2), 1, POCKET_ALBUM, b"", quit_after_frames=2)
    assert not any(_SGR_SEQUENCE.search(frame) for frame in frames)
    screen = _replay(frames, 80, 24)
    assert _glyphs(screen, range(3, 19), range(0, 32)).strip()
    assert _painted(screen, range(0, 22), range(32, 34)) == 0
    assert "PLAYING" in screen.display[23]


def test_linux_console_tier_draws_the_cover_in_ascii(tmp_path: Path) -> None:
    _, frames = _play(
        tmp_path, _pocket_html(2), 1, POCKET_ALBUM, b"", quit_after_frames=2, glyphs="ascii"
    )
    screen = _replay(frames, 80, 24)
    panel = _glyphs(screen, range(3, 19), range(0, 32))
    assert panel.strip()
    assert all(ord(char) < 128 for char in panel)


def test_albums_without_a_cover_keep_the_full_width_stage(tmp_path: Path) -> None:
    _, frames = _play(
        tmp_path, _forest_html(3), 1, FOREST_ALBUM, b"", quit_after_frames=2, color_mode="truecolor"
    )
    assert not any("\x1b[2K" in frame for frame in frames)
    screen = _replay(frames, 80, 24)
    assert _painted(screen, range(0, 22), range(0, 80)) == 22 * 80


def test_resizing_the_panel_leaves_no_stale_pixels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def size(_fd: int) -> tuple[int, int]:
        calls.append(len(calls))
        return (80, 24) if len(calls) <= 3 else (100, 24)

    monkeypatch.setattr("agentic_av.native._size", size)
    _, frames = _play(
        tmp_path, _pocket_html(2), 1, POCKET_ALBUM, b"", quit_after_frames=8, color_mode="truecolor"
    )
    assert len(calls) >= 4, "the widening must happen before the quit"
    screen = _replay(frames, 100, 24)
    # At 100 columns the panel grows to 40x20 and stays centered: rows 2-21, columns 1-40.
    assert _painted(screen, range(1, 21), range(0, 40)) == 40 * 20
    assert _painted(screen, range(0, 22), range(40, 42)) == 0
    assert _painted(screen, range(0, 1), range(0, 40)) == 0
    assert _painted(screen, range(21, 22), range(0, 40)) == 0
    assert _painted(screen, range(0, 22), range(42, 100)) == 22 * 58
    assert "PLAYING" in screen.display[23]


@pytest.mark.parametrize(
    ("key", "expected_title"),
    [(b"n", POCKET_ALBUM.tracks[1].title), (b"g", POCKET_ALBUM.tracks[0].title)],
)
def test_cover_remains_visible_after_movement_and_tier_changes(
    tmp_path: Path, key: bytes, expected_title: str
) -> None:
    _, frames = _play(
        tmp_path,
        _pocket_html(2),
        1,
        POCKET_ALBUM,
        b"",
        keys_after_frames={1: key, 6: b"q"},
        color_mode="truecolor",
        glyphs="half",
    )
    screen = _replay(frames, 80, 24)
    assert expected_title in screen.display[23]
    assert _painted(screen, range(3, 19), range(0, 32)) == 32 * 16
    assert _painted(screen, range(0, 22), range(32, 34)) == 0
    assert _painted(screen, range(0, 22), range(34, 80)) == 22 * 46


def test_a_cover_that_fails_verification_is_omitted_with_a_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(asset: str, sha256: str) -> np.ndarray:
        raise ArtworkError(f"{asset} does not match the approved SHA-256 {sha256}")

    monkeypatch.setattr("agentic_av.native.load_cover", refuse)
    _, frames = _play(tmp_path, _pocket_html(2), 1, POCKET_ALBUM, b"", quit_after_frames=2)
    assert not any("\x1b[2K" in frame for frame in frames)
    screen = _replay(frames, 80, 24)
    assert "cover art unavailable" in screen.display[23]


def test_cover_layout_keeps_the_stage_share_and_drops_the_panel_when_small() -> None:
    layout = _layout(80, 22, 2.0, 1.0)
    panel = layout.cover
    assert (panel.top, panel.left, panel.cols, panel.rows) == (4, 0, 32, 16)
    assert (layout.stage_left, layout.stage_cols) == (34, 46)
    assert _layout(80, 22, 2.0, None).cover is None
    for width, rows in ((40, 22), (80, 5)):
        small = _layout(width, rows, 2.0, 1.0)
        assert small.cover is None
        assert (small.stage_left, small.stage_cols) == (0, width)

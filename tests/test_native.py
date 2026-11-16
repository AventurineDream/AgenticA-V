"""Tests for native album playback: extraction, frames, and the playback loop.

The bundled archives are ~70 MB of HTML, so tests build tiny synthetic
`.html.gz` documents in each album's shape and pass them as `source`. A fake
player stands in for mpv/ffplay, and a pipe stands in for the TTY, so
`play_native` never touches real audio or the terminal.
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Any

import pytest

from agentic_av.catalog import Album, CatalogEntry, Track
from agentic_av.library import AlbumError
from agentic_av.native import (
    NativeError,
    _player_for,
    _scene_rows,
    extract_album,
    play_native,
)
from agentic_av.paint import render_ansi
from agentic_av.palette import builtin_palettes
from agentic_av.scenes import FAMILIES, EventIndex, normalize_events

FOREST = "nurse-log-ground-moves-anyway.html.gz"
AQUATIC = "drowning-collective-are-we-fish.html.gz"
COUPON = "coupon-seance-saturn.html.gz"
ROOMS = "quiet-machinery-atlas-unlit-rooms.html.gz"

# base64 of b"ONE" and b"TWO": distinct payloads prove per-movement files.
ONE, TWO = "T05F", "VFdP"


def _gz(html: str) -> bytes:
    return gzip.compress(html.encode("utf-8"))


def _forest_html() -> str:
    """Nurse-Log shape: `window.NURSE_LOG_ALBUM` with a data URI per track."""
    data = {
        "tracks": [
            {
                "number": 1,
                "scene": "root",
                "events": [["harp", 0.0, 1.0, 60, 0.5, 0.0]],
                "audio": f"data:audio/mpeg;base64,{ONE}",
            },
            {"number": 2, "scene": "rain", "events": [], "audio": f"data:audio/mpeg;base64,{TWO}"},
        ]
    }
    return f"<script>window.NURSE_LOG_ALBUM={json.dumps(data)};</script>"


def _aquatic_html() -> str:
    """Drowning shape: track `audio` paths keyed into `band02-assets`."""
    events = {"tracks": [{"audio": "../audio/mix.mp3"}, {"audio": "../track-02/audio/mix.mp3"}]}
    assets = {
        "../audio/mix.mp3": f"data:audio/mpeg;base64,{ONE}",
        "../track-02/audio/mix.mp3": f"data:audio/mpeg;base64,{TWO}",
    }
    return (
        f"<script>window.BAND02_VISUAL_EVENTS={json.dumps(events)};</script>"
        f'<script type="application/json" id="band02-assets">{json.dumps(assets)}</script>'
    )


def _coupon_html() -> str:
    """Coupon shape: one album `<audio>` and a `const tracks=[...]` literal."""
    return (
        f'<audio id="audio" src="data:audio/mpeg;base64,{ONE}"></audio>'
        "<script>const tracks=["
        "{start:0,title:'Customs',text:'01'},"
        "{start:77.5,title:'Rosin',text:'02'}"
        "];</script>"
    )


def _album(asset: str, starts: tuple[float, float] = (0.0, 4.0)) -> Album:
    return Album(
        artist="Test Band",
        band="Test Band",
        title="Test Album",
        duration_s=starts[1] + 4.0,
        asset=asset,
        tracks=(
            Track(number=1, title="One", start_s=starts[0]),
            Track(number=2, title="Two", start_s=starts[1]),
        ),
    )


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
    first, second = native.tracks
    assert first.audio == second.audio
    assert first.audio.read_bytes() == b"ONE"
    assert (first.offset_s, second.offset_s) == (0.0, 77.5)
    assert (first.scene, second.scene) == ("arrival", "friction")


def test_extraction_reuses_cached_files(tmp_path: Path) -> None:
    source = _gz(_forest_html())
    first = extract_album(FOREST, tmp_path, source)
    stamp = first.tracks[1].audio.stat().st_mtime_ns
    second = extract_album(FOREST, tmp_path, source)
    assert second.tracks[1].audio == first.tracks[1].audio
    assert second.tracks[1].audio.stat().st_mtime_ns == stamp


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


# --- playback loop -------------------------------------------------------------


class FakePlayer:
    """Stand-in for mpv: `time-pos` is the clock; records seeks and close."""

    def __init__(self, media: Path, offset: float) -> None:
        self.media = media
        self.offset = offset
        self.time_pos = offset
        self.seeks: list[float] = []
        self.closed = False

    def get(self, name: str) -> Any:
        """Report `time-pos` like mpv IPC."""
        return self.time_pos if name == "time-pos" else None

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
    """Write-only output that discards frames."""

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass


def _play(
    tmp_path: Path,
    html: str,
    number: int,
    album: Album,
    keys: bytes,
    after_switch: bytes = b"",
) -> list[FakePlayer]:
    """Run `play_native` on a pipe preloaded with `keys`.

    `after_switch` is written when the second player starts. A quit in the
    same read as a track key returns before the switch, so tests that need
    the switch queue their `q` here.
    """
    entries = [CatalogEntry(album, track) for track in album.tracks]
    players: list[FakePlayer] = []
    read_fd, write_fd = os.pipe()
    os.write(write_fd, keys)

    def factory(media: Path, offset: float) -> FakePlayer:
        players.append(FakePlayer(media, offset))
        if len(players) == 2 and after_switch:
            os.write(write_fd, after_switch)
        return players[-1]

    try:
        result = play_native(
            entries[number - 1],
            entries,
            builtin_palettes()[0],
            "none",
            input_stream=_Pipe(read_fd),
            output_stream=_Sink(),
            cache_home=tmp_path,
            source=_gz(html),
            player_factory=factory,
        )
    finally:
        os.close(read_fd)
        os.close(write_fd)
    assert result == "quit"
    return players


def test_playback_starts_the_selected_movement_and_q_stops_it(tmp_path: Path) -> None:
    players = _play(tmp_path, _coupon_html(), 2, _album(COUPON, (0.0, 77.5)), b"q")
    assert len(players) == 1
    assert players[0].offset == 77.5
    assert players[0].closed


def test_seek_is_relative_to_the_movement_and_n_loads_the_next_file(tmp_path: Path) -> None:
    players = _play(tmp_path, _forest_html(), 1, _album(FOREST, (0.0, 60.0)), b"\x1b[Cn", b"q")
    first, second = players
    assert first.seeks == [10.0]
    assert first.media.read_bytes() == b"ONE"
    assert second.media.read_bytes() == b"TWO"
    assert first.closed and second.closed


def test_previous_movement_is_not_skipped_by_a_stale_position(tmp_path: Path) -> None:
    """`p` from Coupon's second movement lands on the first and stays there.

    The second movement's clock reads 77.5 s into the shared mix, exactly the
    first movement's length; judging the new movement by it would skip on.
    """
    players = _play(tmp_path, _coupon_html(), 2, _album(COUPON, (0.0, 77.5)), b"p", b"q")
    assert [p.offset for p in players] == [77.5, 0.0]


# --- player selection --------------------------------------------------------


def test_missing_players_raise_a_listener_facing_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("agentic_av.native._mpv_available", lambda: False)
    monkeypatch.setattr("agentic_av.native._ffplay_available", lambda: False)
    with pytest.raises(NativeError, match="install mpv or ffplay"):
        _player_for(tmp_path / "a.mp3", 0.0)

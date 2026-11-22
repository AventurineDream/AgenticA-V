"""Check the now-playing presentation as a terminal shows it.

Splash, transport, and title-card bytes are replayed through pyte, so the tests check
the cells a listener sees: where the cover lands, which text survives at small sizes,
and that the accent stays legible on every built-in theme. Covers are the bundled
receipt files, so accents are measured on the real artwork.
"""

from __future__ import annotations

import numpy as np
import pyte
import pytest

from clangor_visualis_machina.catalog import ALBUMS
from clangor_visualis_machina.colorutil import contrast_ratio
from clangor_visualis_machina.nowplaying import (
    Layout,
    album_accent,
    splash,
    status_parts,
    title_card,
    transport,
)
from clangor_visualis_machina.palette import builtin_palettes
from clangor_visualis_machina.viz.cover import cover_accent, load_cover, prepare_cover
from clangor_visualis_machina.viz.glyphs import Cells

_COVERED = [album for album in ALBUMS if album.cover is not None]
_PALETTE = builtin_palettes()[0]


def _replay(frame: bytes, width: int, height: int) -> pyte.Screen:
    screen = pyte.Screen(width, height)
    pyte.Stream(screen).feed(frame.decode("utf-8"))
    return screen


def _colored(screen: pyte.Screen, rows: range, cols: range) -> int:
    return sum(1 for row in rows for col in cols if screen.buffer[row][col].bg != "default")


def _splash(width: int, height: int, *, cover: bool = True) -> pyte.Screen:
    album = _COVERED[0]
    pixels = load_cover(album.cover.asset, album.cover.sha256)
    frame = splash(
        title=album.title,
        artist=album.artist,
        cover=prepare_cover(pixels) if cover else None,
        ratio=1.0 if cover else None,
        width=width,
        height=height,
        aspect=2.0,
        tier="half",
        palette=_PALETTE,
        accent=_PALETTE.accent,
        color_mode="truecolor",
        status=" Listening… First Movement",
    )
    return _replay(frame, width, height)


def test_splash_centers_the_cover_above_a_letter_spaced_title() -> None:
    album = _COVERED[0]
    screen = _splash(80, 24)
    # 13 cover rows (55% of 24) by 26 columns, centered with three text rows below.
    assert _colored(screen, range(3, 16), range(27, 53)) == 26 * 13
    assert _colored(screen, range(0, 23), range(0, 27)) == 0
    assert " ".join(album.title.upper()) in screen.display[17]
    assert album.artist in screen.display[18]
    assert screen.display[23].startswith(" Listening… First Movement")


@pytest.mark.parametrize(("width", "height"), [(1, 1), (12, 3), (24, 8), (40, 12), (200, 60)])
def test_splash_degrades_without_wrapping_at_any_size(width: int, height: int) -> None:
    screen = _splash(width, height)
    # The status keeps the last row; without room for a full-size cover, only text shows.
    if width >= 12:
        assert screen.display[height - 1].startswith(" Listening…")
    if height < 12:
        assert _colored(screen, range(0, height - 1), range(width)) == 0


def test_splash_without_a_cover_keeps_title_and_artist() -> None:
    album = _COVERED[0]
    screen = _splash(80, 24, cover=False)
    assert album.artist in "".join(screen.display)
    assert _colored(screen, range(0, 23), range(80)) == 0


@pytest.mark.parametrize("album", _COVERED, ids=lambda album: album.title)
def test_cover_accents_stay_legible_on_every_theme(album) -> None:
    rgb = cover_accent(load_cover(album.cover.asset, album.cover.sha256))
    for palette in builtin_palettes():
        accent = album_accent(rgb, (), palette)
        assert contrast_ratio(accent, palette.background) >= 3.0, palette.name


def test_a_small_lit_feature_outvotes_a_large_dim_field() -> None:
    room = np.full((64, 64, 3), (12, 18, 30), dtype=np.uint8)
    room[20:28, 40:48] = (230, 150, 60)
    red, _, blue = cover_accent(room)
    assert red > blue
    gray = np.full((32, 32, 3), 90, dtype=np.uint8)
    assert cover_accent(gray) == (90, 90, 90)


def test_without_a_cover_the_accent_follows_the_movement_palette() -> None:
    palette = next(item for item in builtin_palettes() if item.dark)
    assert album_accent(None, ("#000000", "#ff9900"), palette) == "#ff9900"
    assert album_accent(None, (), palette) == album_accent(None, ("nonsense",), palette)


def test_native_transport_hints_show_jkl_and_track_arrows() -> None:
    parts = status_parts(
        120,
        playing=True,
        clock="0:00",
        position="",
        title="",
        scene="",
        motion="full",
        note="",
    )
    text = "".join(value for value, _ in parts)
    assert "←/→ track" in text
    assert "j/l seek" in text
    assert "k/space pause" in text


def _rail(progress: float, width: int = 20) -> str:
    parts = status_parts(
        width, playing=True, clock="0:00", position="", title="", scene="", motion="full", note=""
    )
    frame = transport(
        width,
        12,
        progress=progress,
        ticks={15},
        parts=parts,
        palette=_PALETTE,
        accent=_PALETTE.accent,
        color_mode="none",
    )
    return _replay(frame, width, 12).display[10]


def test_rail_fills_with_a_half_cell_playhead_and_marks_sections() -> None:
    assert _rail(0.5) == "━" * 10 + "─" * 5 + "┴" + "─" * 4
    assert _rail(0.525) == "━" * 10 + "╸" + "─" * 4 + "┴" + "─" * 4
    assert _rail(1.0) == "━" * 15 + "┻" + "━" * 4


def _cells(rows: int, cols: int, value: int = 200) -> Cells:
    color = np.full((rows, cols, 3), value, dtype=np.uint8)
    glyph = np.zeros((rows, cols), dtype=np.uint16)
    return Cells("half", False, glyph, color, color.copy())


def test_title_card_darkens_the_picture_under_its_text_and_then_expires() -> None:
    plan = Layout(stage_left=10, stage_cols=60, cover=None)
    kwargs = dict(
        number=2,
        count=6,
        title="Rain in the Hinges",
        palette=_PALETTE,
        accent=_PALETTE.accent,
        color_mode="truecolor",
    )
    frame = title_card(_cells(20, 60), plan, 20, age_s=1.0, fade=True, **kwargs)
    screen = _replay(frame, 80, 22)
    assert "MOVEMENT 2 OF 6" in screen.display[17][10:]
    assert "Rain in the Hinges" in screen.display[18][10:]
    scrim = screen.buffer[18][14].bg
    assert int(scrim[:2], 16) < 200 * 0.5
    assert title_card(_cells(20, 60), plan, 20, age_s=5.0, fade=True, **kwargs) == b""
    assert title_card(_cells(6, 60), plan, 6, age_s=1.0, fade=True, **kwargs) == b""
    assert title_card(None, plan, 20, age_s=1.0, fade=True, **kwargs) == b""

"""Verify the bundled A-02 covers: receipt bytes, refusal paths, and bounded rendering.

The receipt hashes and sizes come from the records in docs/decisions/0002. Rendering
tests replay the emitted bytes through pyte, so they check what a terminal would show:
which cells the panel paints, whether its gap stays clear, and whether no-color output
carries any SGR sequence.
"""

from __future__ import annotations

import hashlib
import re
from importlib.resources import files

import numpy as np
import pyte
import pytest

from agentic_av.catalog import ALBUMS, validate_catalog
from agentic_av.viz.cover import ArtworkError, decode_cover, load_cover, render_cover

_ASSET = "nurse-log-the-forest-has-a-pocket.jpg"
_POCKET_ALBUM = "nurse-log-the-forest-has-a-pocket.html.gz"
_RECEIPT_SHA256 = "e42821bc820a81a7f6b6e168dc772d1540aebfe256bfda23387bc9aecc9fdab6"
_RECEIPT_BYTES = 370_848
_DC2_ASSET = "drowning-collective-the-shape-that-stays.jpg"
_DC2_ALBUM = "drowning-collective-the-shape-that-stays.html.gz"
_DC2_SHA256 = "15ebebe5901876171853a20858d7f828b989bbca8c3d4fd4d78f15f2a2933d4a"
# Coupon Seance A-02's agent-proposed cover (ADR 0002 amendment); Aven's merge approves it.
_HAUNT_ALBUM = "coupon-seance-buy-one-haunt-one-free.html.gz"
_HAUNT_ASSET = "coupon-seance-buy-one-haunt-one-free.jpg"
_HAUNT_SHA256 = "4e0418ab45a0285967c980318bf976a11cf120f1a72243f05d7d49a8b5e3047f"
# Quiet Machinery A-02's agent-proposed cover (ADR 0002 amendment); Aven's merge approves it.
_DUSK_ALBUM = "quiet-machinery-instruments-for-measuring-dusk.html.gz"
_DUSK_ASSET = "quiet-machinery-instruments-for-measuring-dusk.jpg"
_DUSK_SHA256 = "cd29193cde9fc0a53e40fd8b37fda8fa845ffc397dd0c39451fb19bf1db4c81a"
_SGR = re.compile(r"\x1b\[[0-9;]*m")


def _artwork_bytes() -> bytes:
    return files("agentic_av").joinpath("artwork", _ASSET).read_bytes()


def _replay(frame: bytes | str, width: int, height: int) -> pyte.Screen:
    text = frame.decode("utf-8") if isinstance(frame, bytes) else frame
    screen = pyte.Screen(width, height)
    pyte.Stream(screen).feed(text)
    return screen


def _painted(screen: pyte.Screen) -> set[tuple[int, int]]:
    """Zero-based (row, col) of cells that show a glyph or carry a color."""
    cells = set()
    for row in range(screen.lines):
        for col in range(screen.columns):
            char = screen.buffer[row][col]
            if char.data != " " or char.fg != "default" or char.bg != "default":
                cells.add((row, col))
    return cells


def test_packaged_cover_is_the_approved_receipt_file() -> None:
    data = _artwork_bytes()
    assert len(data) == _RECEIPT_BYTES
    assert hashlib.sha256(data).hexdigest() == _RECEIPT_SHA256
    pixels = load_cover(_ASSET, _RECEIPT_SHA256)
    assert pixels.shape == (1024, 1024, 3)
    assert pixels.dtype == np.uint8


def test_only_approved_a02_covers_are_recorded_and_the_artwork_folder_holds_only_them() -> None:
    """Bundled cover scope is exact, with each file matching its recorded bytes."""
    validate_catalog()
    covered = {
        album.asset: (album.cover.asset, album.cover.sha256)
        for album in ALBUMS
        if album.cover is not None
    }
    assert covered == {
        _POCKET_ALBUM: (_ASSET, _RECEIPT_SHA256),
        _DC2_ALBUM: (_DC2_ASSET, _DC2_SHA256),
        _HAUNT_ALBUM: (_HAUNT_ASSET, _HAUNT_SHA256),
        _DUSK_ALBUM: (_DUSK_ASSET, _DUSK_SHA256),
    }
    names = sorted(
        path.name
        for path in files("agentic_av").joinpath("artwork").iterdir()
        if not path.name.startswith(".") and path.name != "__pycache__"
    )
    assert names == sorted([_ASSET, _DC2_ASSET, _HAUNT_ASSET, _DUSK_ASSET])
    dc2 = files("agentic_av").joinpath("artwork", _DC2_ASSET).read_bytes()
    assert len(dc2) == 404_381
    assert hashlib.sha256(dc2).hexdigest() == _DC2_SHA256
    assert load_cover(_DC2_ASSET, _DC2_SHA256).shape == (1024, 1024, 3)
    haunt = files("agentic_av").joinpath("artwork", _HAUNT_ASSET).read_bytes()
    assert hashlib.sha256(haunt).hexdigest() == _HAUNT_SHA256
    assert load_cover(_HAUNT_ASSET, _HAUNT_SHA256).shape == (1024, 1024, 3)
    dusk = files("agentic_av").joinpath("artwork", _DUSK_ASSET).read_bytes()
    assert hashlib.sha256(dusk).hexdigest() == _DUSK_SHA256
    assert load_cover(_DUSK_ASSET, _DUSK_SHA256).shape == (1024, 1024, 3)


def test_altered_bytes_are_refused_before_decoding() -> None:
    with pytest.raises(ArtworkError, match="SHA-256"):
        decode_cover(_artwork_bytes() + b"\0", _RECEIPT_SHA256)


def test_a_matching_digest_still_needs_a_jpeg() -> None:
    data = b"not an image"
    with pytest.raises(ArtworkError, match="JPEG"):
        decode_cover(data, hashlib.sha256(data).hexdigest())


@pytest.mark.parametrize("color_mode", ["truecolor", "256"])
def test_color_cover_paints_exactly_its_panel(color_mode: str) -> None:
    pixels = load_cover(_ASSET, _RECEIPT_SHA256)
    top, left, cols, rows = 3, 5, 20, 10
    frame = render_cover(
        pixels, cols=cols, rows=rows, tier="half", color_mode=color_mode, top=top, left=left
    )
    screen = _replay(frame, 40, 20)
    box = {(row, col) for row in range(top - 1, top - 1 + rows) for col in range(left, left + cols)}
    assert _painted(screen) == box
    colors = {screen.buffer[row][col].bg for row, col in box}
    assert len(colors) >= 4


@pytest.mark.parametrize("tier", ["half", "ascii"])
def test_colorless_cover_has_glyphs_inside_the_panel_and_no_sgr(tier: str) -> None:
    pixels = load_cover(_ASSET, _RECEIPT_SHA256)
    top, left, cols, rows = 2, 4, 24, 8
    frame = render_cover(
        pixels, cols=cols, rows=rows, tier=tier, color_mode="none", top=top, left=left
    )
    text = frame.decode("utf-8")
    assert _SGR.search(text) is None
    screen = _replay(text, 40, 16)
    box = {(row, col) for row in range(top - 1, top - 1 + rows) for col in range(left, left + cols)}
    ink = {
        (row, col)
        for row in range(screen.lines)
        for col in range(screen.columns)
        if screen.buffer[row][col].data != " "
    }
    assert ink
    assert ink <= box
    if tier == "ascii":
        assert all(ord(screen.buffer[row][col].data) < 128 for row, col in ink)

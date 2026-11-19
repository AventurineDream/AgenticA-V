"""Verify the approved covers: receipt bytes, refusal paths, and bounded rendering.

Each receipt hash and size comes from the approval record in docs/decisions/0002. Rendering
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
_RECEIPT_SHA256 = "e42821bc820a81a7f6b6e168dc772d1540aebfe256bfda23387bc9aecc9fdab6"
_RECEIPT_BYTES = 370_848
# album asset -> (cover asset, receipt SHA-256, receipt bytes), copied from ADR 0002.
_RECEIPTS = {
    "coupon-seance-saturn.html.gz": (
        "coupon-seance-saturn.jpg",
        "b44173b91ff51c4bada8fb601180858a414c931d049e429f4205049d608d1dbe",
        402_633,
    ),
    "drowning-collective-are-we-fish.html.gz": (
        "drowning-collective-are-we-fish.jpg",
        "07eb2ef0caa9977f9f4f905dce13bb92fece2e6f0a049468c609dcff72c38385",
        416_511,
    ),
    "nurse-log-ground-moves-anyway.html.gz": (
        "nurse-log-ground-moves-anyway.jpg",
        "76762a94a87b14db5f5b8a1cb2576fe3784cb9012eba710a33cad57c2ed8cbbd",
        779_334,
    ),
    "quiet-machinery-atlas-unlit-rooms.html.gz": (
        "quiet-machinery-atlas-unlit-rooms.jpg",
        "d479b0d15146192fa17fe76f4929c3e520b4bc1c56861a4ed9bc06294901244f",
        315_007,
    ),
    "nurse-log-the-forest-has-a-pocket.html.gz": (_ASSET, _RECEIPT_SHA256, _RECEIPT_BYTES),
}
_SGR = re.compile(r"\x1b\[[0-9;]*m")


def _artwork_bytes(asset: str = _ASSET) -> bytes:
    return files("agentic_av").joinpath("artwork", asset).read_bytes()


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


@pytest.mark.parametrize(("asset", "sha256", "size"), list(_RECEIPTS.values()))
def test_packaged_cover_is_the_approved_receipt_file(asset: str, sha256: str, size: int) -> None:
    data = _artwork_bytes(asset)
    assert len(data) == size
    assert hashlib.sha256(data).hexdigest() == sha256
    pixels = load_cover(asset, sha256)
    assert pixels.shape == (1024, 1024, 3)
    assert pixels.dtype == np.uint8


def test_each_album_records_its_receipt_cover_and_the_folder_holds_only_those() -> None:
    validate_catalog()
    covered = {
        album.asset: (album.cover.asset, album.cover.sha256)
        for album in ALBUMS
        if album.cover is not None
    }
    assert covered == {album: receipt[:2] for album, receipt in _RECEIPTS.items()}
    names = sorted(
        path.name
        for path in files("agentic_av").joinpath("artwork").iterdir()
        if not path.name.startswith(".") and path.name != "__pycache__"
    )
    assert names == sorted(asset for asset, _, _ in _RECEIPTS.values())


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

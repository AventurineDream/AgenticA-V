"""Verify exact mosaic previews, sparse braille dots, and stdlib PNG serialization."""

import struct
import zlib
from pathlib import Path

import numpy as np
import pytest

from agentic_av.viz.glyphs import TIERS, Cells
from agentic_av.viz.png import rasterize, write_png


@pytest.mark.parametrize("tier", ["octant", "sextant", "quadrant", "half"])
def test_mosaic_subpixel_blocks(tier):
    spec = TIERS[tier]
    count = spec.sub_w * spec.sub_h
    glyph = np.arange(1 << count, dtype=np.uint16)[None, :]
    fg = np.broadcast_to(np.array([20, 200, 80], dtype=np.uint8), (*glyph.shape, 3)).copy()
    bg = np.broadcast_to(np.array([4, 8, 16], dtype=np.uint8), fg.shape).copy()
    cells = Cells(tier, False, glyph, fg, bg)
    image = rasterize(cells, cell_px=(spec.sub_w * 3, spec.sub_h * 3))
    for pattern in range(1 << count):
        for bit in range(count):
            y = (bit // spec.sub_w) * 3
            x = pattern * spec.sub_w * 3 + (bit % spec.sub_w) * 3
            np.testing.assert_array_equal(
                image[y : y + 3, x : x + 3],
                np.broadcast_to(
                    fg[0, pattern] if pattern & (1 << bit) else bg[0, pattern], (3, 3, 3)
                ),
            )


@pytest.mark.parametrize("tier", ["braille", "ascii"])
def test_nonmosaic_coverage_and_mono(tier):
    glyph = np.array([[len(TIERS[tier].glyphs) - 1, 0]], dtype=np.uint16)
    fg = np.full((1, 2, 3), 255, dtype=np.uint8)
    cells = Cells(tier, True, glyph, fg, fg)
    image = rasterize(cells)
    assert image.shape == (16, 16, 3)
    assert 0 < image[:, :8].mean() < 255
    assert not image[:, 8:].any()


def test_png_chunks_and_pixels(tmp_path: Path):
    image = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)[:, ::-1]
    path = tmp_path / "test.png"
    write_png(path, image)
    raw = path.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    offset, chunks = 8, {}
    while offset < len(raw):
        length = struct.unpack("!I", raw[offset : offset + 4])[0]
        kind = raw[offset + 4 : offset + 8]
        data = raw[offset + 8 : offset + 8 + length]
        crc = struct.unpack("!I", raw[offset + 8 + length : offset + 12 + length])[0]
        assert zlib.crc32(kind + data) == crc
        chunks[kind] = data
        offset += length + 12
    assert struct.unpack("!IIBBBBB", chunks[b"IHDR"]) == (5, 4, 8, 2, 0, 0, 0)
    pixels = np.frombuffer(zlib.decompress(chunks[b"IDAT"]), dtype=np.uint8).reshape(4, 16)
    assert not pixels[:, 0].any()
    np.testing.assert_array_equal(pixels[:, 1:].reshape(4, 5, 3), image)


def test_invalid_dimensions_and_dtype(tmp_path):
    cells = Cells(
        "half",
        False,
        np.zeros((1, 1), dtype=np.uint16),
        np.zeros((1, 1, 3), dtype=np.uint8),
        np.zeros((1, 1, 3), dtype=np.uint8),
    )
    with pytest.raises(ValueError):
        rasterize(cells, cell_px=(0, 10))
    with pytest.raises(ValueError):
        write_png(tmp_path / "invalid.png", np.zeros((2, 3, 3)))

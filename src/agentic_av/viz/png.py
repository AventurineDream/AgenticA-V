"""Preview fitted cells as RGB arrays and write dependency-free PNG files.

Mosaics reproduce each pattern exactly. Braille uses circular dots; ASCII uses
coverage masks of the generated font, not a claim about the viewer's own font.
Only file writing has side effects; Pillow is not a runtime dependency.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

from agentic_av.viz._ascii_shapes import MASKS
from agentic_av.viz.glyphs import TIERS, Cells


def rasterize(cells: Cells, *, cell_px: tuple[int, int] = (8, 16)) -> np.ndarray:
    """Expand cell patterns into a uint8 RGB preview without changing Cells.

    Args:
        cells: Fitted glyphs and sRGB colors; mono uses white on black.
        cell_px: Cell width and height in pixels, both positive. Uneven mosaic
            divisions assign each pixel to the sub-pixel containing its center.

    Returns:
        RGB image, shape (rows*cell_height, cols*cell_width, 3). ASCII is an honest
        approximation using nearest-resized 8x16 antialiased font masks.

    Raises:
        ValueError: Cell dimensions are nonpositive.
        KeyError: Unknown tier.
    """
    width, height = cell_px
    if min(width, height) <= 0:
        raise ValueError("cell pixel dimensions must be positive")
    spec = TIERS[cells.tier]
    y, x = np.mgrid[:height, :width]
    if cells.tier == "ascii":
        masks = np.asarray(MASKS, dtype=np.float32) / 255
        coverage = masks[cells.glyph][..., y * 16 // height, x * 8 // width]
    elif cells.tier == "braille":
        coverage = np.zeros((*cells.glyph.shape, height, width), dtype=np.float32)
        for row in range(4):
            for col in range(2):
                # Dots occupy less area than block mosaics, as in real braille.
                dot = (
                    ((x + 0.5 - (col + 0.5) * width / 2) / (width / 6)) ** 2
                    + ((y + 0.5 - (row + 0.5) * height / 4) / (height / 12)) ** 2
                ) <= 1
                on = (cells.glyph >> (row * 2 + col)) & 1
                coverage += on[..., None, None] * dot
    else:
        bit = ((2 * y + 1) * spec.sub_h // (2 * height)) * spec.sub_w + (
            2 * x + 1
        ) * spec.sub_w // (2 * width)
        coverage = ((cells.glyph[..., None, None] >> bit) & 1).astype(np.float32)
    if cells.mono:
        image = np.repeat((coverage * 255)[..., None], 3, axis=-1)
    else:
        fg = cells.fg.astype(np.float32)[..., None, None, :]
        bg = cells.bg.astype(np.float32)[..., None, None, :]
        image = bg + coverage[..., None] * (fg - bg)
    rows, cols = cells.glyph.shape
    return (
        np.rint(image)
        .astype(np.uint8)
        .transpose(0, 2, 1, 3, 4)
        .reshape(rows * height, cols * width, 3)
    )


def write_png(path: Path, rgb8: np.ndarray) -> None:
    """Write an RGB8 image as a standard PNG using only stdlib compression.

    Args:
        path: Destination file (overwritten); its parent must already exist.
        rgb8: uint8 array of shape (height, width, 3), dimensions positive.

    Raises:
        ValueError: Image dtype or shape is invalid.
        OSError: Destination cannot be written.
    """
    if rgb8.dtype != np.uint8 or rgb8.ndim != 3 or rgb8.shape[2] != 3 or min(rgb8.shape[:2]) <= 0:
        raise ValueError("PNG input must be a nonempty RGB uint8 image")
    height, width = rgb8.shape[:2]

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
        )

    scanlines = np.zeros((height, 1 + width * 3), dtype=np.uint8)
    scanlines[:, 1:] = rgb8.reshape(height, width * 3)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(scanlines.tobytes()))
        + chunk(b"IEND", b"")
    )

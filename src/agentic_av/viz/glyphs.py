"""Fit linear-light images to two-color terminal cells without terminal I/O.

Stage supplies the image; encode and png consume Cells. Bit patterns are row-major,
left first, including braille (whose Unicode bit order differs). Soft mosaic cells
preserve top/bottom color resolution instead of unstable luminance partitions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from agentic_av.viz._ascii_shapes import SAMPLE_WEIGHTS, SHAPES


@dataclass(frozen=True, slots=True)
class Tier:
    """Describe width-one glyphs indexed by row-major sub-pixel patterns.

    Attributes:
        name: Stable tier identifier.
        sub_w: Horizontal samples per terminal cell.
        sub_h: Vertical samples per terminal cell.
        glyphs: Pattern-indexed glyphs; ASCII instead uses printable-code order.
    """

    name: str
    sub_w: int
    sub_h: int
    glyphs: tuple[str, ...]


# Unicode 16's 230 new octants plus the 26 pre-existing equivalents. A literal
# keeps Python 3.11 (Unicode 14) independent of the runtime character database.
_OCTANTS = tuple(
    " \U0001cea8\U0001ceab\U0001fb82\U0001cd00\u2598\U0001cd01\U0001cd02"
    "\U0001cd03\U0001cd04\u259d\U0001cd05\U0001cd06\U0001cd07\U0001cd08\u2580"
    "\U0001cd09\U0001cd0a\U0001cd0b\U0001cd0c\U0001fbe6\U0001cd0d\U0001cd0e\U0001cd0f"
    "\U0001cd10\U0001cd11\U0001cd12\U0001cd13\U0001cd14\U0001cd15\U0001cd16\U0001cd17"
    "\U0001cd18\U0001cd19\U0001cd1a\U0001cd1b\U0001cd1c\U0001cd1d\U0001cd1e\U0001cd1f"
    "\U0001fbe7\U0001cd20\U0001cd21\U0001cd22\U0001cd23\U0001cd24\U0001cd25\U0001cd26"
    "\U0001cd27\U0001cd28\U0001cd29\U0001cd2a\U0001cd2b\U0001cd2c\U0001cd2d\U0001cd2e"
    "\U0001cd2f\U0001cd30\U0001cd31\U0001cd32\U0001cd33\U0001cd34\U0001cd35\U0001fb85"
    "\U0001cea3\U0001cd36\U0001cd37\U0001cd38\U0001cd39\U0001cd3a\U0001cd3b\U0001cd3c"
    "\U0001cd3d\U0001cd3e\U0001cd3f\U0001cd40\U0001cd41\U0001cd42\U0001cd43\U0001cd44"
    "\u2596\U0001cd45\U0001cd46\U0001cd47\U0001cd48\u258c\U0001cd49\U0001cd4a"
    "\U0001cd4b\U0001cd4c\u259e\U0001cd4d\U0001cd4e\U0001cd4f\U0001cd50\u259b"
    "\U0001cd51\U0001cd52\U0001cd53\U0001cd54\U0001cd55\U0001cd56\U0001cd57\U0001cd58"
    "\U0001cd59\U0001cd5a\U0001cd5b\U0001cd5c\U0001cd5d\U0001cd5e\U0001cd5f\U0001cd60"
    "\U0001cd61\U0001cd62\U0001cd63\U0001cd64\U0001cd65\U0001cd66\U0001cd67\U0001cd68"
    "\U0001cd69\U0001cd6a\U0001cd6b\U0001cd6c\U0001cd6d\U0001cd6e\U0001cd6f\U0001cd70"
    "\U0001cea0\U0001cd71\U0001cd72\U0001cd73\U0001cd74\U0001cd75\U0001cd76\U0001cd77"
    "\U0001cd78\U0001cd79\U0001cd7a\U0001cd7b\U0001cd7c\U0001cd7d\U0001cd7e\U0001cd7f"
    "\U0001cd80\U0001cd81\U0001cd82\U0001cd83\U0001cd84\U0001cd85\U0001cd86\U0001cd87"
    "\U0001cd88\U0001cd89\U0001cd8a\U0001cd8b\U0001cd8c\U0001cd8d\U0001cd8e\U0001cd8f"
    "\u2597\U0001cd90\U0001cd91\U0001cd92\U0001cd93\u259a\U0001cd94\U0001cd95"
    "\U0001cd96\U0001cd97\u2590\U0001cd98\U0001cd99\U0001cd9a\U0001cd9b\u259c"
    "\U0001cd9c\U0001cd9d\U0001cd9e\U0001cd9f\U0001cda0\U0001cda1\U0001cda2\U0001cda3"
    "\U0001cda4\U0001cda5\U0001cda6\U0001cda7\U0001cda8\U0001cda9\U0001cdaa\U0001cdab"
    "\u2582\U0001cdac\U0001cdad\U0001cdae\U0001cdaf\U0001cdb0\U0001cdb1\U0001cdb2"
    "\U0001cdb3\U0001cdb4\U0001cdb5\U0001cdb6\U0001cdb7\U0001cdb8\U0001cdb9\U0001cdba"
    "\U0001cdbb\U0001cdbc\U0001cdbd\U0001cdbe\U0001cdbf\U0001cdc0\U0001cdc1\U0001cdc2"
    "\U0001cdc3\U0001cdc4\U0001cdc5\U0001cdc6\U0001cdc7\U0001cdc8\U0001cdc9\U0001cdca"
    "\U0001cdcb\U0001cdcc\U0001cdcd\U0001cdce\U0001cdcf\U0001cdd0\U0001cdd1\U0001cdd2"
    "\U0001cdd3\U0001cdd4\U0001cdd5\U0001cdd6\U0001cdd7\U0001cdd8\U0001cdd9\U0001cdda"
    "\u2584\U0001cddb\U0001cddc\U0001cddd\U0001cdde\u2599\U0001cddf\U0001cde0"
    "\U0001cde1\U0001cde2\u259f\U0001cde3\u2586\U0001cde4\U0001cde5\u2588"
)
_SEXTANTS = tuple(" 🬀🬁🬂🬃🬄🬅🬆🬇🬈🬉🬊🬋🬌🬍🬎🬏🬐🬑🬒🬓▌🬔🬕🬖🬗🬘🬙🬚🬛🬜🬝🬞🬟🬠🬡🬢🬣🬤🬥🬦🬧▐🬨🬩🬪🬫🬬🬭🬮🬯🬰🬱🬲🬳🬴🬵🬶🬷🬸🬹🬺🬻█")
_QUADRANTS = tuple(" ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█")
_BRAILLE_BITS = (0, 3, 1, 4, 2, 5, 6, 7)
_BRAILLE = tuple(
    chr(0x2800 + sum(((pattern >> bit) & 1) << dot for bit, dot in enumerate(_BRAILLE_BITS)))
    if pattern
    else " "
    for pattern in range(256)
)
TIER_ORDER = ("octant", "sextant", "quadrant", "half", "braille", "ascii")
TIERS: Mapping[str, Tier] = MappingProxyType(
    {
        "octant": Tier("octant", 2, 4, _OCTANTS),
        "sextant": Tier("sextant", 2, 3, _SEXTANTS),
        "quadrant": Tier("quadrant", 2, 2, _QUADRANTS),
        "half": Tier("half", 1, 2, tuple(" ▀▄█")),
        "braille": Tier("braille", 2, 4, _BRAILLE),
        "ascii": Tier("ascii", 2, 3, tuple(chr(code) for code in range(32, 127))),
    }
)


@dataclass(slots=True)
class Cells:
    """Own one fitted frame with uint16 glyph indices and uint8 sRGB colors.

    Attributes:
        tier: Key in TIERS.
        mono: Whether glyph patterns alone carry luminance (colors ignored).
        glyph: Glyph indices, shape (rows, cols).
        fg: Foreground RGB bytes, shape (rows, cols, 3).
        bg: Background RGB bytes, shape (rows, cols, 3).
    """

    tier: str
    mono: bool
    glyph: np.ndarray
    fg: np.ndarray
    bg: np.ndarray


_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
# 65536 linear samples keep rounding error below one output code even near black.
_LINEAR = np.linspace(0, 1, 65536, dtype=np.float64)
_SRGB = np.rint(
    255 * np.where(_LINEAR <= 0.0031308, 12.92 * _LINEAR, 1.055 * _LINEAR ** (1 / 2.4) - 0.055)
).astype(np.uint8)
# 12/255 gamma-luminance contrast is low enough for gradients but above noise.
_SOFT_CONTRAST = 12 / 255
_BAYER = np.array(
    [
        [0, 48, 12, 60, 3, 51, 15, 63],
        [32, 16, 44, 28, 35, 19, 47, 31],
        [8, 56, 4, 52, 11, 59, 7, 55],
        [40, 24, 36, 20, 43, 27, 39, 23],
        [2, 50, 14, 62, 1, 49, 13, 61],
        [34, 18, 46, 30, 33, 17, 45, 29],
        [10, 58, 6, 54, 9, 57, 5, 53],
        [42, 26, 38, 22, 41, 25, 37, 21],
    ],
    dtype=np.float32,
)
_SHAPES = np.asarray(SHAPES, dtype=np.float32)
_SHAPE_COST = np.sum(_SHAPES * _SHAPES, axis=1)
_SAMPLES = np.asarray(SAMPLE_WEIGHTS, dtype=np.float32)


def _srgb(rgb: np.ndarray) -> np.ndarray:
    return _SRGB[np.rint(np.clip(rgb, 0, 1) * 65535).astype(np.uint16)]


def fit(rgb: np.ndarray, tier: str, *, mono: bool = False) -> Cells:
    """Fit a linear-light image without modifying its storage.

    Args:
        rgb: Finite RGB image, shape (rows*sub_h, cols*sub_w, 3); clipped to 0..1.
        tier: Key in TIERS.
        mono: Ordered sub-pixel dithering instead of two-color fitting.

    Returns:
        Newly owned glyph and sRGB color arrays. Soft mosaics use a stable upper
        half (middle sextant row belongs to the top); equal encoded halves use space.

    Raises:
        KeyError: Unknown tier.
        ValueError: Image dimensions are incompatible with the tier.
    """
    spec = TIERS[tier]
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.shape[0] % spec.sub_h or rgb.shape[1] % spec.sub_w:
        raise ValueError("image shape must match the tier sub-pixel grid")
    rows, cols = rgb.shape[0] // spec.sub_h, rgb.shape[1] // spec.sub_w
    count = spec.sub_w * spec.sub_h
    image = np.clip(rgb, 0, 1)
    blocks = (
        image.reshape(rows, spec.sub_h, cols, spec.sub_w, 3)
        .transpose(0, 2, 1, 3, 4)
        .reshape(rows, cols, count, 3)
    )
    lum_image = (_srgb(image).astype(np.float32) @ _LUMA) / 255
    lum = (
        lum_image.reshape(rows, spec.sub_h, cols, spec.sub_w)
        .transpose(0, 2, 1, 3)
        .reshape(rows, cols, count)
    )
    low, high = lum.min(axis=-1), lum.max(axis=-1)
    if mono:
        y, x = np.ogrid[: image.shape[0], : image.shape[1]]
        on_image = lum_image > (_BAYER[y % 8, x % 8] + 0.5) / 64
        on = (
            on_image.reshape(rows, spec.sub_h, cols, spec.sub_w)
            .transpose(0, 2, 1, 3)
            .reshape(rows, cols, count)
        )
    else:
        on = lum > ((low + high) * 0.5)[..., None]
    weight = on.astype(np.float32)
    lit_count = weight.sum(axis=-1)[..., None]
    total = np.einsum("...pc->...c", blocks)
    lit = np.einsum("...pc,...p->...c", blocks, weight)
    fg = lit / np.maximum(lit_count, 1)
    bg = (total - lit) / np.maximum(count - lit_count, 1)
    if tier == "ascii":
        samples = (on.astype(np.float32) if mono else lum) @ _SAMPLES
        peak = samples.max(axis=-1, keepdims=True)
        # Harri's normalized exponent retains the brightest sample while crunching
        # the darker ones, emphasizing contours without global brightness pumping.
        samples = samples * samples / np.maximum(peak, 1e-6)
        scores = samples.reshape(-1, 6) @ (-2 * _SHAPES.T)
        scores += _SHAPE_COST
        glyph = scores.argmin(axis=-1).reshape(rows, cols).astype(np.uint16)
        if not mono:
            flat = high == low
            glyph[flat] = 0
            bg[flat] = total[flat] / count
    else:
        glyph = (on * (1 << np.arange(count, dtype=np.uint16))).sum(axis=-1, dtype=np.uint16)
        if not mono and tier != "braille":
            soft = high - low < _SOFT_CONTRAST
            split = ((spec.sub_h + 1) // 2) * spec.sub_w
            soft_blocks = blocks[soft]
            fg[soft] = soft_blocks[:, :split].mean(axis=1)
            bg[soft] = soft_blocks[:, split:].mean(axis=1)
            glyph[soft] = (1 << split) - 1
    f8, b8 = _srgb(fg), _srgb(bg)
    if not mono:
        equal = np.all(f8 == b8, axis=-1)
        glyph[equal] = 0
        full = (glyph == (1 << count) - 1) if tier != "ascii" else np.zeros_like(equal)
        glyph[full] = 0
        b8[full] = f8[full]
    return Cells(tier, mono, glyph, f8, b8)

"""Decode bundled album covers, fit them into terminal panels, and pick their accent.

`native.py` decides where the panel sits. This module verifies the packaged JPEG
against its receipt SHA-256 and decodes it with Pillow (a declared runtime
dependency). It converts the image to linear light before any resampling, so
highlights and fine detail are averaged as light rather than as gamma-encoded
numbers. A Lanczos filter keeps edges crisp at half-block resolution, and the
stage's mosaic fitter and row encoder finish the job. Color and no-color output
therefore follow the stage's rules. Nothing here writes to the terminal; the
caller places the returned bytes inside its synchronized frame.

`cover_accent` reduces a cover to one signature color, which the player uses to tie
its chrome to the album. It never alters the image itself.
"""

from __future__ import annotations

import hashlib
import io
from importlib.resources import files

import numpy as np
from PIL import Image

from agentic_av.viz.encode import FrameEncoder
from agentic_av.viz.glyphs import TIERS, fit

# sRGB byte -> linear light; a gather is far cheaper than the power curve per pixel.
_CODES = np.arange(256, dtype=np.float64) / 255
_TO_LINEAR = np.where(_CODES <= 0.04045, _CODES / 12.92, ((_CODES + 0.055) / 1.055) ** 2.4).astype(
    np.float32
)
# Accent search: a small thumbnail is enough to find a hue family, and 18 bins of 20
# degrees separate the families a listener would name (teal versus green, amber versus red).
_ACCENT_THUMB = 48
_HUE_BINS = 18
# Below this mean weight per pixel the cover is effectively gray, and its mean is the accent.
_MIN_VIVID = 1e-3
# The accent's brightest channel is raised to at least this, keeping hue and saturation.
_ACCENT_VALUE = 0.85
# Prepared covers keep at least this many pixels on their short side.
_PREPARED_EDGE = 256


class ArtworkError(RuntimeError):
    """A packaged cover is missing, altered, or not a decodable JPEG."""


def decode_cover(data: bytes, sha256: str) -> np.ndarray:
    """Verify one cover's bytes and decode them.

    The digest is checked before decoding, so an altered file never reaches the
    decoder. Shipped bytes must equal the receipt exactly; metadata is not stripped.

    Args:
        data: Exact file bytes as shipped.
        sha256: Expected lowercase hex digest from the selection receipt.

    Returns:
        Owned uint8 RGB array of shape (height, width, 3), in sRGB.

    Raises:
        ArtworkError: The digest differs, or the bytes are not a decodable JPEG.
    """
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ArtworkError("cover bytes do not match the recorded SHA-256")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "JPEG":
                raise ArtworkError(f"cover is {image.format}, not JPEG")
            return np.array(image.convert("RGB"), dtype=np.uint8)
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise ArtworkError(f"cover is not a decodable JPEG: {error}") from error


def load_cover(asset: str, sha256: str) -> np.ndarray:
    """Read one packaged cover from `agentic_av/artwork` and decode it.

    Args:
        asset: JPEG basename, as recorded in the catalog.
        sha256: Expected digest; see `decode_cover`.

    Returns:
        Owned uint8 RGB pixels in sRGB.

    Raises:
        ArtworkError: The file is unreadable, altered, or not a JPEG.
    """
    try:
        data = files("agentic_av").joinpath("artwork", asset).read_bytes()
    except OSError as error:
        raise ArtworkError(f"cover {asset} is unreadable: {error}") from error
    return decode_cover(data, sha256)


def render_cover(
    pixels: np.ndarray,
    *,
    cols: int,
    rows: int,
    tier: str,
    color_mode: str,
    top: int,
    left: int,
) -> bytes:
    """Fit a cover into a `cols` by `rows` panel and encode it as terminal rows.

    The image is converted to linear light first, because `fit` expects linear
    input and because averaging light keeps bright detail from muddying. It is
    then Lanczos-resampled to the tier's sub-pixel grid; the filter's slight
    overshoot is clipped. Every panel row is emitted, so a caller that clears the
    area first gets the full picture.

    Args:
        pixels: sRGB uint8 RGB image from `load_cover`, or the float32 linear
            image from `prepare_cover`, which skips the per-call conversion.
        cols: Panel width in character cells, positive.
        rows: Panel height in character cells, positive.
        tier: Mosaic tier key, such as ``half`` or ``ascii``.
        color_mode: ``truecolor``, ``256``, or ``none``. ``none`` emits dithered
            glyphs with no SGR sequences.
        top: One-based terminal row of the panel's top edge.
        left: Zero-based column offset of the panel's left edge.

    Returns:
        Cursor-addressed UTF-8/ANSI bytes with no sync wrapper or clear.

    Raises:
        ValueError: The panel size, offset, color mode, or pixel dtype is invalid.
        KeyError: The tier is unknown.
    """
    if cols < 1 or rows < 1:
        raise ValueError("cover panel dimensions must be positive")
    spec = TIERS[tier]
    if pixels.dtype == np.uint8:
        linear = prepare_cover(pixels)
    elif pixels.dtype == np.float32:
        linear = pixels
    else:
        raise ValueError(f"cover pixels must be uint8 sRGB or float32 linear, not {pixels.dtype}")
    size = (cols * spec.sub_w, rows * spec.sub_h)
    # Pillow resamples float images one band at a time ("F" mode).
    bands = [
        np.asarray(
            Image.fromarray(np.ascontiguousarray(linear[..., band])).resize(
                size, Image.Resampling.LANCZOS
            )
        )
        for band in range(3)
    ]
    linear_rgb = np.clip(np.stack(bands, axis=-1), 0, 1).astype(np.float32)
    cells = fit(linear_rgb, tier, mono=color_mode == "none")
    return FrameEncoder(color_mode).encode(cells, top=top, left=left)


def prepare_cover(pixels: np.ndarray) -> np.ndarray:
    """Convert a decoded cover to linear light, area-reduced for repeated fitting.

    Linearizing a full 1024-pixel cover costs tens of milliseconds, too much to
    repeat on every layout change, so the player prepares a cover once. The image
    is reduced by the largest integer factor that keeps its short side at least
    `_PREPARED_EDGE` pixels, enough for a 128-row half-block panel; larger panels
    upsample slightly, which Lanczos handles gracefully. Averaging
    happens after linearization, so it is an exact area mean of light; a few edge
    pixels are cropped when the size is not a multiple of the factor.

    Args:
        pixels: sRGB uint8 RGB image from `load_cover`.

    Returns:
        Owned, contiguous float32 linear RGB in 0..1, accepted by `render_cover`.
    """
    height, width = pixels.shape[:2]
    factor = max(1, min(height, width) // _PREPARED_EDGE)
    linear = _TO_LINEAR[pixels]
    if factor > 1:
        rows, cols = height // factor, width // factor
        linear = (
            linear[: rows * factor, : cols * factor]
            .reshape(rows, factor, cols, factor, 3)
            .mean(axis=(1, 3))
        )
    return np.ascontiguousarray(linear, dtype=np.float32)


def cover_accent(pixels: np.ndarray) -> tuple[int, int, int]:
    """Pick a cover's signature color: the dominant vivid hue family.

    Each pixel of a small thumbnail votes for its hue with a weight of chroma
    squared (saturation times value, squared). Near-black, near-gray, and
    washed-out areas barely count, and a small lit feature outvotes a large dim
    field (Dusk's amber light shaft over its blue-black room). The winning
    20-degree hue bin, pooled with its two neighbors so a family split across a
    bin edge is not penalized, is averaged by the same weights. A cover with no
    meaningful color returns its plain mean, unscaled.

    Args:
        pixels: sRGB uint8 RGB image from `load_cover`.

    Returns:
        An sRGB byte triple. For a colorful cover it carries the family's hue and
        saturation, scaled so its brightest channel reaches at least
        `_ACCENT_VALUE`: dark covers still yield a color that reads as light on a
        dark background. A gray or black cover returns its unscaled mean. Callers
        enforce their own contrast, as `nowplaying.album_accent` does.
    """
    thumb = Image.fromarray(pixels).resize((_ACCENT_THUMB, _ACCENT_THUMB), Image.Resampling.BOX)
    flat = np.asarray(thumb, dtype=np.float32).reshape(-1, 3) / 255
    high, low = flat.max(axis=1), flat.min(axis=1)
    chroma = high - low
    weight = chroma**2
    if weight.mean() < _MIN_VIVID:
        return _bytes(flat.mean(axis=0))
    red, green, blue = flat.T
    safe = np.maximum(chroma, 1e-6)
    hue = np.where(
        high == red,
        ((green - blue) / safe) % 6,
        np.where(high == green, (blue - red) / safe + 2, (red - green) / safe + 4),
    )
    bins = (hue / 6 * _HUE_BINS).astype(np.int64) % _HUE_BINS
    votes = np.bincount(bins, weights=weight, minlength=_HUE_BINS)
    pooled = votes + np.roll(votes, 1) + np.roll(votes, -1)
    best = int(pooled.argmax())
    members = np.isin(bins, [(best - 1) % _HUE_BINS, best, (best + 1) % _HUE_BINS])
    chosen = weight * members
    mean = (flat * chosen[:, None]).sum(axis=0) / chosen.sum()
    return _bytes(mean * max(1.0, _ACCENT_VALUE / max(float(mean.max()), 1e-6)))


def _bytes(rgb: np.ndarray) -> tuple[int, int, int]:
    """Round a 0..1 RGB triple to sRGB bytes."""
    red, green, blue = (round(float(value) * 255) for value in rgb)
    return red, green, blue

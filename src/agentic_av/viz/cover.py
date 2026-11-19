"""Decode bundled album covers and fit them into terminal panels.

`native.py` decides where the panel sits. This module verifies the packaged JPEG
against its receipt SHA-256, decodes it with Pillow (a declared runtime
dependency), resamples it in sRGB, converts to linear light, and fits it with the
stage's mosaic fitter and row encoder. Color and no-color output therefore follow
the stage's rules. Nothing here writes to the terminal; the caller places the
returned bytes inside its synchronized frame.
"""

from __future__ import annotations

import hashlib
import io
from importlib.resources import files

import numpy as np
from PIL import Image

from agentic_av.viz.encode import FrameEncoder
from agentic_av.viz.glyphs import TIERS, fit


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

    The image is box-filtered to the tier's sub-pixel grid, then converted to
    linear light because `fit` expects linear input. Every panel row is emitted,
    so a caller that clears the area first gets the full picture.

    Args:
        pixels: sRGB uint8 RGB image from `load_cover`.
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
        ValueError: The panel size, offset, or color mode is invalid.
        KeyError: The tier is unknown.
    """
    if cols < 1 or rows < 1:
        raise ValueError("cover panel dimensions must be positive")
    spec = TIERS[tier]
    sampled = Image.fromarray(pixels).resize(
        (cols * spec.sub_w, rows * spec.sub_h), Image.Resampling.BOX
    )
    srgb = np.asarray(sampled, dtype=np.float32) / 255
    linear_rgb = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    cells = fit(linear_rgb.astype(np.float32), tier, mono=color_mode == "none")
    return FrameEncoder(color_mode).encode(cells, top=top, left=left)

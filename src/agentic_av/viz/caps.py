"""Choose conservative terminal glyphs and bound the sub-pixel workload.

Playback calls these helpers; detection uses supplied environment only and never
probes by printing. Pixel dimensions come from the terminal ioctl when available.
"""

from __future__ import annotations

import fcntl
import struct
import termios
from collections.abc import Mapping

from agentic_av.viz.glyphs import TIERS


def detect_tier(env: Mapping[str, str]) -> str:
    """Select verified native mosaics, honoring an explicit glyph override.

    Args:
        env: Environment variables; never mutated.

    Returns:
        Validated AAV_GLYPHS, octant for kitty, ascii for linux/dumb, otherwise half.

    Raises:
        ValueError: AAV_GLYPHS is set to an unknown tier (including empty strings).
    """
    override = env.get("AAV_GLYPHS")
    if override is not None:
        if override not in TIERS:
            raise ValueError(f"unknown AAV_GLYPHS tier: {override!r}")
        return override
    term = env.get("TERM", "")
    if term in ("linux", "dumb"):
        return "ascii"
    # kitty draws octants internally, not via font fallback; also verified live
    # with all 256 patterns in kitty 0.49.2 for this project.
    # Primary source: https://github.com/kovidgoyal/kitty/blob/master/kitty/decorations.c
    # render_box_char dispatches U+1CD00..1CDE5 to octant(); PR #9850 adds corners.
    if term == "xterm-kitty" or env.get("TERM_PROGRAM", "").lower() == "kitty":
        return "octant"
    return "half"


def cell_aspect(fd: int) -> float:
    """Return cell height/width from TIOCGWINSZ, or 2.0 when unavailable.

    Args:
        fd: Terminal file descriptor; it is not closed or modified.

    Returns:
        Positive cell aspect ratio; missing/zero dimensions use the fallback.
    """
    try:
        rows, cols, width, height = struct.unpack(
            "HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8)
        )
    except (OSError, ValueError):
        return 2.0
    if min(rows, cols, width, height) == 0:
        return 2.0
    return height * cols / (width * rows)


def budget_tier(tier: str, cols: int, rows: int) -> str:
    """Step down mosaic resolution when the image would exceed 110k samples.

    Args:
        tier: Requested tier identifier.
        cols: Canvas width in terminal cells, nonnegative.
        rows: Canvas height in terminal cells, nonnegative.

    Returns:
        A tier at or below the requested sampling cost. Half is the minimum
        mosaic; ASCII stays ASCII because console compatibility beats the budget.

    Raises:
        KeyError: Unknown tier.
        ValueError: Negative canvas dimensions.
    """
    spec = TIERS[tier]
    if min(cols, rows) < 0:
        raise ValueError("canvas dimensions must be nonnegative")
    if tier == "ascii":
        return tier
    if cols * rows * spec.sub_w * spec.sub_h <= 110_000:
        return tier
    for candidate in ("sextant", "quadrant", "half"):
        lower = TIERS[candidate]
        if (
            lower.sub_w * lower.sub_h < spec.sub_w * spec.sub_h
            and cols * rows * lower.sub_w * lower.sub_h <= 110_000
        ):
            return candidate
    return "half"

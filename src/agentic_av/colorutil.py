"""Hex color math for palettes and the stage painter.

paint, palette, nowplaying, and the viz encoder call this. No I/O. Hex colors that leave
this module are lowercase ``#rrggbb``; ``to_xterm256`` is the index exception.
Three-digit hex is rejected: Omarchy themes use six. The xterm-256 rule lives
only here so the scalar chrome path and the vectorized frame encoder agree.
"""

from __future__ import annotations

import functools
import math
import re

import numpy as np

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_hex(value: str) -> tuple[int, int, int] | None:
    """Parse ``#rrggbb`` into channels from 0 to 255.

    Args:
        value: A color token. Surrounding space is ignored. ``#RGB`` is not
            accepted.

    Returns:
        Channel triple, or None when the token is not six-digit hex.
    """
    match = _HEX.fullmatch(value.strip())
    if not match:
        return None
    raw = match.group(1)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def normalize_hex(value: str) -> str | None:
    """Return lowercase ``#rrggbb``, or None if `value` is not six-digit hex."""
    parsed = parse_hex(value)
    if parsed is None:
        return None
    return to_hex(parsed)


def to_hex(rgb: tuple[int, int, int]) -> str:
    """Format a channel triple as lowercase ``#rrggbb``.

    Args:
        rgb: Channels from 0 to 255. Values outside that range are clamped.

    Returns:
        Lowercase hex, including the leading ``#``.
    """
    r, g, b = (max(0, min(255, channel)) for channel in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def mix(a: str, b: str, t: float) -> str:
    """Blend `a` toward `b`.

    Args:
        a: Start color, ``#rrggbb``.
        b: End color, ``#rrggbb``.
        t: 0 returns `a`, 1 returns `b`. Out of range is clamped.

    Returns:
        Blended ``#rrggbb``.

    Raises:
        ValueError: Either color is not six-digit hex. Callers pass palette
            roles, which are already normalized.
    """
    left = parse_hex(a)
    right = parse_hex(b)
    if left is None or right is None:
        raise ValueError(f"mix() needs #rrggbb, got {a!r} and {b!r}")
    amount = max(0.0, min(1.0, t))
    blended = tuple(round(c0 + (c1 - c0) * amount) for c0, c1 in zip(left, right, strict=True))
    return to_hex(blended)


def relative_luminance(value: str) -> float:
    """Return WCAG relative luminance for `value`, from 0 to 1.

    Raises:
        ValueError: `value` is not six-digit hex.
    """
    parsed = parse_hex(value)
    if parsed is None:
        raise ValueError(f"relative_luminance() needs #rrggbb, got {value!r}")

    def channel(unit: int) -> float:
        srgb = unit / 255
        if srgb <= 0.04045:
            return srgb / 12.92
        return ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(unit) for unit in parsed)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """Return the WCAG contrast ratio between two ``#rrggbb`` colors, ≥ 1."""
    lighter = relative_luminance(a)
    darker = relative_luminance(b)
    if darker > lighter:
        lighter, darker = darker, lighter
    return (lighter + 0.05) / (darker + 0.05)


def to_xterm256(value: str) -> int:
    """Quantize ``#rrggbb`` to an xterm-256 color index.

    Cube channels snap to ``0, 95, 135, 175, 215, 255``, not a uniform
    ``0..255 / 5`` scale (that maps ``#5f0000`` to 88 instead of 52). The gray
    ramp is ``8, 18, ..., 238``. Cube black (16) and white (231) win when they
    are nearer than that ramp. When that nearest entry is neutral but the color
    visibly has a hue, `xterm256_hue_match` substitutes a cube entry of the
    same hue family; see that function for why.

    Args:
        value: A ``#rrggbb`` color.

    Returns:
        An index from 16 to 255. ANSI colors 0-15 are not used.

    Raises:
        ValueError: `value` is not six-digit hex.
    """
    parsed = parse_hex(value)
    if parsed is None:
        raise ValueError(f"to_xterm256() needs #rrggbb, got {value!r}")
    red, green, blue = parsed
    cube_index = tuple(_nearest_level(channel, _CUBE_LEVELS) for channel in (red, green, blue))
    cube_rgb = tuple(_CUBE_LEVELS[index] for index in cube_index)
    cube_color = 16 + 36 * cube_index[0] + 6 * cube_index[1] + cube_index[2]
    cube_dist = _sq_dist((red, green, blue), cube_rgb)
    gray_slot = min(
        range(len(_GRAY_LEVELS)),
        key=lambda index: _sq_dist((red, green, blue), (_GRAY_LEVELS[index],) * 3),
    )
    gray_level = _GRAY_LEVELS[gray_slot]
    gray_dist = _sq_dist((red, green, blue), (gray_level, gray_level, gray_level))
    # Strictly nearer gray keeps an exact cube color, including black and white.
    if gray_dist < cube_dist:
        nearest, neutral = 232 + gray_slot, True
    else:
        nearest, neutral = cube_color, cube_index[0] == cube_index[1] == cube_index[2]
    if neutral:
        hue_color = int(xterm256_hue_match(np.array((red, green, blue))))
        if hue_color:
            return hue_color
    return nearest


# xterm's cube is 0, then 95, then +40. Dividing by 51 rounds 95 onto 135.
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)
# Indexes 232-255. Not 23 even steps across 8..255; 238 is the last ramp value.
_GRAY_LEVELS = tuple(8 + 10 * step for step in range(24))

# Hue match thresholds, in OKLab units (L and chroma 0..1). Tuned on the bundled
# covers: Coupon Seance's dark violet sky (chroma ~0.055) must keep its hue,
# while warm-gray walls and near-black tinted backgrounds stay on the ramp.
_HUE_MIN_CHROMA = 0.045  # below this a source reads as gray; keep the ramp
# A candidate must stay in the source's hue family. At 25 degrees more of Quiet
# Machinery's tan light shaft went dark red, and the sky magenta, not violet.
_HUE_MAX_ANGLE = math.radians(12)
# The cube's first step is large (0 to 95), so the darkest violet (#5f0087) sits
# well above a dark sky; 0.12 left the sky's darkest corner as gray blotches.
_HUE_MAX_LIGHTNESS = 0.16
_HUE_CANDIDATE_CHROMA = 0.04  # the candidate must itself be chromatic
_HUE_SHIFT = 3  # 8-bit channel to 5-bit table bin

_LMS = np.array(
    (
        (0.4122214708, 0.5363325363, 0.0514459929),
        (0.2119034982, 0.6806995451, 0.1073969566),
        (0.0883024619, 0.2817188376, 0.6299787005),
    )
)
_OKLAB = np.array(
    (
        (0.2104542553, 0.7936177850, -0.0040720468),
        (1.9779984951, -2.4285922050, 0.4505937099),
        (0.0259040371, 0.7827717662, -0.8086757136),
    )
)
_SRGB = np.arange(256) / 255
_TO_LINEAR = np.where(_SRGB <= 0.04045, _SRGB / 12.92, ((_SRGB + 0.055) / 1.055) ** 2.4)


def xterm256_hue_match(rgb: np.ndarray) -> np.ndarray:
    """Return a same-hue cube index for each color, or 0 where none applies.

    Euclidean-nearest quantization sends dark, muted colors to the gray ramp:
    the cube has no dark muted entries (its first step is 0 to 95), so a violet
    sky such as ``#2b1b37`` is nearer ramp gray 235 than any cube color and a
    cover loses its hue. For a color with visible OKLab chroma this returns the
    nearest cube entry (OKLab distance) within a narrow hue angle and a bounded
    lightness change. `to_xterm256` and the frame encoder use it only when their
    nearest entry is neutral, so chromatic matches and true grays are unchanged.

    The candidate comes from a table of 5-bit bins, then is checked against the
    exact color, so binning never lends a dark warm gray the hue of its bin.

    Args:
        rgb: Integer sRGB channels 0..255, shape (..., 3).

    Returns:
        Integer array of shape ``rgb.shape[:-1]``: cube indexes 16..231, or 0
        to keep the nearest entry.
    """
    channels = np.asarray(rgb, dtype=np.intp)
    table, cube_lab = _hue_table()
    bins = channels >> _HUE_SHIFT
    candidate = table[bins[..., 0], bins[..., 1], bins[..., 2]]
    source = _oklab_linear(_TO_LINEAR[channels])
    target = cube_lab[np.maximum(candidate.astype(np.intp) - 16, 0)]
    keep = (
        (candidate > 0)
        & (np.hypot(source[..., 1], source[..., 2]) >= _HUE_MIN_CHROMA)
        & (_hue_turn(source, target) <= _HUE_MAX_ANGLE)
        & (np.abs(source[..., 0] - target[..., 0]) <= _HUE_MAX_LIGHTNESS)
    )
    return np.where(keep, candidate, 0)


@functools.cache
def _hue_table() -> tuple[np.ndarray, np.ndarray]:
    """Build the per-bin hue candidates once and the cube's OKLab values.

    Bin centers are ranked against every chromatic cube entry within the hue and
    lightness limits; the source-chroma gate is left to the exact per-color check.
    """
    bins = 256 >> _HUE_SHIFT
    centers = (np.arange(bins) << _HUE_SHIFT) + (1 << (_HUE_SHIFT - 1))
    levels = np.asarray(_CUBE_LEVELS)
    # meshgrid "ij" order matches cube index 16 + 36r + 6g + b.
    cube_rgb = np.stack(np.meshgrid(levels, levels, levels, indexing="ij"), -1).reshape(-1, 3)
    cube_lab = _oklab_linear(_TO_LINEAR[cube_rgb])
    grid = np.stack(np.meshgrid(centers, centers, centers, indexing="ij"), -1).reshape(-1, 3)
    source = _oklab_linear(_TO_LINEAR[grid])
    best = np.zeros(len(grid), dtype=np.uint8)
    best_distance = np.full(len(grid), np.inf)
    for index, target in enumerate(cube_lab):
        if np.hypot(target[1], target[2]) < _HUE_CANDIDATE_CHROMA:
            continue
        distance = ((source - target) ** 2).sum(axis=-1)
        better = (
            (distance < best_distance)
            & (_hue_turn(source, target) <= _HUE_MAX_ANGLE)
            & (np.abs(source[:, 0] - target[0]) <= _HUE_MAX_LIGHTNESS)
        )
        best[better] = 16 + index
        best_distance[better] = distance[better]
    table = best.reshape(bins, bins, bins)
    table.flags.writeable = False
    cube_lab.flags.writeable = False
    return table, cube_lab


def _oklab_linear(linear: np.ndarray) -> np.ndarray:
    """Convert linear-light RGB (0..1, shape (..., 3)) to OKLab (L, a, b)."""
    return np.cbrt(linear @ _LMS.T) @ _OKLAB.T


def _hue_turn(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Return the absolute OKLab hue angle between colors, in radians (0..pi)."""
    turn = np.arctan2(left[..., 2], left[..., 1]) - np.arctan2(right[..., 2], right[..., 1])
    return np.abs((turn + math.pi) % (2 * math.pi) - math.pi)


def _nearest_level(channel: int, levels: tuple[int, ...]) -> int:
    """Return the index of the closest level. Ties prefer the darker level."""
    return min(range(len(levels)), key=lambda index: (abs(channel - levels[index]), index))


def _sq_dist(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2

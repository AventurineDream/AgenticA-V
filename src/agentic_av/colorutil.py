"""Hex color math for palettes and the stage painter.

paint and palette call this. No I/O. Hex colors that leave this module are
lowercase ``#rrggbb``; ``to_xterm256`` is the index exception. Three-digit hex
is rejected: Omarchy themes use six.
"""

from __future__ import annotations

import re

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
    are nearer than that ramp. Raises ValueError on a bad token.

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
        return 232 + gray_slot
    return cube_color


# xterm's cube is 0, then 95, then +40. Dividing by 51 rounds 95 onto 135.
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)
# Indexes 232-255. Not 23 even steps across 8..255; 238 is the last ramp value.
_GRAY_LEVELS = tuple(8 + 10 * step for step in range(24))


def _nearest_level(channel: int, levels: tuple[int, ...]) -> int:
    """Return the index of the closest level. Ties prefer the darker level."""
    return min(range(len(levels)), key=lambda index: (abs(channel - levels[index]), index))


def _sq_dist(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2

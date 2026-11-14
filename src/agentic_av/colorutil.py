"""Hex color math for palettes and the stage painter.

paint and palette call this. No I/O. Every color that leaves this module is
lowercase ``#rrggbb``. Three-digit hex is rejected: Omarchy themes use six.
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

    The 6x6x6 cube plus the grayscale ramp. Used only when the terminal is
    not truecolor. Raises ValueError on a bad token.
    """
    parsed = parse_hex(value)
    if parsed is None:
        raise ValueError(f"to_xterm256() needs #rrggbb, got {value!r}")
    r, g, b = parsed
    if abs(r - g) < 8 and abs(g - b) < 8:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + round((r - 8) / 247 * 23)

    def cube(channel: int) -> int:
        return round(channel / 255 * 5)

    return 16 + 36 * cube(r) + 6 * cube(g) + cube(b)

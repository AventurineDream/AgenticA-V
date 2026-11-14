"""Deterministic abstract fields for the media-free demonstration reel.

paint samples these functions in pixel space; no random state or image assets
are used, so screenshots and test fixtures are repeatable at a fixed time.
"""

from __future__ import annotations

import math

PROGRAM_LABELS = {
    "garden": "Signal Garden",
    "aperture": "Iris Study",
    "scan": "Raster Weather",
    "tide": "Tidal Memory",
}


def _hash(x: int, y: int, t: int) -> float:
    """Return stable 0..1 value noise at one integer lattice point."""
    value = (x * 0x45D9F3B + y * 0x119DE1F3 + t * 0x3449) & 0xFFFFFFFF
    value = ((value ^ (value >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    value = ((value ^ (value >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    return ((value ^ (value >> 16)) & 0xFFFF) / 65535


def _noise(x: float, y: float, t: float) -> float:
    """Smooth bilinear value noise with one temporal lattice coordinate."""
    xi, yi, ti = math.floor(x), math.floor(y), math.floor(t)
    fx, fy, ft = x - xi, y - yi, t - ti
    fx, fy, ft = (v * v * (3 - 2 * v) for v in (fx, fy, ft))
    front = _hash(xi, yi, ti) + (_hash(xi + 1, yi, ti) - _hash(xi, yi, ti)) * fx
    back = _hash(xi, yi + 1, ti) + (_hash(xi + 1, yi + 1, ti) - _hash(xi, yi + 1, ti)) * fx
    upper = front + (back - front) * fy
    front2 = _hash(xi, yi, ti + 1) + (_hash(xi + 1, yi, ti + 1) - _hash(xi, yi, ti + 1)) * fx
    back2 = (
        _hash(xi, yi + 1, ti + 1) + (_hash(xi + 1, yi + 1, ti + 1) - _hash(xi, yi + 1, ti + 1)) * fx
    )
    lower = front2 + (back2 - front2) * fy
    return upper + (lower - upper) * ft


def sample(
    program: str, x: float, y: float, t: float, *, shimmer: bool = True
) -> tuple[float, float]:
    """Sample normalized pixel coordinates and time into luminance and hue.

    Args:
        program: One of ``garden``, ``aperture``, ``scan``, or ``tide``.
        x: Horizontal normalized coordinate, 0..1.
        y: Vertical normalized coordinate, 0..1.
        t: Field time in seconds.
        shimmer: Add high-frequency grain and a restrained peak hue glint.
            Structural phase stays on `t`, so dropping shimmer does not move the motif.

    Returns:
        Luminance and hue, each clamped to 0..1.

    Raises:
        ValueError: `program` is not one of the four demonstration fields.
    """
    x, y = max(0.0, min(1.0, x)), max(0.0, min(1.0, y))
    tau = 2 * math.pi
    # Each program is a different shape. Shared bands made every scene read
    # as the same stripe once the palette shader ran.
    if program == "garden":
        warp = _noise(x * 3.4 + t * 0.03, y * 3.1, t * 0.02)
        bend = _noise(x * 1.5 - t * 0.015, y * 2.4 + 3.0, t * 0.018)
        core = math.exp(-((x - 0.62) ** 2 + (y - 0.38) ** 2) * 16)
        bloom = math.exp(-((x - 0.28) ** 2 + (y - 0.70) ** 2) * 12)
        filament = math.sin((x * 2.1 + warp * 1.6) * tau + y * 5.2)
        branch = math.sin((y * 1.8 + bend * 1.3) * tau - x * 3.6)
        veins = max(0.0, filament) ** 2 * 0.52 + max(0.0, branch) ** 2 * 0.36
        lum = 0.045 + veins + core * 0.74 + bloom * 0.42
        hue = 0.16 + 0.40 * x + 0.22 * y + 0.24 * warp
        if shimmer:
            grain = math.sin((x * 47 + y * 31 + t) * tau)
            lum += 0.04 * grain
            # Vein peaks exceed 1, so luminance grain clamps off. The same
            # phase tints hue near that ceiling: one frequency, no flicker.
            peak = min(1.0, max(0.0, lum))
            hue += 0.045 * grain * peak * peak
        hue %= 1
    elif program == "aperture":
        dx, dy = (x - 0.5) * 1.15, (y - 0.5) * 1.72
        radius = math.hypot(dx, dy)
        theta = math.atan2(dy, dx)
        iris = 0.22 + 0.035 * math.sin(t * 0.12)
        pupil = math.exp(-((radius / 0.055) ** 2))
        ring = math.exp(-(((radius - iris) / 0.016) ** 2))
        halo = math.exp(-(((radius - iris - 0.10) / 0.02) ** 2))
        petals = 0.5 + 0.5 * math.cos(theta * 8 + t * 0.07)
        spokes = (0.5 + 0.5 * math.cos(theta * 22)) if shimmer else 0.0
        lum = 0.02 + pupil * 0.95 + ring * (0.42 + petals * 0.4) + halo * 0.28
        lum += spokes * 0.05 * math.exp(-radius * 2.4)
        hue = (0.55 + theta / tau * 0.32 + petals * 0.08 + 0.06 * radius) % 1
    elif program == "scan":
        raster = 0.5 + 0.5 * math.sin(y * 11 * math.pi)
        band = 0.5 + 0.5 * math.sin(y * 3.1 * math.pi + t * 0.18)
        sweep_x = 0.5 + 0.40 * math.sin(t * 0.17)
        sweep = math.exp(-(((x - sweep_x) / 0.05) ** 2))
        # Weather band may trough; the sweep stays bright at every phase.
        lum = 0.03 + 0.14 * raster * band + 0.66 * sweep
        if shimmer:
            lum += (_noise(x * 37, y * 19, t * 0.65) - 0.5) * 0.06
        hue = (0.03 + 0.70 * x + 0.14 * band) % 1
    elif program == "tide":
        swell = math.sin((x * 1.35 + y * 2.6) * tau - t * 0.16)
        crest_y = 0.58 + 0.16 * math.sin(x * tau + t * 0.09)
        crest = math.exp(-(((y - crest_y) / 0.09) ** 2))
        deep = math.exp(-(((y - (crest_y + 0.16)) / 0.18) ** 2))
        foam = crest * (0.84 + 0.16 * math.sin(x * 20 + t)) if shimmer else crest
        lum = 0.04 + 0.16 * (0.5 + 0.5 * swell) * (1.0 - y)
        lum += 0.78 * foam + 0.12 * deep
        hue = (0.46 + 0.22 * swell + 0.18 * y + 0.08 * x) % 1
    else:
        raise ValueError(f"unknown visual program {program!r}")
    return max(0.0, min(1.0, lum)), max(0.0, min(1.0, hue))

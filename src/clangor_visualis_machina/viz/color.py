"""Convert scene palettes and interpolate in perceptual OKLab space.

Paint uses float32 linear-light sRGB throughout; only palette input is hex sRGB.
Conversions retain out-of-gamut values so their round trip remains meaningful.
"""

import numpy as np

# Ottosson's OKLab matrices, specified for linear sRGB and a D65 white point.
_RGB_LMS = np.array(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ],
    dtype=np.float32,
)
_LMS_LAB = np.array(
    [
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ],
    dtype=np.float32,
)
_LAB_LMS = np.linalg.inv(_LMS_LAB).astype(np.float32)
_LMS_RGB = np.linalg.inv(_RGB_LMS).astype(np.float32)


def linear(hex_color: str) -> np.ndarray:
    """Decode a six-digit sRGB palette entry to linear light.

    Args:
        hex_color: Exactly ``#rrggbb``; hexadecimal digits are case insensitive.

    Returns:
        An owned float32 RGB vector in 0..1.

    Raises:
        ValueError: The input is not a six-digit hex color.
    """
    if not isinstance(hex_color, str) or len(hex_color) != 7 or hex_color[0] != "#":
        raise ValueError("expected #rrggbb")
    try:
        channels = (
            np.array(
                [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)],
                dtype=np.float32,
            )
            / 255.0
        )
    except ValueError as exc:
        raise ValueError("expected #rrggbb") from exc
    return np.where(
        channels <= 0.04045,
        channels / 12.92,
        ((channels + 0.055) / 1.055) ** 2.4,
    ).astype(np.float32)


def to_oklab(rgb) -> np.ndarray:
    """Convert linear sRGB to OKLab without clipping HDR or negative components.

    Args:
        rgb: Array with final axis RGB, in linear-light units.

    Returns:
        Float32 array of the same shape, with final axis L, a, b.
    """
    return np.cbrt(np.asarray(rgb, dtype=np.float32) @ _RGB_LMS.T) @ _LMS_LAB.T


def from_oklab(lab) -> np.ndarray:
    """Convert OKLab to linear sRGB, retaining out-of-gamut values.

    Args:
        lab: Array with final axis L, a, b.

    Returns:
        Float32 linear RGB with the same shape; values may lie outside 0..1.
    """
    return (np.asarray(lab, dtype=np.float32) @ _LAB_LMS.T) ** 3 @ _LMS_RGB.T


def _rgb(value):
    return linear(value) if isinstance(value, str) else np.asarray(value, dtype=np.float32)


def mix(a, b, t) -> np.ndarray:
    """Interpolate palette colors in OKLab, with broadcast interpolation factors.

    Args:
        a: Linear RGB array or hex color at t=0.
        b: Linear RGB array or hex color at t=1.
        t: Scalar or array of factors; 0..1 interpolates, other values extrapolate.

    Returns:
        Float32 linear RGB, with one final color axis. No gamut clipping occurs.
    """
    left, right = to_oklab(_rgb(a)), to_oklab(_rgb(b))
    factor = np.asarray(t, dtype=np.float32)[..., None]
    return from_oklab(left + (right - left) * factor)


def ramp(stops, *, n: int = 256, positions=None) -> np.ndarray:
    """Bake a perceptually interpolated palette for fast scalar-field coloring.

    Args:
        stops: Two or more hex colors or linear RGB vectors.
        n: Number of lookup entries, at least two.
        positions: Strictly increasing stop locations from 0 to 1; defaults to even spacing.

    Returns:
        Owned float32 (n, 3) linear RGB lookup; endpoints equal the given colors.

    Raises:
        ValueError: Stop count, positions, or lookup length is invalid.
    """
    colors = np.asarray([_rgb(stop) for stop in stops], dtype=np.float32)
    if colors.ndim != 2 or colors.shape[1] != 3 or len(colors) < 2 or n < 2:
        raise ValueError("a ramp needs at least two RGB stops and two entries")
    pos = np.asarray(
        np.linspace(0, 1, len(colors)) if positions is None else positions,
        dtype=np.float32,
    )
    if (
        pos.shape != (len(colors),)
        or not np.all(np.isfinite(pos))
        or pos[0] != 0
        or pos[-1] != 1
        or np.any(np.diff(pos) <= 0)
    ):
        raise ValueError("positions must increase strictly from 0 to 1")
    samples = np.linspace(0, 1, n, dtype=np.float32)
    indices = np.minimum(np.searchsorted(pos, samples, side="right") - 1, len(colors) - 2)
    factors = (samples - pos[indices]) / (pos[indices + 1] - pos[indices])
    result = mix(colors[indices], colors[indices + 1], factors)
    result[0], result[-1] = colors[0], colors[-1]
    return result


def shade(color, lightness: float = 1.0, chroma: float = 1.0) -> np.ndarray:
    """Scale OKLCH lightness and chroma without changing the hue angle.

    Args:
        color: Hex or linear RGB, with optional leading array dimensions.
        lightness: Nonnegative multiplier of OKLab L.
        chroma: Nonnegative multiplier of OKLab a and b.

    Returns:
        Float32 linear RGB; out-of-gamut results are retained for tone mapping.

    Raises:
        ValueError: Either multiplier is negative or nonfinite.
    """
    if min(lightness, chroma) < 0 or not np.isfinite(lightness + chroma):
        raise ValueError("shade multipliers must be finite and nonnegative")
    lab = to_oklab(_rgb(color))
    lab *= np.array([lightness, chroma, chroma], dtype=np.float32)
    return from_oklab(lab)

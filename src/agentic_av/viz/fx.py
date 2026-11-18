"""Apply linear-light feedback and finishing effects to scene-owned surfaces.

Feedback owns its history and sampling scratch; other in-place effects reuse
scratch on Surface. All time-dependent rates use seconds, never frame counts.
No terminal encoding or scene-specific color choices belong in this module.
"""

import cmath
import math

import numpy as np

from .draw import _velocity


def _axis_box(source, target, radius, axis):
    target[:] = source
    n = source.shape[axis]
    first = [slice(None)] * source.ndim
    last = first.copy()
    first[axis], last[axis] = slice(0, 1), slice(-1, None)
    for offset in range(1, min(radius, n - 1) + 1):
        lo = [slice(None)] * source.ndim
        hi = lo.copy()
        edge_lo, edge_hi = lo.copy(), lo.copy()
        lo[axis], hi[axis] = slice(None, -offset), slice(offset, None)
        edge_lo[axis], edge_hi[axis] = slice(0, offset), slice(-offset, None)
        target[tuple(hi)] += source[tuple(lo)]
        target[tuple(lo)] += source[tuple(hi)]
        target[tuple(edge_lo)] += source[tuple(first)]
        target[tuple(edge_hi)] += source[tuple(last)]
    if radius >= n:
        target += source[tuple(first)] * (radius - n + 1)
        target += source[tuple(last)] * (radius - n + 1)
    target *= 1 / (2 * radius + 1)


def _blur(source, radius, target, scratch):
    _axis_box(source, scratch, radius, 1)
    _axis_box(scratch, target, radius, 0)


def blur(array, radius: int) -> np.ndarray:
    """Return a separable box blur with constant edge extension.

    Args:
        array: Nonempty scalar (h,w) or multichannel (h,w,c) array; never mutated.
        radius: Nonnegative integer support radius in sub-pixels, not scene units.

    Returns:
        Owned float32 array of the same shape. Constants and channel separation
        are preserved, including singleton axes and radii larger than the image.

    Raises:
        ValueError: Radius or input shape is invalid.
    """
    source = np.asarray(array, dtype=np.float32)
    if source.ndim not in (2, 3) or min(source.shape) < 1:
        raise ValueError("blur expects a nonempty (h,w) or (h,w,c) array")
    if not isinstance(radius, int) or radius < 0:
        raise ValueError("blur radius must be a nonnegative integer")
    target, scratch = np.empty_like(source), np.empty_like(source)
    _blur(source, radius, target, scratch)
    return target


def _buffers(surface):
    if not hasattr(surface, "_fx_buffers"):
        surface._fx_buffers = {}
    return surface._fx_buffers


def bloom(surface, *, threshold=0.6, gain=0.5, radius=2) -> None:
    """Add blurred highlight energy in place, retaining linear RGB and HDR range.

    Args:
        surface: Surface whose rgb is both input and destination.
        threshold: Nonnegative linear channel threshold; only excess energy glows.
        gain: Nonnegative linear glow multiplier.
        radius: Nonnegative integer blur radius in sub-pixels; callers may scale it
            by surface.dx/dy when a fixed physical halo width is required.

    Raises:
        ValueError: Threshold, gain, or radius is invalid.
    """
    if threshold < 0 or gain < 0 or not math.isfinite(threshold + gain):
        raise ValueError("bloom threshold and gain must be finite and nonnegative")
    if not isinstance(radius, int) or radius < 0:
        raise ValueError("bloom radius must be a nonnegative integer")
    buffers = _buffers(surface)
    if "bloom" not in buffers:
        buffers["bloom"] = tuple(np.empty_like(surface.rgb) for _ in range(3))
    highlights, halo, scratch = buffers["bloom"]
    np.subtract(surface.rgb, threshold, out=highlights)
    np.maximum(highlights, 0, out=highlights)
    _blur(highlights, radius, halo, scratch)
    halo *= gain
    surface.rgb += halo


def vignette(surface, strength=0.35) -> None:
    """Darken the perimeter with a cached smooth elliptical falloff in place.

    Args:
        surface: Surface whose linear RGB is multiplied by the falloff.
        strength: Fraction of light removed at the corners, clamped to 0..1.
    """
    strength = float(np.clip(strength, 0, 1))
    buffers = _buffers(surface)
    key = ("vignette", strength)
    if key not in buffers:
        distance = ((surface.u / surface.half_w) ** 2 + surface.v**2) * 0.5
        buffers[key] = 1 - strength * np.clip(distance, 0, 1)
    surface.rgb *= buffers[key][..., None]


# Bayer ranks give bounded, zero-mean texture without a per-frame RNG allocation.
_BAYER = np.array([[0, 2], [3, 1]], dtype=np.float32)
for _ in range(2):
    _BAYER = np.block([[4 * _BAYER, 4 * _BAYER + 2], [4 * _BAYER + 3, 4 * _BAYER + 1]])
_BAYER = (_BAYER + 0.5) / 64 - 0.5


def grain(surface, amount: float, tick: int) -> None:
    """Add deterministic, bounded ordered grain in place, identically in all channels.

    Args:
        surface: Surface whose linear RGB is perturbed; final clipping is tone_map's job.
        amount: Peak-to-peak linear amplitude, nonnegative and finite.
        tick: Integer texture phase selected from picture time by the scene, not
            implicitly advanced here; holding tick holds the grain exactly.

    Raises:
        ValueError: Amount is negative or nonfinite.
    """
    if amount < 0 or not math.isfinite(amount):
        raise ValueError("grain amount must be finite and nonnegative")
    buffers = _buffers(surface)
    if "grain" not in buffers:
        y, x = np.arange(surface.h)[:, None] % 8, np.arange(surface.w)[None, :] % 8
        buffers["grain"] = (x, y)
    x, y = buffers["grain"]
    np.multiply(_BAYER[(y + tick // 8) % 8, (x + tick) % 8], amount, out=surface._scalar)
    surface.rgb += surface._scalar[..., None]


def tone_map(surface, exposure: float = 1.0) -> None:
    """Apply a monotonic Reinhard shoulder in place, producing finite linear RGB.

    Args:
        surface: Surface with arbitrary linear RGB, including overbright highlights.
        exposure: Finite nonnegative linear exposure multiplier.

    Raises:
        ValueError: Exposure is negative or nonfinite.

    Notes:
        Negative and NaN input becomes black; positive infinity becomes white.
        This does not perform the sRGB transfer function (the cell fitter does).
    """
    if exposure < 0 or not math.isfinite(exposure):
        raise ValueError("exposure must be finite and nonnegative")
    np.fmax(surface.rgb, 0, out=surface.rgb)
    np.minimum(surface.rgb, np.finfo(np.float32).max, out=surface.rgb)
    if exposure == 0:
        surface.rgb.fill(0)
        return
    # Dividing by 1/exposure avoids overflow from multiplying huge HDR inputs.
    np.add(surface.rgb, 1 / exposure, out=surface._scratch)
    np.divide(surface.rgb, surface._scratch, out=surface.rgb)
    np.clip(surface.rgb, 0, 1, out=surface.rgb)


class Feedback:
    """Scene-owned, dt-aware warped frame history with transparent black boundaries.

    Args:
        surface: Surface defining history dimensions and scene-space coordinates.

    Notes:
        The zero-motion path never resamples, avoiding creeping interpolation blur.
        Warped samples outside the image contribute black, not clamped edge colors.
        Resizing automatically discards history rather than stretching stale trails.
    """

    def __init__(self, surface):
        self._shape = surface.rgb.shape
        self._history = np.zeros_like(surface.rgb)
        self._warped = np.empty_like(surface.rgb)
        self._gather = np.empty_like(surface.rgb)
        shape = self._shape[:2]
        self._maps = [
            (np.empty(shape, dtype=np.intp), np.empty((*shape, 1), dtype=np.float32))
            for _ in range(4)
        ]
        self._coords = tuple(np.empty(shape, dtype=np.float32) for _ in range(6))
        self._integer = tuple(np.empty(shape, dtype=np.intp) for _ in range(4))
        self._valid = np.empty(shape, dtype=bool)
        self._check = np.empty(shape, dtype=bool)
        self._px = np.arange(surface.w, dtype=np.float32)[None, :]
        self._py = np.arange(surface.h, dtype=np.float32)[:, None]
        self._key = None
        self.time = 0.0

    def reset(self) -> None:
        """Discard all stored light and restart the flow clock at zero seconds."""
        self._history.fill(0)
        self.time = 0.0

    def _mapping(self, surface, dt, zoom, rotate, drift, flow):
        key = (dt, zoom, rotate, tuple(drift), surface.dx, surface.dy)
        if flow is None and self._key == key:
            return self._maps
        # Exact inverse of an affine velocity field, including simultaneous
        # rotation/zoom/drift. Pixel displacements are added to integer centers:
        # zero velocity fields therefore cannot introduce round-trip blur.
        rate = complex(zoom, rotate)
        factor = cmath.exp(-rate * dt)
        offset = complex(*drift) * ((1 - factor) / rate if rate else dt)
        x, y, ax, ay, tx, ty = self._coords
        np.multiply(surface.u, factor.real - 1, out=x)
        np.multiply(surface.v, factor.imag, out=tx)
        x -= tx
        x -= offset.real
        x /= surface.dx
        x += self._px
        np.multiply(surface.u, factor.imag, out=y)
        np.multiply(surface.v, factor.real - 1, out=tx)
        y += tx
        y -= offset.imag
        y /= surface.dy
        y += self._py
        if flow is not None:
            vx, vy = _velocity(flow, surface.u, surface.v, self.time + dt * 0.5)
            np.multiply(vx, dt / surface.dx, out=tx)
            np.multiply(vy, dt / surface.dy, out=ty)
            x -= tx
            y -= ty
        ix, iy, jx, jy = self._integer
        np.floor(x, out=ax)
        np.floor(y, out=ay)
        np.copyto(ix, ax, casting="unsafe")
        np.copyto(iy, ay, casting="unsafe")
        np.subtract(x, ax, out=ax)
        np.subtract(y, ay, out=ay)
        for (ox, oy), (index, weight) in zip(
            ((0, 0), (1, 0), (0, 1), (1, 1)),
            self._maps,
            strict=True,
        ):
            np.add(ix, ox, out=jx)
            np.add(iy, oy, out=jy)
            np.greater_equal(jx, 0, out=self._valid)
            np.less(jx, surface.w, out=self._check)
            self._valid &= self._check
            np.greater_equal(jy, 0, out=self._check)
            self._valid &= self._check
            np.less(jy, surface.h, out=self._check)
            self._valid &= self._check
            if ox:
                np.copyto(tx, ax)
            else:
                np.subtract(1, ax, out=tx)
            if oy:
                np.copyto(ty, ay)
            else:
                np.subtract(1, ay, out=ty)
            np.multiply(tx, ty, out=weight[..., 0])
            weight[..., 0] *= self._valid
            np.clip(jy, 0, surface.h - 1, out=index)
            index *= surface.w
            np.clip(jx, 0, surface.w - 1, out=jx)
            index += jx
        self._key = key if flow is None else None
        return self._maps

    def apply(
        self,
        surface,
        dt,
        *,
        half_life_s,
        zoom=0.0,
        rotate=0.0,
        drift=(0.0, 0.0),
        flow=None,
        mode="max",
    ) -> None:
        """Warp, decay, combine, and store the resulting RGB image in place.

        Args:
            surface: Current painted RGB input and combined output, never aliased to history.
            dt: Finite nonnegative elapsed picture time in seconds. At zero, history
                is unchanged and max(current, history) is displayed in either mode.
            half_life_s: Positive decay half-life in seconds; infinity disables decay.
            zoom: Exponential enlargement rate per second (positive expands outward).
            rotate: Clockwise angular velocity in radians per second.
            drift: Pair of constant scene-unit velocities per second.
            flow: Optional Flow, callable (x,y,t), or (vx,vy) scene-unit/s fields;
                adds inverse semi-Lagrangian advection to the affine warp.
            mode: 'max' takes max(current, decayed history). 'add' treats current
                as emitted RGB *per second*, integrating its contribution exactly
                under decay, so repeated frames do not brighten with frame rate.

        Raises:
            ValueError: dt, half-life, transform parameters, or mode is invalid.

        Notes:
            History includes the newly combined image. In add mode with finite
            half-life, constant emission converges to emission / (ln(2)/half_life).
            Feed an instantaneous color in max mode, a rate in add mode; do not
            multiply the add source by dt again. All sampling is bilinear.
        """
        if (
            not math.isfinite(dt)
            or dt < 0
            or half_life_s <= 0
            or math.isnan(half_life_s)
            or not np.all(np.isfinite((zoom, rotate, *drift)))
            or mode not in ("max", "add")
        ):
            raise ValueError("invalid feedback time, half-life, transform, or mode")
        if self._shape != surface.rgb.shape:
            self.__init__(surface)
        if dt == 0:
            np.maximum(surface.rgb, self._history, out=surface.rgb)
            return
        rate = math.log(2) / half_life_s
        decay = math.exp(-rate * dt)
        if zoom == 0 and rotate == 0 and drift[0] == 0 and drift[1] == 0 and flow is None:
            np.multiply(self._history, decay, out=self._warped)
        else:
            maps = self._mapping(surface, dt, zoom, rotate, drift, flow)
            self._warped.fill(0)
            for index, weight in maps:
                np.take(
                    self._history.reshape(-1, 3),
                    index.ravel(),
                    axis=0,
                    out=self._gather.reshape(-1, 3),
                )
                self._gather *= weight
                self._warped += self._gather
            self._warped *= decay
        if mode == "max":
            np.maximum(surface.rgb, self._warped, out=surface.rgb)
        else:
            surface.rgb *= -math.expm1(-rate * dt) / rate if rate else dt
            surface.rgb += self._warped
        np.copyto(self._history, surface.rgb)
        self.time += dt

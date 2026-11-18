"""Own linear RGB canvases, isotropic coordinates, and reusable compositing scratch.

Scenes paint in centered scene units (vertical extent two), independent of mosaic
sampling. Returned layers belong to the caller; coordinate and resampling caches
belong to the surface. No terminal, audio, or scene-module dependencies live here.
"""

import math

import numpy as np

from . import color as palette


def _grid(h, w, half_w):
    x = (np.arange(w, dtype=np.float32) + 0.5) * (2 * half_w / w) - half_w
    y = (np.arange(h, dtype=np.float32) + 0.5) * (2 / h) - 1
    u, v = np.meshgrid(x, y)
    u.flags.writeable = v.flags.writeable = False
    return u, v


class Surface:
    """A scene's mutable linear RGB canvas with physically isotropic coordinates.

    Args:
        cols: Positive terminal width in cells.
        rows: Positive terminal height in cells.
        sub_w: Positive horizontal samples per cell.
        sub_h: Positive vertical samples per cell.
        cell_aspect: Physical cell height divided by width, positive and finite.

    Attributes:
        rgb: Writable float32 (h, w, 3) linear-light image, allowed to exceed one.
        u: Read-only scene x coordinates at sub-pixel centers.
        v: Read-only scene y coordinates, positive downward.
        pixel_area: Scene-unit area per sub-pixel; multiply a layer sum by this
            to compare integrated light across tiers. Point weights are *not*
            automatically scaled: use ``scene_energy / pixel_area`` if desired.
        dx: Horizontal scene-unit spacing of samples.
        dy: Vertical scene-unit spacing of samples.

    Raises:
        ValueError: Dimensions or cell aspect are not positive and finite.
    """

    def __init__(self, cols: int, rows: int, sub_w: int, sub_h: int, cell_aspect: float = 2.0):
        if any(not isinstance(n, int) or n < 1 for n in (cols, rows, sub_w, sub_h)):
            raise ValueError("surface dimensions must be positive integers")
        if not math.isfinite(cell_aspect) or cell_aspect <= 0:
            raise ValueError("cell_aspect must be positive and finite")
        self.cols, self.rows = cols, rows
        self.sub_w, self.sub_h = sub_w, sub_h
        self.cell_aspect = cell_aspect
        self.w, self.h = cols * sub_w, rows * sub_h
        self.half_w = cols / (rows * cell_aspect)
        self.dx, self.dy = 2 * self.half_w / self.w, 2 / self.h
        self.pixel_area = self.dx * self.dy
        self.rgb = np.zeros((self.h, self.w, 3), dtype=np.float32)
        self.u, self.v = _grid(self.h, self.w, self.half_w)
        self._r = self._theta = None
        self._scratch = np.empty_like(self.rgb)
        self._scalar = np.empty((self.h, self.w), dtype=np.float32)
        self._indices = np.empty((self.h, self.w), dtype=np.intp)
        self._coarse = {1: (self.u, self.v)}
        self._resample = {}

    @property
    def r(self) -> np.ndarray:
        """Return the cached read-only scene-unit radius at every sub-pixel center."""
        if self._r is None:
            self._r = np.hypot(self.u, self.v)
            self._r.flags.writeable = False
        return self._r

    @property
    def theta(self) -> np.ndarray:
        """Return cached read-only polar angles in radians, clockwise from scene +x."""
        if self._theta is None:
            self._theta = np.arctan2(self.v, self.u)
            self._theta.flags.writeable = False
        return self._theta

    def px(self, x, y) -> tuple[np.ndarray, np.ndarray]:
        """Map scene coordinates to floating sub-pixel indices (centers are integers).

        Args:
            x: Scalar or array of horizontal scene units.
            y: Scalar or array of vertical scene units.

        Returns:
            Float32 x and y arrays, without clipping to the canvas.
        """
        return (
            (np.asarray(x, dtype=np.float32) + self.half_w) / self.dx - 0.5,
            (np.asarray(y, dtype=np.float32) + 1) / self.dy - 0.5,
        )

    def coarse(self, k) -> tuple[np.ndarray, np.ndarray]:
        """Return cached centered coordinates on a grid k times coarser.

        Args:
            k: Positive integer reduction factor; dimensions round upward.

        Returns:
            Read-only scene-coordinate arrays with shape (ceil(h/k), ceil(w/k)).
            Their extent matches the full surface, including odd dimensions.

        Raises:
            ValueError: k is not a positive integer.
        """
        if not isinstance(k, int) or k < 1:
            raise ValueError("coarse factor must be a positive integer")
        if k not in self._coarse:
            self._coarse[k] = _grid(
                (self.h + k - 1) // k,
                (self.w + k - 1) // k,
                self.half_w,
            )
        return self._coarse[k]

    def upsample(self, field_k) -> np.ndarray:
        """Bilinearly enlarge a scalar coarse field, with constant edge extension.

        Args:
            field_k: Nonempty 2-D field sampled at uniformly spaced scene centers.

        Returns:
            Owned float32 (h, w) array, preserving the input range and constants.
            Lookup geometry is cached by input shape; the returned field is not shared.

        Raises:
            ValueError: The input is not a nonempty scalar field.
        """
        field = np.asarray(field_k, dtype=np.float32)
        if field.ndim != 2 or min(field.shape) < 1:
            raise ValueError("upsample expects a nonempty 2-D field")
        if field.shape == (self.h, self.w):
            return field.copy()
        if field.shape not in self._resample:
            kh, kw = field.shape
            x = np.clip((np.arange(self.w, dtype=np.float32) + 0.5) * kw / self.w - 0.5, 0, kw - 1)
            y = np.clip((np.arange(self.h, dtype=np.float32) + 0.5) * kh / self.h - 0.5, 0, kh - 1)
            ix, iy = x.astype(np.intp), y.astype(np.intp)
            self._resample[field.shape] = (
                ix,
                np.minimum(ix + 1, kw - 1),
                (x - ix).astype(np.float32),
                iy,
                np.minimum(iy + 1, kh - 1),
                (y - iy).astype(np.float32)[:, None],
            )
        ix, jx, ax, iy, jy, ay = self._resample[field.shape]
        # Separable gathers avoid four full-resolution advanced-indexing temporaries.
        horizontal = field[:, ix] * (1 - ax) + field[:, jx] * ax
        return (horizontal[iy] * (1 - ay) + horizontal[jy] * ay).astype(np.float32)

    def layer(self) -> np.ndarray:
        """Return a new owned zeroed float32 scalar (h, w) drawing layer."""
        return np.zeros((self.h, self.w), dtype=np.float32)

    def fill(self, color) -> None:
        """Replace all RGB samples with a linear RGB vector or hex palette color.

        Args:
            color: Linear RGB vector or ``#rrggbb`` string; HDR values are permitted.
        """
        self.rgb[:] = palette._rgb(color)

    def gradient(self, top, bottom, *, mid=None, mid_at=0.5) -> None:
        """Replace the canvas with a vertical perceptual gradient, independent of tier.

        Args:
            top: Linear or hex color at the upper scene boundary.
            bottom: Linear or hex color at the lower scene boundary.
            mid: Optional intermediate palette color.
            mid_at: Intermediate stop as fraction of canvas height, strictly within 0..1.

        Raises:
            ValueError: An intermediate stop is outside the open interval 0..1.
        """
        t = (np.arange(self.h, dtype=np.float32) + 0.5) / self.h
        if mid is None:
            colors = palette.mix(top, bottom, t)
        else:
            if not 0 < mid_at < 1:
                raise ValueError("mid_at must lie strictly between zero and one")
            colors = np.where(
                (t < mid_at)[:, None],
                palette.mix(top, mid, np.minimum(t / mid_at, 1)),
                palette.mix(mid, bottom, np.maximum((t - mid_at) / (1 - mid_at), 0)),
            )
        self.rgb[:] = colors[:, None, :]

    def add(self, layer, color, gain: float = 1.0) -> None:
        """Add a tinted scalar field in place, without clipping or energy rescaling.

        Args:
            layer: Scalar or (h, w) intensity field in sub-pixel energy units.
            color: Linear RGB vector or hex color.
            gain: Linear multiplier; negative values subtract light.
        """
        np.multiply(
            np.asarray(layer, dtype=np.float32)[..., None], palette._rgb(color), out=self._scratch
        )
        if gain != 1:
            self._scratch *= gain
        self.rgb += self._scratch

    def add_ramp(self, layer, ramp, gain: float = 1.0) -> None:
        """Color a normalized scalar field through a baked ramp and add it in place.

        Args:
            layer: Scalar or (h, w) lookup coordinates; clamped to 0..1.
            ramp: Nonempty (n, 3) linear RGB lookup, usually ``color.ramp``.
            gain: Linear intensity multiplier, with no hidden area normalization.

        Raises:
            ValueError: The ramp does not contain RGB vectors.
        """
        table = np.asarray(ramp, dtype=np.float32)
        if table.ndim != 2 or table.shape[1] != 3 or len(table) == 0:
            raise ValueError("ramp must have shape (n, 3)")
        np.clip(layer, 0, 1, out=self._scalar)
        self._scalar *= len(table) - 1
        np.rint(self._scalar, out=self._scalar)
        np.copyto(self._indices, self._scalar, casting="unsafe")
        np.take(table, self._indices, axis=0, out=self._scratch)
        self._scratch *= gain
        self.rgb += self._scratch

    def screen(self, layer, color) -> None:
        """Screen a tinted field over the image in place (no implicit clipping).

        Args:
            layer: Scalar or (h, w) intensity, normally 0..1.
            color: Linear RGB or hex tint, normally 0..1.
        """
        np.multiply(
            np.asarray(layer, dtype=np.float32)[..., None], palette._rgb(color), out=self._scratch
        )
        np.subtract(1, self.rgb, out=self.rgb)
        np.subtract(1, self._scratch, out=self._scratch)
        self.rgb *= self._scratch
        np.subtract(1, self.rgb, out=self.rgb)

    def cover(self, alpha, color) -> None:
        """Alpha-composite a constant color over the image in place.

        Args:
            alpha: Scalar or (h, w) opacity, clamped to 0..1.
            color: Linear RGB or hex color; HDR values are permitted.
        """
        np.clip(alpha, 0, 1, out=self._scalar)
        np.subtract(palette._rgb(color), self.rgb, out=self._scratch)
        self._scratch *= self._scalar[..., None]
        self.rgb += self._scratch

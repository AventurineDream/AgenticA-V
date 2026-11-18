"""Paint additive geometry and seeded procedural fields in isotropic scene units.

Scene authors supply scalar layers owned by a Surface. Geometry is vectorized;
only fixed-size interpolation corners and noise octaves use Python loops. Point
weights conserve sub-pixel energy, not scene-area energy: explicit normalization
with Surface.pixel_area is the caller's choice, never a hidden tier adjustment.
"""

import math

import numpy as np


def _splat(layer, x, y, weight):
    x, y, weight = np.broadcast_arrays(x, y, weight)
    h, w = layer.shape
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(weight)
    valid &= (x > -1) & (x < w) & (y > -1) & (y < h)
    x, y, weight = x[valid], y[valid], weight[valid]
    if not x.size:
        return
    ix, iy = np.floor(x).astype(np.intp), np.floor(y).astype(np.intp)
    ax, ay = x - ix, y - iy
    # Bincount resolves overlapping splats without slow repeated-index np.add.at.
    for ox, oy, factor in (
        (0, 0, (1 - ax) * (1 - ay)),
        (1, 0, ax * (1 - ay)),
        (0, 1, (1 - ax) * ay),
        (1, 1, ax * ay),
    ):
        jx, jy = ix + ox, iy + oy
        ok = (jx >= 0) & (jx < w) & (jy >= 0) & (jy < h)
        layer += np.bincount(
            jy[ok] * w + jx[ok],
            weights=(weight * factor)[ok],
            minlength=h * w,
        ).reshape(h, w)


def points(surface, layer, x, y, weight=1.0) -> None:
    """Bilinearly splat points additively into a scalar layer.

    Args:
        surface: Coordinate owner; x and y are isotropic scene units.
        layer: Mutable float (h, w) array; may be noncontiguous.
        x: Broadcastable scene x coordinates.
        y: Broadcastable scene y coordinates, positive downward.
        weight: Total sub-pixel energy per point, broadcastable with x and y.
            Interior points conserve this exactly at every tier. For equal
            scene-integrated light use ``weight = energy / surface.pixel_area``.

    Notes:
        Out-of-frame contributions are discarded, not clamped into a bright border.
        A point has a one-sample bilinear footprint; its width therefore follows
        the grid. Use disc for a finite, resolution-independent physical radius.
        Nonfinite points or weights are ignored.
    """
    px, py = surface.px(x, y)
    _splat(layer, px, py, np.asarray(weight, dtype=np.float32))


def _strokes(surface, layer, x0, y0, x1, y1, w0, w1):
    x0, y0, x1, y1, w0, w1 = np.broadcast_arrays(x0, y0, x1, y1, w0, w1)
    x0, y0, x1, y1, w0, w1 = (a.ravel() for a in (x0, y0, x1, y1, w0, w1))
    px, py = surface.px(x0, y0)
    qx, qy = surface.px(x1, y1)
    dx, dy = qx - px, qy - py
    length = np.hypot(dx, dy)
    finite = np.isfinite(px + py + dx + dy + w0 + w1) & (length > 0)
    # Liang-Barsky clipping bounds sample work by the visible canvas, including
    # one sample of bilinear support. It does not renormalize clipped energy.
    lo = np.zeros_like(px)
    hi = np.ones_like(px)
    for start, delta, low, high in ((px, dx, -1, surface.w), (py, dy, -1, surface.h)):
        moving = delta != 0
        inverse = np.zeros_like(delta)
        np.divide(1, delta, out=inverse, where=moving)
        a, b = (low - start) * inverse, (high - start) * inverse
        lo = np.maximum(lo, np.where(moving, np.minimum(a, b), 0))
        hi = np.minimum(hi, np.where(moving, np.maximum(a, b), 1))
        finite &= moving | ((start > low) & (start < high))
    keep = finite & (hi > lo)
    if not np.any(keep):
        return
    px, py, dx, dy, length, lo, hi, w0, w1 = (
        a[keep] for a in (px, py, dx, dy, length, lo, hi, w0, w1)
    )
    visible = length * (hi - lo)
    # Two midpoint samples per sub-pixel suppress diagonal gaps without a
    # per-vertex loop; ragged repeat avoids a huge longest-segment rectangle.
    counts = np.maximum(1, np.ceil(visible * 2).astype(np.intp))
    ids = np.repeat(np.arange(len(counts)), counts)
    offsets = np.arange(len(ids)) - np.repeat(np.cumsum(counts) - counts, counts)
    fraction = (offsets + 0.5) / counts[ids]
    t = lo[ids] + (hi[ids] - lo[ids]) * fraction
    weight = (w0[ids] + (w1[ids] - w0[ids]) * t) * visible[ids] / counts[ids]
    _splat(layer, px[ids] + dx[ids] * t, py[ids] + dy[ids] * t, weight)


def lines(surface, layer, x, y, weight=1.0, *, closed: bool = False) -> None:
    """Resample and splat polylines with constant energy per sub-pixel of length.

    Args:
        surface: Coordinate owner; geometry is in isotropic scene units.
        layer: Mutable scalar (h, w) destination.
        x: Scene x vertices, shape (..., n); each last-axis row is one polyline.
        y: Broadcastable scene y vertices with the same convention.
        weight: Scalar, per-polyline (...,) or per-vertex (..., n) energy per
            Euclidean sub-pixel of stroke length. Vertex weights interpolate.
        closed: Join each row's final vertex back to its first.

    Notes:
        Weight per sub-pixel length gives similar local brightness across tiers,
        not equal scene-integrated energy. For fixed physical energy per scene
        length, multiply weight by scene_length / pixel_length / pixel_area;
        the orientation-dependent pixel metric is intentional. Disc/ring supply
        finite scene-unit widths when that is preferable. Endpoints have no
        extra cap energy; degenerate or fewer-than-two-vertex lines paint nothing.
    """
    x, y = np.broadcast_arrays(np.asarray(x, np.float32), np.asarray(y, np.float32))
    if x.ndim == 0 or x.shape[-1] < 2:
        return
    weights = np.asarray(weight, dtype=np.float32)
    if weights.shape == x.shape[:-1] and weights.ndim:
        weights = weights[..., None]
    weights = np.broadcast_to(weights, x.shape)
    if closed:
        _strokes(
            surface,
            layer,
            x,
            y,
            np.roll(x, -1, -1),
            np.roll(y, -1, -1),
            weights,
            np.roll(weights, -1, -1),
        )
    else:
        _strokes(
            surface,
            layer,
            x[..., :-1],
            y[..., :-1],
            x[..., 1:],
            y[..., 1:],
            weights[..., :-1],
            weights[..., 1:],
        )


def segments(surface, layer, x0, y0, x1, y1, weight=1.0) -> None:
    """Splat many independent strokes with the same metric and energy as lines.

    Args:
        surface: Coordinate owner; endpoints are isotropic scene units.
        layer: Mutable scalar (h, w) destination.
        x0: Broadcastable starting x coordinates.
        y0: Starting y coordinates.
        x1: Ending x coordinates.
        y1: Ending y coordinates.
        weight: Energy per sub-pixel of stroke length, broadcast per segment.
            No hidden area normalization occurs; see lines for tier conventions.

    Notes:
        Strokes have a bilinear one-sample footprint. Offscreen energy is lost,
        zero-length strokes paint nothing, and nonfinite inputs are ignored.
    """
    values = [np.asarray(v, dtype=np.float32) for v in (x0, y0, x1, y1, weight)]
    _strokes(surface, layer, *values, values[-1])


def disc(surface, cx, cy, radius, *, soft: float = 0.02) -> np.ndarray:
    """Return a soft isotropic disc as a resolution-independent coverage field.

    Args:
        surface: Coordinate owner.
        cx: Center x, in scene units (scalar or broadcastable field).
        cy: Center y, in scene units.
        radius: Nonnegative radius, in scene units.
        soft: Nonnegative scene-unit half-width of edge smoothing; zero is a hard edge.

    Returns:
        Owned float32 (h, w) coverage in 0..1. Coverage, unlike point energy,
        is an intensive quantity and needs no tier normalization.

    Raises:
        ValueError: Radius or softness is negative.
    """
    if np.any(np.asarray(radius) < 0) or soft < 0:
        raise ValueError("radius and softness must be nonnegative")
    distance = np.hypot(surface.u - cx, surface.v - cy)
    if soft == 0:
        return (distance <= radius).astype(np.float32)
    return smoothstep(-soft, soft, np.asarray(radius) - distance)


def ring(surface, cx, cy, radius, width, *, squash=1.0, angle=0.0, soft=0.01) -> np.ndarray:
    """Return coverage of a rotated, optionally squashed scene-unit annulus.

    Args:
        surface: Coordinate owner.
        cx: Scene x center.
        cy: Scene y center.
        radius: Nonnegative centerline radius before squash, in scene units.
        width: Nonnegative full stroke width before squash, in scene units.
        squash: Positive local y scale; one gives a physically round ring.
        angle: Clockwise rotation in radians.
        soft: Nonnegative edge smoothing half-width before squash, in scene units.

    Returns:
        Float32 (h, w) coverage in 0..1. Both width and brightness are intensive
        physical quantities, so no resolution normalization is needed.

    Raises:
        ValueError: Radius, width, softness, or squash is invalid.
    """
    if radius < 0 or width < 0 or soft < 0 or squash <= 0:
        raise ValueError("ring sizes must be nonnegative and squash must be positive")
    x, y = surface.u - cx, surface.v - cy
    c, s = math.cos(angle), math.sin(angle)
    r = np.hypot(x * c + y * s, (y * c - x * s) / squash)
    distance = width * 0.5 - np.abs(r - radius)
    if soft == 0:
        return (distance >= 0).astype(np.float32)
    return smoothstep(-soft, soft, distance)


def _tile_sample(tile, u, v, *, gradient=False):
    u, v = np.broadcast_arrays(np.asarray(u, np.float32), np.asarray(v, np.float32))
    size = len(tile)
    x, y = np.remainder(u, 1) * size, np.remainder(v, 1) * size
    ix, iy = x.astype(np.intp), y.astype(np.intp)
    ax, ay = (x - ix).astype(np.float32), (y - iy).astype(np.float32)
    # float32 remainder can round tiny negative coordinates up to exactly one.
    ix %= size
    iy %= size
    jx, jy = (ix + 1) % size, (iy + 1) % size
    a, b, c, d = tile[iy, ix], tile[iy, jx], tile[jy, ix], tile[jy, jx]
    if gradient:
        return (
            ((b - a) * (1 - ay) + (d - c) * ay).astype(np.float32) * size,
            ((c - a) * (1 - ax) + (d - b) * ax).astype(np.float32) * size,
        )
    return ((a * (1 - ax) + b * ax) * (1 - ay) + (c * (1 - ax) + d * ax) * ay).astype(np.float32)


class Noise:
    """Seeded periodic value noise with all octaves baked into cached textures.

    Args:
        seed: Deterministic numpy RNG seed.
        size: Texture side length, at least four; this is sampling quality, not period.

    Notes:
        u and v have period one. Each parameter set is baked once; a full field
        lookup then performs one bilinear sample, independent of octave count.
        Integer octave lattice sizes keep noninteger lacunarity seamless too.
    """

    def __init__(self, seed: int, size: int = 256):
        if not isinstance(size, int) or size < 4:
            raise ValueError("noise tile size must be an integer of at least four")
        self.seed, self.size = seed, size
        self._tiles = {}

    def _tile(self, octaves, lacunarity, gain):
        key = (octaves, float(lacunarity), float(gain))
        if key not in self._tiles:
            if (
                not isinstance(octaves, int)
                or octaves < 1
                or lacunarity < 1
                or not math.isfinite(lacunarity)
                or not 0 <= gain <= 1
            ):
                raise ValueError("invalid noise octaves, lacunarity, or gain")
            rng = np.random.default_rng(self.seed)
            tile = np.zeros((self.size, self.size), dtype=np.float32)
            axis = np.arange(self.size, dtype=np.float32) / self.size
            amplitude, total = 1.0, 0.0
            for octave in range(octaves):
                cells = min(self.size, max(1, round(4 * lacunarity**octave)))
                lattice = rng.random((cells, cells), dtype=np.float32)
                position = axis * cells
                index = position.astype(np.intp)
                fraction = position - index
                fraction = (fraction * fraction * (3 - 2 * fraction)).astype(np.float32)
                next_index = (index + 1) % cells
                a = lattice[index[:, None], index] * (1 - fraction)
                a += lattice[index[:, None], next_index] * fraction
                b = lattice[next_index[:, None], index] * (1 - fraction)
                b += lattice[next_index[:, None], next_index] * fraction
                tile += (a * (1 - fraction[:, None]) + b * fraction[:, None]) * amplitude
                total += amplitude
                amplitude *= gain
            tile /= total
            tile.flags.writeable = False
            self._tiles[key] = tile
        return self._tiles[key]

    def fbm(self, u, v, *, octaves=4, lacunarity=2.0, gain=0.5) -> np.ndarray:
        """Sample one cached fractal tile at broadcastable periodic coordinates.

        Args:
            u: Horizontal coordinates; one unit is one seamless tile period.
            v: Vertical coordinates, broadcastable with u.
            octaves: Positive number of baked noise octaves.
            lacunarity: Frequency multiplier per octave, finite and at least one.
            gain: Amplitude multiplier per octave in 0..1.

        Returns:
            Owned float32 broadcast-shaped field in 0..1; no frame-global RNG is used.

        Raises:
            ValueError: Fractal parameters are invalid.
        """
        return _tile_sample(self._tile(octaves, lacunarity, gain), u, v)

    def warped(self, u, v, *, strength=0.1, octaves=4) -> np.ndarray:
        """Sample deterministic domain-warped fBm without allocating another texture.

        Args:
            u: Horizontal tile coordinates, period one.
            v: Vertical tile coordinates, broadcastable with u.
            strength: Maximum domain displacement per axis, in tile periods.
            octaves: Positive baked octave count.

        Returns:
            Float32 0..1 field; two offset samples displace the final lookup.
        """
        u, v = np.asarray(u, np.float32), np.asarray(v, np.float32)
        du = self.fbm(u + 0.317, v + 0.719, octaves=octaves) - 0.5
        dv = self.fbm(u + 0.613, v + 0.127, octaves=octaves) - 0.5
        return self.fbm(u + 2 * strength * du, v + 2 * strength * dv, octaves=octaves)


class Flow:
    """A deterministic moving curl field, suitable for scene-space advection.

    Args:
        seed: Seed for the periodic scalar potential.
        scale: Positive spatial frequency multiplier per scene unit.

    Raises:
        ValueError: Scale is nonpositive or nonfinite.
    """

    def __init__(self, seed: int, scale: float = 1.0):
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("flow scale must be positive and finite")
        self.scale = scale
        self._noise = Noise(seed)
        self._tile = self._noise._tile(4, 2.0, 0.5)

    def at(self, x, y, t: float) -> tuple[np.ndarray, np.ndarray]:
        """Return divergence-free velocity from a translated scalar potential.

        Args:
            x: Broadcastable scene x coordinates.
            y: Scene y coordinates, positive downward.
            t: Absolute picture time in seconds, not frame number.

        Returns:
            Float32 (vx, vy) fields in scene units per second. Spatial mixed
            derivatives cancel within each bilinear tile patch; seams are periodic.
        """
        dx, dy = _tile_sample(
            self._tile,
            np.asarray(x) * self.scale * 0.2 + t * 0.013,
            np.asarray(y) * self.scale * 0.2 + t * 0.017,
            gradient=True,
        )
        return dy * (0.02 * self.scale), -dx * (0.02 * self.scale)


def _velocity(flow, x, y, t):
    if hasattr(flow, "at"):
        return flow.at(x, y, t)
    if callable(flow):
        return flow(x, y, t)
    return flow


class Particles:
    """Seeded struct-of-arrays particles, with explicit boundary and lifetime policy.

    Args:
        count: Nonnegative number of particles.
        seed: RNG seed for initialization and default respawn.

    Attributes:
        x: Float32 scene-unit positions, initially uniform in -1..1.
        y: Float32 scene-unit positions, initially uniform in -1..1.
        vx: Float32 horizontal velocity in scene units per second, initially zero.
        vy: Float32 vertical velocity in scene units per second, initially zero.
        age: Elapsed lifetime in seconds, initially zero.
        life: Lifetime in seconds, initially infinite; expired particles respawn.
        columns: Mapping of user column names to owned float32 per-particle arrays.
        bounds: (xmin, xmax, ymin, ymax) scene-unit rectangle; initially (-1, 1, -1, 1).
        policy: 'wrap' (default), 'respawn', or 'none' for boundary crossings.
        respawn: Optional callback (particles, boolean_mask); called after default
            respawn to customize only the expired/crossing rows, without a Python loop.

    Raises:
        ValueError: Count is not a nonnegative integer.
    """

    def __init__(self, count: int, seed: int):
        if not isinstance(count, int) or count < 0:
            raise ValueError("particle count must be a nonnegative integer")
        self.rng = np.random.default_rng(seed)
        self.x = self.rng.uniform(-1, 1, count).astype(np.float32)
        self.y = self.rng.uniform(-1, 1, count).astype(np.float32)
        self.vx, self.vy = np.zeros(count, np.float32), np.zeros(count, np.float32)
        self.age, self.life = np.zeros(count, np.float32), np.full(count, np.inf, np.float32)
        self.columns = {}
        self.bounds = (-1.0, 1.0, -1.0, 1.0)
        self.policy, self.respawn = "wrap", None
        self.time = 0.0

    def add_column(self, name: str, values=0.0) -> np.ndarray:
        """Attach a caller-defined float32 per-particle column.

        Args:
            name: Unique nonempty name, not colliding with a particle attribute.
            values: Scalar or array broadcastable to (count,); copied on attachment.

        Returns:
            Owned mutable column, also accessible as columns[name]. Respawn preserves
            custom columns unless the caller's respawn callback overwrites them.

        Raises:
            ValueError: Name is empty, reserved, duplicated, or values cannot broadcast.
        """
        if not name or name in self.columns or hasattr(self, name):
            raise ValueError("particle column name is empty or already in use")
        column = np.broadcast_to(np.asarray(values, np.float32), self.x.shape).copy()
        self.columns[name] = column
        return column

    def step(self, dt: float, flow=None, *, drag=0.0) -> None:
        """Advance positions, lifetimes, and policies in seconds, vectorized.

        Args:
            dt: Finite nonnegative picture-time step in seconds; zero changes nothing.
            flow: Optional Flow, callable (x,y,t), or (vx,vy) tuple in scene units/s.
                It supplies velocity, not acceleration; midpoint sampling reduces
                timestep error for spatially varying fields.
            drag: Finite nonnegative exponential velocity damping rate in 1/seconds.
                Displacement integrates the damped velocity analytically.

        Raises:
            ValueError: Time step, drag, bounds, or boundary policy is invalid.
        """
        if not math.isfinite(dt) or dt < 0 or not math.isfinite(drag) or drag < 0:
            raise ValueError("dt and drag must be finite and nonnegative")
        xmin, xmax, ymin, ymax = self.bounds
        if xmax <= xmin or ymax <= ymin or not np.all(np.isfinite(self.bounds)):
            raise ValueError("particle bounds must have finite positive extents")
        if self.policy not in ("wrap", "respawn", "none"):
            raise ValueError("unknown particle boundary policy")
        if dt == 0:
            return
        if flow is not None:
            vx, vy = _velocity(flow, self.x, self.y, self.time)
            self.vx[:], self.vy[:] = _velocity(
                flow,
                self.x + np.asarray(vx) * (dt * 0.5),
                self.y + np.asarray(vy) * (dt * 0.5),
                self.time + dt * 0.5,
            )
        decay = math.exp(-drag * dt)
        distance = -math.expm1(-drag * dt) / drag if drag else dt
        self.x += self.vx * distance
        self.y += self.vy * distance
        self.vx *= decay
        self.vy *= decay
        self.age += dt
        expired = self.age >= self.life
        if self.policy == "wrap":
            self.x[:] = (self.x - xmin) % (xmax - xmin) + xmin
            self.y[:] = (self.y - ymin) % (ymax - ymin) + ymin
        elif self.policy == "respawn":
            expired |= (self.x < xmin) | (self.x >= xmax) | (self.y < ymin) | (self.y >= ymax)
        count = np.count_nonzero(expired)
        if count:
            self.x[expired] = self.rng.uniform(xmin, xmax, count)
            self.y[expired] = self.rng.uniform(ymin, ymax, count)
            self.vx[expired] = self.vy[expired] = self.age[expired] = 0
            if self.respawn is not None:
                self.respawn(self, expired)
        self.time += dt


def smoothstep(a, b, x):
    """Return cubic 0..1 interpolation between scalar/array edges a and b.

    Args:
        a: Lower edge in the same units as x.
        b: Upper edge; may be below a for a reversed transition, but not equal.
        x: Broadcastable samples.

    Returns:
        Float32 clamped cubic interpolation; equal edges form a hard step at a.
    """
    a, b, x = np.broadcast_arrays(
        np.asarray(a, np.float32),
        np.asarray(b, np.float32),
        np.asarray(x, np.float32),
    )
    t = np.zeros(x.shape, dtype=np.float32)
    np.divide(x - a, b - a, out=t, where=b != a)
    np.copyto(t, x >= a, where=b == a)
    np.clip(t, 0, 1, out=t)
    return t * t * (3 - 2 * t)


def ease_out(x):
    """Return cubic ease-out of dimensionless scalar/array progress, clamped to 0..1.

    Args:
        x: Dimensionless progress.

    Returns:
        Float32 progress that reaches one with zero terminal velocity.
    """
    return 1 - (1 - np.clip(np.asarray(x, np.float32), 0, 1)) ** 3


def ease_in_out(x):
    """Return symmetric cubic easing of dimensionless scalar/array progress.

    Args:
        x: Dimensionless progress, clamped to 0..1.

    Returns:
        Float32 progress with zero velocity at both endpoints.
    """
    return smoothstep(0, 1, x)


def pulse(phase, sharpness=6.0):
    """Return a smooth periodic pulse, never a frame-dependent impulse.

    Args:
        phase: Scalar or array in cycles; integer phases are pulse peaks.
        sharpness: Positive finite exponent; larger values make a narrower pulse.

    Returns:
        Float32 intensity in 0..1, periodic with period one.

    Raises:
        ValueError: Sharpness is not positive and finite.
    """
    if sharpness <= 0 or not math.isfinite(sharpness):
        raise ValueError("pulse sharpness must be positive and finite")
    return ((0.5 + 0.5 * np.cos(np.asarray(phase, np.float32) * (2 * np.pi))) ** sharpness).astype(
        np.float32
    )

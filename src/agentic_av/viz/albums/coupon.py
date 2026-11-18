"""Paint Coupon Seance's seven deadpan cosmic-store compositions for the mosaic Stage.

The factory follows the shared Scene contract. Seeded geometry uses picture seconds;
audio only deforms small surfaces through slow envelopes. Held frames are immutable,
and seek discards spectral history and exposure state. No I/O occurs during painting.
"""

from __future__ import annotations

import numpy as np

from .. import draw
from ..color import linear, mix
from ..fx import Feedback
from ..scene import Frame, Movement, Scene
from ..surface import Surface

_TURN = 2 * np.pi
_FLOOR = linear("#06080d")
# Normalized real pages carry these colors; old/minimal extraction payloads may not.
_PALETTES = {
    "arrival": ("#ebb476", "#a9d5c0", "#dd745c"),
    "friction": ("#d6f77b", "#e689e2", "#b3ddec"),
    "commerce": ("#f4a35d", "#ddf899", "#ee86a8"),
    "pursuit": ("#ff826b", "#86dddd", "#eddfb1"),
    "memory": ("#d7e9d4", "#8eccc7", "#b4a8df"),
    "gravity": ("#bd94ed", "#faaf65", "#db7296"),
    "return": ("#efd395", "#a6e0a6", "#ebaeb2"),
}


class _Coupon(Scene):
    """Own the album's starfield, receipt strip, and held-frame lifecycle."""

    def __init__(self, movement: Movement):
        super().__init__(movement)
        defaults = _PALETTES[movement.scene]
        palette = movement.palette[:3] + defaults[len(movement.palette[:3]) :]
        self.colors = tuple(linear(c) for c in palette)
        self.rng = np.random.default_rng(movement.seed)
        self.stars = self.rng.random((170, 4), dtype=np.float32)
        self.phase = self.rng.uniform(0, _TURN, 4200).astype(np.float32)
        self.radius = self.rng.uniform(1.25, 2.35, 4200).astype(np.float32)
        self.mass = self.rng.uniform(0.35, 1, 4200).astype(np.float32)
        self.band = np.minimum(6, ((self.radius - 1.25) / 1.1 * 7).astype(np.intp))
        self.keep = ~((self.radius > 1.74) & (self.radius < 1.84))
        self.keep &= ~((self.radius > 1.47) & (self.radius < 1.52))
        self.bands = np.zeros(7, dtype=np.float32)
        self.impulses = np.zeros(3, dtype=np.float32)
        self.history = np.zeros((80, 7), dtype=np.float32)
        self.history_dt = 0.0
        self.ready = False
        self.shape = (0, 0)
        self.angle = np.linspace(0, _TURN, 240, dtype=np.float32)
        self.thread = np.linspace(0, 1, 320, dtype=np.float32)
        self.bar_x = np.linspace(-1, 1, 70, dtype=np.float32)
        self.bar_id = np.arange(70) % 7
        self.feedback = None

    def resize(self, surface: Surface) -> None:
        """Rebuild canvas buffers without changing the seeded composition.

        Args:
            surface: Destination with cell and sub-pixel dimensions.
        """
        self.shape = (surface.h, surface.w)
        self.layer = surface.layer()
        self._aisle_layers = tuple(surface.layer() for _ in range(3))
        self.last = np.empty_like(surface.rgb)
        self.floor = np.empty_like(surface.rgb)
        haze = np.exp(-((surface.u - 0.2) ** 2 + (surface.v + 0.1) ** 2) * 1.3)
        for channel in range(3):
            self.floor[..., channel] = _FLOOR[channel] + haze * self.colors[1][channel] * 0.006
        self.edge = np.clip(1.08 - 0.12 * (surface.u**2 + surface.v**2), 0.3, 1)
        self.ready = False
        if self.movement.scene == "pursuit":
            self.feedback = Feedback(surface)

    def seek(self) -> None:
        """Clear exposure, slow envelopes, and the forty-second receipt history."""
        if self.feedback is not None:
            self.feedback.reset()
        self.ready = False
        self.bands.fill(0)
        self.impulses.fill(0)
        self.history.fill(0)
        self.history_dt = 0.0

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint a complete picture, or repeat the last picture while held.

        Args:
            surface: Mutable linear RGB canvas, repainted completely.
            frame: Musical instant; tau/dt are picture seconds and energy is 0..1.
        """
        if self.shape != (surface.h, surface.w):
            self.resize(surface)
        if frame.dt == 0 and self.ready:
            np.copyto(surface.rgb, self.last)
            return
        # The additional envelope is intentionally slower than the analysis envelope:
        # even adversarial onsets cannot exchange large illuminated regions at beat rate.
        blend = 1 - np.exp(-max(0, frame.dt) / 0.85)
        if not self.ready:
            blend = 1.0
        target = frame.levels.bands if frame.energy > 0 else np.zeros(7, dtype=np.float32)
        self.bands += blend * (target - self.bands)
        onsets = np.array([frame.levels.kick, frame.levels.snare, frame.levels.hat])
        self.impulses += blend * (onsets * frame.energy - self.impulses)
        self.history_dt += max(0, frame.dt)
        if self.history_dt >= 0.5:
            steps = min(80, int(self.history_dt / 0.5))
            self.history[steps:] = self.history[:-steps]
            self.history[:steps] = self.bands
            self.history_dt %= 0.5
        np.copyto(surface.rgb, self.floor)
        self._stars(surface, frame)
        self._paint(surface, frame)
        if self.movement.scene != "return":
            self._barcode(surface, frame)
        np.multiply(surface.rgb, self.edge[..., None], out=surface.rgb)
        np.maximum(surface.rgb, 0, out=surface.rgb)
        if self.feedback is not None:
            self.feedback.apply(surface, frame.dt, half_life_s=0.16, zoom=0.12, mode="max")
        np.copyto(self.last, surface.rgb)
        self.ready = True

    def _clear(self) -> np.ndarray:
        self.layer.fill(0)
        return self.layer

    def _stroke(self, surface, x, y, color, weight=0.12):
        layer = self._clear()
        draw.lines(surface, layer, x, y, weight)
        surface.add(layer, color)

    def _stars(self, surface, frame):
        density = 0.27 if self.movement.scene == "memory" else 1.0
        count = int(len(self.stars) * density)
        star = self.stars[:count]
        # Forward optical expansion, not sideways scrolling, ties all seven worlds.
        travel = frame.tau * 0.007 + frame.energy * frame.levels.travel * 0.0006
        depth = (star[:, 2] + travel) % 1
        scale = 0.25 + depth**2 * 1.3
        x = (star[:, 0] - 0.5) * 2 * surface.half_w * scale
        y = (star[:, 1] - 0.5) * 2 * scale
        if self.movement.scene == "gravity":
            dx, dy = x - 0.22, y + 0.08
            radius2 = dx * dx + dy * dy + 0.12
            x += dx * 0.09 / radius2
            y += dy * 0.09 / radius2
        twinkle = 0.9 + 0.1 * np.sin(frame.tau * 0.6 + star[:, 3] * _TURN)
        weight = (0.015 + star[:, 3] ** 5 * 0.26) * twinkle
        weight *= 1 + self.bands[6] * 0.12
        draw.points(surface, self._clear(), x, y, weight)
        surface.add(self.layer, mix(self.colors[1], np.ones(3, dtype=np.float32), 0.45))

    def _barcode(self, surface, frame):
        late = self._arc(frame)
        gain = 0.10
        if self.movement.scene == "memory":
            gain *= max(0, (late - 0.65) / 0.35) * 0.4
        x = self.bar_x * min(1.25, surface.half_w * 0.7)
        heights = 0.012 + self.bands[self.bar_id] * 0.065
        y = np.full_like(x, 0.88)
        if self.movement.scene == "gravity":
            distance = x - 0.22
            pull = (0.08 + 0.98 * late) * np.exp(-(distance**2) / 0.4)
            y -= pull
            x = 0.22 + distance * (1 - 0.45 * late)
        layer = self._clear()
        draw.segments(surface, layer, x, y, x, y - heights, gain)
        surface.add(layer, self.colors[1])
        self._stroke(surface, x, y + 0.016, self.colors[0], gain * 0.35)
        if self.movement.scene == "gravity":
            radius = 0.18 + 0.055 * late + 0.018 * self.bands[0]
            surface.cover(draw.disc(surface, 0.22, -0.08, radius, soft=0.006), _FLOOR * 0.3)

    def _arc(self, frame):
        # Progress/audio time would bypass the reduced and still picture clocks.
        return float(np.clip(frame.tau / max(1, self.movement.duration_s), 0, 1))

    def _sphere(self, surface, frame, cx, cy, radius, *, earth=False, sunrise=0):
        ix, iy = surface.px(
            np.array([cx - radius, cx + radius]), np.array([cy - radius, cy + radius])
        )
        x0, x1 = max(0, int(ix[0]) - 1), min(surface.w, int(ix[1]) + 2)
        y0, y1 = max(0, int(iy[0]) - 1), min(surface.h, int(iy[1]) + 2)
        if x1 <= x0 or y1 <= y0:
            return
        u = (surface.u[y0:y1, x0:x1] - cx) / radius
        v = (surface.v[y0:y1, x0:x1] - cy) / radius
        rr = u * u + v * v
        inside = rr < 1
        z = np.sqrt(np.maximum(0, 1 - rr))
        light = np.maximum(0, -u * 0.55 - v * 0.30 + z * 0.76) ** 1.6
        latitude = v * 0.95 - u * 0.3
        cloud = 0.5 + 0.5 * np.sin(latitude * 25 + 0.8 * np.sin(u * 4 + frame.tau * 0.13))
        if earth:
            cloud = 0.5 + 0.5 * np.sin(u * 12 + np.sin(v * 9) * 2 + frame.tau * 0.07)
        warm = sunrise * np.exp(-((u + 0.78) ** 2 + (v + 0.36) ** 2) * 8)
        for channel in range(3):
            tint = (
                self.colors[0][channel] * (0.27 + cloud * 0.20)
                + self.colors[1][channel] * (1 - cloud) * 0.18
            )
            value = tint * (0.015 + light) + warm * self.colors[0][channel] * 0.5
            target = surface.rgb[y0:y1, x0:x1, channel]
            np.copyto(target, value, where=inside)

    def _rings(self, surface, frame, cx, cy, radius, opening, tilt, *, receipt=False):
        angle = self.phase + frame.tau * 0.24 / self.radius**1.5
        ripple = self.impulses[0] * 0.018 * np.sin(self.radius * 19 - frame.tau * 2)
        rr = self.radius * radius + ripple
        x = np.cos(angle) * rr
        depth = np.sin(angle) * rr
        y = depth * opening
        ct, st = np.cos(tilt), np.sin(tilt)
        qx, qy = cx + ct * x - st * y, cy + st * x + ct * y
        visible = self.keep & ~((depth < 0) & (x * x + y * y < radius**2))
        # The far ring behind the unlit hemisphere receives the planet's shadow.
        shadow = np.where((depth < 0) & (x > -radius * 0.12) & (x < radius), 0.12, 1)
        weight = self.mass * visible * shadow * 0.16
        if receipt:
            age = np.clip(((self.radius - 1.25) / 1.1 * 79).astype(np.intp), 0, 79)
            spectrum = self.history[age, self.band]
            weight *= 0.45 + spectrum * 0.75
            # Fine receipt-like radial rulings remain visible during silent playback.
            weight *= 0.58 + 0.42 * (np.sin(self.radius * 150) > 0)
        else:
            weight *= 0.7 + self.bands[self.band] * 0.4
        for band in range(3):
            mask = self.band % 3 == band
            draw.points(surface, self._clear(), qx[mask], qy[mask], weight[mask])
            surface.add(self.layer, self.colors[band])

    def _paint(self, surface, frame):
        raise NotImplementedError


class _Arrival(_Coupon):
    """Approach a shaded Saturn through a seven-band Keplerian ring spectrum."""

    def _paint(self, surface, frame):
        arc = draw.smoothstep(0, 1, self._arc(frame))
        radius = 0.29 + 0.17 * arc
        cx, cy = 0.25 - arc * 0.10, -0.12
        self._sphere(surface, frame, cx, cy, radius)
        self._rings(surface, frame, cx, cy, radius, 0.32, -0.31)


class _Friction(_Coupon):
    """A rosin-dusted speaker cone with changing Chladni nodes and bowed strings."""

    def __init__(self, movement):
        super().__init__(movement)
        self.grain_start = self.rng.uniform(-0.95, 0.95, (3000, 2)).astype(np.float32)
        self.nodes = []
        for n, m in ((2, 3), (3, 4), (4, 5)):
            xy = self.grain_start.copy()
            # Relax once, not per frame: each mode is a seeded nodal dust reservoir.
            for _ in range(45):
                x, y = xy.T
                f = np.cos(n * np.pi * x) * np.cos(m * np.pi * y)
                f -= np.cos(m * np.pi * x) * np.cos(n * np.pi * y)
                gx = -n * np.pi * np.sin(n * np.pi * x) * np.cos(m * np.pi * y)
                gx += m * np.pi * np.sin(m * np.pi * x) * np.cos(n * np.pi * y)
                gy = -m * np.pi * np.cos(n * np.pi * x) * np.sin(m * np.pi * y)
                gy += n * np.pi * np.cos(m * np.pi * x) * np.sin(n * np.pi * y)
                rate = f / (gx * gx + gy * gy + 1) * 0.5
                xy[:, 0] -= gx * rate
                xy[:, 1] -= gy * rate
            self.nodes.append(xy)

    def _paint(self, surface, frame):
        arc = self._arc(frame)
        cx, cy, radius = -0.12 + 0.18 * arc, -0.05, 0.70
        distance = np.sqrt((surface.u - cx) ** 2 + (surface.v - cy) ** 2) / radius
        cone = np.maximum(0, 1 - distance) * (0.55 + 0.45 * np.cos(distance * 25))
        surface.add(cone, self.colors[2], 0.026)
        surface.add(draw.ring(surface, cx, cy, radius, 0.013, soft=0.008), self.colors[2], 0.13)
        surface.add(draw.ring(surface, cx, cy, 0.19, 0.008), self.colors[0], 0.09)
        bar_s = 4 * 60 / (self.movement.bpm or 150)
        mode = frame.tau / bar_s + float(self.bands[3]) * 0.2
        index = int(mode) % 3
        fraction = draw.smoothstep(0, 0.6, (mode % 1) * bar_s)
        xy = self.nodes[index] * (1 - fraction) + self.nodes[(index + 1) % 3] * fraction
        rad = np.linalg.norm(xy, axis=1)
        valid = rad < 0.94
        n, m = index + 2, index + 3
        local = np.cos(n * np.pi * xy[:, 0]) * np.cos(m * np.pi * xy[:, 1])
        local -= np.cos(m * np.pi * xy[:, 0]) * np.cos(n * np.pi * xy[:, 1])
        amplitude = 0.002 + np.abs(local) * (0.003 + self.bands[2] * 0.008)
        amplitude += self.impulses[0] * 0.012
        jitter = np.sin(self.phase[:3000] + frame.tau * 3) * amplitude
        x = cx + xy[:, 0] * radius + jitter
        y = cy + xy[:, 1] * radius + jitter * np.sin(self.phase[:3000])
        draw.points(surface, self._clear(), x[valid], y[valid], 0.11)
        surface.add(self.layer, self.colors[0])
        u = self.thread
        for ribbon in range(3):
            slip = np.sin(u * 34 - frame.tau * 1.3 + ribbon)
            slip = np.tanh(slip * 2.7)
            y = cy + (ribbon - 1) * 0.22 + 0.06 * np.sin(u * 9 + frame.tau * 0.3)
            y += slip * (0.012 + self.bands[3 + ribbon] * 0.018) * np.sin(u * np.pi)
            self._stroke(surface, (u - 0.5) * 2.1, y, self.colors[1], 0.10)


class _Commerce(_Coupon):
    """Advance through seven spectral shelf rows toward a distant ringed planet."""

    def _paint(self, surface, frame):
        self._aisle(surface, frame, chase=False)

    def _aisle(self, surface, frame, *, chase):
        arc = self._arc(frame)
        speed = 2.5 if chase else 1
        bpm = self.movement.bpm or 160
        # Beat position is a musical offset, while tau supplies the silent clock.
        # Integrators are gain-scaled so they cannot smuggle audio time into still art.
        beat = frame.tau * bpm / 60 * (1 - frame.energy * 0.04)
        beat += frame.energy * frame.levels.beat * 0.04
        travel = beat * speed
        fraction = travel % 1
        eased = fraction * fraction * (3 - 2 * fraction)
        depth = (np.arange(1, 15, dtype=np.float32) - eased) / 7
        depth += 0.18
        scale = 1 / depth
        roll = 0.0
        if chase:
            roll = 0.09 * np.sin(frame.tau * 0.17 + frame.energy * frame.levels.drive * 0.002)
        cx, cy = -0.18 + arc * 0.18, -0.17
        ct, st = np.cos(roll), np.sin(roll)

        def project(x, y):
            return cx + ct * x - st * y, cy + st * x + ct * y

        layers = self._aisle_layers
        for layer in layers:
            layer.fill(0)
        sides = np.array([-1, 1], dtype=np.float32)[:, None, None]
        band_offsets = (np.arange(7, dtype=np.float32) / 6 - 0.5)[None, :, None]
        x = sides * scale[None, None, :] * 0.78
        y = band_offsets * scale[None, None, :] * 1.05
        px, py = project(x, y)
        draw.lines(surface, layers[1], px, py, 0.035)
        heights = (0.035 + self.bands[None, :, None] * 0.055) * scale[None, None, :]
        widths = 0.035 * scale[None, None, :]
        # Color batches avoid re-splatting each of the fourteen shelf bands.
        for color_index in range(3):
            bands = np.flatnonzero(np.arange(7) % 3 == color_index)
            draw.segments(
                surface,
                layers[color_index],
                px[:, bands],
                py[:, bands],
                px[:, bands] - sides * widths,
                py[:, bands] - heights[:, bands],
                0.16,
            )
        indices = np.arange(0, len(scale), 2)
        wall_x = sides[:, 0, 0, None] * scale[indices][None, :] * 0.78
        wall_y = 0.63 * scale[indices][None, :]
        x0, y0 = project(wall_x, -wall_y)
        x1, y1 = project(wall_x, wall_y)
        draw.segments(surface, layers[0], x0, y0, x1, y1, 0.055)
        rail_x = sides[:, 0, 0, None] * np.array([0.04, 2.8], dtype=np.float32)[None, :]
        rail_y = np.broadcast_to(np.array([0.03, 1.1], dtype=np.float32), rail_x.shape)
        px, py = project(rail_x, rail_y)
        draw.lines(surface, layers[2], px, py, 0.06)
        if chase:
            self._patrol(surface, frame, cx, cy, layers)
        for layer, color in zip(layers, self.colors, strict=True):
            surface.add(layer, color)
        self._sphere(surface, frame, cx, cy - 0.02, 0.06)
        self._stroke(
            surface,
            cx + np.cos(self.angle) * 0.12,
            cy - 0.02 + np.sin(self.angle) * 0.025,
            self.colors[0],
            0.08,
        )

    def _patrol(self, surface, frame, cx, cy, layers):
        bar_s = 4 * 60 / (self.movement.bpm or 174)
        phase = frame.tau / bar_s + np.array([0, 0.5], dtype=np.float32)
        angle = np.sin(phase * _TURN) * 0.72 + np.pi * 0.5
        edges = np.array([-0.012, 0.012], dtype=np.float32)
        reach = np.linspace(0, 2, 120, dtype=np.float32)
        x = cx + np.cos(angle[:, None, None] + edges[None, :, None]) * reach
        y = cy + np.sin(angle[:, None, None] + edges[None, :, None]) * reach
        for beam in range(2):
            draw.lines(surface, layers[beam], x[beam], y[beam], 0.065)
        # A geometric long exposure gives streak depth without accumulating on dt=0.
        ids = np.arange(12, dtype=np.float32)
        z = (ids / 12 + frame.tau * 0.27) % 1
        theta = self.phase[:12]
        x = cx + np.cos(theta) * z**2 * 2.2
        y = cy + np.sin(theta) * z**2 * 1.3
        tail = 0.03 + z * 0.08 + self.impulses[2] * 0.06
        draw.segments(
            surface, layers[2], x, y, x - np.cos(theta) * tail, y - np.sin(theta) * tail, 0.10 * z
        )


class _Pursuit(_Commerce):
    """Roll the aisle into a chase with continuously travelling patrol beams."""

    def _paint(self, surface, frame):
        self._aisle(surface, frame, chase=True)


class _Memory(_Coupon):
    """Suspend a single seven-partial string between darkness and a small Earth."""

    def _paint(self, surface, frame):
        arc = self._arc(frame)
        cx, cy = 0.72 - arc * 0.15, -0.46 + arc * 0.04
        self._sphere(surface, frame, cx, cy, 0.115, earth=True)
        breath = 1 + 0.025 * np.sin(frame.tau * 0.35) + self.bands[0] * 0.018
        for ring in range(3):
            radius = (0.16 + ring * 0.07) * breath
            self._stroke(
                surface,
                cx + np.cos(self.angle) * radius,
                cy + np.sin(self.angle) * radius * 0.75,
                self.colors[1],
                0.022 / (ring + 1),
            )
        u = self.thread
        x = -min(surface.half_w * 0.8, 1.55) + (cx + min(surface.half_w * 0.8, 1.55)) * u
        baseline = 0.70 + (cy - 0.70) * u
        # Analytic shutter samples give long exposure without frame-rate-dependent trails.
        for trail in range(5):
            time = frame.tau - trail * 0.14
            wave = np.zeros_like(u)
            for partial in range(7):
                amplitude = (0.014 + self.bands[partial] * 0.025) / (partial + 1)
                wave += (
                    amplitude
                    * np.sin((partial + 1) * np.pi * u)
                    * np.cos(time * (0.62 + partial * 0.19))
                )
            wave += 0.024 * np.sin(u * np.pi) * np.sin(time * 0.4 + u * 5)
            self._stroke(
                surface, x, baseline + wave, self.colors[trail % 3], 0.09 * np.exp(-trail * 0.65)
            )


class _Gravity(_Coupon):
    """Lens stars and the receipt around a precessing, asymmetric accretion disc."""

    def _paint(self, surface, frame):
        arc = self._arc(frame)
        cx, cy = 0.22, -0.08
        radius = 0.18 + 0.055 * arc + 0.018 * self.bands[0]
        precession = -0.15 + 0.13 * np.sin(frame.tau * 0.035) + self.bands[1] * 0.04
        angle = self.phase + frame.tau * 0.33 / self.radius**1.5
        rr = (self.radius - 0.6) * 0.48
        x, y = np.cos(angle) * rr, np.sin(angle) * rr * 0.27
        qx = cx + np.cos(precession) * x - np.sin(precession) * y
        qy = cy + np.sin(precession) * x + np.cos(precession) * y
        lens = np.exp(-((x / (radius * 1.1)) ** 2)) * np.maximum(0, -np.sin(angle))
        qy -= lens * radius * 1.35
        visible = ((qx - cx) ** 2 + (qy - cy) ** 2) > radius**2
        weight = self.mass * visible * (0.06 + 0.19 * (0.5 + 0.5 * np.cos(angle)))
        draw.points(surface, self._clear(), qx, qy, weight)
        surface.add(self.layer, self.colors[1])
        surface.cover(draw.disc(surface, cx, cy, radius, soft=0.006), linear("#030407"))
        rim = draw.ring(surface, cx, cy, radius * 1.09, 0.008, soft=0.007)
        surface.add(rim, self.colors[0], 0.30)
        self._stroke(
            surface,
            cx + np.cos(self.angle) * radius * 1.25,
            cy + np.sin(self.angle) * radius * 1.25,
            self.colors[2],
            0.026,
        )


class _Return(_Coupon):
    """Recede above Saturn's receipt-rings as forty seconds of spectrum drift out."""

    def _paint(self, surface, frame):
        arc = draw.smoothstep(0, 1, self._arc(frame))
        radius = 0.43 - 0.19 * arc
        cx, cy = -0.04 + arc * 0.32, -0.08
        sunrise = draw.smoothstep(
            max(0, self.movement.duration_s - 60), self.movement.duration_s, frame.tau
        )
        self._sphere(surface, frame, cx, cy, radius, sunrise=sunrise)
        self._rings(surface, frame, cx, cy, radius, 0.68, -0.16, receipt=True)


def build_scene(movement: Movement) -> Scene:
    """Build the specific Coupon movement's seeded scene for the album registry.

    Args:
        movement: Coupon metadata; scene must name one of the seven published movements.

    Returns:
        An independent scene with no size-dependent state until resize or render.

    Raises:
        ValueError: If scene is not one of the seven Coupon movement keys.
    """
    scenes = {
        "arrival": _Arrival,
        "friction": _Friction,
        "commerce": _Commerce,
        "pursuit": _Pursuit,
        "memory": _Memory,
        "gravity": _Gravity,
        "return": _Return,
    }
    try:
        return scenes[movement.scene](movement)
    except KeyError as error:
        raise ValueError(f"Unknown Coupon scene: {movement.scene}") from error

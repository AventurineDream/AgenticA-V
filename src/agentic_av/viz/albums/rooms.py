"""Paint Quiet Machinery's six self-lit sculptures for the mosaic scene registry.

Each room has its own geometry and musical mechanism. Scene space is isotropic;
all autonomous motion uses picture time, and audio state advances only with dt.
Seeded details and analytic damped responses make seeks reproducible without trails.
"""

from __future__ import annotations

import numpy as np

from ..color import linear, mix
from ..draw import lines, points, smoothstep
from ..scene import Frame, Movement, Scene
from ..score import NOTE
from ..surface import Surface

_PARTS = ("mallet", "bell", "wind", "bass", "drums", "air")
_EMPTY = np.empty(0, dtype=NOTE)


class _Room(Scene):
    """Share restrained materials, seeded dust, and held audio snapshots."""

    def __init__(self, movement: Movement):
        self.movement = movement
        palette = movement.palette or ("#10141f", "#557b88", "#d5ae78")
        self.base, self.cool, self.warm = [linear(c) for c in palette[:3]]
        self.metal = mix(self.cool, self.warm, 0.45)
        rng = np.random.default_rng(movement.seed)
        self.dust = rng.uniform(0, 1, (110, 4)).astype(np.float32)
        self.phase = rng.uniform(0, 2 * np.pi, 24).astype(np.float32)
        self.q = np.linspace(0, 1, 160, dtype=np.float32)
        self.a = np.linspace(0, 2 * np.pi, 200, dtype=np.float32)
        self._shape = None
        self._initialized = False
        self.seek()

    def resize(self, surface: Surface) -> None:
        """Cache coordinate views and reusable drawing layers for a new canvas.

        Args:
            surface: Destination canvas, whose dimensions are terminal sub-pixels.
        """
        self._shape = surface.rgb.shape
        self.u, self.v = surface.u, surface.v
        self._stroke_layers = tuple(surface.layer() for _ in range(3))
        self._dot_layers = tuple(surface.layer() for _ in range(3))
        self._glow_layers = tuple(surface.layer() for _ in range(3))
        self._face_layers = tuple(surface.layer() for _ in range(2))
        self._field, self._temp = surface.layer(), surface.layer()
        self._cache(surface)
        self.seek()

    def _color_index(self, color) -> int:
        if color is self.cool:
            return 0
        if color is self.warm:
            return 1
        return 2

    def seek(self) -> None:
        """Discard smoothed musical state and the held score snapshot after a jump."""
        self.signals = np.zeros(6, dtype=np.float32)
        self.notes = dict.fromkeys(_PARTS, _EMPTY)
        self.audio_t = 0.0
        self._score = None
        self._features = None
        self._initialized = False

    def _cache(self, surface: Surface) -> None:
        self.falloff = np.exp(-0.65 * (surface.u**2 + surface.v**2)).astype(np.float32)

    def _begin(self, surface: Surface, frame: Frame) -> float:
        if self._shape != surface.rgb.shape:
            self.resize(surface)
        for group in (
            self._stroke_layers,
            self._dot_layers,
            self._glow_layers,
            self._face_layers,
        ):
            for layer in group:
                layer.fill(0)
        if frame.energy <= 0:
            self.signals.fill(0)
            self.notes = dict.fromkeys(_PARTS, _EMPTY)
            self._score = None
            self._features = None
            self._initialized = True
        elif frame.dt > 0 or not self._initialized:
            # A paused seek/resize needs the requested score snapshot, but must
            # not integrate it as elapsed simulation time.
            self.audio_t = frame.t
            self._score, self._features = frame.score, frame.features
            lv = frame.levels
            target = np.array(
                [lv.mid, lv.treble, lv.mid, lv.bass, lv.hat, lv.slow_loud], dtype=np.float32
            )
            if frame.score is not None:
                # Stage scales score velocities once; do not apply energy a second time.
                target = np.maximum(
                    target, [frame.score.level(p, frame.t, decay_s=1.4) for p in _PARTS]
                )
                self.notes = {p: frame.score.recent(p, frame.t, 8.0) for p in _PARTS}
                if self.movement.scene == "lattice":
                    target[2] = frame.score.level("wind", frame.t, decay_s=1.4, kind="clarinet")
            else:
                self.notes = dict.fromkeys(_PARTS, _EMPTY)
            if frame.dt > 0:
                self.signals += (target - self.signals) * (1 - np.exp(-frame.dt / 0.8))
            else:
                self.signals[:] = target
            self._initialized = True
        surface.fill(self.base * 0.035)
        return float(smoothstep(0, 1, np.clip(frame.tau / self.movement.duration_s, 0, 1)))

    def _stroke(self, surface, x, y, color, gain=0.35, weight=1.0):
        index = self._color_index(color)
        lines(surface, self._stroke_layers[index], x, y, weight * gain)

    def _dots(self, surface, x, y, color, weight=0.2):
        points(surface, self._dot_layers[self._color_index(color)], x, y, weight)

    def _glow(self, surface, x, y, sx, sy, color, gain):
        np.subtract(self.u, x, out=self._field)
        self._field /= sx
        np.square(self._field, out=self._field)
        np.subtract(self.v, y, out=self._temp)
        self._temp /= sy
        np.square(self._temp, out=self._temp)
        self._field += self._temp
        self._field *= -1
        np.exp(self._field, out=self._field)
        target = self._glow_layers[self._color_index(color)]
        np.multiply(self._field, gain, out=self._temp)
        np.add(target, self._temp, out=target)

    def _finish(self, surface, frame, cx, cy, radius=0.6):
        # Dust exists only in the sculpture's spill; there is no global starfield.
        x = (self.dust[:, 0] * 2 - 1) * surface.half_w
        y = (self.dust[:, 1] * 2 + frame.tau * (0.002 + self.dust[:, 2] * 0.002)) % 2 - 1
        weight = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / radius**2)
        self._dots(surface, x, y, self.metal, weight * 0.09)
        # Each material retains its instrumental identity even in the sparsest room.
        bell = self.signals[1]
        self._glow(surface, cx + 0.10, cy, 0.045 + bell * 0.035, 0.06, self.cool, bell * 0.018)
        self._dots(surface, [cx - 0.075], [cy + 0.035], self.warm, self.signals[0] * 0.12)
        tick = 0.012 * self.signals[4]
        self._stroke(
            surface,
            [cx + radius * 0.55, cx + radius * 0.55 + tick],
            [cy + radius * 0.38, cy + radius * 0.38],
            self.metal,
            0.12,
        )
        for group, colors in (
            (self._stroke_layers, (self.cool, self.warm, self.metal)),
            (self._dot_layers, (self.cool, self.warm, self.metal)),
            (self._glow_layers, (self.cool, self.warm, self.metal)),
            (self._face_layers, (self.warm, self.cool)),
        ):
            for layer, color in zip(group, colors, strict=True):
                surface.add(layer, color)
        surface.rgb *= self.falloff[..., None]

    def _wind_arcs(self, surface, frame, x0, y0, x1, y1, gain=0.12):
        wind = self.signals[2]
        q = self.q
        bend = (0.08 + 0.12 * wind) * np.sin(frame.tau * 0.12 + self.phase[0])
        self._stroke(
            surface,
            x0 + (x1 - x0) * q,
            y0 + (y1 - y0) * q - np.sin(np.pi * q) * bend,
            self.cool,
            gain,
        )


class _Aperture(_Room):
    """A torn light aperture and a damped copper pendulum."""

    def _pendulum(self, frame):
        angle = 0.07 * np.sin(frame.tau * 0.69) * np.exp(-frame.tau / 900)
        if self._score is not None:
            notes = self._score.recent("bass", self.audio_t, 16)
            age = self.audio_t - notes["onset"]
            # Impulse response of theta'' + 2 gamma theta' + omega^2 theta = force.
            angle += float(
                np.sum(notes["vel"] * 0.13 * np.exp(-0.26 * age) * np.sin(2.25 * age) / 2.25)
            )
        elif self._features is not None:
            times, strengths = self._features.onsets("low", self.audio_t - 16, self.audio_t)
            age = self.audio_t - times
            angle += float(
                np.sum(
                    strengths
                    * frame.energy
                    * 0.07
                    * np.exp(-0.26 * age)
                    * np.sin(2.25 * age)
                    / 2.25
                )
            )
        else:
            angle += self.signals[3] * 0.035 * np.sin(frame.tau * 2.25)
        return np.clip(angle, -0.22, 0.22)

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint the tear, swinging shadow, copper edge repairs, and plumb weight.

        Args:
            surface: Linear RGB canvas mutated in place.
            frame: Held musical instant; geometry uses picture seconds only.
        """
        arc = self._begin(surface, frame)
        cx, cy = -0.24, -0.06
        angle = self._pendulum(frame)
        px, py = cx + np.sin(angle) * 0.9, -0.78 + np.cos(angle) * 0.9
        x, y = self.u - cx, self.v - cy
        polar = np.arctan2(y, x)
        tear = 1 + 0.08 * np.sin(7 * polar + self.phase[0]) + 0.05 * np.sin(13 * polar)
        distance = np.sqrt((x / (0.28 + 0.10 * arc)) ** 2 + (y / 0.55) ** 2) / tear
        opening = np.clip((1 - distance) * 80, 0, 1)
        self._glow(surface, cx, cy, 0.62, 0.78, self.cool, 0.055)
        surface.add(opening * (0.035 + 0.035 * (1 + y)), self.cool)
        edge = np.exp(-(((distance - 1) / 0.025) ** 2))
        surface.add(edge, self.warm, 0.33)
        outer = np.exp(-(((distance - 1.065) / 0.032) ** 2))
        surface.add(outer * (0.35 + 0.65 * np.maximum(0, np.sin(19 * polar))), self.metal, 0.15)
        # The shadow moves over existing illumination, never replaces a large bright field.
        shadow = np.exp(-(((self.u - (cx + 1.9 * (px - cx))) / 0.075) ** 2))
        shadow *= np.exp(-(((self.v - 0.20) / 0.6) ** 2))
        surface.rgb *= 1 - 0.65 * shadow[..., None]
        a = self.a
        ex = cx + (0.28 + 0.10 * arc) * np.cos(a) * (
            1 + 0.08 * np.sin(7 * a + self.phase[0]) + 0.05 * np.sin(13 * a)
        )
        ey = cy + 0.55 * np.sin(a) * (
            1 + 0.08 * np.sin(7 * a + self.phase[0]) + 0.05 * np.sin(13 * a)
        )
        selected = np.exp(-(((np.angle(np.exp(1j * (a - frame.tau * 0.10)))) / 0.13) ** 2))
        self._dots(surface, ex, ey, self.warm, selected * (0.15 + self.signals[0] * 0.25))
        self._stroke(surface, [cx, px], [-0.9, py], self.metal, 0.28)
        cone = np.abs(self.u - px) < 0.065 * (1 - np.abs(self.v - py) / 0.14)
        surface.cover(cone.astype(np.float32), self.warm * 0.10)
        self._stroke(
            surface,
            [px, px - 0.06, px, px + 0.06, px],
            [py - 0.13, py + 0.02, py + 0.11, py + 0.02, py - 0.13],
            self.warm,
            0.5,
        )
        self._wind_arcs(surface, frame, cx - 0.20, -0.28, cx + 0.20, 0.24)
        self._finish(surface, frame, cx, cy)


class _Crossing(_Room):
    """Two seven-panel accordion screens with multiplicative overlap shadows."""

    def __init__(self, movement):
        super().__init__(movement)
        widths = np.array([0.10, 0.18, 0.12, 0.23, 0.13, 0.17, 0.11], np.float32)
        self.edges = np.r_[0, np.cumsum(widths)] - widths.sum() / 2

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint two sliding folded screens and thin breath bridges.

        Args:
            surface: Linear RGB destination mutated in place.
            frame: Musical instant with picture time in seconds.
        """
        arc = self._begin(surface, frame)
        slide = 0.30 * np.sin(frame.tau * 0.032) + (arc - 0.5) * 0.48
        phase = frame.tau * (self.movement.bpm or 108) / 60 * 2
        for screen, (offset, slope) in enumerate(((-0.22 + slide, 0.28), (0.20 - slide, -0.30))):
            local = self.u - offset
            height = self.v - slope * local + (0.08 if screen else -0.12)
            height -= self.signals[3] * 0.012 * np.sin(local * 3)
            inside = (np.abs(height) < 0.46) & (local > self.edges[0]) & (local < self.edges[-1])
            if screen:
                shadow = np.where(inside, 0.22, 1)
                surface.rgb *= shadow[..., None]
                np.multiply(self._stroke_layers[1], shadow, out=self._stroke_layers[1])
                np.multiply(self._face_layers[0], shadow, out=self._face_layers[0])
            # Seven fixed physical panels, not seven independent per-frame objects.
            # Seven unequal panels share three vectorized stroke calls per screen.
            panels = np.arange(7, dtype=np.float32)
            left, right = self.edges[:-1], self.edges[1:]
            fold = 0.27 + 0.20 * np.cos(panels * 2.1 + screen)
            light = 0.5 + 0.5 * np.cos(2 * np.pi * (phase / 7 - panels / 7))
            shade = fold * (0.8 + frame.energy * 0.1 * light)
            material = self.cool if screen else self.warm
            panel_index = np.searchsorted(self.edges[1:-1], local, side="right")
            self._face_layers[screen][inside] = shade[panel_index[inside]] * 0.12
            xl = left + offset
            yt = -0.46 + slope * left - (0.08 if screen else -0.12)
            target = self._stroke_layers[self._color_index(material)]
            lines(
                surface,
                target,
                np.broadcast_to(xl[:, None], (7, 2)),
                np.column_stack((yt, yt + 0.92)),
                0.13 + fold * 0.2,
            )
            lines(
                surface,
                target,
                np.column_stack((xl, right + offset)),
                np.column_stack((yt, yt + slope * (right - left))),
                0.26,
            )
            # Engravings follow the face, with uneven widths preserving the sevenfold meter.
            offsets = np.array([-0.26, -0.20, 0.20, 0.23], dtype=np.float32)[:, None]
            lines(
                surface,
                self._stroke_layers[2],
                np.broadcast_to(self.edges[None, :] + offset, (4, 8)),
                self.edges[None, :] * slope + offsets - (0.08 if screen else -0.12),
                0.055,
            )
        self._wind_arcs(surface, frame, -0.7 + slide, -0.15, 0.65 - slide, 0.1, 0.19)
        self._finish(surface, frame, 0, 0, 0.85)


class _Bell(_Room):
    """A flared, meridian-engraved bell whose mouth carries decaying rim modes."""

    def render(self, surface: Surface, frame: Frame) -> None:
        """Shade the resonant shell and its pitch-selected two-to-five-lobed lip.

        Args:
            surface: Linear RGB destination mutated in place.
            frame: Musical instant; recent bell notes excite small geometric modes.
        """
        arc = self._begin(surface, frame)
        scale = 0.74 + 0.34 * arc
        cx, top, bottom = 0.20, -0.62 * scale, 0.38 * scale
        bottom += self.signals[3] * 0.012
        yy = np.clip((self.v - top) / (bottom - top), 0, 1)
        radius = (0.13 + 0.48 * yy**2.4) * scale
        xx = (self.u - cx) / radius
        shell = (np.abs(xx) < 1) & (self.v > top) & (self.v < bottom)
        light = 0.02 + 0.10 * np.maximum(0, 1 - xx**2) ** 2
        specular = np.exp(-(((xx + 0.56) / 0.09) ** 2)) * 0.15
        surface.add(shell * (light + specular), self.metal)
        meridians = np.linspace(-0.97, 0.97, 19, dtype=np.float32)
        q = self.q
        y = top + q * (bottom - top)
        r = (0.13 + 0.48 * q**2.4) * scale
        x = cx + meridians[:, None] * r
        sway = self.signals[2] * 0.015 * np.sin(frame.tau * 0.35 + q * 3)
        latest = self.notes["bell"]
        mode = 3 if not len(latest) else 2 + int(latest[-1]["midi"]) % 4
        nodes = 1 + self.signals[1] * 0.5 * np.sin(mode * np.arccos(meridians)) ** 8
        self._stroke(surface, x + sway, np.broadcast_to(y, x.shape), self.cool, 0.12, weight=nodes)
        a = self.a
        deformation = np.zeros_like(a)
        notes = self.notes["bell"]
        if len(notes):
            age = self.audio_t - notes["onset"]
            modes = 2 + notes["midi"].astype(int) % 4
            deformation = np.sum(
                (notes["vel"] * np.exp(-age / 2.8) * 0.018)[:, None]
                * np.cos(modes[:, None] * a + notes["pan"][:, None]),
                axis=0,
            )
        rlip = 0.61 * scale * (1 + deformation + 0.005 * np.sin(a * 3 + frame.tau * 0.32))
        lipx, lipy = cx + rlip * np.cos(a), bottom + rlip * np.sin(a) * 0.27
        # A dark mouth occludes the shell, giving the below-eye-level view real depth.
        mouth = ((self.u - cx) / (0.60 * scale)) ** 2 + (
            (self.v - bottom) / (0.16 * scale)
        ) ** 2 < 1
        surface.cover(mouth.astype(np.float32), self.base * 0.018)
        self._stroke(surface, lipx, lipy, self.cool, 0.55)
        self._stroke(surface, lipx * 0.98 + cx * 0.02, lipy - 0.025, self.warm, 0.18)
        for shift in (0.07, 0.17, 0.30):
            expansion = 1 + shift + 0.025 * np.sin(frame.tau * 0.25)
            self._stroke(
                surface, cx + (lipx - cx) * expansion, lipy + shift, self.cool, 0.08 * (1 - shift)
            )
        self._stroke(surface, [cx, cx], [-1, top], self.metal, 0.24)
        self._finish(surface, frame, cx, 0, 0.8)


class _Lattice(_Room):
    """Oblique Voronoi salt plates, widening faults, and halite vertices."""

    def __init__(self, movement):
        super().__init__(movement)
        rng = np.random.default_rng(movement.seed + 19)
        self.sites = rng.uniform([-1.1, -0.5], [1.1, 1.3], (23, 2)).astype(np.float32)
        self.vertex = rng.uniform([-0.8, -0.35], [0.85, 0.85], (14, 2)).astype(np.float32)

    def _cache(self, surface):
        # Build nearest/runner-up distances once, not a (pixels x sites) tensor per frame.
        super()._cache(surface)
        y = (self.v - 0.20) / 0.55
        best = np.full_like(self.u, np.inf)
        second = np.full_like(best, np.inf)
        identity = np.zeros(self.u.shape, np.int16)
        for i, (x0, y0) in enumerate(self.sites):
            d = (self.u - x0) ** 2 + (y - y0) ** 2
            nearer = d < best
            second = np.where(nearer, best, np.minimum(second, d))
            best = np.minimum(best, d)
            identity[nearer] = i
        self.fault = np.sqrt(second) - np.sqrt(best)
        self.plate_id = identity
        self.plane = np.exp(-((self.u / 1.0) ** 4 + ((self.v - 0.17) / 0.48) ** 4))
        # Actual Voronoi vertices occur where three nearest squared distances agree.
        distances = np.stack([(self.u - x) ** 2 + (y - yy) ** 2 for x, yy in self.sites])
        near = np.partition(distances, 2, axis=0)[:3]
        candidates = np.argwhere((near.max(axis=0) - near.min(axis=0) < 0.035) & (self.plane > 0.4))
        if len(candidates):
            chosen = candidates[np.linspace(0, len(candidates) - 1, 14).astype(int)]
            self.vertex = np.column_stack((self.u[tuple(chosen.T)], self.v[tuple(chosen.T)]))

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint separated crystal faces, localized clarinet faults, and bar growth.

        Args:
            surface: Linear RGB destination mutated in place.
            frame: Musical instant with a three-quarter picture-clock growth cycle.
        """
        arc = self._begin(surface, frame)
        gap = 0.012 + 0.065 * arc
        fault = self.fault + np.sin(self.plate_id * 2.3) * self.signals[3] * 0.004
        plates = smoothstep(gap, gap + 0.018, fault) * self.plane
        shade = 0.025 + 0.025 * (self.plate_id % 5) / 4
        surface.add(plates * shade, self.metal)
        edges = np.exp(-(((fault - gap - 0.008) / 0.012) ** 2)) * self.plane
        surface.add(edges, self.cool, 0.15)
        # Clarinet pitch selects one crack neighborhood, never the whole bright lattice.
        wind = self.notes["wind"]
        chosen = int(frame.tau / 7) % len(self.sites)
        if len(wind):
            chosen = int(wind[-1]["midi"]) % len(self.sites)
        faultlight = edges * (self.plate_id == chosen)
        surface.add(faultlight, self.cool, self.signals[2] * 0.18)
        mallet = self.notes["mallet"]
        if len(mallet):
            note = mallet[-1]
            plate = int(note["midi"]) % len(self.sites)
            surface.add(plates * (self.plate_id == plate), self.warm, self.signals[0] * 0.025)
        # Eased bar steps: growth has zero slope at each boundary, even without analysis.
        bar = frame.tau * (self.movement.bpm or 84) / 180
        growth = (np.floor(bar) + smoothstep(0.15, 0.85, bar % 1)) / 40
        size = 0.012 + 0.025 * np.clip(growth, 0, 1)
        sag = self.signals[3] * 0.007 * np.sin(frame.tau * 0.2)
        for i, (x, y) in enumerate(self.vertex):
            s = size * (0.6 + (i % 4) / 4)
            self._stroke(
                surface,
                [x - s, x, x + s, x, x - s, x - s, x, x, x + s, x + s],
                [
                    y,
                    y - s * 0.6,
                    y,
                    y + s * 0.6,
                    y,
                    y + s,
                    y + s * 1.6,
                    y + s * 0.6,
                    y,
                    y + s + sag,
                ],
                self.warm,
                0.16,
            )
        self._finish(surface, frame, 0, 0.2, 0.8)


class _Void(_Room):
    """An almost empty plaster room holding one small warm light."""

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint near-black perspective, a swaying cord, dust cone, and bell memory.

        Args:
            surface: Linear RGB destination mutated in place.
            frame: Musical instant; light occupies only a tiny fraction of the room.
        """
        arc = self._begin(surface, frame)
        cx = -0.30 + 0.015 * np.sin(frame.tau * 0.20) * (1 + self.signals[3])
        cy = -0.38 + 0.28 * arc
        self._glow(surface, cx, cy, 0.36, 0.42, self.warm, 0.016)
        # Architectural edges remain below the sculpture's light, not a neon room grid.
        back = np.array([-0.67, 0.60, 0.60, -0.67, -0.67], np.float32)
        by = np.array([-0.55, -0.55, 0.54, 0.54, -0.55], np.float32)
        self._stroke(surface, back, by, self.cool, 0.035)
        for x, y, ox, oy in (
            (-0.67, -0.55, -1.5, -1),
            (0.60, -0.55, 1.5, -1),
            (-0.67, 0.54, -1.5, 1),
            (0.60, 0.54, 1.5, 1),
        ):
            self._stroke(surface, [x, ox], [y, oy], self.cool, 0.025)
        doorway = (self.u > 0.30) & (self.u < 0.48) & (self.v > -0.13) & (self.v < 0.54)
        surface.cover(doorway.astype(np.float32), self.base * 0.008)
        self._stroke(surface, [cx - 0.01, cx], [-0.72, cy], self.metal, 0.12)
        breath = 1 + 0.07 * np.sin(frame.tau * 0.6) + self.signals[1] * 0.08
        self._glow(surface, cx, cy, 0.018 * breath, 0.022 * breath, self.warm, 0.64)
        cone = np.exp(-(((self.u - cx) / (0.03 + np.maximum(0, self.v - cy) * 0.16)) ** 2))
        cone *= np.maximum(0, 1 - (self.v - cy) / 0.7) * (self.v > cy)
        surface.add(cone, self.warm, 0.009)
        # Slow decays are small wall marks, never a beat-driven whole-room wash.
        for note in self.notes["bell"][-8:]:
            age = self.audio_t - float(note["onset"])
            mx = cx + float(note["pan"]) * 0.35
            my = 0.11 + (float(note["midi"]) % 12) * 0.013
            self._glow(
                surface,
                mx,
                my,
                0.025,
                0.045,
                self.warm,
                float(note["vel"]) * np.exp(-age / 3) * 0.035,
            )
        self._finish(surface, frame, cx, cy + 0.1, 0.27)


class _Dawn(_Room):
    """A seven-fork aerial earns a copper horizon, then closes to one point."""

    def __init__(self, movement):
        super().__init__(movement)
        self.tipx = np.array([-0.67, -0.48, -0.23, -0.05, 0.20, 0.48, 0.71], np.float32)
        self.tipy = np.array([-0.25, -0.60, -0.38, -0.75, -0.48, -0.31, -0.55], np.float32)

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint unequal voice arms, travelling notes, and slowly opening field arches.

        Args:
            surface: Linear RGB destination mutated in place.
            frame: Musical instant; radiance landmarks are interpreted in picture seconds.
        """
        arc = self._begin(surface, frame)
        # The authored 168/185/240 s markers are picture-time landmarks, so still holds.
        on, full, off = 168.0, 185.0, 240.0
        if self._score is not None:
            on = self._score.markers.get("radiance_on", on)
            full = self._score.markers.get("radiance_full", full)
            off = self._score.markers.get("radiance_off", off)
        radiance = float(
            smoothstep(on, full, frame.tau)
            * (1 - smoothstep(off, self.movement.duration_s, frame.tau))
        )
        horizon = 0.66
        width = 0.18 + radiance * 1.2
        self._glow(surface, -0.12, horizon, width, 0.065, self.warm, 0.022 * radiance)
        self._stroke(
            surface, [-width, width], [horizon, horizon], self.warm, 0.025 + 0.12 * radiance
        )
        self._stroke(surface, [-0.07, -0.07], [horizon, -0.50], self.metal, 0.24)
        q = self.q
        sag = self.signals[3] * 0.018
        spread = 0.72 + 0.34 * np.sin(np.pi * arc)
        arms = np.arange(7, dtype=np.float32)
        xs = self.tipx * spread
        rooty = 0.29 - arms * 0.045
        elbows = rooty - 0.13 - sag
        metal_x = np.column_stack((np.full(7, -0.07), xs * 0.64, xs, xs))
        metal_y = np.column_stack((rooty, elbows, self.tipy + 0.13, self.tipy))
        lines(surface, self._stroke_layers[2], metal_x, metal_y, 0.31)
        warm_x = np.column_stack((xs - 0.025, xs + 0.025))
        warm_y = np.broadcast_to(self.tipy[:, None], warm_x.shape)
        lines(surface, self._stroke_layers[1], warm_x, warm_y, 0.36)
        t = (frame.tau * 0.045 + arms / 7) % 1
        points(
            surface,
            self._dot_layers[1],
            -0.07 + (xs + 0.07) * t,
            rooty + (self.tipy - rooty) * t,
            0.22,
        )
        arch = np.arange(0, 7, 2)
        ax = xs[arch, None] + (0.24 + radiance * 0.28) * np.sin(np.pi * q)
        ay = self.tipy[arch, None] + (horizon - self.tipy[arch, None]) * q
        ax += 0.015 * self.signals[2] * np.sin(q * 6 + frame.tau * 0.2)
        lines(surface, self._stroke_layers[0], ax, ay, 0.045 + 0.08 * radiance)
        for part in ("mallet", "bell", "wind"):
            notes = self.notes[part][-12:]
            if not len(notes):
                continue
            age = self.audio_t - notes["onset"]
            t = np.clip(age / 4.5, 0, 1)
            arm = notes["voice"].astype(np.intp) % 7
            x = -0.07 + (self.tipx[arm] * spread + 0.07) * t
            y = 0.2 + (self.tipy[arm] - 0.2) * t
            color = self._dot_layers[0 if part == "bell" else 1]
            points(surface, color, x, y, notes["vel"] * 0.25 * (1 - t))
        self._glow(surface, -0.07, horizon - 0.02, 0.025, 0.022, self.warm, 0.20 + arc * 0.18)
        self._finish(surface, frame, -0.07, 0, 0.8)


_SCENES = {
    "aperture": _Aperture,
    "crossing": _Crossing,
    "orbit": _Bell,
    "lattice": _Lattice,
    "void": _Void,
    "dawn": _Dawn,
}


def build_scene(movement: Movement) -> Scene:
    """Build the authored Quiet Machinery sculpture selected by its scene key.

    Args:
        movement: Rooms movement metadata, including its immutable seed and palette.

    Returns:
        An unresized scene with no I/O or global random state.

    Raises:
        ValueError: The movement names an unknown rooms scene.
    """
    try:
        return _SCENES[movement.scene](movement)
    except KeyError as exc:
        raise ValueError(f"Unknown rooms scene: {movement.scene}") from exc

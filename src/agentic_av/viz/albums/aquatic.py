"""Paint six scored conversations in water for the album scene registry.

Shared, seeded pigment advection gives the album its submerged material; each
movement owns a different current and focal geometry. Only picture time advances
art. Audio bends small shapes, never switches large illuminated regions.
"""

from __future__ import annotations

import math

import numpy as np

from ..color import linear, mix
from ..draw import Flow, lines, points, ring, smoothstep
from ..scene import Frame, Movement, Scene
from ..surface import Surface

_PALETTES = (
    ("#e9e3c7", "#bb8eb1", "#82d7d4", "#183a61"),
    ("#f3b38b", "#c389cc", "#90ded3", "#143159"),
    ("#edf3db", "#a8c8c3", "#b3dfa3", "#203943"),
    ("#f9b296", "#bda0e6", "#7cddd8", "#182755"),
    ("#f0d9c5", "#baa1b0", "#aacacd", "#172c40"),
    ("#f5deae", "#b1bde0", "#a7e5d9", "#16374c"),
)


class _Water(Scene):
    """Own low-resolution pigment, interpolation caches, and the water column."""

    def __init__(self, movement: Movement):
        super().__init__(movement)
        palette = movement.palette if len(movement.palette) >= 4 else _PALETTES[movement.index]
        self.colors = np.asarray([linear(c) for c in palette[:4]], dtype=np.float32)
        self.floor = linear("#08171f")
        self.flow = Flow(movement.seed, scale=1.4)
        rng = np.random.default_rng(movement.seed)
        self.dust = rng.uniform(0, 1, (110, 4)).astype(np.float32)
        self.phase = rng.uniform(0, 2 * np.pi, (14, 1)).astype(np.float32)
        self.s = np.linspace(0, 1, 100, dtype=np.float32)[None, :]
        self.taper = np.maximum(np.sin(self.s * np.pi), 0) ** 0.8
        # A handful of sharp strands sit in front of the soft advected pigment;
        # raising the entire cloud would erase its depth and negative space.
        self.strokes = self.taper * (0.035 + (np.arange(14) % 3 == 0) * 0.34)[:, None]
        self.depth = np.linspace(0, 1, 14, dtype=np.float32)[:, None]
        self._size = None
        self._held = False

    def resize(self, surface: Surface) -> None:
        """Allocate canvas-dependent pigment and scratch storage, clearing history.

        Args:
            surface: Output canvas; dimensions are sub-pixels and terminal cells.
        """
        self._size = surface.rgb.shape
        # A small fluid grid is deliberately softer than foreground filaments.
        cols = max(2, surface.cols // 2)
        aspect = cols / (surface.rows * surface.half_w)
        self.ink = Surface(cols, surface.rows, 1, 1, cell_aspect=aspect)
        self.pigment = np.zeros_like(self.ink.rgb)
        self.deposit = self.ink.layer()
        self.layer = surface.layer()
        self.work = np.empty_like(surface.rgb)
        self.blend = np.empty_like(surface.rgb)
        self.horizontal = np.empty((self.ink.h, surface.w, 3), dtype=np.float32)
        self.horizontal_blend = np.empty_like(self.horizontal)
        self.picture = np.empty_like(surface.rgb)
        self._ix, self._iy = np.meshgrid(
            np.arange(self.ink.w, dtype=np.float32),
            np.arange(self.ink.h, dtype=np.float32),
        )
        x = np.linspace(0, self.ink.w - 1, surface.w, dtype=np.float32)
        y = np.linspace(0, self.ink.h - 1, surface.h, dtype=np.float32)
        self._x = np.minimum(x.astype(np.intp), self.ink.w - 2)
        self._y = np.minimum(y.astype(np.intp), self.ink.h - 2)
        self._fx = (x - self._x)[None, :, None].astype(np.float32)
        self._fy = (y - self._y)[:, None, None].astype(np.float32)
        self._gx, self._gy = 1 - self._fx, 1 - self._fy
        self.seek()

    def seek(self) -> None:
        """Clear advected pigment and the held picture after a discontinuity."""
        if self._size is not None:
            self.pigment.fill(0)
        self._held = False

    def _arc(self, frame):
        # Unlike audio progress, this cannot sneak motion into reduced/still art.
        return float(smoothstep(0, 1, frame.tau / max(1, self.movement.duration_s)))

    def _current(self, x, y, tau):
        vx, vy = self.flow.at(x, y, tau * 0.08)
        return vx * 0.025 + 0.008, vy * 0.025 - 0.012

    def _curves(self, frame):
        arc = self._arc(frame)
        s, d = self.s, self.depth
        x = (s * 1.55 - 0.65) * (0.9 + arc * 0.22)
        x = np.broadcast_to(x, (14, 100)).copy()
        y = -0.3 + (d - 0.5) * 0.58 + np.sin(s * 7 + self.phase + frame.tau * 0.075) * 0.09
        y += np.sin(s * 14 - frame.tau * 0.035 + self.phase) * (0.018 + s * 0.06)
        x += np.sin(self.phase + frame.tau * 0.025) * s * 0.12
        return x, y

    def _advect(self, frame):
        dt = min(max(frame.dt, 0), 0.1)
        vx, vy = self._current(self.ink.u, self.ink.v, frame.tau)
        x = np.clip(self._ix - vx * dt * self.ink.w / (2 * self.ink.half_w), 0, self.ink.w - 1)
        y = np.clip(self._iy - vy * dt * self.ink.h / 2, 0, self.ink.h - 1)
        ix = np.minimum(x.astype(np.intp), self.ink.w - 2)
        iy = np.minimum(y.astype(np.intp), self.ink.h - 2)
        fx, fy = (x - ix)[..., None], (y - iy)[..., None]
        self.ink.rgb[:] = (
            self.pigment[iy, ix] * (1 - fx) * (1 - fy)
            + self.pigment[iy, ix + 1] * fx * (1 - fy)
            + self.pigment[iy + 1, ix] * (1 - fx) * fy
            + self.pigment[iy + 1, ix + 1] * fx * fy
        ) * (0.5 ** (dt / 5.0))

    def _pigment(self, surface, frame, x, y, colors):
        self._advect(frame)
        # Continuous tiny deposits avoid bright onset-triggered puffs. The
        # first image is a finished painting, not an empty simulation warm-up.
        gain = 0.025 if not self._held else -math.expm1(-min(frame.dt, 0.1) / 4) * 0.35
        for indices, tint in ((slice(None, 7), colors[1]), (slice(7, None), colors[0])):
            self.deposit.fill(0)
            lines(self.ink, self.deposit, x[indices], y[indices], weight=self.taper * 0.5)
            self.ink.add(self.deposit, tint, gain=gain)
        self._notes(self.ink, frame, colors, layer=self.deposit, gain=gain * 2)
        self.pigment[:] = self.ink.rgb
        # Separable interpolation keeps all full-canvas storage reusable.
        np.take(self.pigment, self._x, axis=1, out=self.horizontal)
        np.multiply(self.horizontal, self._gx, out=self.horizontal)
        np.take(self.pigment, self._x + 1, axis=1, out=self.horizontal_blend)
        np.multiply(self.horizontal_blend, self._fx, out=self.horizontal_blend)
        np.add(self.horizontal, self.horizontal_blend, out=self.horizontal)
        np.take(self.horizontal, self._y, axis=0, out=self.work)
        np.multiply(self.work, self._gy, out=self.work)
        np.take(self.horizontal, self._y + 1, axis=0, out=self.blend)
        np.multiply(self.blend, self._fy, out=self.blend)
        np.add(self.work, self.blend, out=self.work)
        surface.rgb += self.work

    def _light(self, surface, frame, colors):
        u, v = surface.u, surface.v
        sparse = self.movement.index == 4
        gain = 0.2 if sparse else 1.0
        tau = frame.tau
        slow = frame.levels.slow_loud if frame.energy > 0 else 0
        shafts = np.exp(-(((u + 0.42 * v - 0.22 - 0.06 * math.sin(tau * 0.025)) / 0.17) ** 2))
        shafts += 0.42 * np.exp(-(((u + 0.34 * v + 0.72) / 0.095) ** 2))
        shafts *= np.exp(-(v + 1) * 1.7) * (0.012 + slow * 0.003) * gain
        surface.add(shafts, colors[2])
        caustic = np.sin(u * 7 + v * 3 + tau * 0.03) + np.sin(u * 4 - v * 6 - tau * 0.04)
        caustic = np.maximum(caustic - 1.5, 0) ** 2 * 0.004 * gain
        surface.add(caustic * np.exp(-(v + 1) * 2), colors[0])

    def _membrane(self, surface, frame, colors):
        if self.movement.index in (2, 4):
            return
        bass = frame.levels.slow_bass if frame.energy > 0 else 0
        score = frame.score if frame.energy > 0 else None
        pitch = 40.0
        if score is not None:
            notes = score.recent("bass", frame.t, 5)
            if len(notes):
                note = notes[-1]
                pitch += (float(note["midi"]) - 40) * float(note["vel"])
                bass += score.level("bass", frame.t, decay_s=1.5) * 0.3
        cx = -0.48 if self.movement.index == 1 else 0.15
        cy = 0.6 + 0.025 * math.sin(frame.tau * 0.24)
        radius = 0.72 + 0.02 * math.sin(frame.tau * 0.2) + 0.025 * bass
        rim = ring(surface, cx, cy, radius, 0.018, squash=0.23, angle=-0.08, soft=0.016)
        surface.add(rim, colors[3], gain=0.4)
        # Bass displaces a narrow veil above the membrane, never its brightness.
        self.layer.fill(0)
        x = np.linspace(cx - radius, cx + radius, 140, dtype=np.float32)
        y = cy - 0.11 + np.sin(x * 5 + frame.tau * 0.25 + pitch * 0.01) * (0.025 + bass * 0.025)
        lines(surface, self.layer, x, y, weight=0.10)
        surface.add(self.layer, colors[2], gain=0.065)

    def _notes(self, surface, frame, colors, *, layer=None, gain=0.18):
        if frame.energy <= 0 or frame.score is None:
            return
        if layer is None:
            layer = self.layer
        notes = frame.score.recent("piano", frame.t, 7)
        if not len(notes):
            return
        # Bound dense adversarial scores without selecting a single bright winner.
        notes = notes[-48:]
        age = frame.t - notes["onset"]
        upper = notes["pan"] >= 0
        if "lower" in frame.score.voices:
            upper = notes["voice"] != frame.score.voices.index("lower")
        for mask, tint in ((upper, colors[0]), (~upper, colors[1])):
            n, a = notes[mask], age[mask]
            if not len(n):
                continue
            q = self.s[:, :35]
            side = np.where(upper[mask], 1, -1)[:, None]
            x = side * (0.95 - a[:, None] * 0.025 - q * (0.18 + n["vel"][:, None] * 0.2))
            y = (58 - n["midi"][:, None]) * 0.013 - 0.2 - a[:, None] * 0.009
            y = y + np.sin(q * 8 + n["midi"][:, None] * 0.4 + frame.tau * 0.08) * q * 0.07
            layer.fill(0)
            weight = n["vel"] * np.exp(-a / 3) * 0.11
            lines(surface, layer, x, y, weight=weight[:, None])
            surface.add(layer, tint, gain=gain)

    def _grains(self, surface, frame, colors):
        d = self.dust
        count = 18 if self.movement.index == 4 else len(d)
        d = d[:count]
        x = (d[:, 0] * 2 - 1) * surface.half_w
        y = (d[:, 1] * 2 - 1 - frame.tau * (0.008 + d[:, 2] * 0.013) + 1) % 2 - 1
        x += 0.05 * np.sin(y * 4 + frame.tau * 0.05 + d[:, 3] * 6)
        self.layer.fill(0)
        hat = frame.levels.hat if frame.energy > 0 else 0
        # Percussion tilts existing tiny grains; it does not turn them on/off.
        x += hat * 0.008 * d[:, 2]
        points(surface, self.layer, x, y, weight=0.08 + d[:, 2] ** 4 * 0.6)
        surface.add(self.layer, colors[2], gain=0.6 if self.movement.index != 4 else 0.25)

    def _detail(self, surface, frame, colors):
        # Fine branches provide a second depth plane, not another bright mass.
        x, y = self._curves(frame)
        self.layer.fill(0)
        lines(surface, self.layer, x[::4, ::3], y[::4, ::3] - 0.025, weight=0.018)
        surface.add(self.layer, colors[2], gain=0.16)

    def _pressure(self, frame, x, y):
        if frame.energy <= 0:
            return x, y
        bass = frame.levels.slow_bass
        kick = frame.levels.kick
        pad = 0.0
        if frame.score is not None:
            bass += frame.score.level("bass", frame.t, decay_s=1.8) * 0.25
            kick += frame.score.level("drums", frame.t, decay_s=0.6, kind="kick") * 0.2
            pad = frame.score.level("texture", frame.t, decay_s=4, kind="pad")
        # Fast signals have milliscene-unit displacement bounds. Even alternating
        # score fixtures cannot swap large bright/dark areas at musical rates.
        swell = np.exp(-(((x - 0.15) / 0.85) ** 2))
        y = y - swell * (0.018 * bass + 0.004 * kick * np.sin(x * 9))
        x = x + np.sin(y * 3 + frame.tau * 0.05) * pad * 0.012
        return x, y

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint a complete water composition, holding repeated zero-step frames.

        Args:
            surface: Mutable linear RGB output canvas.
            frame: Audio signals and picture-clock seconds; dt zero freezes history.
        """
        if self._size != surface.rgb.shape:
            self.resize(surface)
        if frame.dt == 0 and self._held:
            surface.rgb[:] = self.picture
            return
        colors = self._palette(frame)
        surface.fill(self.floor * (0.65 if self.movement.index == 4 else 1.0))
        self._light(surface, frame, colors)
        x, y = self._pressure(frame, *self._curves(frame))
        self._pigment(surface, frame, x, y, colors)
        for indices, tint in ((slice(None, 7), colors[1]), (slice(7, None), colors[0])):
            self.layer.fill(0)
            weight = self.strokes[: len(x)][indices]
            lines(surface, self.layer, x[indices], y[indices], weight=weight)
            surface.add(self.layer, tint, gain=0.65 if self.movement.index != 4 else 0.3)
        self._membrane(surface, frame, colors)
        self._notes(surface, frame, colors)
        self._grains(surface, frame, colors)
        self._detail(surface, frame, colors)
        self.picture[:] = surface.rgb
        self._held = True

    def _palette(self, frame):
        return self.colors


class _Kindness(_Water):
    """A suspended branching plume with a missing eighth in its current."""

    def _curves(self, frame):
        x, y = super()._curves(frame)
        arc = self._arc(frame)
        # The seven-eighth passage follows picture time, not audio-time sections.
        if 114.285714 <= frame.tau < 154.285714:
            bar = (frame.tau - 114.285714) / 2.5
            hiccup = math.sin(2 * math.pi * bar) ** 9 * 0.016 * frame.energy
            y += hiccup * np.sin(self.s * math.pi)
        y += arc * 0.28 * self.s
        return x, y


class _Question(_Water):
    """A left-hand bass question answered by pigment and a turning shoal."""

    def _curves(self, frame):
        x, y = super()._curves(frame)
        turn = math.sin(frame.tau * 0.15)
        x = x * 0.65 + 0.35
        y += self.s * 0.23 * turn + self._arc(frame) * 0.25
        return x, y

    def _detail(self, surface, frame, colors):
        d = self.dust[:42]
        turn = math.sin(frame.tau * 0.15)
        if frame.energy > 0 and frame.score is not None:
            turn += 0.6 * (
                frame.score.level("piano", frame.t, decay_s=1.2)
                - frame.score.level("bass", frame.t, decay_s=1.2)
            )
        angle = 0.5 * turn
        x = (d[:, 0] - 0.5) * 1.5 - 0.2
        y = (d[:, 1] - 0.5) * 0.5 + 0.06
        q = np.array([0, 1], dtype=np.float32)[None, :]
        self.layer.fill(0)
        lines(
            surface,
            self.layer,
            x[:, None] + q * 0.035 * math.cos(angle),
            y[:, None] + q * 0.035 * math.sin(angle),
            weight=0.065,
        )
        surface.add(self.layer, colors[2], gain=0.28)


class _Current(_Water):
    """Long open streaklines cross a boundless lateral column."""

    def _current(self, x, y, tau):
        vx, vy = super()._current(x, y, tau)
        return vx + 0.075, vy * 0.5

    def _curves(self, frame):
        s, d = self.s, self.depth
        x = np.broadcast_to((s - 0.5) * 5.2, (14, 100)).copy()
        arc = self._arc(frame)
        y = (d - 0.5) * (1.05 + arc * 0.4) - 0.12
        y = y + np.sin(s * 7 - frame.tau * 0.12 + self.phase) * 0.055
        y += np.sin(s * 3 + frame.tau * 0.04) * (0.18 - arc * 0.09)
        return x, y


class _Downbeat(_Water):
    """Opposing vertical currents negotiate across a sinuous shear seam."""

    def _current(self, x, y, tau):
        vx, vy = super()._current(x, y, tau)
        seam = 0.12 + np.sin(y * 4 + tau * 0.05) * 0.08
        return vx * 0.6, vy + np.tanh((x - seam) * 8) * 0.06

    def _curves(self, frame):
        s, d = self.s, self.depth
        side = np.where(d < 0.5, -1, 1)
        y = np.broadcast_to((s - 0.5) * 1.8, (14, 100)).copy()
        y *= side
        x = 0.16 + (d - 0.5) * (1 + self._arc(frame) * 0.55)
        x = x + np.sin(y * 4 + frame.tau * 0.075 + self.phase * 0.15) * 0.13
        return x, y

    def _detail(self, surface, frame, colors):
        # A dark sinking drop is geometric pressure rather than a bright beat.
        beat = frame.tau * (self.movement.bpm or 96) / 240
        age = beat % 1
        y = -0.8 + age * 2.2
        x = 0.13 + 0.06 * math.sin(frame.tau * 0.06)
        shadow = np.exp(-(((surface.u - x) / 0.065) ** 2) - ((surface.v - y) / 0.11) ** 2)
        surface.cover(shadow * 0.6, self.floor * 0.3)


class _Air(_Water):
    """Two small notes leave a thin unfinished contour and rising bubbles."""

    def _curves(self, frame):
        x, y = super()._curves(frame)
        # The family material remains, but only two hairline strands survive.
        x = x[:2] * 0.36 + 0.18
        y = y[:2] * 0.24 - 0.04
        return x, y

    def _detail(self, surface, frame, colors):
        arc = self._arc(frame)
        x = np.array([-0.12, 0.24 + arc * 0.16], dtype=np.float32)
        y = np.array([-0.14, -0.22 + 0.07 * math.sin(frame.tau * 0.04)], dtype=np.float32)
        self.layer.fill(0)
        lines(surface, self.layer, x, y, weight=0.08)
        points(surface, self.layer, x, y, weight=0.55)
        surface.add(self.layer, colors[0], gain=0.34)
        # Bubbles inherit phrase positions; their rise is entirely picture-clock.
        self.layer.fill(0)
        for i in range(6):
            age = (frame.tau * 0.018 + i / 6) % 1
            cx = float(x[i % 2]) + 0.035 * math.sin(age * 5 + i)
            cy = float(y[i % 2]) - age * 0.85
            bubble = ring(surface, cx, cy, 0.009 + age * 0.009, 0.003, soft=0.005)
            np.add(self.layer, bubble * (0.022 * (1 - age)), out=self.layer)
        surface.add(self.layer, colors[2])
        self._motif(surface, frame, colors)

    def _motif(self, surface, frame, colors):
        if frame.energy <= 0 or frame.score is None:
            return
        self.layer.fill(0)
        painted = False
        for motif in frame.score.motifs:
            if not isinstance(motif, dict):
                continue
            notes = np.asarray(motif.get("notes", ()), dtype=np.float32)
            if notes.ndim != 2 or notes.shape[1] != 2 or len(notes) < 2:
                continue
            visible = notes[(notes[:, 0] <= frame.t) & (notes[:, 0] > frame.t - 9)]
            if len(visible) < 2:
                continue
            x = (visible[:, 0] - notes[0, 0]) * 0.025 - 0.15
            y = (60 - visible[:, 1]) * 0.014 - 0.18
            lines(surface, self.layer, x, y, weight=0.045 * frame.energy)
            painted = True
        if painted:
            surface.add(self.layer, colors[0], gain=0.2)


class _Major(_Kindness):
    """The first water remembered, gradually admitting amber from above."""

    def __init__(self, movement):
        super().__init__(movement)
        self.pale = mix(self.colors, linear("#9caeb3"), 0.18)
        self.amber = np.asarray(
            [linear(c) for c in ("#f5deae", "#8daed9", "#e3bb79", "#263c4b")],
            dtype=np.float32,
        )

    def _palette(self, frame):
        marker = 144.48697
        if frame.energy > 0 and frame.score is not None:
            marker = float(frame.score.markers.get("major_onset", marker))
        # Picture time prevents harmonic state from moving during still/reduced.
        warm = float(smoothstep(marker, marker + 11, frame.tau))
        return mix(self.pale, self.amber, warm)

    def _light(self, surface, frame, colors):
        super()._light(surface, frame, colors)
        warm = float(smoothstep(144.48697, 155.48697, frame.tau))
        shaft = np.exp(-(((surface.u + 0.25 * surface.v - 0.45) / (0.12 + warm * 0.28)) ** 2))
        shaft *= np.exp(-(surface.v + 1) * 1.3) * warm * 0.028
        surface.add(shaft, colors[0])

    def _detail(self, surface, frame, colors):
        _Air._motif(self, surface, frame, colors)
        if frame.energy <= 0 or frame.score is None:
            return
        # Old contours survive as a dim palimpsest, separate from live notes.
        self.layer.fill(0)
        painted = False
        for index, motif in enumerate(frame.score.motifs[:8]):
            if not isinstance(motif, dict):
                continue
            notes = np.asarray(motif.get("notes", ()), dtype=np.float32)
            if notes.ndim != 2 or notes.shape[1] != 2 or len(notes) < 2:
                continue
            reveal = float(smoothstep(notes[-1, 0], notes[-1, 0] + 8, frame.tau))
            x = (notes[:, 0] - notes[0, 0]) * 0.025 - 0.65 + index * 0.12
            y = (60 - notes[:, 1]) * 0.014 + 0.12 + index * 0.025
            lines(surface, self.layer, x, y, weight=0.022 * frame.energy * reveal)
            painted = True
        if painted:
            surface.add(self.layer, colors[1], gain=0.18)


def build_scene(movement: Movement) -> Scene:
    """Construct the movement's distinct seeded water painter.

    Args:
        movement: Aquatic metadata with a zero-based index in 0..5.

    Returns:
        A fresh scene; no rendering state is shared between movements.

    Raises:
        ValueError: The movement index does not name one of the six compositions.
    """
    classes = (_Kindness, _Question, _Current, _Downbeat, _Air, _Major)
    if not 0 <= movement.index < len(classes):
        raise ValueError("aquatic movement index must be in 0..5")
    return classes[movement.index](movement)

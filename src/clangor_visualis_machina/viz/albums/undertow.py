"""Paint Drowning Collective's The Shape That Stays as pressure, currents and black gaps.

The native Stage supplies audio time for score queries and independently scaled picture
seconds for drift and the opening's arc, including reduced-motion pacing. Six seeded
compositions share smoothing and exact held pictures, not an A-01 painter or raster cover.
Signal envelopes deform geometry, never gate illumination.
"""

from __future__ import annotations

import math

import numpy as np

from ..color import linear
from ..draw import ease_in_out, lines, points
from ..scene import Frame, Movement, Scene
from ..surface import Surface

_DEFAULT_PALETTE = ("#07151b", "#337778", "#d4ccb0")
_RIGHT, _LEFT, _BASS, _KICK, _SNARE, _HAT, _MEMORY = range(7)
_SMOOTH_S = 0.8


class _Undertow(Scene):
    """Own one movement's stable material, smoothed deformations and held pixels."""

    def __init__(self, movement: Movement):
        super().__init__(movement)
        palette = movement.palette or _DEFAULT_PALETTE
        self.deep, self.mid, self.chalk = (linear(c) for c in palette[:3])
        rng = np.random.default_rng(movement.seed)
        self.phase = rng.uniform(-math.pi, math.pi, 12).astype(np.float32)
        self.q = np.linspace(-1, 1, 96, dtype=np.float32)
        self.theta = np.linspace(0, 2 * math.pi, 112, dtype=np.float32)
        self._mod = np.zeros(7, dtype=np.float32)
        self._target = np.zeros_like(self._mod)
        self._shape = None
        self._held = None

    def resize(self, surface: Surface) -> None:
        """Rebuild material and scratch buffers for a canvas without advancing time.

        Args:
            surface: Target with dimensions in terminal sub-pixels.
        Side effects: Invalidates held pixels; retains the musical smoothing state.
        """
        self._shape = surface.rgb.shape
        self._held = None
        self._layer = surface.layer()
        self._detail = surface.layer()
        self._x = self.q * surface.half_w
        self._u = surface.u / surface.half_w
        self._grain = (
            0.85
            + 0.07 * np.sin(self._u * 63 + np.sin(surface.v * 21) + self.phase[0])
            + 0.045 * np.sin(surface.v * 91 - self._u * 17 + self.phase[1])
        ).astype(np.float32)
        self._background = np.empty_like(surface.rgb)
        depth = (surface.v + 1) * 0.5
        for channel in range(3):
            self._background[..., channel] = self.deep[channel] * (1.1 - 0.55 * depth) * self._grain
        self._vignette = np.clip(1.08 - 0.20 * (self._u**2 + surface.v**2), 0.45, 1)

    def seek(self) -> None:
        """Discard held pixels and musical deformation after a discontinuous seek."""
        self._held = None
        self._mod.fill(0)

    def _signals(self, frame: Frame) -> None:
        target = self._target
        target.fill(0)
        if frame.energy:
            level, score, t = frame.levels, frame.score, frame.t
            target[:] = (
                level.treble * 0.25,
                level.mid * 0.25,
                level.slow_bass,
                level.kick,
                level.snare,
                level.hat,
                0,
            )
            if score is not None:
                # Scored hands stay independent even when cymbals dominate the mix.
                # Broad audio bands are only a score-less fallback for these two routes.
                target[_RIGHT] = score.level("piano", t, voice="right")
                target[_LEFT] = score.level("piano", t, voice="left")
                target[_BASS] = max(target[_BASS], score.level("bass", t, decay_s=0.8))
                target[_KICK] = max(target[_KICK], score.level("drums", t, kind="kick"))
                target[_SNARE] = max(target[_SNARE], score.level("drums", t, kind="snare"))
                target[_HAT] = max(target[_HAT], score.level("drums", t, kind="hat"))
                target[_MEMORY] = score.level("memory", t, decay_s=2.5)
        self._mod += (target - self._mod) * -math.expm1(-max(frame.dt, 0) / _SMOOTH_S)
        if frame.energy == 0:
            self._mod.fill(0)

    def _stroke(self, surface, x, y, color, weight=0.8):
        self._layer.fill(0)
        lines(surface, self._layer, x, y, weight)
        surface.add(self._layer, color)

    def _paint_body(self, surface, coverage, gain=0.85):
        surface.add(coverage * self._grain, self.mid, gain)

    def _cut(self, surface, coverage):
        # A void removes existing pigment rather than drawing an additive dark color.
        surface.rgb *= (1 - 0.985 * np.clip(coverage, 0, 1))[..., None]

    def _currents(self, surface, frame, *, vertical=False):
        """Paint the two independently scored currents with faint mineral echoes."""
        for hand, offset, color in (
            (_RIGHT, -0.22, self.chalk * 0.65),
            (_LEFT, 0.23, self.mid * 1.7),
        ):
            curve = offset + (0.035 + 0.11 * self._mod[hand]) * np.sin(
                self.q * 3.5 + frame.tau * 0.035 + self.phase[hand]
            )
            self._layer.fill(0)
            for echo, weight in ((0.0, 0.85), (0.034, 0.24)):
                if vertical:
                    x, y = (curve + echo) * surface.half_w, self.q
                else:
                    x, y = self._x, curve + echo
                lines(surface, self._layer, x, y, weight)
            surface.add(self._layer, color)

    def _marks(self, surface, frame):
        if not frame.energy or frame.score is None:
            return
        notes = frame.score.recent("piano", frame.t, 2.2)
        for voice, row, color in (("right", -0.22, self.chalk), ("left", 0.23, self.mid * 1.8)):
            if voice not in frame.score.voices:
                continue
            selected = notes[notes["voice"] == frame.score.voices.index(voice)][-20:]
            if not len(selected):
                continue
            age = frame.t - selected["onset"]
            x = (selected["midi"] * 0.137 + selected["onset"] * 0.071) % 1 * 2 - 1
            x *= surface.half_w * 0.8
            y = row + 0.045 * np.sin(selected["midi"] * 0.3 + age)
            self._detail.fill(0)
            # Small score annotations, not a canvas-wide energy or brightness control.
            points(surface, self._detail, x, y, 0.055 * np.sin(np.pi * age / 2.2))
            surface.add(self._detail, color)

    def _paint(self, surface, frame, arc):
        raise NotImplementedError

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint a complete linear-light picture or replay exact held pixels.

        Args:
            surface: Mutable output canvas, rebuilt if its sub-pixel shape changed.
            frame: Audio time/score and picture tau/dt in seconds. Zero energy ignores
                audio, score and section; zero dt holds the previous complete picture.
        Side effects: Updates smoothing and the private held-image cache only.
        """
        if self._shape != surface.rgb.shape:
            self.resize(surface)
        if frame.dt == 0 and self._held is not None:
            surface.rgb[:] = self._held
            return
        surface.rgb[:] = self._background
        self._signals(frame)
        arc = float(ease_in_out(np.clip(frame.tau / max(self.movement.duration_s, 1), 0, 1)))
        self._paint(surface, frame, arc)
        self._marks(surface, frame)
        surface.rgb *= self._vignette[..., None]
        if self._held is None:
            self._held = np.empty_like(surface.rgb)
        self._held[:] = surface.rgb


class _Seam(_Undertow):
    """Let two lyrical routes pass a heavy, irregular split pressure body."""

    def _paint(self, surface, frame, arc):
        u, v = self._u, surface.v
        drift = 0.035 * math.sin(frame.tau * 0.04 + self.phase[2])
        for side, height in ((-1, 0.84), (1, 0.69)):
            radius = np.hypot((u - side * (0.48 + drift)) / 0.64, (v + 0.05) / height)
            rough = 0.035 * np.sin(v * 17 + self.phase[3]) + 0.02 * np.sin(u * 23 + v * 9)
            body = np.clip((1 + 0.08 * self._mod[_BASS] + rough - radius) * 18, 0, 1)
            self._paint_body(surface, body)
        seam = 0.045 * np.sin(v * 5 + frame.tau * 0.035)
        width = 0.025 + 0.018 * self._mod[_KICK]
        self._cut(surface, np.clip((width - np.abs(u - seam)) * 90, 0, 1))
        self._currents(surface, frame)
        fracture_width = 0.012 + 0.006 * self._mod[_SNARE]
        fracture = np.exp(-(((v - 0.48 - 0.06 * np.sin(u * 7)) / fracture_width) ** 2))
        self._cut(surface, fracture * np.clip(u + 0.9, 0, 1) * 0.9)


class _Shoal(_Undertow):
    """Give the bass off-center hollow chambers and the hands separate tendrils."""

    def _paint(self, surface, frame, arc):
        for i, (cx, cy, rx, ry) in enumerate(
            (
                (-0.55, -0.4, 0.37, 0.28),
                (0.38, -0.18, 0.4, 0.36),
                (-0.3, 0.4, 0.31, 0.25),
                (0.63, 0.58, 0.24, 0.22),
            )
        ):
            pressure = 0.035 * self._mod[_BASS] * math.sin(i + self.phase[2])
            cx += 0.018 * math.sin(frame.tau * 0.04 + i)
            r = np.hypot((self._u - cx) / (rx + pressure), (surface.v - cy) / ry)
            r += 0.025 * np.sin(surface.v * 21 + self._u * 13 + self.phase[i])
            wall = np.clip((1 - np.abs(r - 0.88)) * 7 - 5.6, 0, 1)
            self._paint_body(surface, wall, 0.8)
            inner = 0.86 - 0.10 * self._mod[_BASS]
            angle = self.theta
            self._stroke(
                surface,
                (cx + rx * inner * np.cos(angle)) * surface.half_w,
                cy + ry * inner * np.sin(angle),
                self.chalk * 0.24,
                0.6,
            )
        for hand, sign in ((_RIGHT, -1), (_LEFT, 1)):
            x = self._x * 0.65
            y = sign * 0.16 + 0.3 * np.sin(self.q * 2.4 + self.phase[hand])
            y += 0.10 * self._mod[hand] * np.cos(self.q * 5 - frame.tau * 0.04)
            self._stroke(surface, x, y, self.chalk * 0.45 if sign < 0 else self.mid * 1.6, 0.7)


class _Shelf(_Undertow):
    """Carry five long lateral strata through gaps rather than a repeating staff."""

    def _paint(self, surface, frame, arc):
        u, v = self._u, surface.v
        for i, level in enumerate((-0.78, -0.41, -0.03, 0.34, 0.76)):
            wave = 0.055 * np.sin(u * 2.4 + i * 0.8 - frame.tau * 0.025)
            wave += 0.015 * np.sin(u * 15 + self.phase[i])
            width = 0.035 + 0.025 * self._mod[_BASS] + 0.009 * i
            coverage = np.clip((width - np.abs(v - level - wave)) * 65, 0, 1)
            self._paint_body(surface, coverage, 0.55 + i * 0.07)
        for i, position in enumerate((-0.82, -0.42, 0.02, 0.4, 0.79)):
            x = position + 0.025 * math.sin(frame.tau * 0.035 + i)
            gap = np.clip((0.018 - np.abs(u - x - 0.025 * np.sin(v * 3 + i))) * 100, 0, 1)
            self._cut(surface, gap)
        self._currents(surface, frame)


class _Fault(_Undertow):
    """Run opposed vertical currents through one dark, displaced shear."""

    def _paint(self, surface, frame, arc):
        u, v = self._u, surface.v
        drift = 0.025 * math.sin(frame.tau * 0.03 + self.phase[4])
        for side in (-1, 1):
            r = np.hypot((u - side * 0.69 - drift) / 0.47, (v + side * 0.16) / 1.15)
            edge = 0.045 * np.sin(v * 11 + self.phase[side + 1])
            self._paint_body(surface, np.clip((1 + edge + 0.08 * self._mod[_BASS] - r) * 18, 0, 1))
        self._currents(surface, frame, vertical=True)
        shear = 0.08 * np.sin(u * 3.5 + frame.tau * 0.025)
        width = 0.025 + 0.025 * self._mod[_KICK] + 0.012 * self._mod[_SNARE]
        self._cut(surface, np.clip((width - np.abs(v - shear)) * 80, 0, 1))
        # Echo a fault with one fixed-palette mineral edge, not an onset flash.
        self._stroke(
            surface,
            self._x,
            0.08 * np.sin(self.q * 3.5 + frame.tau * 0.025) + width,
            self.mid * 0.7,
            0.6,
        )


class _Hollow(_Undertow):
    """Protect a large empty center inside an incomplete, low curled basin."""

    def _paint(self, surface, frame, arc):
        u, v = self._u, surface.v
        cx = 0.24 + 0.025 * math.sin(frame.tau * 0.025)
        radius = np.hypot((u - cx) * 0.8, (v - 0.20) * 0.9)
        rim = 0.50 + 0.035 * self._mod[_BASS]
        wall = np.clip((0.055 - np.abs(radius - rim)) * 55, 0, 1)
        opening = np.clip((v + 0.02 + 0.05 * np.sin(u * 5)) * 12, 0, 1)
        self._paint_body(surface, wall * opening, 0.85)
        angle = np.linspace(0.05, math.pi - 0.08, 80, dtype=np.float32)
        self._stroke(
            surface,
            (cx + 0.54 * np.cos(angle)) * surface.half_w,
            0.2 + 0.44 * np.sin(angle),
            self.chalk * 0.25,
            0.65,
        )
        for hand, sign in ((_RIGHT, -1), (_LEFT, 1)):
            x = self._x * 0.55
            y = -0.18 + sign * 0.08 + 0.14 * np.sin(self.q * 1.7 + self.phase[hand])
            y += 0.1 * self._mod[hand] * np.sin(self.q * 3 - frame.tau * 0.025)
            self._stroke(surface, x, y, self.chalk * 0.55 if sign < 0 else self.mid * 1.8, 0.75)


class _Estuary(_Undertow):
    """Braid remembered routes around a gradually opening amber negative space."""

    def _paint(self, surface, frame, arc):
        u, v = self._u, surface.v
        boundary = 0.36 + 0.09 * np.sin(u * 3 + frame.tau * 0.025 + self.phase[1])
        self._paint_body(surface, np.clip((v - boundary) * 16, 0, 1), 0.6)
        radius = np.hypot((u - 0.46) * 1.2, v + 0.47)
        opening = np.clip((0.13 + 0.23 * arc - radius) * 14, 0, 1)
        surface.add(opening * self._grain, self.chalk, 0.16)
        for i, hand in enumerate((_RIGHT, _LEFT, _BASS, _MEMORY, _HAT)):
            y = -0.55 + i * 0.24 + 0.085 * np.sin(self.q * 4 + i * 0.9 - frame.tau * 0.035)
            y += 0.055 * self._mod[hand] * np.sin(self.q * 8 + self.phase[i])
            self._stroke(
                surface, self._x, y, self.chalk * 0.48 if i in (0, 3) else self.mid * 1.6, 0.85
            )
        seam = 0.04 * np.sin(v * 6 + frame.tau * 0.02)
        self._cut(surface, np.clip((0.014 - np.abs(u - seam)) * 100, 0, 1) * np.clip(v + 0.2, 0, 1))


_SCENES = {
    "seam": _Seam,
    "shoal": _Shoal,
    "shelf": _Shelf,
    "fault": _Fault,
    "hollow": _Hollow,
    "estuary": _Estuary,
}


def build_scene(movement: Movement) -> Scene:
    """Construct a seeded painter for one of The Shape That Stays' six movements.

    Args:
        movement: Immutable metadata with the scene key, palette and stable seed.

    Returns:
        A new scene owning its material, smoothing and exact held-image cache.

    Raises:
        ValueError: The movement names no known undertow scene.
    """
    try:
        painter = _SCENES[movement.scene]
    except KeyError as error:
        raise ValueError(f"unknown undertow scene: {movement.scene}") from error
    return painter(movement)

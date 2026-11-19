"""Paint The Forest Has a Pocket's six groove-locked worlds for the mosaic Stage.

Each chapter draws its own picture of the album's pocket: a root lattice, hinged rain,
a bent spiral, elbowed canopy, five fern spaces and a braided river. Geometry follows
picture time and smoothed musical envelopes; score notes place only small marks.
The painter is independent of the A-01 forest visuals, which keep their own family.
Only a zero picture step, from still motion or a held clock, freezes the picture; zero
energy and silence clear audio-driven terms while geometry continues with picture time.
No state is global.
"""

from __future__ import annotations

import math

import numpy as np

from ..color import linear
from ..draw import ease_in_out, lines, points, segments
from ..scene import Frame, Movement, Scene
from ..surface import Surface

_FLOOR = linear("#060d0b")
_DEFAULT_PALETTE = ("#091c18", "#497453", "#d0b575")
# Envelopes follow a first-order 0.65 s time constant in picture time;
# light is never gated on each beat.
_SMOOTH_S = 0.65
_MARK_WINDOW_S = 2.2
_BASS, _GUITAR, _HARP, _KICK, _SNARE, _HAT, _SECTION, _GUST = range(8)
_CHANNELS = 8


class _Pocket(Scene):
    """Share groove-locked smoothing, held pictures and note marks across chapters.

    Subclasses paint geometry in `_paint` and place note marks in `_place`. `MARKS`
    lists the score parts whose recent notes receive a small point each frame.
    """

    MARKS: tuple[str, ...] = ("harp", "guitar")

    def __init__(self, movement: Movement):
        super().__init__(movement)
        palette = movement.palette or _DEFAULT_PALETTE
        self.deep, self.mid, self.lit = (linear(c) for c in palette[:3])
        self.bpm = movement.bpm or 96.0
        rng = np.random.default_rng(movement.seed)
        self.jitter = rng.uniform(-1, 1, (6, 17, 2)).astype(np.float32)
        self.drops = rng.uniform(0, 1, (120, 3)).astype(np.float32)
        self.spores = rng.uniform(0, 1, (80, 3)).astype(np.float32)
        self.bend = rng.uniform(0, 1, (13, 5)).astype(np.float32)
        self.q = np.linspace(0, 1, 64, dtype=np.float32)
        self._shape = None
        self._held = None
        self._mod = np.zeros(_CHANNELS, dtype=np.float32)

    def resize(self, surface: Surface) -> None:
        """Rebuild the soil-to-sky backdrop, vignette and scratch layers for a canvas.

        Args:
            surface: Target canvas; musical and picture clocks are not advanced.
        """
        self._shape = surface.rgb.shape
        self._half_w = surface.half_w
        self._layer = surface.layer()
        self._detail = surface.layer()
        self._held = None
        y = (surface.v + 1) * 0.5
        self._background = np.empty_like(surface.rgb)
        for channel in range(3):
            self._background[..., channel] = np.interp(
                y,
                (0, 0.6, 1),
                (self.deep[channel] * 0.5, self.mid[channel] * 0.25, _FLOOR[channel]),
            )
        self._vignette = np.clip(
            1.06 - 0.3 * (surface.v**2 + (surface.u / surface.half_w) ** 2), 0.2, 1
        ).astype(np.float32)

    def seek(self) -> None:
        """Drop held pixels and smoothed deformation after a discontinuous clock jump."""
        self._held = None
        self._mod.fill(0)

    def _progress(self, frame: Frame) -> float:
        """Return the movement's eased picture progress, clamped to 0..1."""
        return float(ease_in_out(frame.tau / max(self.movement.duration_s, 1)))

    def _signals(self, frame: Frame) -> None:
        """Smooth this picture's musical targets into `self._mod`; zero energy clears them.

        Levels and score velocities arrive already scaled by energy from Stage, so this
        method only selects the channels and integrates them over picture time.
        """
        target = np.zeros(_CHANNELS, dtype=np.float32)
        if frame.energy:
            level, score, t = frame.levels, frame.score, frame.t
            target[_BASS] = level.slow_bass
            target[_GUITAR] = level.mid
            target[_HARP] = level.treble
            target[_KICK] = level.kick
            target[_SNARE] = level.snare
            target[_HAT] = level.hat
            if score is not None:
                target[_BASS] = max(target[_BASS], score.level("bass", t, decay_s=0.8))
                target[_GUITAR] = max(target[_GUITAR], score.level("guitar", t, decay_s=0.5))
                target[_HARP] = max(target[_HARP], score.level("harp", t, decay_s=1.2))
                target[_KICK] = max(
                    target[_KICK], score.level("drums", t, decay_s=0.15, kind="kick")
                )
                target[_SNARE] = max(
                    target[_SNARE], score.level("drums", t, decay_s=0.15, kind="snare")
                )
                target[_HAT] = max(target[_HAT], score.level("drums", t, decay_s=0.1, kind="hat"))
                # Rain noise gives a short gust cue; moving rain continues with picture time.
                target[_GUST] = score.level("rain", t, decay_s=2.5)
            if frame.section is not None:
                target[_SECTION] = frame.section.intensity
        blend = -math.expm1(-max(frame.dt, 0) / _SMOOTH_S)
        self._mod += (target - self._mod) * blend
        if frame.energy == 0:
            self._mod.fill(0)

    def _stroke(self, surface, x, y, color, weight=1.0):
        """Add one scalar polyline layer tinted with `color`; weights follow `lines`."""
        self._layer.fill(0)
        lines(surface, self._layer, x, y, weight)
        surface.add(self._layer, color)

    def _marks(self, surface: Surface, frame: Frame) -> None:
        """Place a point for each recent note of `MARKS`; silent or zero-energy frames skip."""
        if not frame.energy or frame.score is None:
            return
        for part in self.MARKS:
            notes = frame.score.recent(part, frame.t, _MARK_WINDOW_S)[-24:]
            if not len(notes):
                continue
            age = frame.t - notes["onset"]
            x, y = self._place(part, notes, age, frame)
            self._detail.fill(0)
            points(
                surface,
                self._detail,
                x,
                y,
                notes["vel"] * np.sin(np.pi * age / _MARK_WINDOW_S) * 0.6,
            )
            surface.add(self._detail, self.lit, 0.8)

    def _paint(self, surface: Surface, frame: Frame, arc: float) -> None:
        """Paint this chapter's geometry; implemented by each painter."""
        raise NotImplementedError

    def _place(self, part, notes, age, frame: Frame):
        """Return scene coordinates of the marks for `notes`; implemented by each painter."""
        raise NotImplementedError

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint one complete chapter, holding exactly when picture dt is zero.

        Args:
            surface: Linear-light output mutated in place.
            frame: Musical instant; tau and dt are picture seconds. Zero energy
                suppresses score, section, integrator and audio-clock influence.
        """
        if self._shape != surface.rgb.shape:
            self.resize(surface)
        if frame.dt == 0 and self._held is not None:
            surface.rgb[:] = self._held
            return
        surface.rgb[:] = self._background
        self._signals(frame)
        self._paint(surface, frame, self._progress(frame))
        self._marks(surface, frame)
        surface.rgb *= self._vignette[..., None]
        if self._held is None:
            self._held = np.empty_like(surface.rgb)
        self._held[:] = surface.rgb


class _Root(_Pocket):
    """Grow a rectilinear root lattice whose nodes are where the bass takes root."""

    MARKS = ("bass", "harp")

    def __init__(self, movement: Movement):
        super().__init__(movement)
        self.cols = np.linspace(-0.95, 0.95, 17, dtype=np.float32)
        self.rows = np.linspace(-0.5, 0.95, 6, dtype=np.float32)

    def _lattice(self, frame: Frame):
        x = self.cols[None, :] * self._half_w + 0.012 * self.jitter[..., 0]
        y = self.rows[:, None] + 0.012 * self.jitter[..., 1]
        # The kick pushes the lattice in a slow wave; the quarter-note breath is geometry only.
        breath = math.sin(2 * math.pi * frame.tau * self.bpm / 60)
        push = self._mod[_KICK] * 0.03 + 0.004 * breath
        return x, y + push * np.sin(x * 3 - frame.tau * 0.4)

    def _paint(self, surface, frame, arc):
        x, y = self._lattice(frame)
        rows = np.arange(6, dtype=np.float32)
        reveal = ease_in_out(np.clip(arc * 1.4 - (5 - rows) * 0.12, 0, 1)).astype(np.float32)
        self._stroke(surface, x, y, self.mid, (0.4 + 0.9 * self._mod[_BASS]) * reveal)
        columns = np.arange(17, dtype=np.float32)
        falloff = np.abs(columns - 8) * 0.04
        center = ease_in_out(np.clip(arc * 1.5 - falloff, 0, 1)).astype(np.float32)
        weight = (0.3 + 0.7 * self._mod[_GUITAR]) * center
        self._stroke(surface, x.T, y.T, self.mid * 0.7, weight)
        self._detail.fill(0)
        points(surface, self._detail, x, y, (0.02 + 0.1 * self._mod[_BASS]) * reveal[:, None])
        surface.add(self._detail, self.lit, 0.6)

    def _place(self, part, notes, age, frame: Frame):
        x, y = self._lattice(frame)
        node = notes["midi"].astype(int) % 102
        rows, cols = node // 17, node % 17
        return x[rows, cols], y[rows, cols]


class _Rain(_Pocket):
    """Pass slanted rain through seven hinges whose knuckles flex with the snare."""

    MARKS = ("guitar", "harp")

    def __init__(self, movement: Movement):
        super().__init__(movement)
        self.hinges = np.linspace(-0.8, 0.8, 7, dtype=np.float32)
        self.knuckles = np.linspace(-1.05, 1.05, 22, dtype=np.float32)
        self.ripple = np.linspace(-1, 1, 256, dtype=np.float32)

    def _hinge_x(self, tau: float):
        sway = np.sin(tau * 0.9 + np.arange(7, dtype=np.float32) * 1.3)
        return (self.hinges * self._half_w + 0.03 * self._mod[_SNARE] * sway).astype(np.float32)

    def _paint(self, surface, frame, arc):
        tau = frame.tau
        hx = self._hinge_x(tau)
        index = np.arange(7, dtype=np.float32)
        bow = 0.012 * np.sin(self.knuckles[None, :] * 5 + tau * 0.4 + index[:, None])
        x = (hx[:, None] + bow).astype(np.float32)
        y = np.broadcast_to(self.knuckles, x.shape)
        reveal = ease_in_out(np.clip(arc * 1.3 - index * 0.06, 0, 1)).astype(np.float32)
        self._stroke(surface, x, y, self.mid * 0.9, (0.6 + 0.6 * self._mod[_GUITAR]) * reveal)
        self._detail.fill(0)
        points(
            surface,
            self._detail,
            x[:, ::3],
            y[:, ::3],
            (0.05 + 0.1 * self._mod[_SNARE]) * reveal[:, None],
        )
        surface.add(self._detail, self.lit, 0.5)
        slant = 0.22 + 0.25 * self._mod[_GUST]
        for depth in range(3):
            drops = self.drops[depth::3]
            speed = 0.12 + depth * 0.08
            length = (0.04 + depth * 0.035) * (0.8 + arc * 0.4)
            dx = (drops[:, 0] * 2 - 1) * self._half_w * 1.2
            dy = (drops[:, 1] * 2 + tau * speed) % 2.2 - 1.1
            self._layer.fill(0)
            segments(
                surface,
                self._layer,
                dx,
                dy,
                dx + slant * length,
                dy + length,
                0.2 + depth * 0.15,
            )
            surface.add(self._layer, self.lit if depth == 2 else self.mid, 0.5)
        xs = self.ripple * self._half_w
        for offset in (0.0, 0.07):
            ys = 0.7 + offset + 0.02 * self._mod[_HAT] * np.sin(xs * 16 - tau)
            self._stroke(surface, xs, ys, self.mid * 0.4, 0.6)

    def _place(self, part, notes, age, frame: Frame):
        midi = notes["midi"].astype(int)
        return self._hinge_x(frame.tau)[midi % 7], self.knuckles[(midi * 3) % 22]


class _Spiral(_Pocket):
    """Unwind a three-arm bark spiral whose arms bend with the guitar's weight."""

    MARKS = ("guitar", "harp")

    def __init__(self, movement: Movement):
        super().__init__(movement)
        self.path = np.linspace(0, 1, 160, dtype=np.float32)[None, :]
        self.arms = (np.arange(3, dtype=np.float32) * (2 * np.pi / 3))[:, None]

    def _arms_xy(self, frame: Frame, arc: float):
        theta = self.path * (4 * np.pi) * (0.35 + 0.65 * arc)
        r = 0.03 * np.exp(0.28 * theta)
        angle = theta + self.arms + frame.tau * 0.05
        angle = angle + 0.35 * self._mod[_GUITAR] * np.sin(r * 5 - frame.tau * 0.25)
        cx, cy = 0.25 * self._half_w, -0.05
        return cx + r * np.cos(angle), cy + 0.9 * r * np.sin(angle), r

    def _paint(self, surface, frame, arc):
        x, y, r = self._arms_xy(frame, arc)
        # Bark reaches about 1.01 scene units on the last turn, so width clamps it at one.
        width = np.broadcast_to(0.5 + np.minimum(r, 1.0), x.shape)
        self._stroke(surface, x, y, self.mid * 0.8, width)
        self._stroke(surface, x + 0.012, y, self.lit * 0.25, 0.6)
        glow = np.exp(-((surface.u - 0.25 * self._half_w) ** 2 + (surface.v + 0.05) ** 2) / 0.05)
        surface.add(glow, self.lit, 0.06 + 0.05 * self._mod[_SECTION])

    def _place(self, part, notes, age, frame: Frame):
        x, y, _ = self._arms_xy(frame, self._progress(frame))
        midi = notes["midi"].astype(int)
        arm, step = midi % 3, (midi * 7) % 160
        return x[arm, step], y[arm, step]


class _Canopy(_Pocket):
    """Hang branches from the top edge; each turns at right angles on a shared grid."""

    MARKS = ("harp", "bass")

    def __init__(self, movement: Movement):
        super().__init__(movement)
        self.hang = np.linspace(-0.95, 0.95, 13, dtype=np.float32)

    def _branches(self, frame: Frame, arc: float):
        """Return polyline vertices (13, 9) and elbow points (13, 4) for every branch."""
        reach = (self.bend[:, :4] * 2 - 1) * 0.2
        xk = np.concatenate((np.zeros((13, 1), np.float32), np.cumsum(reach, axis=1)), axis=1)
        xk = self.hang[:, None] * self._half_w + xk
        stagger = np.arange(13, dtype=np.float32)[:, None] * 0.04
        grow = ease_in_out(np.clip(arc * 1.5 - stagger, 0, 1))
        segment = 0.3 + 0.2 * self.bend[:, 4:5]
        yk = -1.1 + np.arange(5, dtype=np.float32)[None, :] * segment * grow
        x = xk[:, [0, 0, 1, 1, 2, 2, 3, 3, 4]]
        y = yk[:, [0, 1, 1, 2, 2, 3, 3, 4, 4]]
        return x.astype(np.float32), y.astype(np.float32), xk[:, 1:], yk[:, 1:]

    def _paint(self, surface, frame, arc):
        x, y, ex, ey = self._branches(frame, arc)
        weight = (0.8 + 0.6 * self._mod[_HARP]) * (1 - 0.3 * np.abs(self.hang))
        self._stroke(surface, x, y, self.mid * 0.7, weight)
        self._stroke(surface, x + 0.01, y, self.lit * 0.3, weight * 0.5)
        self._detail.fill(0)
        points(surface, self._detail, ex, ey, 0.04 + 0.12 * self._mod[_HARP])
        surface.add(self._detail, self.lit, 0.7)
        cx, cy = -0.3 * self._half_w, -0.25 - 0.1 * arc
        radius = np.hypot(surface.u - cx, surface.v - cy)
        breath = 0.02 * math.sin(2 * math.pi * frame.tau * self.bpm / 120)
        gap = np.exp(-(((radius - 0.42 - breath) / 0.1) ** 2))
        surface.add(gap, self.lit, 0.07)

    def _place(self, part, notes, age, frame: Frame):
        _, _, ex, ey = self._branches(frame, self._progress(frame))
        midi = notes["midi"].astype(int)
        branch, elbow = midi % 13, (midi // 13) % 4
        return ex[branch, elbow], ey[branch, elbow]


class _Spores(_Pocket):
    """Grow five fern spaces that take turns swaying; spores climb from every space."""

    MARKS = ("harp", "guitar")

    def _space_xy(self, tau: float):
        sx = np.linspace(-0.8, 0.8, 5, dtype=np.float32) * self._half_w
        base = (0.62 + 0.04 * np.sin(sx * 1.5 + tau * 0.1)).astype(np.float32)
        return sx, base

    def _paint(self, surface, frame, arc):
        tau = frame.tau
        sx, base = self._space_xy(tau)
        # Each space sways on its own beat of a five-beat cycle; this is geometry, not light.
        turn = np.sin(2 * np.pi * (tau * self.bpm / 60 - np.arange(5)) / 5).astype(np.float32)
        height = (0.14 + 0.32 * arc) * (1 + 0.08 * turn) + 0.04 * self._mod[_HARP]
        q = np.linspace(0.15, 1.0, 7, dtype=np.float32)[None, :]
        stem_x = np.broadcast_to(sx[:, None], (5, 7))
        stem_y = base[:, None] - height[:, None] * q
        self._stroke(surface, stem_x, stem_y, self.mid * 0.9, 0.9)
        for side in (-1, 1):
            reach = 0.12 * np.sin(q * np.pi) * (0.6 + 0.4 * arc)
            self._layer.fill(0)
            segments(
                surface,
                self._layer,
                stem_x,
                stem_y,
                stem_x + side * reach,
                stem_y - reach * 0.6,
                0.6,
            )
            surface.add(self._layer, self.mid, 0.7)
        space = np.minimum((self.spores[:, 2] * 5).astype(int), 4)
        rise = (self.spores[:, 1] * 1.6 + tau * (0.03 + 0.02 * self.spores[:, 0])) % 1.6
        x = sx[space] + np.sin(tau * 0.1 + self.spores[:, 0] * 6) * 0.12
        y = base[space] - 0.15 - rise
        self._detail.fill(0)
        points(surface, self._detail, x, y, 0.12 + 0.2 * self.spores[:, 0])
        surface.add(self._detail, self.lit, 0.6)

    def _place(self, part, notes, age, frame: Frame):
        sx, base = self._space_xy(frame.tau)
        space = notes["midi"].astype(int) % 5
        return sx[space], base[space] - 0.1 - 0.05 * age


class _River(_Pocket):
    """Braid nine strands toward one horizon, locked to a four-beat pocket."""

    MARKS = ("bass", "harp")

    def __init__(self, movement: Movement):
        super().__init__(movement)
        self.lanes = np.linspace(-1, 1, 9, dtype=np.float32)[:, None]

    def _spread(self, depth, arc: float):
        return (0.08 + depth * (0.55 + 0.35 * arc)) * self._half_w

    def _strands(self, frame: Frame, arc: float):
        depth = self.q[None, :] ** 1.5
        spread = self._spread(depth, arc)
        pocket = math.sin(2 * math.pi * frame.tau * self.bpm / 240)
        cx = 0.1 * self._half_w
        x = (
            cx
            + self.lanes * spread
            + 0.12 * depth * np.sin(depth * 9 - frame.tau * 0.2 + self.lanes * 2)
            + 0.03 * pocket * depth
        )
        y = np.broadcast_to(1.0 - 1.1 * depth, x.shape)
        return x.astype(np.float32), y.astype(np.float32)

    def _paint(self, surface, frame, arc):
        x, y = self._strands(frame, arc)
        outer = 0.6 + 0.8 * np.abs(self.lanes[:, 0]) ** 2
        weight = outer * (0.5 + 0.5 * self._mod[_BASS])
        self._stroke(surface, x, y, self.mid * (0.5 + 0.2 * self._mod[_GUITAR]), weight)
        self._stroke(surface, x[::2], y[::2], self.lit * 0.4, weight[::2] * 0.6)
        distance_sq = (surface.u - 0.1 * self._half_w) ** 2 + (surface.v + 0.1) ** 2
        surface.add(
            np.exp(-distance_sq / (0.05 + 0.05 * arc)),
            self.lit,
            0.08 + 0.06 * self._mod[_SECTION],
        )

    def _place(self, part, notes, age, frame: Frame):
        midi = notes["midi"].astype(int)
        depth = np.clip(age / _MARK_WINDOW_S, 0, 1).astype(np.float32)
        lane = self.lanes[midi % 9, 0]
        x = 0.1 * self._half_w + lane * self._spread(depth, self._progress(frame))
        return x, 1.0 - 1.1 * depth


_SCENES = {
    "root": _Root,
    "rain": _Rain,
    "spiral": _Spiral,
    "canopy": _Canopy,
    "spores": _Spores,
    "river": _River,
}


def build_scene(movement: Movement) -> Scene:
    """Construct the seeded painter for one of The Forest Has a Pocket's six chapters.

    Args:
        movement: Pocket metadata, including the scene key, palette, BPM and stable seed.

    Returns:
        A scene owning its geometry, signal smoothing and held image.

    Raises:
        ValueError: The movement does not name a known pocket scene.
    """
    try:
        painter = _SCENES[movement.scene]
    except KeyError as error:
        raise ValueError(f"unknown pocket scene: {movement.scene}") from error
    return painter(movement)

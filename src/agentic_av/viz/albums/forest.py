"""Paint Nurse Log's six rooted, rain-soaked worlds for the mosaic Stage.

Geometry uses picture time only; score time locates small musical marks. Seeded
branch networks and reusable scalar layers keep the forest deterministic and cheap.
Score velocities arrive energy-scaled from Stage; zero energy ignores all signals.
"""

from __future__ import annotations

import math

import numpy as np

from ..color import linear
from ..draw import lines, points, segments
from ..scene import Frame, Movement, Scene
from ..surface import Surface

_FLOOR = linear("#050f0a")
_FOG = linear("#132a1c")
_TRUNK = linear("#173323")


def _ease(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


class _Forest(Scene):
    """Share layered forest atmosphere while keeping each chapter's own geometry."""

    def __init__(self, movement: Movement):
        super().__init__(movement)
        palette = movement.palette or ("#0b2119", "#496f43", "#a3b67b")
        self.colors = tuple(linear(c) for c in palette[:3])
        rng = np.random.default_rng(movement.seed)
        self.trees = rng.uniform(0, 1, (3, 13, 4)).astype(np.float32)
        self.motes = rng.uniform(0, 1, (110, 4)).astype(np.float32)
        self.phase = rng.uniform(0, 2 * np.pi, 48).astype(np.float32)
        self.q = np.linspace(0, 1, 48, dtype=np.float32)
        self.angle = np.linspace(0, 2 * np.pi, 181, dtype=np.float32)
        # Every level splits in two; the fixed topology makes growing roots continuous.
        branches = [(0.22, -0.15, 0.22, 0.12, 0.0, 0.16)]
        frontier = [(0.22, 0.12, np.pi / 2, 0.0)]
        for depth in range(6):
            next_frontier = []
            for x, y, angle, _ in frontier:
                for side in (-1, 1):
                    a = angle + side * rng.uniform(0.35, 0.85)
                    length = rng.uniform(0.19, 0.35) * (0.79**depth)
                    end_x, end_y = x + np.cos(a) * length, y + np.sin(a) * length
                    start = 0.06 + depth * 0.12
                    branches.append((x, y, end_x, end_y, start, start + 0.19))
                    next_frontier.append((end_x, end_y, a, start))
            frontier = next_frontier
        self.roots = np.asarray(branches, dtype=np.float32)
        self._shape = None
        self._held = None
        self._mod = np.zeros(7, dtype=np.float32)

    def resize(self, surface: Surface) -> None:
        """Rebuild atmosphere and scratch layers for a target in sub-pixels.

        Args:
            surface: Target canvas; no musical time is advanced.
        """
        self._shape = surface.rgb.shape
        self._layer = surface.layer()
        self._detail = surface.layer()
        self._held = None
        y = (surface.v + 1) * 0.5
        top = self.colors[0] * 0.55
        self._background = np.empty_like(surface.rgb)
        for channel in range(3):
            self._background[..., channel] = np.interp(
                y, (0, 0.65, 1), (top[channel], _FOG[channel] * 0.75, _FLOOR[channel])
            )
        self._vignette = np.clip(
            1.08 - 0.34 * (surface.v**2 + (surface.u / surface.half_w) ** 2), 0.2, 1
        ).astype(np.float32)

    def seek(self) -> None:
        """Drop held pixels and smoothed musical deformation after a clock jump."""
        self._held = None
        self._mod.fill(0)

    def _signals(self, frame):
        target = np.zeros(7, dtype=np.float32)
        if frame.energy:
            level = frame.levels
            target[:] = (
                level.slow_bass,
                level.mid,
                level.treble,
                level.kick,
                level.snare,
                level.hat,
                0.5 * frame.energy,
            )
            if frame.score is not None:
                for index, part in enumerate(("bass", "guitar", "reeds")):
                    target[index] = max(
                        target[index], frame.score.level(part, frame.t, decay_s=0.8)
                    )
            if frame.section is not None:
                target[6] = frame.section.intensity
        # A long response suppresses rapid score/onset changes without making motion laggy.
        blend = -math.expm1(-max(frame.dt, 0) / 0.65)
        self._mod += (target - self._mod) * blend
        if frame.energy == 0:
            self._mod.fill(0)
        return self._mod

    def _ground(self, x, tau, base=0.55):
        bass, guitar = self._mod[:2]
        return (
            base
            + (0.024 + 0.035 * bass + 0.018 * guitar) * np.sin(x * 2.5 - tau * 0.21)
            + 0.016 * np.sin(x * 6 + tau * 0.12)
        )

    def _stroke(self, surface, x, y, color, weight=1.0):
        self._layer.fill(0)
        lines(surface, self._layer, x, y, weight)
        surface.add(self._layer, color)

    def _atmosphere(self, surface, tau, ground=0.55, *, trunks=True, shafts=3):
        if shafts:
            # Shafts illuminate gaps, not the whole screen; no onset controls their light.
            u = surface.u
            shaft = self._detail
            shaft.fill(0)
            for index in range(shafts):
                center = -0.85 + index * 0.8 + 0.05 * np.sin(tau * 0.045 + index)
                shaft += np.exp(-(((u + surface.v * 0.38 - center) / 0.075) ** 2))
            shaft *= np.clip((0.8 - surface.v) * 0.13, 0, 0.22)
            surface.add(shaft, self.colors[2], 0.22)
        if trunks:
            q = self.q[None, :]
            trunks_layer = self._layer
            highlights_layer = self._detail
            trunks_layer.fill(0)
            highlights_layer.fill(0)
            bark_x_rows, bark_y_rows, bark_weights = [], [], []
            branch_x_rows, branch_y_rows, branch_weights = [], [], []
            highlight_x_rows, highlight_y_rows = [], []
            for depth in range(3):
                trees = self.trees[depth, ::2]
                x0 = (trees[:, 0:1] * 2 - 1) * surface.half_w * 1.15
                base = self._ground(x0, tau, ground) - (2 - depth) * 0.13
                sway = np.sin(tau * 0.08 + trees[:, 1:2] * 6)
                sway *= 0.018 + depth * 0.009 + self._mod[1] * 0.018
                slope = 0.05 * np.cos(x0 * 2.5 - tau * 0.21)
                x = x0 + (1 - q) ** 2 * sway + (1 - q) * slope
                y = -1.2 + q * (base + 1.2)
                offsets = np.array([-1, 0, 1], dtype=np.float32)[None, :, None]
                bark_x = x[:, None, :] + offsets * (0.007 + depth * 0.008)
                bark_y = np.broadcast_to(y[:, None, :], bark_x.shape)
                bark_x = bark_x.reshape(-1, bark_x.shape[-1])
                bark_y = bark_y.reshape(-1, bark_y.shape[-1])
                bark_x_rows.append(bark_x)
                bark_y_rows.append(bark_y)
                bark_weights.append(np.full(len(bark_x), 0.65 + depth * 0.2, np.float32))
                bx = np.stack((x0[:, 0], x0[:, 0] - 0.13, x0[:, 0] - 0.25), axis=1)
                by = np.stack((base[:, 0] - 0.5, base[:, 0] - 0.7, base[:, 0] - 0.74), axis=1)
                branch_x_rows.append(
                    np.pad(bx, ((0, 0), (0, self.q.size - bx.shape[1])), mode="edge")
                )
                branch_y_rows.append(
                    np.pad(by, ((0, 0), (0, self.q.size - by.shape[1])), mode="edge")
                )
                branch_weights.append(np.full(len(bx), 1 + depth, np.float32))
                highlight_x_rows.append(x + 0.019)
                highlight_y_rows.append(y)
            # Trunks dominate this scene; one splat per shared material avoids
            # repeating full-canvas composites for each depth and branch.
            lines(
                surface,
                trunks_layer,
                np.concatenate((*bark_x_rows, *branch_x_rows)),
                np.concatenate((*bark_y_rows, *branch_y_rows)),
                np.concatenate((*bark_weights, *branch_weights)),
            )
            lines(
                surface,
                highlights_layer,
                np.concatenate(highlight_x_rows),
                np.concatenate(highlight_y_rows),
                0.65,
            )
            surface.add(trunks_layer, _TRUNK)
            surface.add(highlights_layer, self.colors[1] * 0.14)
        ground_y = self._ground(surface.u, tau, ground)
        surface.cover(_ease((surface.v - ground_y) / 0.04), _FLOOR * 0.55)
        self._stroke(
            surface,
            surface.u[0],
            self._ground(surface.u[0], tau, ground),
            self.colors[1] * 0.42,
            1.1,
        )

    def _ferns(self, surface, x, y, size, tau):
        x, y, size = np.broadcast_arrays(x, y, size)
        q = np.linspace(0, 1, 10, dtype=np.float32)[None, :]
        tilt = 0.2 * np.sin(tau * 0.09 + x[:, None])
        stem_x = x[:, None] + size[:, None] * (0.32 * q**2 + tilt * q)
        stem_y = y[:, None] - size[:, None] * q
        self._stroke(surface, stem_x, stem_y, self.colors[1], 0.7)
        for side in (-1, 1):
            reach = size[:, None] * np.sin(q * np.pi) * 0.3
            self._layer.fill(0)
            segments(
                surface,
                self._layer,
                stem_x,
                stem_y,
                stem_x + side * reach,
                stem_y - reach * 0.5,
                0.55,
            )
            surface.add(self._layer, self.colors[1], 0.65)

    def _notes(self, surface, frame, *, roots=False):
        if not frame.energy or frame.score is None:
            return
        for part, color in (("harp", self.colors[2]), ("reeds", self.colors[1])):
            notes = frame.score.recent(part, frame.t, 2.8)[-24:]
            if not len(notes):
                continue
            age = frame.t - notes["onset"]
            pitch = np.clip((notes["midi"] - 40) / 50, 0, 1)
            if roots:
                index = (notes["midi"].astype(int) * 7) % len(self.roots)
                root = self.roots[index]
                along = np.clip(age * frame.energy / 2.8, 0, 1)
                x = root[:, 0] + (root[:, 2] - root[:, 0]) * along
                y = root[:, 1] + (root[:, 3] - root[:, 1]) * along
                y += self._ground(x, frame.tau, -0.28) + 0.28
            else:
                motion_age = age * frame.energy
                x = (pitch - 0.5) * surface.half_w * 1.4
                x += 0.07 * np.sin(motion_age * 1.4)
                y = 0.1 - pitch * 0.65 - 0.04 * motion_age
            self._detail.fill(0)
            weight = notes["vel"] * np.sin(np.pi * age / 2.8) * 0.7
            points(surface, self._detail, x, y, weight)
            surface.add(self._detail, color)
            q = np.linspace(0, 1, 7, dtype=np.float32)[None, :]
            self._stroke(
                surface,
                x[:, None] - q * 0.08,
                y[:, None] + np.sin(q * np.pi) * 0.025,
                color * 0.13,
                weight[:, None],
            )
            if isinstance(self, _Spores) and part == "harp":
                # A note releases a localized puff; its total light stays tiny.
                direction = np.linspace(-1, 1, 5, dtype=np.float32)[None, :]
                puff_x = x[:, None] + direction * motion_age[:, None] * 0.025
                puff_y = y[:, None] - motion_age[:, None] * 0.025
                self._detail.fill(0)
                points(
                    surface,
                    self._detail,
                    puff_x,
                    np.broadcast_to(puff_y, puff_x.shape),
                    weight[:, None] * 0.12,
                )
                surface.add(self._detail, color)

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint one complete forest chapter, holding exactly when picture dt is zero.

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
        arc = float(_ease(frame.tau / max(self.movement.duration_s, 1)))
        self._paint(surface, frame, arc)
        self._notes(surface, frame, roots=isinstance(self, _Roots))
        surface.rgb *= self._vignette[..., None]
        if self._held is None:
            self._held = np.empty_like(surface.rgb)
        self._held[:] = surface.rgb


class _Roots(_Forest):
    """Reveal a branching cutaway below a compressed, gently heaving soil bed."""

    def _paint(self, surface, frame, arc):
        tau = frame.tau
        self._atmosphere(surface, tau, -0.28)
        # Cutaway strata: compress locally rather than changing soil brightness.
        q = self.q[None, :]
        x = np.broadcast_to(np.linspace(-surface.half_w, surface.half_w, 48), (5, 48))
        bands = np.arange(5, dtype=np.float32)[:, None]
        y = -0.1 + bands * (0.17 - 0.015 * self._mod[0])
        y = y + 0.018 * np.sin(x * 4 - tau * 0.09 + bands)
        self._stroke(surface, x, y, self.colors[1] * 0.11, 0.65)
        root = self.roots
        travel = frame.energy * frame.levels.travel / max(self.movement.duration_s, 1)
        growth = 0.13 + 0.85 * arc + min(travel, 0.04)
        reveal = _ease((growth - root[:, 4]) / (root[:, 5] - root[:, 4]))[:, None]
        p = q * reveal
        x = root[:, 0:1] + (root[:, 2:3] - root[:, 0:1]) * p
        y = root[:, 1:2] + (root[:, 3:4] - root[:, 1:2]) * p
        x += 0.012 * np.sin(p * np.pi) * np.sin(tau * 0.12 + y * 7)
        y += self._ground(x, tau, -0.28) + 0.28
        self._stroke(surface, x, y, self.colors[1], 1.15 * reveal)
        self._stroke(surface, x[::7], y[::7], self.colors[2] * 0.58, 0.65 * reveal[::7])
        fx = np.linspace(-surface.half_w, surface.half_w, 13, dtype=np.float32)
        self._ferns(surface, fx, self._ground(fx, tau, -0.28), np.full(13, 0.14), tau)


class _Rain(_Forest):
    """Carry three rain depths over ferns, localized crowns and ground ripples."""

    def _paint(self, surface, frame, arc):
        tau = frame.tau
        self._atmosphere(surface, tau, 0.66, shafts=2)
        motes = self.motes
        for depth in range(3):
            speed = 0.11 + depth * 0.09
            x = (motes[:, 0] * 2 - 1) * surface.half_w * 1.2
            y = (motes[:, 1] * 2 + tau * speed) % 2.2 - 1.1
            length = (0.035 + depth * 0.035) * (0.8 + arc * 0.5)
            slant = 0.28 + 0.14 * self._mod[2]
            # The snare curtain travels continuously; its brightness never gates.
            curtain = 0.045 * self._mod[4] * np.sin(x * 1.2 - tau * 0.6)
            self._layer.fill(0)
            segments(
                surface,
                self._layer,
                x + curtain,
                y,
                x + slant * length,
                y + length,
                (0.24 + depth * 0.17) * (0.5 + 0.5 * np.sin(np.pi * arc)),
            )
            density = _ease((0.3 + self._mod[6] * 0.7 - motes[:, 3]) * 5)
            self._detail.fill(0)
            curtain_x = surface.half_w * np.sin(tau * 0.12) * (0.6 + self._mod[4] * 0.2)
            curtain_weight = np.exp(-(((x - curtain_x) / 0.18) ** 2)) * density
            points(
                surface,
                self._detail,
                x + slant * length * 0.5,
                y + length * 0.5,
                curtain_weight * 0.14,
            )
            surface.add(self._detail, self.colors[2], 0.4)
            surface.add(self._layer, self.colors[2] if depth == 2 else self.colors[1], 0.55)
        fx = np.linspace(-surface.half_w, surface.half_w, 9, dtype=np.float32)
        self._ferns(surface, fx, self._ground(fx, tau, 0.66), np.full(9, 0.22), tau)
        # Small crowns persist as geometry while their opening follows the hat envelope.
        q = np.linspace(0, np.pi, 15, dtype=np.float32)[None, :]
        cx = fx[::2, None]
        radius = 0.027 + self._mod[5] * 0.018
        x = cx + np.cos(q) * radius
        y = self._ground(cx, tau, 0.65) - np.sin(q) * radius * 0.7
        self._stroke(surface, x, y, self.colors[2] * 0.55, 0.7)
        x = surface.u[0]
        for offset in (0.04, 0.09):
            y = self._ground(x, tau, 0.7 + offset) + self._mod[3] * 0.012 * np.sin(x * 16 - tau)
            self._stroke(surface, x, y, self.colors[1] * 0.4, 0.6)


class _Rings(_Forest):
    """Rotate an irregular trunk cross-section against its outer root ring."""

    def _paint(self, surface, frame, arc):
        tau = frame.tau
        self._atmosphere(surface, tau, 0.86, shafts=2)
        theta = self.angle[None, :]
        bpm = self.movement.bpm or 112
        # Seven smoothly eased steps per 7/4 bar, using the picture clock (never t).
        beat = tau * bpm / 60
        step = math.floor(beat)
        turn = (step + float(_ease(beat - step))) * 2 * np.pi / 49
        radii = np.linspace(0.045, 0.73 + arc * 0.12, 39, dtype=np.float32)[:, None]
        r = radii * (1 + 0.018 * np.sin(theta * 9 + self.phase[:39, None]))
        r += 0.005 * np.sin(theta * 23 + radii * 31)
        a = theta + turn
        x = 0.23 + r * np.cos(a)
        y = -0.03 + r * np.sin(a) * 0.93
        self._stroke(surface, x, y, self.colors[1] * 0.62, 0.7)
        self._stroke(surface, x[::6], y[::6], self.colors[2] * 0.68, 0.95)
        r = 0.83 + 0.035 * np.sin(theta * 11 - turn * 2)
        self._stroke(
            surface,
            0.23 + r * np.cos(theta - turn),
            -0.03 + r * np.sin(theta - turn) * 0.93,
            self.colors[1],
            1.6,
        )
        # Radial fissures are dark wedges, opening under the bass's weight.
        q = self.q[None, :]
        a = np.arange(7, dtype=np.float32)[:, None] * 2 * np.pi / 7 + turn
        rr = 0.27 + q * 0.51
        self._layer.fill(0)
        lines(
            surface,
            self._layer,
            0.23 + rr * np.cos(a),
            -0.03 + rr * np.sin(a) * 0.93,
            0.7 + self._mod[0] * 1.4,
        )
        surface.cover(np.clip(self._layer, 0, 0.85), _FLOOR * 0.3)
        if frame.energy and frame.score is not None:
            notes = frame.score.recent("harp", frame.t, 2)[-5:]
            ids = notes["midi"].astype(int) % len(radii)
            if len(ids):
                self._stroke(
                    surface, x[ids], y[ids], self.colors[2] * 0.1, notes["vel"][:, None] * 0.45
                )


class _Canopy(_Forest):
    """Open branching cedar crowns around an off-center breathing sky gap."""

    def _paint(self, surface, frame, arc):
        tau = frame.tau
        # Looking up eliminates the horizon but keeps three layers of converging trunks.
        bpm = self.movement.bpm or 70
        bar_phase = tau * bpm / 240 * 2 * np.pi
        breath = np.sin(bar_phase) * (0.016 + self._mod[2] * 0.018)
        cx, cy = 0.3, -0.24 - arc * 0.14
        q = self.q[None, :]
        angles = np.linspace(0, 2 * np.pi, 19, endpoint=False, dtype=np.float32)[:, None]
        for depth in range(3):
            inner = 0.15 + arc * 0.15 + depth * 0.11 + breath
            r = inner + q * (1.9 - inner)
            a = angles + 0.09 * np.sin(q * 4 + self.phase[:19, None])
            x = cx + np.cos(a) * r
            y = cy + np.sin(a) * r
            self._stroke(surface, x, y, self.colors[1] * (0.22 + 0.13 * depth), 2.2 + depth * 2.4)
            self._stroke(surface, x + 0.013, y, self.colors[2] * 0.23, 0.6)
        # Forked crowns frame irregular sky gaps, rather than filling a radial disc.
        for side in (-1, 1):
            a = angles + side * q * 0.42
            r = 0.34 + q * 0.69 + breath
            self._stroke(
                surface, cx + np.cos(a) * r, cy + np.sin(a) * r, self.colors[1] * 0.48, 1.5
            )
        glow = np.exp(-((surface.u - cx) ** 2 + (surface.v - cy) ** 2) / 0.1)
        surface.add(glow, self.colors[2], 0.075)


class _Spores(_Forest):
    """Grow seedlings from a fallen log under one shaft and rising spore tails."""

    def _paint(self, surface, frame, arc):
        tau = frame.tau
        self._atmosphere(surface, tau, 0.83, shafts=1)
        x = surface.u[0]
        log_y = self._ground(x, tau, 0.53) + 0.08 * np.sin(x * 1.5)
        band = np.abs(surface.v - log_y[None, :])
        surface.cover(_ease((0.12 - band) / 0.035), _TRUNK * 0.65)
        for offset in (-0.09, -0.055, 0.04):
            self._stroke(surface, x, log_y + offset, self.colors[1] * 0.33, 0.7)
        fx = np.linspace(-1.25, 1.35, 8, dtype=np.float32)
        growth = 0.07 + arc * np.linspace(0.17, 0.4, 8, dtype=np.float32)
        fy = self._ground(fx, tau, 0.47) + 0.08 * np.sin(fx * 1.5)
        self._ferns(surface, fx, fy, growth, tau)
        motes = self.motes[:72]
        x = (motes[:, 0] * 2 - 1) * surface.half_w
        y = 0.5 - ((motes[:, 1] * 1.7 + tau * (0.012 + motes[:, 2] * 0.018)) % 1.7)
        x += np.sin(tau * 0.1 + motes[:, 3] * 6 + y) * 0.09
        self._detail.fill(0)
        points(surface, self._detail, x, y, 0.13 + motes[:, 2] * 0.22)
        surface.add(self._detail, self.colors[2], 0.65)
        self._layer.fill(0)
        segments(surface, self._layer, x, y, x - 0.012, y + 0.025, 0.08)
        surface.add(self._layer, self.colors[1])


class _River(_Forest):
    """Braid flowing ground toward a horizon between breathing fern-lined banks."""

    def _paint(self, surface, frame, arc):
        tau = frame.tau
        self._atmosphere(surface, tau, 0.72, shafts=3)
        q = self.q[None, :]
        lanes = np.linspace(-1, 1, 39, dtype=np.float32)[:, None]
        depth = q**1.6
        y = -0.17 + depth * 1.35
        spread = 0.07 + depth * (0.95 + arc * 0.8)
        x = 0.25 + lanes * spread + 0.13 * depth * np.sin(q * 9 - tau * 0.19 + lanes * 2)
        y = np.broadcast_to(y, x.shape)
        self._stroke(
            surface, x, y, self.colors[1] * (0.5 + self._mod[1] * 0.15), 0.6 + self._mod[0] * 0.25
        )
        self._stroke(surface, x[::7], y[::7], self.colors[2] * 0.55, 0.7)
        # Riverbank silhouettes share the same travelling terrain deformation as the trees.
        for side in (-1, 1):
            bank_x = 0.25 + side * spread[0] * 1.09
            bank_y = y[0] + 0.025 * np.sin(q[0] * 8 - tau * 0.21)
            bank_y += 0.025 * self._mod[6] * np.sin(q[0] * 12 - tau * 0.3)
            self._stroke(surface, bank_x, bank_y, self.colors[1] * 0.75, 1.8)
            self._ferns(surface, bank_x[::7], bank_y[::7], 0.04 + depth[0, ::7] * 0.2, tau)


_SCENES = {
    "root": _Roots,
    "rain": _Rain,
    "spiral": _Rings,
    "canopy": _Canopy,
    "spores": _Spores,
    "river": _River,
}


def build_scene(movement: Movement) -> Scene:
    """Construct a seeded painter for one of Nurse Log's six chapters.

    Args:
        movement: Forest metadata, including scene key, palette and stable seed.

    Returns:
        A scene owning its own geometry, signal smoothing and held image.

    Raises:
        ValueError: The movement does not name a known forest scene.
    """
    try:
        painter = _SCENES[movement.scene]
    except KeyError as error:
        raise ValueError(f"unknown forest scene: {movement.scene}") from error
    return painter(movement)

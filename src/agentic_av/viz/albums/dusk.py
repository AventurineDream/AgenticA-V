"""Paint Quiet Machinery A-02, *Instruments for Measuring Dusk*, as six room-scale instruments.

Each chapter is one instrument in its own geometry: an iris with an inner set that turns the
other way, two crossing reeds made of strands, a glowing bell body with striations and rings
across its plane, salt fault lines with twin traces, a warm room whose window widens behind
mullions, and a guyed mast with a lattice. Score notes place marks only while energy is nonzero;
each mark ramps in with a cubic attack and tails out with a flat end, so no mark steps the
picture at onset or expiry. Smoothed audio and note envelopes move geometry and light, and picture
time drives drift. A zero picture step holds the last image. The painter is independent of the
A-01 rooms family, which keeps its own sculptures. No state is global.
"""

from __future__ import annotations

import math

import numpy as np

from ..color import linear
from ..draw import disc, ease_in_out, lines, points, ring, segments, smoothstep
from ..scene import Frame, Movement, Scene
from ..score import NOTE
from ..surface import Surface

_EMPTY = np.empty(0, dtype=NOTE)
_EMPTY.flags.writeable = False
_DEFAULT_PALETTE = ("#0b1220", "#c98a5a", "#7f9cc7")
# Envelopes follow a first-order 0.65 s time constant in picture time, so audio swells
# geometry and light gradually instead of stepping on each beat.
_SMOOTH_S = 0.65
_BASS, _VIBES, _CLARINET, _FLUTE, _AIR = range(5)
_CHANNELS = 5
# Note-driven geometry (sheet bends, fault slip) eases with the same time constant and
# holds its last value through rests, so a phrase gap never snaps a line back to rest.
_GLIDE_CLARINET, _GLIDE_FLUTE, _GLIDE_BASS = range(3)
# Seconds a note's mark stays visible; each also bounds that part's `_recent` window.
_MARIMBA_S = 1.5
_VIBES_S = 5.0
_PERC_S = 3.0
_FAULT_Y = np.linspace(-1, 1, 96, dtype=np.float32)
# Half-width of soft edges in scene units; about one mosaic sub-pixel at typical tiers.
_EDGE = 0.01
# Seconds over which a note's mark fades in, so an onset never steps a mark from dark
# to full light within one frame.
_ATTACK_S = 0.12
# Blade rim angles of the nine-blade iris; both of its sets share them.
_BLADE = np.arange(9, dtype=np.float32) / 9 * 2 * np.pi
# Rings are tabulated on this radial grid. Every ring stays below about 0.5 scene units, so the
# table's last sample is zero and the clamp np.interp applies beyond it adds no light.
_PROFILE_R = np.linspace(0, 0.6, 256, dtype=np.float32)


def _edge(distance, soft: float = _EDGE):
    """Return a 0..1 coverage ramp of a signed distance, positive inside, with width `soft`."""
    return np.clip(distance / soft + 0.5, 0, 1).astype(np.float32)


def _rise(t: float, onset):
    """Return a 0..1 cubic attack for marks: seconds since onset over `_ATTACK_S`, clipped.

    The cubic has zero slope at both ends, so a mark has no kink where its attack completes.
    """
    return smoothstep(0, _ATTACK_S, t - onset)


def _fade(age):
    """Return a mark's 1..0 tail at `age`, a fraction of its window, flat where it expires.

    The squared ramp meets zero with zero slope, so a note leaving its score window does not
    step the picture.
    """
    return np.clip(1 - age, 0, 1) ** 2


def _rings(metric, radii, widths, gains, soft: float = _EDGE):
    """Sum concentric ring coverage over one distance metric by tabulating each ring radially.

    Args:
        metric: Float32 scene-unit distance from each ring's centre, in the convention of
            `draw.ring` (any squash is already applied).
        radii: Centreline radii in scene units, scalar or shape (n,); each below about 0.5.
        widths: Full stroke widths in scene units, broadcastable to the radii.
        gains: Linear energy per ring, broadcastable to the radii.
        soft: Edge smoothing half-width in scene units, as for `draw.ring`.

    Returns:
        Owned float32 field shaped like `metric`. Work scales with the ring count over a
        256-sample radial profile plus one canvas-sized interpolation. No ring is dropped,
        so dense passages do not step when their oldest mark is evicted.
    """
    radii = np.asarray(radii, np.float32).reshape(-1)
    if not len(radii):
        return np.zeros(np.shape(metric), dtype=np.float32)
    widths = np.broadcast_to(np.asarray(widths, np.float32), radii.shape)[:, None]
    gains = np.broadcast_to(np.asarray(gains, np.float32), radii.shape)[:, None]
    coverage = smoothstep(-soft, soft, widths * 0.5 - np.abs(_PROFILE_R - radii[:, None]))
    profile = (gains * coverage).sum(axis=0)
    return np.interp(metric, _PROFILE_R, profile).astype(np.float32)


class _Dusk(Scene):
    """Share palette roles, smoothed envelopes, held pictures and note access across chapters.

    Palette roles follow the album's scene code: palette[0] is the room, palette[1] the
    warm (copper) light and palette[2] the cool (oxidized blue) structure. Subclasses paint
    geometry in `_paint`; they read notes only through `_recent`, which honours zero energy.
    """

    def __init__(self, movement: Movement):
        super().__init__(movement)
        palette = movement.palette or _DEFAULT_PALETTE
        self.base, self.warm, self.cool = (linear(c) for c in palette[:3])
        rng = np.random.default_rng(movement.seed)
        self.grains = rng.uniform(0, 1, (160, 3)).astype(np.float32)
        self._shape = None
        self._held = None
        self._mod = np.zeros(_CHANNELS, dtype=np.float32)
        self._target = np.zeros_like(self._mod)
        self._glides = np.zeros(3, dtype=np.float32)

    def resize(self, surface: Surface) -> None:
        """Rebuild the room-tone backdrop, vignette and scratch layers for a canvas.

        Args:
            surface: Target canvas; musical and picture clocks are not advanced.
        """
        self._shape = surface.rgb.shape
        self.half_w = surface.half_w
        self._layer = surface.layer()
        self._detail = surface.layer()
        self._held = None
        u = surface.u / surface.half_w
        v = surface.v
        down = ((v + 1) * 0.5)[..., None]
        room = (1 - down) * self.base * 0.85 + down * self.base * 0.35
        grain = (
            1
            + 0.06 * np.sin(u * 41 + v * 23 + self.grains[0, 0] * 2 * np.pi)
            + 0.04 * np.sin(v * 57 - u * 19 + self.grains[1, 1] * 2 * np.pi)
        )
        self._background = (room * grain[..., None]).astype(np.float32)
        self._vignette = np.clip(
            1.05 - 0.3 * (surface.v**2 + (surface.u / surface.half_w) ** 2), 0.2, 1
        ).astype(np.float32)

    def seek(self) -> None:
        """Drop the held picture and smoothed envelopes after a discontinuous clock jump."""
        self._held = None
        self._mod.fill(0)
        self._glides.fill(0)

    def _progress(self, frame: Frame) -> float:
        """Return the movement's eased picture progress, clamped to 0..1."""
        return float(ease_in_out(frame.tau / max(self.movement.duration_s, 1)))

    def _signals(self, frame: Frame) -> None:
        """Smooth this picture's musical targets into `self._mod`; zero energy clears them.

        Levels and score velocities arrive already scaled by energy from Stage, so this
        method only selects channels and integrates them over picture time.
        """
        target = self._target
        target.fill(0)
        if frame.energy:
            level, score, t = frame.levels, frame.score, frame.t
            target[_BASS] = level.slow_bass
            target[_AIR] = level.treble
            if score is not None:
                target[_BASS] = max(target[_BASS], score.level("bass", t, decay_s=0.5))
                target[_VIBES] = score.level("vibes", t, decay_s=1.6)
                target[_CLARINET] = score.level("clarinet", t, decay_s=0.6)
                target[_FLUTE] = score.level("flute", t, decay_s=0.4)
        blend = -math.expm1(-max(frame.dt, 0) / _SMOOTH_S)
        self._mod += (target - self._mod) * blend
        if frame.energy == 0:
            self._mod.fill(0)

    def _glide(self, index: int, notes, frame: Frame, value: float) -> float:
        """Ease one note-driven geometry term toward `value`, holding it through rests.

        Args:
            index: Glide slot (`_GLIDE_*`).
            notes: Recent notes of the driving part; empty means hold the current value.
            frame: Frame whose picture dt sets the easing step; zero energy resets to rest.
            value: Target taken from the newest note, used only when `notes` is non-empty.

        Returns:
            The eased value for this frame.
        """
        if not frame.energy:
            self._glides[index] = 0
            return 0.0
        if len(notes):
            blend = -math.expm1(-max(frame.dt, 0) / _SMOOTH_S)
            self._glides[index] += (value - self._glides[index]) * blend
        return float(self._glides[index])

    def _recent(self, frame: Frame, part: str, window_s: float) -> np.ndarray:
        """Return every note of `part` starting within `window_s` seconds, without a count cap.

        Zero energy or a missing score yields no notes, so audio-free frames ignore the score.
        A count cap would evict the oldest mark of a dense passage and step the picture.
        """
        if not frame.energy or frame.score is None:
            return _EMPTY
        return frame.score.recent(part, frame.t, window_s)

    @staticmethod
    def _pitch(notes) -> float:
        """Return the last note's pitch as -1..1 around middle C, or zero without notes.

        The ±40-semitone half-span around middle C maps to ±1, keeping the bend within the
        sheet's visible range.
        """
        if not len(notes):
            return 0.0
        return float(np.clip((float(notes[-1]["midi"]) - 60) / 40, -1, 1))

    def _stroke(self, surface, x, y, color, weight=1.0, gain=1.0):
        """Add a scalar polyline layer tinted with `color`; weights follow `lines`.

        Args:
            surface: Target canvas, mutated in place.
            x: Scene x vertices, shape (..., n); each last-axis row is one polyline.
            y: Scene y vertices with the same shape as x.
            color: Linear RGB vector for the stroke.
            weight: Stroke energy per sub-pixel of length, as for `lines`.
            gain: Linear multiplier applied when the layer is added.
        """
        self._layer.fill(0)
        lines(surface, self._layer, x, y, weight)
        surface.add(self._layer, color, gain)

    def _paint(self, surface: Surface, frame: Frame, arc: float) -> None:
        """Paint this chapter's geometry; implemented by each painter."""
        raise NotImplementedError

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint one complete chapter, holding exactly when picture dt is zero.

        Args:
            surface: Linear-light output mutated in place.
            frame: Musical instant; tau and dt are picture seconds, t is movement seconds
                used only for note ages. Zero energy suppresses score and audio
                influence while geometry continues with picture time.
        """
        if self._shape != surface.rgb.shape:
            self.resize(surface)
        if frame.dt == 0 and self._held is not None:
            surface.rgb[:] = self._held
            return
        surface.rgb[:] = self._background
        self._signals(frame)
        self._paint(surface, frame, self._progress(frame))
        surface.rgb *= self._vignette[..., None]
        if self._held is None:
            self._held = np.empty_like(surface.rgb)
        self._held[:] = surface.rgb


class _Survey(_Dusk):
    """An iris of nine blades that open with the vibraphone, with an inner set turning back.

    Marimba cell ticks leave the rim and travel outward as they fade.
    """

    RIM = 0.5
    # The inner set's radius as a fraction of RIM; its blades sit half a step out of phase.
    INNER = 0.6

    def _blades(self, surface, angle, radius, opening, sweep, color, gain):
        """Add one ring of blades from rim points to pivots, each pivot turned by `sweep`.

        Args:
            surface: Target canvas, mutated in place.
            angle: Rim angles in radians, shape (n,).
            radius: Rim radius in scene units.
            opening: Pivot radius as a multiple of `radius`; above one, pivots pass the rim.
            sweep: Radians from each rim point to its pivot; its sign sets the turn.
            color: Linear RGB tint.
            gain: Linear multiplier for the blade layer.
        """
        x0, y0 = radius * np.cos(angle), radius * np.sin(angle)
        x1 = radius * opening * np.cos(angle + sweep)
        y1 = radius * opening * np.sin(angle + sweep)
        self._layer.fill(0)
        segments(surface, self._layer, x0, y0, x1, y1, 0.8)
        surface.add(self._layer, color, gain)

    def _paint(self, surface, frame, arc):
        opening = 0.25 + 0.5 * self._mod[_VIBES] + 0.2 * arc
        self._blades(surface, _BLADE + frame.tau * 0.01, self.RIM, opening, 1.1, self.cool, 0.45)
        # Bass opens the inner set, so the two sets do not share one envelope.
        inner_open = 0.35 + 0.4 * self._mod[_BASS] + 0.1 * arc
        inner = _BLADE + np.pi / 9 - frame.tau * 0.006
        inner_radius = self.RIM * self.INNER
        self._blades(surface, inner, inner_radius, inner_open, -1.1, self.cool, 0.2)
        surface.add(ring(surface, 0.0, 0.0, inner_radius, 0.006, soft=0.006), self.cool, 0.12)
        surface.add(ring(surface, 0.0, 0.0, self.RIM, 0.012, soft=0.008), self.cool, 0.25)
        core = np.exp(-(surface.u**2 + surface.v**2) / (0.02 + 0.06 * opening**2))
        surface.add(core, self.warm, 0.05 + 0.2 * self._mod[_VIBES])
        notes = self._recent(frame, "marimba", _MARIMBA_S)
        if len(notes):
            age = ((frame.t - notes["onset"]) / _MARIMBA_S).astype(np.float32)
            theta = (notes["midi"].astype(int) % 12) / 12 * 2 * np.pi - np.pi / 2
            # A tick leaves the rim and travels outward as its light tails out, so it moves
            # continuously instead of fading in place.
            start = self.RIM * (1.04 + 0.14 * age)
            end = start + self.RIM * 0.1
            gain = _fade(age) * notes["vel"] * 0.8 * _rise(frame.t, notes["onset"])
            self._detail.fill(0)
            segments(
                surface,
                self._detail,
                start * np.cos(theta),
                start * np.sin(theta),
                end * np.cos(theta),
                end * np.sin(theta),
                gain,
            )
            surface.add(self._detail, self.warm, 1.0)


class _Sheets(_Dusk):
    """Two reeds that cross left of centre, each a band of strands.

    The clarinet is low and warm, the flute high and cool. Strands ripple along each reed in a
    travelling wave, the clarinet running right and the flute left, so the reeds keep moving
    between notes.
    """

    STRANDS = 5
    SAMPLES = 96

    def resize(self, surface: Surface) -> None:
        """Rebuild shared layers, then the strand sample positions across this canvas width.

        Args:
            surface: Target canvas; musical and picture clocks are not advanced.
        """
        super().resize(surface)
        self._x_line = np.linspace(-self.half_w, self.half_w, self.SAMPLES, dtype=np.float32)

    def _paint(self, surface, frame, arc):
        s = surface.u / self.half_w
        drift = 0.02 * np.sin(frame.tau * 0.1)
        clarinet_notes = self._recent(frame, "clarinet", 6)
        flute_notes = self._recent(frame, "flute", 6)
        clarinet = self._glide(_GLIDE_CLARINET, clarinet_notes, frame, self._pitch(clarinet_notes))
        flute = self._glide(_GLIDE_FLUTE, flute_notes, frame, self._pitch(flute_notes))
        self._reed(
            surface,
            frame.tau,
            s,
            (0.24 + drift, 0.3),
            clarinet,
            self.warm,
            self._mod[_CLARINET],
            0,
            1,
        )
        self._reed(
            surface,
            frame.tau,
            s,
            (-0.16 - drift, -0.3),
            flute,
            self.cool,
            self._mod[_FLUTE],
            1,
            -1,
        )

    def _reed(self, surface, tau, s, line, pitch, color, light, lane, direction):
        """Add one reed: a bowed band with a bright top crease and strands rippling along it.

        Args:
            surface: Target canvas, mutated in place.
            tau: Picture seconds; the ripple advances with it, never with audio.
            s: Normalized horizontal position per canvas column, u over half_w.
            line: (base, slope) of the unbowed centreline in scene units.
            pitch: Last note's pitch in -1..1, bowing the centreline toward the reed's edges.
            color: Linear RGB tint.
            light: Smoothed envelope 0..1 that thickens the band and brightens its strands.
            lane: Seed lane, 0 or 1, selecting this reed's strand phases and weights.
            direction: +1 or -1, the way the ripple travels along the reed.
        """
        base, slope = line
        centre = base + slope * s - 0.2 * pitch * (1 - s * s)
        half = 0.045 + 0.03 * light
        top = centre - half
        coverage = np.minimum(_edge(surface.v - top), _edge((centre + half) - surface.v))
        surface.add(coverage, color, 0.12 + 0.5 * light)
        # The crease along the top edge keeps the silhouette sharp below cell scale.
        crease = np.exp(-(((surface.v - top) / 0.007) ** 2))
        surface.add(crease, color, 0.1 + 0.3 * light)
        # Strands are sampled on the same bow, so they stay inside the band as it moves.
        k = self.STRANDS
        s_line = self._x_line / self.half_w
        centre_line = base + slope * s_line - 0.2 * pitch * (1 - s_line * s_line)
        offsets = (np.arange(k, dtype=np.float32) / (k - 1) - 0.5) * 1.6 * half
        seeds = self.grains[lane * k : lane * k + k]
        wave = np.sin(3.0 * s_line[None, :] - direction * tau * 0.3 + seeds[:, :1] * (2 * np.pi))
        y = centre_line[None, :] + offsets[:, None] + (0.006 + 0.012 * light) * wave
        self._stroke(surface, self._x_line, y, color, 0.35 + 0.4 * seeds[:, 2], 0.22 + 0.5 * light)


class _Bell(_Dusk):
    """A glowing bell body with striations and a drifting sheen; each vibes note rings its plane.

    Vibraphone decay fills the body. Every vibes note in its window contributes a ring, so a
    dense passage never drops an older ring from the picture.
    """

    CROWN = -0.56
    RIM = 0.36
    HALF_WIDTH = 0.2
    # Rings are seen in a plane squashed to this fraction of their width.
    SQUASH = 0.22
    # Depth fractions, from crown to rim, of the machined striations across the body.
    STRIAE = (0.3, 0.45, 0.6, 0.75, 0.9)

    def resize(self, surface: Surface) -> None:
        """Rebuild shared layers, then one ring-distance map for each pitch class on the canvas.

        Args:
            surface: Target canvas; musical and picture clocks are not advanced.
        """
        super().resize(surface)
        centres = (np.arange(12, dtype=np.float32) / 11 - 0.5) * 0.4
        cy = self.RIM + 0.03
        self._ring_metric = [
            np.hypot(surface.u - x, (surface.v - cy) / self.SQUASH).astype(np.float32)
            for x in centres
        ]

    def _paint(self, surface, frame, arc):
        u, v = surface.u, surface.v
        depth = np.clip((v - self.CROWN) / (self.RIM - self.CROWN), 0, 1)
        half = self.HALF_WIDTH * (0.3 + 0.7 * depth**1.6)
        vertical = np.minimum(_edge(v - self.CROWN), _edge(self.RIM - v))
        body = _edge(half - np.abs(u)) * vertical
        surface.add(body * (1 - 0.5 * depth), self.cool, 0.04 + 0.3 * self._mod[_VIBES])
        outline = np.exp(-(((np.abs(u) - half) / 0.012) ** 2)) * vertical
        surface.add(outline, self.cool, 0.3 + 0.4 * self._mod[_VIBES])
        lip = _edge(0.012 - np.abs(v - self.RIM)) * _edge(self.HALF_WIDTH - np.abs(u))
        surface.add(lip, self.cool, 0.3)
        crown = np.exp(-(u**2 + (v - self.CROWN) ** 2) / 0.02)
        surface.add(crown, self.warm, 0.05 + 0.1 * self._mod[_VIBES])
        self._striae(surface)
        # The sheen crosses the body on a 37 picture-second cycle; sinusoidal, so it never steps.
        sheen_x = 0.5 * self.HALF_WIDTH * math.sin(2 * math.pi * frame.tau / 37.0)
        sheen = np.exp(-(((u - sheen_x) / 0.035) ** 2)) * body
        surface.add(sheen, self.warm, 0.03 + 0.08 * self._mod[_VIBES])
        # A slow ring leaves the rim every six picture seconds, so the bell moves without notes.
        # Its light rises and falls to zero within the cycle, so the wrap never steps light.
        phase = (frame.tau / 6.0) % 1.0
        slow = ring(surface, 0.0, self.RIM + 0.03, self.HALF_WIDTH * (0.6 + 1.6 * phase), 0.012)
        surface.add(slow, self.cool, 0.2 * math.sin(math.pi * phase))
        self._vibes_rings(surface, frame)

    def _striae(self, surface):
        """Add horizontal machined striations, each spanning the body's width at its depth.

        Args:
            surface: Target canvas, mutated in place.
        """
        depth = np.asarray(self.STRIAE, dtype=np.float32)
        y = self.CROWN + (self.RIM - self.CROWN) * depth
        half = self.HALF_WIDTH * (0.3 + 0.7 * depth**1.6) - 0.02
        self._detail.fill(0)
        segments(surface, self._detail, -half, y, half, y, 0.5)
        surface.add(self._detail, self.cool, 0.06 + 0.12 * self._mod[_VIBES])

    def _vibes_rings(self, surface, frame):
        """Ring the bell's plane once per vibes note in its window, with no count cap.

        Args:
            surface: Target canvas, mutated in place.
            frame: Frame supplying the vibes notes and the audio clock for their ages.
        """
        notes = self._recent(frame, "vibes", _VIBES_S)
        if not len(notes):
            return
        age = ((frame.t - notes["onset"]) / _VIBES_S).astype(np.float32)
        radii = self.HALF_WIDTH * (0.6 + 1.6 * age)
        widths = 0.01 + 0.01 * (1 - age)
        gains = _fade(age) * notes["vel"] * 0.45 * _rise(frame.t, notes["onset"])
        slot = notes["midi"].astype(int) % 12
        self._detail.fill(0)
        for k in np.unique(slot):
            pick = slot == k
            self._detail += _rings(self._ring_metric[k], radii[pick], widths[pick], gains[pick])
        surface.add(self._detail, self.warm, 1.0)


class _Faults(_Dusk):
    """Seven salt fault lines that slip with the bass, each with a dimmer twin trace.

    Grains drift down the canvas and fade at its ends, so none teleports from bottom to top.
    Marimba notes leave copper crystals.
    """

    LINES = 7
    INDEX = np.arange(LINES, dtype=np.float32)[:, None]

    def _fault_x(self, index, y, slip: float, amp: float, phase: float):
        """Return fault x positions in scene units for fault indices and heights `y`.

        Args:
            index: Fault number(s), broadcastable with `y`.
            y: Scene heights, -1 at the top and +1 at the bottom.
            slip: Horizontal offset in scene units applied across the mid-height jump.
            amp: Wander amplitude in scene units.
            phase: Wander phase in radians; advances with picture time so faults creep.
        """
        x0 = ((index + 0.5) / self.LINES * 2 - 1) * self.half_w
        # Each fault steps sideways every ninth of its height: a fracture, not a curtain.
        step = 0.08 * (np.floor(y * 9 + index) % 3 - 1)
        return x0 + amp * np.sin(3 * y + 1.3 * index + phase) + slip * np.tanh(6 * y) + step

    def resize(self, surface: Surface) -> None:
        """Rebuild shared layers, then place the salt grains across this canvas width."""
        super().resize(surface)
        self._grain_x = (self.grains[:, 0] * 2 - 1) * self.half_w

    def _paint(self, surface, frame, arc):
        bass = self._recent(frame, "bass", 8)
        target = (float(bass[-1]["midi"]) - 38) / 20 if len(bass) else 0.0
        shift = self._glide(_GLIDE_BASS, bass, frame, target)
        slip = 0.05 * shift + 0.03 * self._mod[_BASS]
        amp = 0.02 + 0.04 * self._mod[_BASS]
        phase = frame.tau * 0.05
        xs = self._fault_x(self.INDEX, _FAULT_Y[None, :], slip, amp, phase).astype(np.float32)
        ys = np.broadcast_to(_FAULT_Y, xs.shape)
        self._stroke(
            surface,
            xs,
            ys,
            self.cool,
            0.5 + 0.8 * self._mod[_BASS],
            0.25 + 0.2 * self._mod[_BASS],
        )
        # The twin trace sits a few sub-cells right of each fault, a fracture's shadow.
        self._stroke(surface, xs + 0.035, ys, self.cool, 0.3, 0.1 + 0.12 * self._mod[_BASS])
        g = self.grains
        grain_y = ((g[:, 1] + frame.tau * 0.004) % 1) * 2 - 1
        # Grains fade at the canvas ends where they wrap, so none teleports bottom to top.
        wrap = smoothstep(-1, -0.85, grain_y) * smoothstep(1, 0.85, grain_y)
        self._detail.fill(0)
        points(
            surface,
            self._detail,
            self._grain_x,
            grain_y,
            (0.03 + 0.08 * self._mod[_AIR]) * (0.3 + g[:, 2]) * wrap,
        )
        surface.add(self._detail, self.cool, 0.8)
        notes = self._recent(frame, "marimba", _MARIMBA_S)
        if len(notes):
            midi = notes["midi"].astype(int)
            age = np.clip((frame.t - notes["onset"]) / _MARIMBA_S, 0, 1)
            crystal_y = -0.9 + 1.8 * ((midi * 5) % 11) / 10
            crystal_x = self._fault_x(midi % self.LINES, crystal_y, slip, amp, phase)
            self._detail.fill(0)
            light = _fade(age) * notes["vel"] * 1.2 * _rise(frame.t, notes["onset"])
            points(surface, self._detail, crystal_x, crystal_y, light)
            surface.add(self._detail, self.warm, 1.0)


class _WarmRoom(_Dusk):
    """A one-point room whose back window widens across the track, with mullions.

    Flute light spills out of the window and down the shaft.
    """

    BACK = (-0.3, 0.3, -0.42, 0.2)  # back wall x0, x1, y0, y1 in scene units
    WINDOW = (0.02, -0.24, 0.02)  # window left, top and bottom edges in scene units

    def resize(self, surface: Surface) -> None:
        """Rebuild shared layers, then the room's edges, whose floor corners follow width."""
        super().resize(surface)
        x0, x1, y0, y1 = self.BACK
        fx = 1.15 * self.half_w
        self._edges = np.array(
            [
                (x0, y0, x1, y0),
                (x1, y0, x1, y1),
                (x1, y1, x0, y1),
                (x0, y1, x0, y0),
                (x0, y0, -fx, -1.0),
                (x1, y0, fx, -1.0),
                (x1, y1, fx, 1.0),
                (x0, y1, -fx, 1.0),
            ],
            dtype=np.float32,
        ).T

    def _paint(self, surface, frame, arc):
        u, v = surface.u, surface.v
        x0, x1, y0, y1 = self.BACK
        self._layer.fill(0)
        segments(surface, self._layer, *self._edges, 0.7)
        surface.add(self._layer, self.cool, 0.35)
        back = _edge(u - x0) * _edge(x1 - u) * _edge(v - y0) * _edge(y1 - v)
        surface.add(back, self.cool, 0.05)
        wx0, wy0, wy1 = self.WINDOW
        wx1 = wx0 + 0.26 * (0.12 + 0.88 * arc)
        window = _edge(u - wx0) * _edge(wx1 - u) * _edge(v - wy0) * _edge(wy1 - v)
        surface.add(window, self.warm, 0.1 + 0.35 * self._mod[_FLUTE])
        spread = np.clip(v - wy1, 0, None) * 0.45
        shaft = _edge(u - (wx0 - spread)) * _edge((wx1 + spread) - u) * _edge(v - wy1)
        falloff = 1 - 0.6 * np.clip((v - wy1) / 1.2, 0, 1)
        surface.add(shaft * falloff, self.warm, 0.04 + 0.12 * self._mod[_FLUTE])
        self._sash(surface, wx0, wx1, wy0, wy1)

    def _sash(self, surface, wx0, wx1, wy0, wy1):
        """Add two cool mullions and a transom across the window, following its widening edges.

        Args:
            surface: Target canvas, mutated in place.
            wx0: Window left edge in scene units.
            wx1: Window right edge in scene units; moves with the widening arc.
            wy0: Window top edge in scene units.
            wy1: Window bottom edge in scene units.
        """
        span = wx1 - wx0
        mid = 0.5 * (wy0 + wy1)
        x0 = np.array([wx0 + span / 3, wx0 + 2 * span / 3, wx0], dtype=np.float32)
        x1 = np.array([wx0 + span / 3, wx0 + 2 * span / 3, wx1], dtype=np.float32)
        y0 = np.array([wy0, wy0, mid], dtype=np.float32)
        y1 = np.array([wy1, wy1, mid], dtype=np.float32)
        self._layer.fill(0)
        segments(surface, self._layer, x0, y0, x1, y1, 0.5)
        surface.add(self._layer, self.cool, 0.2)


class _Mast(_Dusk):
    """A guyed mast with a lattice, whose head sways in picture time and rings on accents.

    Accented percussion rings the tip, and the mast lights late in the track.
    """

    TIP = -0.7
    # Full-motion accent threshold: the transmission score's hits run 0.19-0.68, and 0.42
    # passes mostly the fills and upper layers, so the mast rings on the louder strokes rather
    # than every pulse. Stage scales velocities by energy, so the threshold scales with it
    # and reduced motion still rings on the same strokes.
    ACCENT = 0.42
    # Mast, four guys from two heights, and two cross-arms, as (x0, y0) -> (x1, y1) strokes.
    X0 = np.array([0, 0, 0, 0, 0, -0.12, -0.08], dtype=np.float32)
    Y0 = np.array([1.0, -0.25, -0.25, 0.15, 0.15, -0.25, -0.5], dtype=np.float32)
    Y1 = np.array([TIP, 1.0, 1.0, 1.0, 1.0, -0.25, -0.5], dtype=np.float32)
    WEIGHT = np.array([1.2, 0.5, 0.5, 0.5, 0.5, 0.6, 0.6], dtype=np.float32)
    # Six lattice rungs at evenly spaced fractions of the mast, from base (0) to tip (1).
    RUNG_S = np.arange(1, 7, dtype=np.float32) / 7
    RUNG_HALF = 0.09 * (1 - RUNG_S) + 0.015 * RUNG_S

    def _paint(self, surface, frame, arc):
        hw = self.half_w
        # Only the mast head sways; the guys stay anchored, so the motion reads as a slow lean.
        tip_x = 0.015 * np.sin(frame.tau * 0.4)
        x1 = np.array(
            [tip_x, -0.55 * hw, 0.55 * hw, -0.3 * hw, 0.3 * hw, 0.12, 0.08], dtype=np.float32
        )
        self._layer.fill(0)
        segments(surface, self._layer, self.X0, self.Y0, x1, self.Y1, self.WEIGHT)
        surface.add(self._layer, self.cool, 0.4)
        self._lattice(surface, tip_x)
        self._accents(surface, frame, tip_x)
        lit = float(smoothstep(0.8, 1.0, frame.tau / max(self.movement.duration_s, 1)))
        surface.add(disc(surface, tip_x, self.TIP, 0.014, soft=0.006), self.warm, 0.2 + 0.7 * lit)
        halo = np.exp(-((surface.u - tip_x) ** 2 + (surface.v - self.TIP) ** 2) / 0.03)
        surface.add(halo, self.warm, 0.12 * lit)

    def _lattice(self, surface, tip_x):
        """Add tapered rungs at RUNG_S heights, braced zigzag between successive rungs.

        Args:
            surface: Target canvas, mutated in place.
            tip_x: Current horizontal tip position; the lattice follows the mast's lean.
        """
        px = self.RUNG_S * tip_x
        py = 1.0 + self.RUNG_S * (self.TIP - 1.0)
        rx0, rx1 = px - self.RUNG_HALF, px + self.RUNG_HALF
        x0 = np.concatenate((rx0, rx0[:-1], rx1[:-1]))
        y0 = np.concatenate((py, py[:-1], py[:-1]))
        x1 = np.concatenate((rx1, rx1[1:], rx0[1:]))
        y1 = np.concatenate((py, py[1:], py[1:]))
        self._layer.fill(0)
        segments(surface, self._layer, x0, y0, x1, y1, 0.3)
        surface.add(self._layer, self.cool, 0.22)

    def _accents(self, surface, frame, tip_x):
        """Ring the tip once per accented percussion hit in its window, with no count cap.

        Args:
            surface: Target canvas, mutated in place.
            frame: Frame supplying percussion notes, the audio clock and energy for the threshold.
            tip_x: Current horizontal tip position in scene units.
        """
        notes = self._recent(frame, "perc", _PERC_S)
        notes = notes[notes["vel"] >= self.ACCENT * frame.energy]
        if not len(notes):
            return
        age = ((frame.t - notes["onset"]) / _PERC_S).astype(np.float32)
        metric = np.hypot(surface.u - tip_x, surface.v - self.TIP)
        gains = 0.7 * _fade(age) * _rise(frame.t, notes["onset"])
        surface.add(_rings(metric, 0.02 + 0.45 * age, 0.012, gains, soft=0.008), self.warm, 1.0)


_SCENES = {
    "survey": _Survey,
    "sheets": _Sheets,
    "bell": _Bell,
    "faults": _Faults,
    "warm-room": _WarmRoom,
    "transmission": _Mast,
}


def build_scene(movement: Movement) -> Scene:
    """Construct the seeded painter for one of Instruments for Measuring Dusk's six chapters.

    Args:
        movement: Dusk metadata, including the scene key, palette, duration and stable seed.

    Returns:
        A scene owning its geometry, signal smoothing and held image.

    Raises:
        ValueError: The movement does not name a known dusk scene.
    """
    try:
        painter = _SCENES[movement.scene]
    except KeyError as error:
        raise ValueError(f"unknown dusk scene: {movement.scene}") from error
    return painter(movement)

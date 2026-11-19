"""Paint Quiet Machinery A-02, *Instruments for Measuring Dusk*, as six room-scale instruments.

Each chapter is one instrument in its own geometry: an iris of blades, two crossing sheets,
a glowing bell body with rings across its plane, salt fault lines, a warm room whose window
widens, and a guyed mast that lights at the end. Score notes place marks only while energy
is nonzero, and each mark ramps in rather than stepping on its onset; smoothed audio and
note envelopes move geometry and light, and picture time drives
drift. A zero picture step holds the last image. The painter is independent of the A-01 rooms
family, which keeps its own sculptures. No state is global.
"""

from __future__ import annotations

import math

import numpy as np

from ..color import linear
from ..draw import disc, ease_in_out, lines, points, ring, segments
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


def _edge(distance, soft: float = _EDGE):
    """Return a 0..1 coverage ramp of a signed distance, positive inside, with width `soft`."""
    return np.clip(distance / soft + 0.5, 0, 1).astype(np.float32)


def _rise(t: float, onset):
    """Return a 0..1 attack ramp for marks: seconds since onset over `_ATTACK_S`, clipped."""
    return np.clip((t - onset) / _ATTACK_S, 0, 1).astype(np.float32)


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
        down = ((surface.v + 1) * 0.5)[..., None]
        self._background = ((1 - down) * self.base * 0.85 + down * self.base * 0.35).astype(
            np.float32
        )
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
        target = np.zeros(_CHANNELS, dtype=np.float32)
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
        """Return up to the last 32 notes of `part` starting within `window_s` seconds.

        Zero energy or a missing score yields no notes, so audio-free frames ignore the score.
        """
        if not frame.energy or frame.score is None:
            return _EMPTY
        return frame.score.recent(part, frame.t, window_s)[-32:]

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
    """An iris of nine blades that open with the vibraphone; marimba cell ticks ring its rim."""

    RIM = 0.5

    def _paint(self, surface, frame, arc):
        opening = 0.25 + 0.5 * self._mod[_VIBES] + 0.2 * arc
        angle = np.arange(9, dtype=np.float32) / 9 * 2 * np.pi + frame.tau * 0.01
        x0, y0 = self.RIM * np.cos(angle), self.RIM * np.sin(angle)
        x1 = self.RIM * opening * np.cos(angle + 1.1)
        y1 = self.RIM * opening * np.sin(angle + 1.1)
        self._layer.fill(0)
        segments(surface, self._layer, x0, y0, x1, y1, 0.8)
        surface.add(self._layer, self.cool, 0.45)
        surface.add(ring(surface, 0.0, 0.0, self.RIM, 0.012, soft=0.008), self.cool, 0.25)
        core = np.exp(-(surface.u**2 + surface.v**2) / (0.02 + 0.06 * opening**2))
        surface.add(core, self.warm, 0.05 + 0.2 * self._mod[_VIBES])
        notes = self._recent(frame, "marimba", _MARIMBA_S)
        if len(notes):
            age = ((frame.t - notes["onset"]) / _MARIMBA_S).astype(np.float32)
            theta = (notes["midi"].astype(int) % 12) / 12 * 2 * np.pi - np.pi / 2
            inner, outer = self.RIM * 1.04, self.RIM * 1.14
            self._detail.fill(0)
            segments(
                surface,
                self._detail,
                inner * np.cos(theta),
                inner * np.sin(theta),
                outer * np.cos(theta),
                outer * np.sin(theta),
                np.clip(1 - age, 0, 1) * notes["vel"] * 0.8 * _rise(frame.t, notes["onset"]),
            )
            surface.add(self._detail, self.warm, 1.0)


class _Sheets(_Dusk):
    """Two ribbons that cross left of centre: the clarinet low and warm, the flute high and cool."""

    def _paint(self, surface, frame, arc):
        s = surface.u / self.half_w
        drift = 0.02 * np.sin(frame.tau * 0.1)
        clarinet_notes = self._recent(frame, "clarinet", 6)
        flute_notes = self._recent(frame, "flute", 6)
        clarinet = self._glide(_GLIDE_CLARINET, clarinet_notes, frame, self._pitch(clarinet_notes))
        flute = self._glide(_GLIDE_FLUTE, flute_notes, frame, self._pitch(flute_notes))
        self._ribbon(surface, s, 0.24 + 0.3 * s + drift, clarinet, self.warm, self._mod[_CLARINET])
        self._ribbon(surface, s, -0.16 - 0.3 * s - drift, flute, self.cool, self._mod[_FLUTE])

    def _ribbon(self, surface, s, centre, pitch, color, light):
        """Add one sheet whose centreline bows with its last note; light thickens its band."""
        centre = centre - 0.2 * pitch * (1 - s * s)
        half = 0.045 + 0.03 * light
        coverage = np.minimum(
            _edge(surface.v - (centre - half)), _edge((centre + half) - surface.v)
        )
        surface.add(coverage, color, 0.12 + 0.5 * light)


class _Bell(_Dusk):
    """A glowing bell body that vibraphone decay fills; each vibes note rings its plane."""

    CROWN = -0.56
    RIM = 0.36
    HALF_WIDTH = 0.2

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
        # A slow ring leaves the rim every six picture seconds, so the bell moves without notes.
        # Its light rises and falls to zero within the cycle, so the wrap never steps light.
        phase = (frame.tau / 6.0) % 1.0
        slow = ring(surface, 0.0, self.RIM + 0.03, self.HALF_WIDTH * (0.6 + 1.6 * phase), 0.012)
        surface.add(slow, self.cool, 0.2 * math.sin(math.pi * phase))
        for note in self._recent(frame, "vibes", _VIBES_S)[-8:]:
            age = (frame.t - float(note["onset"])) / _VIBES_S
            x = (int(note["midi"]) % 12 / 11 - 0.5) * 0.4
            radius = self.HALF_WIDTH * (0.6 + 1.6 * age)
            band = ring(surface, x, self.RIM + 0.03, radius, 0.01 + 0.01 * (1 - age), squash=0.22)
            gain = (1 - age) * float(note["vel"]) * 0.45 * float(_rise(frame.t, note["onset"]))
            surface.add(band, self.warm, gain)


class _Faults(_Dusk):
    """Seven salt fault lines that slip with the bass; marimba notes leave copper crystals."""

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
        self._stroke(
            surface,
            xs,
            np.broadcast_to(_FAULT_Y, xs.shape),
            self.cool,
            0.5 + 0.8 * self._mod[_BASS],
            0.25 + 0.2 * self._mod[_BASS],
        )
        g = self.grains
        grain_y = ((g[:, 1] + frame.tau * 0.004) % 1) * 2 - 1
        self._detail.fill(0)
        points(
            surface,
            self._detail,
            self._grain_x,
            grain_y,
            (0.03 + 0.08 * self._mod[_AIR]) * (0.3 + g[:, 2]),
        )
        surface.add(self._detail, self.cool, 0.8)
        notes = self._recent(frame, "marimba", _MARIMBA_S)
        if len(notes):
            midi = notes["midi"].astype(int)
            age = np.clip((frame.t - notes["onset"]) / _MARIMBA_S, 0, 1)
            crystal_y = -0.9 + 1.8 * ((midi * 5) % 11) / 10
            crystal_x = self._fault_x(midi % self.LINES, crystal_y, slip, amp, phase)
            self._detail.fill(0)
            light = (1 - age) * notes["vel"] * 1.2 * _rise(frame.t, notes["onset"])
            points(surface, self._detail, crystal_x, crystal_y, light)
            surface.add(self._detail, self.warm, 1.0)


class _WarmRoom(_Dusk):
    """A one-point room whose back window widens across the track; flute light spills out."""

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


class _Mast(_Dusk):
    """A guyed mast whose head sways in picture time, rings on accented percussion, lights late."""

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
        notes = self._recent(frame, "perc", _PERC_S)
        notes = notes[notes["vel"] >= self.ACCENT * frame.energy][-6:]
        for note in notes:
            age = (frame.t - float(note["onset"])) / _PERC_S
            band = ring(surface, tip_x, self.TIP, 0.02 + 0.45 * age, 0.012, soft=0.008)
            surface.add(band, self.warm, (1 - age) * 0.7 * float(_rise(frame.t, note["onset"])))
        lit = float(np.clip((frame.tau / max(self.movement.duration_s, 1) - 0.8) / 0.2, 0, 1))
        surface.add(disc(surface, tip_x, self.TIP, 0.014, soft=0.006), self.warm, 0.2 + 0.7 * lit)
        halo = np.exp(-((surface.u - tip_x) ** 2 + (surface.v - self.TIP) ** 2) / 0.03)
        surface.add(halo, self.warm, 0.12 * lit)


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

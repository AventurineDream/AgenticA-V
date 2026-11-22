"""Paint Coupon Seance A-02's six haunted-store pictures for the mosaic Stage.

The album's orbit throughline is shared: rings whose register follows the bass, keys as
points by pitch class, a bowed violin memory line, the theremin ghost line and price-gun
blips. Each chapter adds its own structure: a perihelion sun, a ghost outline, a
perspective aisle with ceiling tubes, a coin return, a layaway rail around a dying star,
and an orbit that reopens into a spray of change. Geometry follows picture time; score
notes place small marks that ramp in rather than step, bass onsets swell ring radius
rather than brightness, and audio envelopes only move geometry or slow glow. Held
pictures repeat exactly when picture dt is zero, and zero energy ignores every
audio-driven and score-driven term. No state is global.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from ..color import linear
from ..draw import disc, ease_in_out, lines, points, ring
from ..scene import Frame, Movement, Scene
from ..score import NOTE
from ..surface import Surface

_TAU = 2 * math.pi
# Perihelion's page colors (background, warm, cool); used when a track carries no palette.
_DEFAULT_PALETTE = ("#120d24", "#f0b45a", "#7fd8e6")
# Scene-unit height is 2 (v runs -1..1); the orbit centre sits just below mid-height.
_CY = 0.04
_SMOOTH_S = 0.65
_MARK_WINDOW_S = 2.2
_BASS, _VIOLIN, _HUM, _SECTION = range(4)
_CHANNELS = 4
# Seconds over which a keys point or a bass ring swell reaches full size, so an onset
# never steps a mark from dark to full light within one frame.
_ATTACK_S = 0.12
_S9 = np.linspace(0, 1, 9, dtype=np.float32)
_ELLIPSE_T = np.linspace(0, 1, 129, dtype=np.float32)
_GRID_ROWS = ((np.arange(8, dtype=np.float32) + 1) / 8) ** 1.6
_GRID_SLANT = (np.arange(8, dtype=np.float32) - 3.5) * 0.012
_GRID_WOBBLE = 0.01 * np.sin(np.arange(8, dtype=np.float32))
_DOME = np.linspace(0, math.pi, 33, dtype=np.float32)
_TAPER = np.linspace(0, 1, 5, dtype=np.float32)[1:-1]
_HEM = np.linspace(-0.8, 0.8, 17, dtype=np.float32)
_SCALLOP = np.abs(np.sin(np.linspace(0, 4 * math.pi, 17, dtype=np.float32)))
_NO_NOTES = np.empty(0, dtype=NOTE)
_NO_NOTES.flags.writeable = False


def _recent(frame: Frame, part: str, window: float) -> np.ndarray:
    """Return the score notes of one part that started in the last window seconds.

    Args:
        frame: Current frame; a missing score yields no notes.
        part: Score part name, such as bass or violin.
        window: Look-back in movement seconds.

    Returns:
        A read-only NOTE array, possibly empty.
    """
    if frame.score is None:
        return _NO_NOTES
    return frame.score.recent(part, frame.t, window)


def _is_voice(frame: Frame, notes: np.ndarray, name: str) -> np.ndarray:
    """Return a mask of notes whose score voice is name; a missing name matches nothing.

    Args:
        frame: Current frame, supplying the score's voice table.
        notes: NOTE rows to test.
        name: Voice name such as blip or side-slip.

    Returns:
        A boolean array with one entry per note.
    """
    voices = frame.score.voices if frame.score is not None else ()
    if name not in voices or not len(notes):
        return np.zeros(len(notes), dtype=bool)
    return notes["voice"] == voices.index(name)


def _ellipse(cx: float, cy: float, rx: float, ry: float, angle: float, start=0.0, stop=_TAU):
    """Return the vertices of a rotated, possibly partial, ellipse in scene units.

    Args:
        cx: Centre x in scene units.
        cy: Centre y in scene units, positive downward.
        rx: Horizontal semi-axis before rotation, in scene units.
        ry: Vertical semi-axis before rotation, in scene units.
        angle: Clockwise rotation in radians.
        start: First parameter angle in radians.
        stop: Last parameter angle in radians; equal to start+2*pi closes the ring.

    Returns:
        Two float32 arrays of 129 vertices each.
    """
    theta = start + (stop - start) * _ELLIPSE_T
    px, py = rx * np.cos(theta), ry * np.sin(theta)
    c, s = math.cos(angle), math.sin(angle)
    return (cx + px * c - py * s).astype(np.float32), (cy + px * s + py * c).astype(np.float32)


def _ribbon_xy(midi: np.ndarray, age: np.ndarray, side: float):
    """Return the scene position of a bowed or glided note's head after age seconds.

    Args:
        midi: Note numbers; pitch sets the height on the ribbon band.
        age: Seconds since onset; the head drifts toward the outer edge with age.
        side: +1 for the violin's right band, -1 for the theremin's left band.

    Returns:
        Two float32 arrays of scene coordinates.
    """
    x = side * 0.2 - side * 0.14 * age
    y = 0.72 - (midi - 52) / 40 * 1.44
    return x.astype(np.float32), y.astype(np.float32)


def _ghost_outline(cx: float, cy: float, r: float):
    """Return a sheet-ghost outline: a dome, tapered sides and a scalloped hem.

    Args:
        cx: Centre x in scene units.
        cy: Top of the dome's centre line in scene units, positive downward.
        r: Half-width and dome radius in scene units.

    Returns:
        Two float32 arrays of closed-path vertices.
    """
    body = 1.5 * r
    # The sheet tapers from its shoulders to a narrower hem, so it does not read as a box.
    left_x = cx - r + 0.2 * r * _TAPER
    left_y = cy + body * _TAPER
    hem_x = cx + r * _HEM
    hem_y = cy + body + 0.25 * r * _SCALLOP
    right_x = (2 * cx - left_x)[::-1]
    right_y = left_y[::-1]
    x = np.concatenate((cx + r * np.cos(_DOME), left_x, hem_x, right_x))
    y = np.concatenate((cy - r * np.sin(_DOME), left_y, hem_y, right_y))
    return x.astype(np.float32), y.astype(np.float32)


def _meter_cells(meter):
    """Return the column boundaries within one bar and the bar's column count.

    Args:
        meter: Beats and denominator, or None; 7/8 groups as 2+2+3 and 5/4 as 3+2.

    Returns:
        A tuple of boundary offsets and the bar's total column count.
    """
    if meter == (7, 8):
        return (0, 2, 4), 7
    if meter == (5, 4):
        return (0, 3), 5
    num = meter[0] if meter else 4
    return tuple(range(num)), num


class _Haunt(Scene):
    """Own the shared orbit, ribbon, blip and key machinery for the six haunted scenes.

    Subclasses set the TILT, OPEN, GRAVITY, GHOST and GRID constants that the album's
    visual spec gives each scene, then add structure in `_back` and `_front`. Score
    parts listed in MARKS receive a small point per recent note each frame.
    """

    MARKS: tuple[str, ...] = ("keys", "violin")
    TILT = 0.34
    OPEN = 0.0
    GRAVITY = 0.1
    GHOST = 0.3
    GRID = 0.0
    # Ring brightness is a per-scene knob so a strong grid can dominate the aisle.
    RING_GAIN = 1.0

    def __init__(self, movement: Movement):
        super().__init__(movement)
        palette = (tuple(movement.palette) + _DEFAULT_PALETTE)[:3]
        self.bg, self.warm, self.cool = (linear(c) for c in palette)
        self.bpm = movement.bpm or 96.0
        rng = np.random.default_rng(movement.seed)
        self.coins = rng.uniform(0, 1, (6, 2)).astype(np.float32)
        self._shape = None
        self._held = None
        self._mod = np.zeros(_CHANNELS, dtype=np.float32)
        self._target = np.zeros_like(self._mod)

    def resize(self, surface: Surface) -> None:
        """Rebuild the background, vignette and scratch layers for a canvas.

        Args:
            surface: Target canvas; musical and picture clocks are not advanced.
        """
        self._shape = surface.rgb.shape
        self._half_w = surface.half_w
        self._layer = surface.layer()
        self._detail = surface.layer()
        self._held = None
        u = surface.u / surface.half_w
        v = surface.v
        texture = (
            1
            + 0.06 * np.sin(u * 41 + v * 23 + self.coins[0, 0] * _TAU)
            + 0.04 * np.sin(v * 57 - u * 19 + self.coins[1, 1] * _TAU)
        )
        self._background = (self.bg * texture[..., None]).astype(np.float32)
        self._vignette = np.clip(
            1.06 - 0.3 * (surface.v**2 + (surface.u / surface.half_w) ** 2), 0.2, 1
        ).astype(np.float32)

    def seek(self) -> None:
        """Drop the held picture and smoothed envelopes after a discontinuous clock jump."""
        self._held = None
        self._mod.fill(0)

    def _progress(self, frame: Frame) -> float:
        """Return the movement's eased picture progress, clamped to 0..1.

        Args:
            frame: Frame whose picture clock supplies tau.

        Returns:
            Eased fraction of the movement elapsed in picture time.
        """
        return float(ease_in_out(frame.tau / max(self.movement.duration_s, 1)))

    def _signals(self, frame: Frame) -> None:
        """Smooth this picture's musical targets into `self._mod`; zero energy clears them.

        Levels and score velocities arrive already scaled by energy from Stage, so this
        method only selects the channels and integrates them over picture time.

        Args:
            frame: Frame with calmed levels, optional score and section, and dt.
        """
        target = self._target
        target.fill(0)
        if frame.energy:
            level, score, t = frame.levels, frame.score, frame.t
            target[_BASS] = level.slow_bass
            target[_VIOLIN] = level.slow_loud
            target[_HUM] = level.hat
            if score is not None:
                target[_BASS] = max(target[_BASS], score.level("bass", t, decay_s=0.8))
                target[_VIOLIN] = max(target[_VIOLIN], score.level("violin", t, decay_s=1.2))
                # The tube's room-air noise is a single slow hum, not a per-beat cue.
                target[_HUM] = max(target[_HUM], score.level("tube", t, decay_s=2.0, kind="noise"))
            if frame.section is not None:
                target[_SECTION] = frame.section.intensity
        blend = -math.expm1(-max(frame.dt, 0) / _SMOOTH_S)
        self._mod += (target - self._mod) * blend
        if frame.energy == 0:
            self._mod.fill(0)

    def _stroke(self, surface, x, y, color, weight=1.0):
        """Add one scalar polyline layer tinted with color; weights follow `lines`.

        Args:
            surface: Canvas to accumulate into.
            x: Polyline x vertices in scene units, shape (..., n).
            y: Polyline y vertices in scene units, same shape.
            color: Linear RGB or hex tint.
            weight: Energy per sub-pixel of stroke length, scalar or per polyline.
        """
        self._layer.fill(0)
        lines(surface, self._layer, x, y, weight)
        surface.add(self._layer, color)

    def _glow(self, surface, color, gain, radius=0.75):
        """Add a warm or cool radial bloom centred on the orbit.

        Args:
            surface: Canvas to accumulate into.
            color: Linear RGB or hex tint.
            gain: Linear intensity multiplier.
            radius: Scene-unit e-folding radius of the bloom.
        """
        r2 = surface.u**2 + (surface.v - _CY) ** 2
        surface.add(np.exp(-r2 / (radius * radius)), color, gain)

    def _grid(self, surface, frame):
        """Draw the crooked, perspective grid that follows the bar's meter groupings.

        Column lean follows a continuous, alternating bar phase and the bass envelope
        pushes its amplitude; strength is the scene's GRID constant, so zero draws nothing.

        Args:
            surface: Canvas to accumulate into.
            frame: Frame whose picture clock sets the smooth bar phase and sway.
        """
        if self.GRID <= 0:
            return
        bounds, total = _meter_cells(self.movement.meter)
        push = float(self._mod[_BASS])
        # Tempo counts quarter notes, so a 7/8 bar lasts 3.5 beats, not its 7 columns.
        meter = self.movement.meter or (4, 4)
        bar_phase = frame.tau * self.bpm / 60 / (meter[0] * 4 / meter[1])
        lean = 0.07 * (1 + push) * math.cos(math.pi * bar_phase)
        k = np.arange(-6, 7, dtype=np.float32)[:, None]
        g = np.asarray(bounds, dtype=np.float32)[None, :]
        xb = ((k * total + g) / total * 0.42 + lean).reshape(-1)
        xb = xb + 0.01 * np.sin(frame.tau * 0.11 + k.reshape(-1).repeat(len(bounds)))
        x = (xb[:, None] * _S9[None, :]).astype(np.float32)
        y = (-0.2 + 1.2 * _S9[None, :]).astype(np.float32)
        weight = self.GRID * np.where(
            np.broadcast_to(g, (13, len(bounds))).reshape(-1) == 0, 0.2, 0.09
        )
        self._stroke(surface, x, np.broadcast_to(y, x.shape), self.cool, weight.astype(np.float32))
        v = -0.2 + 1.2 * _GRID_ROWS
        slope = _GRID_SLANT + push * _GRID_WOBBLE
        xs = np.broadcast_to(np.array([-self._half_w, self._half_w], np.float32), (8, 2))
        ys = (v[:, None] + slope[:, None] * xs / self._half_w).astype(np.float32)
        self._stroke(surface, xs, ys, self.cool, np.full(8, self.GRID * 0.09, np.float32))

    def _orbit(self, surface, frame, arc):
        """Draw seven flattened rings; the sounding bass register swells outward.

        Bass onsets move geometry only: the matching ring's radius eases out over
        `_ATTACK_S` and back after the gate. Ring brightness follows the smoothed bass
        envelope, so it never steps on a beat.

        Args:
            surface: Canvas to accumulate into.
            frame: Frame whose picture clock sets slow drift and whose score gives bass.
            arc: Eased picture progress in 0..1; it opens rings and pulls them inward.
        """
        opened = self.OPEN * min(1.0, arc * 1.3)
        start = 0.9 * opened
        angle = -0.18 + math.sin(frame.tau * 0.03) * 0.04
        bass = _recent(frame, "bass", 4)
        bass = bass[bass["onset"] + bass["gate"] + 0.25 >= frame.t]
        register = np.clip(np.floor((bass["midi"] - 28) / 4), 0, 6).astype(int)
        rise = np.clip((frame.t - bass["onset"]) / _ATTACK_S, 0, 1)
        fall = 1 - np.clip((frame.t - bass["onset"] - bass["gate"]) / 0.25, 0, 1)
        swell = bass["vel"] * rise * fall
        gain = (0.5 + 0.4 * float(self._mod[_BASS])) * self.RING_GAIN
        for r in range(7):
            base = 2 * (0.12 + r * 0.055) * (1 + opened * 0.6) * (1 - self.GRAVITY * 0.35 * arc)
            weight = float(swell[register == r].max()) if np.any(register == r) else 0.0
            base *= 1 + 0.06 * weight
            x, y = _ellipse(0.0, _CY, base, base * self.TILT, angle, start, _TAU - start * 0.5)
            self._stroke(surface, x, y, self.warm, gain)

    def _motif(self, surface, frame):
        """Draw one faint full orbit back over the scene in the score's final section.

        Args:
            surface: Canvas to accumulate into.
            frame: Frame whose section must be the score's last to show the motif.
        """
        score = frame.score
        if score is None or frame.section is None or not score.sections:
            return
        if frame.section != score.sections[-1]:
            return
        x, y = _ellipse(0.0, _CY, 0.92, 0.92 * self.TILT, -0.18)
        self._stroke(surface, x, y, self.cool, 0.25)

    def _key_xy(self, notes, age, frame):
        """Return scene positions of keys voicings; the default places them on the orbit.

        Args:
            notes: NOTE rows of the keys part.
            age: Seconds since each onset, same length as notes.
            frame: Frame supplying picture time and progress.

        Returns:
            Two float32 arrays of scene coordinates.
        """
        midi = notes["midi"]
        angle = (midi % 12) / 12 * _TAU + 0.015 * frame.tau
        opened = self.OPEN * min(1.0, self._progress(frame) * 1.3)
        radius = 2 * (0.14 + (midi - 48) * 0.0062) * (1 + opened * 0.6)
        return (
            (radius * np.cos(angle)).astype(np.float32),
            (_CY + radius * np.sin(angle) * self.TILT * 1.6).astype(np.float32),
        )

    def _ribbon(self, surface, notes, color, side, frame, memory, weight):
        """Draw bowed or glided lines whose recent past drifts outward and fades.

        Args:
            surface: Canvas to accumulate into.
            notes: NOTE rows whose onset lies in the memory window.
            color: Linear RGB or hex tint.
            side: +1 for the violin band, -1 for the theremin band.
            frame: Frame supplying the score clock and picture clock.
            memory: Fade length in seconds.
            weight: Overall energy scale for the ribbon.
        """
        t = frame.t
        end = np.minimum(t, notes["onset"] + notes["gate"])
        live = end >= notes["onset"]
        notes, end = notes[live], end[live]
        if not len(notes):
            return
        age = np.clip((t - end) / memory, 0, 1)
        shade = ((1 - age) * (0.25 + 0.6 * notes["vel"]) * weight).astype(np.float32)
        x0 = side * 0.2 - side * 0.14 * (t - notes["onset"])
        x1 = side * 0.2 - side * 0.14 * (t - end)
        x = x0[:, None] + (x1 - x0)[:, None] * _S9[None, :]
        y_base = 0.72 - (notes["midi"] - 52) / 40 * 1.44
        bend = 0.04 * (1 + self.GRAVITY) * np.sin(notes["onset"] * 1.3 + frame.tau * 0.2)
        y = y_base[:, None] - bend[:, None] * np.sin(np.pi * _S9)[None, :]
        self._stroke(surface, x.astype(np.float32), y.astype(np.float32), color, shade)

    def _keys(self, surface, frame):
        """Place the keys voicings as points; side-slips sit a step off and tint cool.

        Args:
            surface: Canvas to accumulate into.
            frame: Frame whose score supplies recent keys and voices.
        """
        keys = _recent(frame, "keys", 3)
        if not len(keys):
            return
        age = frame.t - keys["onset"]
        held = age <= keys["gate"]
        fade = np.clip(1 - (age - keys["gate"]) / 1.2, 0, 1)
        rise = np.clip(age / _ATTACK_S, 0, 1)
        strength = keys["vel"] * rise * np.where(held, 1.0, fade)
        live = strength > 0.01
        slip = _is_voice(frame, keys, "side-slip")
        x, y = self._key_xy(keys, age, frame)
        x = x + 0.024 * slip
        y = y - 0.024 * slip
        for mask, color, gain in ((live & ~slip, self.warm, 0.85), (live & slip, self.cool, 0.6)):
            if not np.any(mask):
                continue
            self._detail.fill(0)
            points(surface, self._detail, x[mask], y[mask], 0.3 * strength[mask])
            surface.add(self._detail, color, gain)

    def _blips(self, surface, frame):
        """Draw price-gun blips as sparks that spread from the orbit and fade in 1.2 s.

        Args:
            surface: Canvas to accumulate into.
            frame: Frame whose score supplies recent ether blips.
        """
        ether = _recent(frame, "ether", 1.2)
        blips = ether[_is_voice(frame, ether, "blip")]
        if not len(blips):
            return
        age = (frame.t - blips["onset"]) / 1.2
        live = (age >= 0) & (age < 1)
        blips, age = blips[live], age[live]
        if not len(blips):
            return
        angle = (blips["midi"] % 12) / 12 * _TAU - 0.02 * frame.tau
        radius = 2 * (0.42 + age * 0.08)
        self._detail.fill(0)
        points(
            surface,
            self._detail,
            (radius * np.cos(angle)).astype(np.float32),
            (_CY + radius * np.sin(angle)).astype(np.float32),
            ((1 - age) * 0.9 * blips["vel"] * 0.15).astype(np.float32),
        )
        surface.add(self._detail, self.cool, 0.9)

    def _strands(self, surface, frame):
        """Draw the shared violin memory line, theremin ghost line, keys and blips.

        Args:
            surface: Canvas to accumulate into.
            frame: Frame whose score supplies the parts and whose GHOST sets memory length.
        """
        memory = 4 + 6 * self.GHOST
        self._ribbon(surface, _recent(frame, "violin", memory), self.warm, 1, frame, memory, 1.2)
        ether = _recent(frame, "ether", memory)
        self._ribbon(
            surface,
            ether[~_is_voice(frame, ether, "blip")],
            self.cool,
            -1,
            frame,
            memory,
            0.7,
        )
        self._keys(surface, frame)
        self._blips(surface, frame)

    def _place(self, part, notes, age, frame: Frame):
        """Return scene coordinates of the marks for `notes`, dispatching on the part.

        Args:
            part: Score part whose recent notes are marked.
            notes: NOTE rows of that part.
            age: Seconds since each onset.
            frame: Current frame.

        Returns:
            Two float32 arrays of scene coordinates.
        """
        if part == "keys":
            return self._key_xy(notes, age, frame)
        if part == "violin":
            return _ribbon_xy(notes["midi"], age, 1)
        if part == "ether":
            return _ribbon_xy(notes["midi"], age, -1)
        return self._place_scene(part, notes, age, frame)

    def _place_scene(self, part, notes, age, frame: Frame):
        """Place bass marks on the ring of their register; scenes may override.

        Args:
            part: Score part name; only bass is used by default.
            notes: NOTE rows of that part.
            age: Seconds since each onset.
            frame: Current frame.

        Returns:
            Two float32 arrays of scene coordinates.
        """
        midi = notes["midi"]
        r = np.clip(np.floor((midi - 28) / 4), 0, 6)
        arc = self._progress(frame)
        base = 2 * (0.12 + r * 0.055) * (1 + self.OPEN * 0.6) * (1 - self.GRAVITY * 0.35 * arc)
        angle = (midi % 12) / 12 * _TAU
        return (
            (base * np.cos(angle)).astype(np.float32),
            (_CY + base * np.sin(angle) * self.TILT).astype(np.float32),
        )

    def _marks(self, surface: Surface, frame: Frame) -> None:
        """Place a point for each recent note of `MARKS`; silent or zero-energy frames skip.

        Args:
            surface: Canvas to accumulate into.
            frame: Current frame; zero energy or no score draws nothing.
        """
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
            surface.add(self._detail, self.warm, 0.8)

    def _back(self, surface: Surface, frame: Frame, arc: float) -> None:
        """Paint what sits behind the orbit; scenes override this.

        Args:
            surface: Canvas to accumulate into.
            frame: Current frame.
            arc: Eased picture progress.
        """

    def _front(self, surface: Surface, frame: Frame, arc: float) -> None:
        """Paint structure in front of the orbit; scenes override this.

        Args:
            surface: Canvas to accumulate into.
            frame: Current frame.
            arc: Eased picture progress.
        """

    def _paint(self, surface: Surface, frame: Frame, arc: float) -> None:
        """Paint the chapter's full geometry in back-to-front order.

        Args:
            surface: Canvas to accumulate into.
            frame: Current frame.
            arc: Eased picture progress.
        """
        self._grid(surface, frame)
        self._back(surface, frame, arc)
        self._orbit(surface, frame, arc)
        self._strands(surface, frame)
        self._front(surface, frame, arc)
        self._motif(surface, frame)

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
        if not frame.energy:
            frame = replace(frame, score=None, section=None)
        surface.rgb[:] = self._background
        self._signals(frame)
        self._paint(surface, frame, self._progress(frame))
        self._marks(surface, frame)
        surface.rgb *= self._vignette[..., None]
        if self._held is None:
            self._held = np.empty_like(surface.rgb)
        self._held[:] = surface.rgb


class _Perihelion(_Haunt):
    """Pass the sun at perihelion: a warm core inside flat rings, with the orbit at rest."""

    TILT = 0.34
    GRAVITY = 0.1
    GHOST = 0.3

    def _back(self, surface, frame, arc):
        self._glow(surface, self.warm, 0.07 + 0.1 * self._mod[_SECTION], radius=0.9)
        radius = 0.05 + 0.02 * self._mod[_BASS]
        surface.add(disc(surface, 0.0, _CY, radius, soft=0.02), self.warm, 0.5)


class _HauntFree(_Haunt):
    """A pale ghost drifts across the orbit and trails a second, dimmer copy of itself."""

    MARKS = ("violin", "ether")
    TILT = 0.5
    OPEN = 0.1
    GRAVITY = 0.15
    GHOST = 0.6

    def _front(self, surface, frame, arc):
        gx = 0.55 * math.sin(frame.tau * 0.05 + 0.8)
        gy = -0.25 + 0.04 * math.sin(frame.tau * 0.11)
        weight = 0.35 + 0.6 * self._mod[_VIOLIN] + 0.2 * self._mod[_SECTION]
        for lag, gain in ((0.0, 1.0), (0.35, 0.4)):
            x, y = _ghost_outline(gx - lag, gy, 0.26)
            self._stroke(surface, x, y, self.cool, weight * gain)
        self._detail.fill(0)
        eyes_x = np.array([gx - 0.08, gx + 0.08], np.float32)
        points(surface, self._detail, eyes_x, np.full(2, gy - 0.02, np.float32), 0.25)
        surface.add(self._detail, self.warm, 0.9)


class _Aisle(_Haunt):
    """A fluorescent aisle: perspective shelves and columns under ceiling tubes."""

    MARKS = ("keys", "bass")
    TILT = 0.22
    GRAVITY = 0.0
    GHOST = 0.2
    GRID = 1.0
    RING_GAIN = 0.45

    def _back(self, surface, frame, arc):
        hum = float(self._mod[_HUM])
        for i in range(3):
            v = -0.9 + 0.22 * i
            x = np.array([[-0.9, 0.9]], np.float32)
            y = np.full((1, 2), v, np.float32)
            self._stroke(surface, x, y, self.warm, 1.0 + 0.6 * hum)

    def _place_scene(self, part, notes, age, frame: Frame):
        if part != "bass":
            return super()._place_scene(part, notes, age, frame)
        bounds, total = _meter_cells(self.movement.meter)
        k = (notes["midi"].astype(int) % 13) - 6
        g = np.asarray(bounds)[(notes["midi"].astype(int) // 13) % len(bounds)]
        xb = (k * total + g) / total * 0.42
        row = ((np.arange(8, dtype=np.float32) + 1) / 8) ** 1.6
        s = row[notes["midi"].astype(int) % 8]
        return (xb * s).astype(np.float32), (-0.2 + 1.2 * s).astype(np.float32)


class _CoinReturn(_Haunt):
    """A tilted coin above a return slot, with coins falling back through the ghost trace."""

    TILT = 0.62
    GRAVITY = 0.25
    GHOST = 1.0

    def _back(self, surface, frame, arc):
        self._glow(surface, self.cool, 0.05, radius=0.8)
        x = np.array([[-0.32, 0.32]], np.float32)
        y = np.full((1, 2), 0.84, np.float32)
        self._stroke(surface, x, y, self.warm, 1.1)

    def _front(self, surface, frame, arc):
        tilt = -0.18 + 0.1 * math.sin(frame.tau * 0.05)
        face = ring(surface, 0.0, -0.1, 0.21, 0.42, squash=self.TILT, angle=tilt, soft=0.01)
        surface.add(face, self.warm, 0.12)
        rim = ring(surface, 0.0, -0.1, 0.42, 0.04, squash=self.TILT, angle=tilt, soft=0.01)
        surface.add(rim, self.warm, 0.9)
        for i in range(6):
            fall = (self.coins[i, 1] + frame.tau * 0.06 * (0.6 + self.coins[i, 0])) % 1.5
            cy = -0.95 + fall / 1.5 * 1.8
            cx = 0.45 * (2 * self.coins[i, 0] - 1)
            phase = fall / 1.5
            edge = min(phase, 1 - phase) / 0.12
            edge = min(1.0, max(0.0, edge))
            fade = edge * edge * (3 - 2 * edge)
            x, y = _ellipse(cx, cy, 0.07, 0.07 * self.TILT, tilt)
            self._stroke(surface, x, y, self.warm, float(0.5 * fade))


class _Layaway(_Haunt):
    """A dying star on a layaway rail: orbits contract toward it and its light dims."""

    MARKS = ("bass", "keys")
    TILT = 0.4
    GRAVITY = 0.9
    GHOST = 0.4
    GRID = 0.2

    def _back(self, surface, frame, arc):
        # Zero energy clears the section, so silence keeps the star at its lowest glow.
        intensity = frame.section.intensity if frame.section is not None else 0.0
        dim = 1 - 0.7 * arc
        r2 = surface.u**2 + (surface.v - _CY) ** 2
        surface.add(np.exp(-r2 / (2 * 0.09**2)), self.warm, 0.75 * dim * (0.6 + 0.4 * intensity))
        surface.add(
            disc(surface, 0.0, _CY, 0.05 * (1 - 0.6 * arc), soft=0.01), self.warm, 0.6 * dim
        )

    def _front(self, surface, frame, arc):
        rail_y = np.full((1, 2), 0.62, np.float32)
        self._stroke(surface, np.array([[-0.9, 0.9]], np.float32), rail_y, self.cool, 0.7)
        tags_x = np.linspace(-0.72, 0.72, 5, dtype=np.float32)
        sway = 0.01 * np.sin(frame.tau * 0.2 + np.arange(5, dtype=np.float32))
        tip = 0.74 + sway
        x = np.stack((tags_x, tags_x), axis=-1)
        y = np.stack((np.full(5, 0.62, np.float32), tip), axis=-1)
        self._stroke(surface, x, y, self.cool, np.full(5, 0.5, np.float32))
        self._detail.fill(0)
        points(surface, self._detail, tags_x, tip, 0.12)
        surface.add(self._detail, self.warm, 0.7)

    def _place_scene(self, part, notes, age, frame: Frame):
        if part != "bass":
            return super()._place_scene(part, notes, age, frame)
        index = notes["midi"].astype(int) % 5
        x = np.linspace(-0.72, 0.72, 5, dtype=np.float32)[index]
        return x, np.full(len(x), 0.74, np.float32)


class _Change(_Haunt):
    """An orbit that reopens into arcs, with the keys spraying out as change."""

    TILT = 0.3
    OPEN = 1.0
    GRAVITY = 0.05
    GHOST = 0.5
    GRID = 0.25

    def _key_xy(self, notes, age, frame):
        angle = (notes["midi"] % 12) / 12 * _TAU + 0.02 * frame.tau
        reach = 0.12 + 0.85 * np.clip(age / 3, 0, 1) ** 0.7
        return (
            (reach * np.cos(angle)).astype(np.float32),
            (_CY + reach * np.sin(angle) * 0.8).astype(np.float32),
        )


_SCENES = {
    "perihelion": _Perihelion,
    "haunt-free": _HauntFree,
    "aisle": _Aisle,
    "coin-return": _CoinReturn,
    "layaway": _Layaway,
    "change": _Change,
}


def build_scene(movement: Movement) -> Scene:
    """Construct the seeded painter for one of Coupon Seance A-02's six movements.

    Args:
        movement: Haunt metadata, including the scene key, palette, BPM, meter and seed.

    Returns:
        A scene owning its geometry, signal smoothing and held image.

    Raises:
        ValueError: The movement does not name a known haunt scene.
    """
    try:
        painter = _SCENES[movement.scene]
    except KeyError as error:
        raise ValueError(f"unknown haunt scene: {movement.scene}") from error
    return painter(movement)

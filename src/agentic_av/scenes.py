"""Code-only album scenes restored from the original A/V.html terminal player.

`native.py` draws one of these into its frame on every tick. The four
families (coupon, aquatic, forest, rooms) are ported from the band source
packs' `cli-player/player.py`: the same glyphs, geometry, motion rates, and
xterm-256 palettes. Only the plumbing changed. Scenes draw into a `Canvas`
of characters and ink slots instead of curses, and score activity comes
from a pre-sorted `EventIndex` instead of a scan of every event per frame.

Motion is a pure function of the movement position in seconds and the
scored instrument activity at that time. Nothing listens to the audio
output; the score is a note-activity model, not a loudness measurement.
"""

from __future__ import annotations

import bisect
import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

# Ink slots match the original curses color pairs: 1 accent, 2 text,
# 3 secondary, 4 light, 5 spark, 6 alert. A canvas cell starts at ink 2.
INK_SLOTS = ("accent", "text", "secondary", "light", "spark", "alert")

# Original per-family xterm-256 indices. `bg` is the scene floor.
FAMILY_PALETTES: dict[str, dict[str, int]] = {
    "coupon": {
        "bg": 17,
        "accent": 220,
        "text": 153,
        "secondary": 110,
        "trace": 67,
        "light": 179,
        "spark": 223,
        "alert": 203,
    },
    "aquatic": {
        "bg": 23,
        "accent": 159,
        "text": 195,
        "secondary": 81,
        "trace": 37,
        "light": 123,
        "spark": 195,
        "alert": 203,
    },
    "forest": {
        "bg": 22,
        "accent": 150,
        "text": 194,
        "secondary": 108,
        "trace": 65,
        "light": 151,
        "spark": 186,
        "alert": 220,
    },
    "rooms": {
        "bg": 53,
        "accent": 221,
        "text": 223,
        "secondary": 182,
        "trace": 96,
        "light": 139,
        "spark": 215,
        "alert": 203,
    },
}

# Per-scene floors that override the family `bg`.
SCENE_BACKGROUNDS: dict[str, dict[str, int]] = {
    "coupon": {"commerce": 18, "return": 23},
    "aquatic": {
        "tidal seed": 23,
        "pressure mouths": 17,
        "kelp cathedral": 22,
        "sheared bloom": 24,
        "blue void": 17,
        "reef aperture": 24,
    },
    "forest": {
        "rain": 23,
        "river": 23,
        "spores": 22,
        "canopy": 22,
        "rings": 22,
        "spiral": 22,
        "root": 22,
    },
    "rooms": {
        "aperture": 17,
        "crossing": 53,
        "resonance": 17,
        "orbit": 17,
        "fault": 52,
        "lattice": 52,
        "warmth": 58,
        "void": 58,
        "transmission": 24,
        "dawn": 24,
    },
}

FAMILIES = frozenset(FAMILY_PALETTES)

# Coupon Seance's HTML carries no score data, so its seven scene names come
# from the original player's track table, in album order.
COUPON_SCENES = ("arrival", "friction", "commerce", "pursuit", "memory", "gravity", "return")
COUPON_SCENE_LABELS = (
    "Orbital arrival",
    "Bowed ribbons",
    "Deep-space grid",
    "Orbital traffic",
    "Violin memory",
    "Low-end gravity",
    "Open return",
)
# Drowning Collective's event data has no scene field; the original player
# assigned these six by track index.
AQUATIC_SCENES = (
    "tidal seed",
    "pressure mouths",
    "kelp cathedral",
    "sheared bloom",
    "blue void",
    "reef aperture",
)

_ALIASES = {
    "marimba": "mallet",
    "vibraphone": "bell",
    "flute": "wind",
    "clarinet": "wind",
    "percussion": "drums",
    "tenor": "reeds",
    "baritone": "reeds",
}
# An event never contributes longer than this many seconds after its onset.
_MAX_AGE_S = 2.6


def xterm_hex(index: int) -> str:
    """Return the standard xterm-256 color for `index` as ``#rrggbb``.

    Args:
        index: 0-255. Values outside are clamped.

    Returns:
        Lowercase hex, so the shared renderer can emit truecolor or 256-color.
    """
    index = max(0, min(255, index))
    if index < 16:
        base = (
            (0, 0, 0),
            (128, 0, 0),
            (0, 128, 0),
            (128, 128, 0),
            (0, 0, 128),
            (128, 0, 128),
            (0, 128, 128),
            (192, 192, 192),
            (128, 128, 128),
            (255, 0, 0),
            (0, 255, 0),
            (255, 255, 0),
            (0, 0, 255),
            (255, 0, 255),
            (0, 255, 255),
            (255, 255, 255),
        )
        red, green, blue = base[index]
    elif index < 232:
        steps = (0, 95, 135, 175, 215, 255)
        cube = index - 16
        red, green, blue = steps[cube // 36], steps[(cube // 6) % 6], steps[cube % 6]
    else:
        gray = 8 + (index - 232) * 10
        red = green = blue = gray
    return f"#{red:02x}{green:02x}{blue:02x}"


@dataclass(frozen=True, slots=True)
class SceneColors:
    """Hex colors for one family and scene.

    Attributes:
        background: Scene floor behind every cell.
        inks: Foreground per ink slot, index 0 for ink 1 (see `INK_SLOTS`).
        trace: Frame lines and dim chrome.
    """

    background: str
    inks: tuple[str, ...]
    trace: str

    def ink(self, slot: int) -> str:
        """Return the foreground for a 1-based ink slot; unknown slots use text."""
        return self.inks[slot - 1] if 1 <= slot <= len(self.inks) else self.inks[1]


def scene_colors(family: str, scene: str) -> SceneColors:
    """Return the original palette for `family`, with the scene's floor.

    Args:
        family: One of `FAMILIES`. Unknown families use coupon, as the
            original did.
        scene: Scene name; selects a floor override when one exists.
    """
    palette = FAMILY_PALETTES.get(family, FAMILY_PALETTES["coupon"])
    floor = SCENE_BACKGROUNDS.get(family, {}).get(scene, palette["bg"])
    return SceneColors(
        background=xterm_hex(floor),
        inks=tuple(xterm_hex(palette[name]) for name in INK_SLOTS),
        trace=xterm_hex(palette["trace"]),
    )


class Canvas:
    """A character grid with one ink slot per cell. Out-of-range puts are ignored."""

    def __init__(self, width: int, height: int) -> None:
        """Create a blank grid; sizes below 1 are raised to 1."""
        self.w, self.h = max(1, width), max(1, height)
        self.chars = [[" "] * self.w for _ in range(self.h)]
        self.inks = [[2] * self.w for _ in range(self.h)]

    def put(self, x: int, y: int, char: str, ink: int = 2) -> None:
        """Set one cell to the first character of `char`."""
        if 0 <= x < self.w and 0 <= y < self.h:
            self.chars[y][x] = char[:1]
            self.inks[y][x] = ink

    def line(self, x0: int, y0: int, x1: int, y1: int, char: str = ".", ink: int = 2) -> None:
        """Draw a Bresenham line, endpoints included."""
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.put(x0, y0, char, ink)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def ellipse(
        self, cx: float, cy: float, rx: float, ry: float, char: str, ink: int, phase: float = 0.0
    ) -> None:
        """Plot an ellipse outline; `phase` rotates where the samples fall, in radians."""
        count = max(24, int(2 * math.pi * max(rx, ry) * 1.8))
        for n in range(count):
            angle = n / count * math.tau + phase
            self.put(round(cx + math.cos(angle) * rx), round(cy + math.sin(angle) * ry), char, ink)


@dataclass(frozen=True, slots=True)
class EventIndex:
    """Scored notes for one movement, sorted by onset for windowed lookup.

    Attributes:
        parts: Instrument part per note.
        onsets: Onset in seconds from the movement start, ascending.
        gates: Note length in seconds.
        velocities: 0-1 note velocity.
    """

    parts: tuple[str, ...]
    onsets: tuple[float, ...]
    gates: tuple[float, ...]
    velocities: tuple[float, ...]

    @classmethod
    def build(cls, rows: Sequence[Sequence[object]]) -> EventIndex:
        """Index normalized ``[part, onset_s, gate_s, velocity]`` rows.

        Malformed rows are skipped, as the original scan skipped them.
        """
        clean: list[tuple[float, str, float, float]] = []
        for row in rows:
            try:
                part, onset, gate, velocity = row
                clean.append((float(onset), str(part), float(gate), float(velocity)))
            except (TypeError, ValueError):
                continue
        clean.sort(key=lambda item: item[0])
        return cls(
            parts=tuple(item[1] for item in clean),
            onsets=tuple(item[0] for item in clean),
            gates=tuple(item[2] for item in clean),
            velocities=tuple(item[3] for item in clean),
        )

    def activity(self, position_s: float, family: str) -> dict[str, float]:
        """Return 0-1 activity per instrument at `position_s`.

        Matches the original `event_activity`: a note contributes from its
        onset for its gate plus 150 ms (at least 120 ms gate, at most
        2.6 s), decaying linearly to a 0.12 floor. Parts are aliased to the
        scene vocabulary, then divided by 4.8 for aquatic and 5.5 otherwise.
        """
        energy: dict[str, float] = {}
        first = bisect.bisect_left(self.onsets, position_s - _MAX_AGE_S)
        last = bisect.bisect_right(self.onsets, position_s)
        for i in range(first, last):
            age = position_s - self.onsets[i]
            span = max(self.gates[i], 0.12) + 0.15
            if 0 <= age <= min(span, _MAX_AGE_S):
                part = _ALIASES.get(self.parts[i], self.parts[i])
                energy[part] = energy.get(part, 0.0) + self.velocities[i] * max(
                    0.12, 1.0 - age / span
                )
        divisor = 4.8 if family == "aquatic" else 5.5
        return {part: min(1.0, value / divisor) for part, value in energy.items()}


def normalize_events(raw: object) -> list[list[object]]:
    """Convert any of the three album event layouts to ``[part, onset, gate, velocity]``.

    Layouts, as the original player accepted them:
    - Drowning Collective: ``{part: [[onset, gate, midi, velocity, ...]]}``.
    - Nurse Log: ``[[part, onset, gate, midi, velocity, ...]]``.
    - Quiet Machinery: ``[{"part", "time", "duration", "velocity"}]``.

    Args:
        raw: The track's ``events`` value from the album data.

    Returns:
        Rows in the input order. Unrecognized rows are dropped.
    """
    rows: list[list[object]] = []
    if isinstance(raw, dict):
        for part, notes in raw.items():
            for note in notes if isinstance(notes, list) else ():
                if isinstance(note, list) and len(note) >= 4:
                    rows.append([str(part), note[0], note[1], note[3]])
    elif isinstance(raw, list):
        for note in raw:
            if isinstance(note, dict):
                rows.append(
                    [
                        str(note.get("part", "other")),
                        note.get("time", 0),
                        note.get("duration", 0.2),
                        note.get("velocity", 0.5),
                    ]
                )
            elif isinstance(note, list) and len(note) >= 5 and isinstance(note[0], str):
                rows.append([note[0], note[1], note[2], note[4]])
    return rows


def _draw_orbit(c: Canvas, scene: str, pos: float, energy: dict[str, float]) -> None:
    cx, cy = c.w * 0.50, c.h * 0.44
    shrink = 0.18 if scene == "gravity" else 0.0
    expand = 0.12 if scene == "return" else 0.0
    base = min(c.w * 0.42, c.h * 0.83) * (1.0 - shrink + expand)
    phase = pos * 0.18
    for idx, ratio in enumerate((0.40, 0.64, 0.87, 1.0)):
        c.ellipse(
            cx,
            cy,
            base * ratio,
            base * ratio * 0.37,
            ".-~o"[idx],
            1 if idx % 2 == 0 else 2,
            phase * (idx % 2 * 2 - 1),
        )
    c.put(round(cx), round(cy), "@", 1)
    for idx, ratio in enumerate((0.40, 0.64, 0.87)):
        a = phase * (idx + 1) + 1.1
        c.put(
            round(cx + math.cos(a) * base * ratio),
            round(cy + math.sin(a) * base * ratio * 0.37),
            "o",
            1,
        )
    if scene in {"friction", "memory"}:
        for lane in range(3):
            y0 = int(c.h * (0.62 + lane * 0.06))
            for x in range(c.w):
                y = y0 + round(
                    math.sin(x * 0.11 + pos * 1.1 + lane) * (1 + energy.get("bass", 0) * 4)
                )
                c.put(x, y, "~" if lane != 1 else "-", 3 if lane == 1 else 2)
    if scene in {"commerce", "pursuit"}:
        for x in range(2, c.w, max(4, c.w // 13)):
            c.line(x, 2, x, c.h - 2, ":", 3)
        for y in range(2, c.h - 1, max(2, c.h // 6)):
            c.line(2, y, c.w - 3, y, ".", 3)
        if scene == "pursuit":
            for i in range(5):
                c.line(2, c.h - 2 - i, c.w - 3, max(1, i), "/", 1)


def _draw_aquatic(c: Canvas, scene: str, pos: float, e: dict[str, float]) -> None:
    cx = c.w * (0.48 + 0.06 * math.sin(pos * 0.08))
    cy = c.h * (0.50 + 0.07 * math.sin(pos * 0.13))
    pressure = 0.35 + e.get("bass", 0) * 0.62
    rx = min(c.w * 0.38, c.h * 1.16) * pressure
    ry = min(c.h * 0.42, c.w * 0.25) * pressure
    if scene == "pressure mouths":
        for side, direction in ((c.w * 0.31, 1), (c.w * 0.69, -1)):
            for i in range(4):
                c.ellipse(
                    side + math.sin(pos * 0.05 + i) * 2,
                    cy,
                    rx * (0.27 + i * 0.12),
                    ry * (0.42 + i * 0.12),
                    "#" if i == 1 else "~",
                    3 if i % 2 else 2,
                    pos * 0.03 * direction,
                )
        c.line(int(c.w * 0.48), 1, int(c.w * 0.52), c.h - 2, " ", 2)
    elif scene == "kelp cathedral":
        for i in range(11):
            x = int((i + 0.5) * c.w / 11)
            lean = int(math.sin(i * 1.7 + pos * 0.12) * max(2, c.w * 0.07))
            c.line(x, c.h - 1, max(0, min(c.w - 1, x + lean)), 1, "|", 3 if i % 2 else 2)
            for y in range(2, c.h - 1, 3):
                c.put(max(0, min(c.w - 1, x + lean * y // max(1, c.h))), y, "f", 4)
    elif scene == "blue void":
        c.ellipse(cx, cy, rx * 0.70, ry * 0.65, ".", 2, pos * 0.02)
        for lane, y0 in enumerate((0.42, 0.56, 0.68)):
            for x in range(c.w):
                y = round(c.h * y0 + math.sin(x * 0.07 + pos * 0.07 + lane) * max(1, c.h * 0.06))
                c.put(x, y, "-" if lane == 1 else ".", 4 if lane == 1 else 2)
    elif scene == "sheared bloom":
        for i in range(7):
            c.ellipse(
                cx + i * 0.8,
                cy,
                rx * (0.30 + i * 0.09),
                ry * (0.35 + i * 0.09),
                "#" if i in (2, 5) else "~",
                3 if i % 2 else 2,
                pos * 0.025 * (i % 2 * 2 - 1),
            )
        c.line(1, c.h - 2, c.w - 2, 1, "x", 1)
    else:
        for i in range(6):
            c.ellipse(
                cx + math.sin(i + pos * 0.03) * i,
                cy,
                rx * (0.50 + i * 0.105),
                ry * (0.48 + i * 0.095),
                "#" if i in (1, 4) else "~",
                3 if i % 2 else 2,
                pos * 0.025 * (i % 3 - 1),
            )
        if scene == "reef aperture":
            c.ellipse(cx, cy, rx * 0.58, ry * 0.52, "o", 1, pos * -0.01)
    for lane, ink in ((0, 4), (1, 2)):
        for x in range(c.w):
            phase = x / max(1, c.w) * 7 + pos * (0.22 if lane == 0 else -0.18) + lane
            y = round(
                c.h * (0.33 if lane == 0 else 0.67)
                + math.sin(phase) * (c.h * 0.12)
                + math.sin(phase * 2.2) * e.get("piano", 0) * 3
            )
            c.put(x, y, "-" if x % 4 else "~", ink)
    fractures = int(e.get("drums", 0) * 18)
    for i in range(fractures):
        x = int((i * 37 + pos * 23) % c.w)
        y = int((i * 11 + pos * 7) % c.h)
        c.put(x, y, "x", 1)
    if e.get("texture", 0) > 0.2:
        for i in range(0, c.w, 5):
            y = int((i * 7 + pos * 2) % max(1, c.h))
            c.put(i, y, ":", 4)


def _draw_forest(c: Canvas, scene: str, pos: float, e: dict[str, float]) -> None:
    cx = c.w // 2
    if scene == "rain":
        for i in range(max(10, c.w // 2)):
            x = (i * 7 + int(pos * 10)) % c.w
            y = (i * 11 + int(pos * 17)) % c.h
            c.line(x, y, min(c.w - 1, x + 1), min(c.h - 1, y + 2), "/", 3)
        for side in (2, c.w - 3):
            for y in range(c.h // 3, c.h):
                c.put(side + int(2 * math.sin(y * 0.2 + pos)), y, "f", 5)
    elif scene in {"rings", "spiral"}:
        for i in range(8):
            c.ellipse(
                cx,
                c.h // 2,
                max(2, c.w * (0.10 + i * 0.045)),
                max(1, c.h * (0.09 + i * 0.035)),
                "o",
                5 if i % 2 else 3,
                pos * (0.025 if i % 2 else -0.025),
            )
    elif scene == "canopy":
        for i in range(10):
            rootx = int(c.w * (i + 0.5) / 10)
            c.line(rootx, c.h - 1, cx + int((i - 4.5) * c.w * 0.12), 0, "/" if i % 2 else "\\", 5)
            for j in range(3):
                y = int(c.h * (0.25 + 0.18 * j))
                c.line(rootx, y, rootx + (j - 1) * 5, max(0, y - 3), "^", 3)
    elif scene == "spores":
        for i in range(30):
            x = (i * 17 + int(pos * 2 + i * 0.7)) % c.w
            y = (c.h - 1 - int(pos * 1.7 + i * 3)) % c.h
            c.put(x, y, "o" if i % 4 == 0 else ".", 5 if i % 4 == 0 else 3)
        for x in range(0, c.w, 4):
            c.put(x, c.h - 2, "f", 5)
    elif scene == "river":
        for row in range(max(4, c.h // 3)):
            y = int(c.h * 0.38 + row * 0.22)
            for x in range(c.w):
                c.put(
                    x,
                    y
                    + round(
                        math.sin(x * 0.10 + pos * (0.2 + row * 0.01)) * (1 + e.get("bass", 0) * 3)
                    ),
                    "~",
                    3 if row % 2 else 5,
                )
        for side in (1, c.w - 2):
            for y in range(c.h // 2, c.h):
                c.put(side + int(math.sin(y * 0.4) * 2), y, "|", 5)
    else:
        for i in range(13):
            x = (i * 13 + cx // 2) % c.w
            c.line(
                x,
                c.h - 1,
                cx + int(math.sin(i + pos * 0.03) * c.w * 0.25),
                c.h // 3,
                "/" if i % 2 else "\\",
                5,
            )
        for i in range(7):
            c.ellipse(
                cx,
                c.h * 0.70,
                max(2, c.w * (0.07 + i * 0.07 + e.get("bass", 0) * 0.06)),
                max(1, c.h * (0.07 + i * 0.045)),
                "~",
                3 if i % 2 else 5,
                pos * 0.01,
            )
    # Harp and reed activity become fine growth/current lines, not invented hits.
    # The original reads "tenor"/"baritone" after aliasing both to "reeds", so
    # only harp moves the thread count; kept as authored.
    threads = int(2 + e.get("harp", 0) * 10 + e.get("tenor", 0) * 4 + e.get("baritone", 0) * 4)
    for i in range(threads):
        x0 = (i * 19 + int(pos * 2)) % c.w
        c.line(x0, c.h - 1, min(c.w - 1, x0 + int(math.sin(i + pos) * 6)), c.h // 3, ":", 4)


def _draw_rooms(c: Canvas, scene: str, pos: float, e: dict[str, float]) -> None:
    cx = c.w // 2
    horizon = int(c.h * (0.70 - e.get("bass", 0) * 0.12))
    if scene == "crossing":
        c.line(2, 1, c.w - 3, c.h - 2, "/", 3)
        c.line(c.w - 3, 1, 2, c.h - 2, "\\", 4)
        for i in range(1, 7):
            x = int(c.w * i / 7)
            c.line(x, 1, c.w - x, c.h - 2, ":", 2)
    elif scene in {"resonance", "orbit"}:
        top = max(1, c.h // 5)
        for y in range(top, c.h - 2):
            half = int((y - top) * 0.42 + 2)
            c.put(cx - half, y, "|", 3)
            c.put(cx + half, y, "|", 3)
        c.line(cx - 2, top, cx + 2, top, "-", 1)
        for i in range(5):
            y = top + 2 + i * max(1, (c.h - top - 5) // 5)
            c.line(cx - max(1, (y - top) // 2), y, cx + max(1, (y - top) // 2), y, "=", 4)
    elif scene in {"fault", "lattice"}:
        for i in range(8):
            x0 = int((i + 0.5) * c.w / 8)
            points = [(x0, 0)]
            for y in range(1, c.h, 2):
                points.append((max(0, min(c.w - 1, x0 + int(math.sin(i * 3 + y * 1.7) * 4))), y))
            for (ax, ay), (bx, by) in itertools.pairwise(points):
                c.line(ax, ay, bx, by, "!", 4 if i % 3 == 0 else 3)
        for y in range(horizon, c.h, 3):
            c.line(0, y, c.w - 1, y, ".", 2)
    elif scene in {"warmth", "void"}:
        c.line(1, horizon, cx, c.h // 2, ".", 2)
        c.line(c.w - 2, horizon, cx, c.h // 2, ".", 2)
        c.put(cx, c.h // 3, "*", 1)
        c.line(cx, c.h // 3 + 1, cx, horizon, ":", 1)
        c.line(2, horizon, c.w - 3, horizon, "-", 2)
    elif scene in {"transmission", "dawn"}:
        mast = c.h - 3
        c.line(cx, mast, cx, 1, "|", 3)
        for arm in range(7):
            x = cx + (arm - 3) * max(2, c.w // 12)
            c.line(
                cx,
                mast - 2,
                x,
                max(1, mast - abs(arm - 3) * 2),
                "/" if arm < 3 else "\\",
                4 if arm == 3 else 3,
            )
        y = max(2, int(c.h * (0.52 + 0.13 * math.sin(pos * 0.06))))
        c.line(1, y, c.w - 2, y, "-", 1)
    else:
        rx = min(c.w * 0.31, c.h * 0.72)
        ry = min(c.h * 0.42, c.w * 0.22)
        for i in range(5):
            c.ellipse(
                cx,
                c.h * 0.46,
                rx * (0.45 + i * 0.14),
                ry * (0.45 + i * 0.13),
                "#" if i == 2 else "o",
                3 if i % 2 else 4,
                pos * 0.01,
            )
        c.put(cx + int(rx * 0.55), int(c.h * 0.67), "o", 1)
    # Scored mallet/bell and wind phrases appear as brief instrument-specific traces.
    for part, glyph, ink in (("mallet", "|", 2), ("bell", "~", 4), ("wind", "-", 5)):
        count = int(e.get(part, 0) * max(1, c.w // 5))
        for i in range(count):
            x = (i * 7 + int(pos * 3)) % c.w
            y = (i * 5 + int(pos * 2)) % c.h
            c.put(x, y, glyph, ink)


_DRAW = {
    "coupon": _draw_orbit,
    "aquatic": _draw_aquatic,
    "forest": _draw_forest,
    "rooms": _draw_rooms,
}


def draw_scene(
    canvas: Canvas, family: str, scene: str, position_s: float, events: EventIndex
) -> None:
    """Draw one movement's scene at `position_s` seconds into it.

    Args:
        canvas: Target grid, drawn over in place.
        family: Visual family; unknown families draw the rooms scene, as
            the original fallback did.
        scene: Scene name from the album data.
        position_s: Seconds from the movement start.
        events: The movement's scored notes.
    """
    energy = events.activity(position_s, family)
    _DRAW.get(family, _draw_rooms)(canvas, scene, position_s, energy)

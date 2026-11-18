"""Own scene clocks, motion holds, transitions, fitting, and terminal row encoding.

Playback and preview supply audio and picture clocks. Held pictures reuse their exact
pixels, preventing feedback accumulation; scores are calmed once here, never by albums.
"""

from dataclasses import replace
from time import perf_counter

import numpy as np

from .albums import build_scene
from .audio import SILENT, Features
from .encode import FrameEncoder
from .fx import tone_map
from .glyphs import TIERS, Cells, fit
from .scene import Frame, Movement, Scene
from .score import Score
from .surface import Surface

_ENERGY = {"full": 1.0, "reduced": 0.35, "still": 0.0}
_CROSSFADE_S = 1.5  # Picture seconds: pauses and still mode must not advance a transition.


def _calmed_score(score: Score | None, energy: float) -> Score | None:
    if score is None or energy == 1:
        return score
    notes = {}
    for part, values in score.notes.items():
        values = values.copy()
        values["vel"] *= energy
        values.flags.writeable = False
        notes[part] = values
    return replace(
        score,
        notes=notes,
        sections=tuple(replace(s, intensity=s.intensity * energy) for s in score.sections),
    )


class Stage:
    """Render an album scene into terminal bytes, retaining the latest fitted cells.

    Args:
        cols: Positive canvas width in character cells.
        rows: Positive canvas height in character cells.
        tier: Key from glyphs.TIERS.
        color_mode: truecolor, 256, or none.
        cell_aspect: Cell height divided by width in physical pixels.

    Attributes:
        surface: Current linear-light canvas (tone mapped after each frame).
        cells: Latest fitted Cells, or None before the first picture.
        timings: Latest render, fit, and encode durations in seconds.

    Raises:
        ValueError: Dimensions or color mode are invalid.
        KeyError: The tier is unknown.
    """

    def __init__(
        self, cols: int, rows: int, *, tier: str, color_mode: str, cell_aspect: float = 2.0
    ):
        self.tier = tier
        self.color_mode = color_mode
        self.cell_aspect = cell_aspect
        self.encoder = FrameEncoder(color_mode)
        self.surface = self._surface(cols, rows)
        self.cells: Cells | None = None
        self.timings = (0.0, 0.0, 0.0)
        self.scene: Scene | None = None
        self._movement: Movement | None = None
        self._features: Features | None = None
        self._scores: dict[str, Score | None] = {}
        self._last_tau: float | None = None
        self._last_motion = "full"
        self._last_frame: Frame | None = None
        self._picture: np.ndarray | None = None
        self._fade_from: np.ndarray | None = None
        self._fade_elapsed = 0.0
        self._redraw = False

    def _surface(self, cols: int, rows: int) -> Surface:
        if cols < 1 or rows < 1:
            raise ValueError("canvas dimensions must be positive")
        tier = TIERS[self.tier]
        return Surface(cols, rows, tier.sub_w, tier.sub_h, self.cell_aspect)

    def open(self, movement: Movement, features: Features | None, score: Score | None) -> None:
        """Replace the scene, fading from its last picture only in full motion.

        Args:
            movement: New composition metadata.
            features: Movement-relative audio analysis, or None for silent playback.
            score: Immutable movement score, or None.

        Raises:
            Exception: Known album import and factory errors propagate.
        """
        scene = build_scene(movement)
        scene.resize(self.surface)
        self._fade_from = (
            self._picture.copy()
            if self._picture is not None and self._last_motion == "full"
            else None
        )
        self._fade_elapsed = 0.0
        self.scene = scene
        self._movement, self._features = movement, features
        self._scores = {mode: _calmed_score(score, energy) for mode, energy in _ENERGY.items()}
        self._last_tau = None
        self._last_frame = None
        self._picture = None
        self.cells = None
        self._redraw = False

    def resize(self, cols: int, rows: int) -> None:
        """Change canvas dimensions and redraw the captured instant on the next frame.

        Args:
            cols: Positive width in character cells.
            rows: Positive height in character cells.

        Raises:
            ValueError: A dimension is not positive.
        """
        self.surface = self._surface(cols, rows)
        if self.scene is not None:
            self.scene.resize(self.surface)
        self._fade_from = None
        self._redraw = True
        self.encoder.invalidate()
        self.cells = None

    def set_tier(self, tier: str) -> None:
        """Switch the mosaic sampling grid and invalidate terminal rows.

        Args:
            tier: Key in glyphs.TIERS.

        Raises:
            KeyError: The requested tier is unknown.
        """
        if tier not in TIERS:
            raise KeyError(tier)
        if tier != self.tier:
            self.tier = tier
            self.resize(self.surface.cols, self.surface.rows)

    def seek(self) -> None:
        """Release a captured picture after an explicit user seek, including still mode.

        The next frame captures the caller's requested clocks with zero picture dt.
        Scene feedback and crossfade history are discarded; no disk or TTY I/O occurs.
        """
        if self.scene is not None:
            self.scene.seek()
        self._picture = None
        self._last_frame = None
        self._last_tau = None
        self._fade_from = None
        self.encoder.invalidate()

    def frame(self, t: float, tau: float, *, motion: str) -> bytes:
        """Render changed canvas rows, without a synchronized-output wrapper.

        Args:
            t: Movement-relative audio time in seconds.
            tau: Motion-scaled picture time in seconds; supplied by the caller.
            motion: full, reduced, or still. A repeated tau holds exact pixels.

        Returns:
            Cursor-addressed UTF-8/ANSI bytes; unchanged pictures return empty bytes.

        Raises:
            RuntimeError: No movement has been opened.
            ValueError: Clocks are not finite or motion is unknown.
        """
        if self.scene is None or self._movement is None:
            raise RuntimeError("open a movement before rendering")
        if motion not in _ENERGY or not np.isfinite(t) or not np.isfinite(tau):
            raise ValueError("finite clocks and a valid motion mode are required")
        start = perf_counter()
        delta = 0.0 if self._last_tau is None else tau - self._last_tau
        jumped = self._last_tau is not None and (delta < 0 or delta > 1)
        held = self._picture is not None and (motion == "still" or delta == 0)
        # Still is a captured composition even if the caller continues advancing tau.
        if jumped and motion != "still":
            self.scene.seek()
            self._fade_from = None
            held = False
        dt = 0.0 if jumped or motion == "still" else max(0.0, delta)
        if motion != "full":
            self._fade_from = None
        if held and not self._redraw:
            self.surface.rgb[:] = self._picture
        else:
            energy = _ENERGY[motion]
            score = self._scores[motion]
            levels = self._features.sample(t).calmed(energy) if self._features else SILENT
            frame = Frame(
                t,
                tau,
                dt,
                energy,
                float(np.clip(t / self._movement.duration_s, 0, 1))
                if self._movement.duration_s > 0
                else 0.0,
                levels,
                self._features,
                score,
                score.section(t) if score else None,
            )
            if held and self._last_frame is not None:
                frame = replace(self._last_frame, dt=0.0)
            self.scene.render(self.surface, frame)
            tone_map(self.surface)
            if self._fade_from is not None:
                self._fade_elapsed += dt
                amount = min(1.0, self._fade_elapsed / _CROSSFADE_S)
                self.surface.rgb *= amount
                self.surface.rgb += self._fade_from * (1 - amount)
                if amount >= 1:
                    self._fade_from = None
            if self._picture is None or self._picture.shape != self.surface.rgb.shape:
                self._picture = self.surface.rgb.copy()
            else:
                np.copyto(self._picture, self.surface.rgb)
            self._last_frame = frame
        self._last_tau, self._last_motion = tau, motion
        self._redraw = False
        rendered = perf_counter()
        self.cells = fit(self.surface.rgb, self.tier, mono=self.color_mode == "none")
        fitted = perf_counter()
        result = self.encoder.encode(self.cells)
        encoded = perf_counter()
        self.timings = (rendered - start, fitted - rendered, encoded - fitted)
        return result

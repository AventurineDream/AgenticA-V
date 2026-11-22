"""Paint unknown albums as a quiet, layered ribbon field rather than a glyph port.

The registry selects this only for unknown families. Closed-form seeded geometry makes
seeks and silent playback deterministic; audio bends ribbons without pulsing their light.
"""

import numpy as np

from ..color import linear
from ..scene import Frame, Movement, Scene
from ..surface import Surface


class GenericScene(Scene):
    """Draw sparse luminous ribbons above a dark, slowly opening horizon.

    Args:
        movement: Palette, stable seed, and movement metadata.
    """

    def __init__(self, movement: Movement):
        super().__init__(movement)
        palette = movement.palette or ("#193047", "#648b9b", "#e2bd83")
        self._colors = tuple(linear(c) for c in palette)
        rng = np.random.default_rng(movement.seed)
        self._phases = rng.uniform(0, 2 * np.pi, 7).astype(np.float32)
        self._layer: np.ndarray | None = None

    def resize(self, surface: Surface) -> None:
        """Allocate the reusable ribbon coverage layer for the new canvas.

        Args:
            surface: Output canvas with sub-pixel dimensions.
        """
        self._layer = surface.layer()

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint a finished composition, with motion even without analysis.

        Args:
            surface: Mutable linear-light RGB target.
            frame: Already-calmed audio and score; times are seconds.
        """
        if self._layer is None:
            self.resize(surface)
        surface.fill(linear("#03070d"))
        haze = np.exp(-((surface.v - 0.48) ** 2) / 0.22)
        surface.add(haze, self._colors[0], 0.09)
        for index, phase in enumerate(self._phases):
            depth = index / 6
            center = -0.58 + depth * 1.18
            bend = 0.06 + 0.08 * frame.progress + 0.035 * frame.levels.bass
            path = center + bend * np.sin(
                surface.u * (1.4 + depth) + frame.tau * (0.11 + depth * 0.025) + phase
            )
            self._layer[:] = np.exp(-(((surface.v - path) / (0.008 + depth * 0.007)) ** 2))
            # Depth changes coverage, not beat-synchronized brightness.
            self._layer *= np.exp(-(((surface.u + 0.2) / (0.7 + depth)) ** 2))
            surface.add(self._layer, self._colors[index % len(self._colors)], 0.12 + depth * 0.22)


def build_scene(movement: Movement) -> Scene:
    """Construct the deterministic unknown-family painter.

    Args:
        movement: Composition metadata and stable seed.

    Returns:
        A new generic scene; Stage supplies its canvas later.
    """
    return GenericScene(movement)

"""Define immutable musical frames and the scene lifecycle shared by albums and Stage.

Audio time supplies signals; picture time supplies geometry. Scene implementations own
size-dependent caches and must discard temporal state on seeks without global randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .audio import Features, Levels
from .score import Score, Section

if TYPE_CHECKING:
    from .surface import Surface


@dataclass(frozen=True, slots=True)
class Movement:
    """Describe one movement independently of extraction and playback.

    Args:
        family: Album registry key; unknown keys use the generic scene.
        index: Zero-based movement index within the album.
        count: Number of movements in the album.
        title: Display title.
        scene: Album-specific composition identifier.
        label: Human-readable scene label.
        duration_s: Movement duration in seconds.
        palette: Immutable sRGB hexadecimal colors.
        bpm: Tempo in beats per minute, or None when unknown.
        meter: Beats and denominator, or None when unknown.
        seed: Stable movement seed; the only source of scene randomness.
    """

    family: str
    index: int
    count: int
    title: str
    scene: str
    label: str
    duration_s: float
    palette: tuple[str, ...]
    bpm: float | None
    meter: tuple[int, int] | None
    seed: int


@dataclass(frozen=True, slots=True)
class Frame:
    """Supply one already-calmed musical instant to a scene.

    Args:
        t: Audio position in movement-relative seconds.
        tau: Motion-scaled picture position in seconds.
        dt: Picture step in seconds, zero while held.
        energy: Reactive gain: full 1, reduced 0.35, still 0.
        progress: Clamped movement fraction, in [0, 1].
        levels: Sampled audio envelopes, already calmed by energy.
        features: Movement-relative analysis, or None for silent fallback.
        score: Score or None; Stage already scales note velocities and section intensity
            by energy. Album painters must not multiply these values by energy again.
        section: Current musical section, or None; intensity is calmed too.
    """

    t: float
    tau: float
    dt: float
    energy: float
    progress: float
    levels: Levels
    features: Features | None
    score: Score | None
    section: Section | None


class Scene:
    """Specify the album painter lifecycle; subclasses implement rendering.

    Args:
        movement: Immutable composition metadata, retained for the scene lifetime.
    """

    def __init__(self, movement: Movement):
        self.movement = movement

    def resize(self, surface: Surface) -> None:
        """Rebuild size-dependent caches without advancing musical state.

        Args:
            surface: New target canvas, with dimensions in sub-pixels.
        """

    def seek(self) -> None:
        """Discard trails and particles after a discontinuity in picture time."""

    def render(self, surface: Surface, frame: Frame) -> None:
        """Paint the complete linear-light image into the supplied canvas.

        Args:
            surface: Mutable output; implementations must paint the whole image.
            frame: Musical signals and geometry clocks for this picture.

        Raises:
            NotImplementedError: If an album failed to implement its painter.
        """
        raise NotImplementedError

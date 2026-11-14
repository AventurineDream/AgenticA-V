"""Pure transport state for the visual player.

The clock is monotonic and stores an anchor only while running. Pausing or
seeking updates that anchor atomically, so system wall-clock changes do not
move the playhead.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(slots=True)
class Playhead:
    """A looping visual playhead; times are seconds and rate is dimensionless."""

    duration_s: float
    position_s: float = 0.0
    playing: bool = True
    rate: float = 1.0
    _clock: Callable[[], float] = field(default=time.monotonic, repr=False)
    _anchor: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise ValueError("duration_s must be positive")
        self.position_s %= self.duration_s
        self._anchor = self._clock()

    @property
    def position(self) -> float:
        """Current wrapped position in seconds."""
        if self.playing:
            return (self.position_s + (self._clock() - self._anchor) * self.rate) % self.duration_s
        return self.position_s

    def toggle(self) -> None:
        """Pause or resume without losing elapsed time."""
        if self.playing:
            self.position_s = self.position
            self.playing = False
        else:
            self._anchor = self._clock()
            self.playing = True

    def seek(self, delta_s: float) -> None:
        """Move by `delta_s`; wrap at the show boundaries."""
        self.position_s = (self.position + delta_s) % self.duration_s
        self._anchor = self._clock()

    def seek_to(self, position_s: float) -> None:
        """Move to an absolute second, clamped to the show duration."""
        self.position_s = max(0.0, min(self.duration_s, position_s))
        if self.position_s >= self.duration_s:
            self.position_s = 0.0
        self._anchor = self._clock()

    def set_rate(self, rate: float) -> None:
        """Change playback multiplier while preserving the current position."""
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.position_s = self.position
        self.rate = rate
        self._anchor = self._clock()

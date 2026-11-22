"""Small TOML show description used by the CLI and the bundled abstract demo.

The show format contains only reusable metadata and program IDs. Authorized
album HTML lives under ``clangor_visualis_machina/albums`` and is not referenced by shows.
TOML decoding is strict to catch typos early.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

PROGRAMS = frozenset({"garden", "aperture", "scan", "tide"})


class ShowError(ValueError):
    """A show description is malformed or asks for an unknown program."""


@dataclass(frozen=True, slots=True)
class Show:
    """An abstract sequence for the terminal player; duration is in seconds."""

    title: str
    detail: str
    duration: float
    tempo: int
    programs: tuple[str, ...]

    def program_at(self, position_s: float) -> tuple[int, str]:
        """Select the program covering `position_s`, wrapping at show duration."""
        span = self.duration / len(self.programs)
        index = min(len(self.programs) - 1, int((position_s % self.duration) / span))
        return index, self.programs[index]

    def chapter_delta(self, position_s: float, step: int) -> tuple[float, float]:
        """Return a chapter target and the signed seconds traveled to reach it.

        Args:
            position_s: Current playhead position in seconds.
            step: Negative moves to a previous program; positive moves forward.
                The player passes -1 or +1.

        Returns:
            Target position in seconds, and logical delta in seconds. Positive
            delta is forward, including a wrap from the last program to the
            first. The sign follows ``step``, not the wrapped position change.
        """
        count = len(self.programs)
        index, _ = self.program_at(position_s)
        target = (index + step) % count * self.duration / count
        raw = target - position_s % self.duration
        if step > 0 and raw < 0:
            raw += self.duration
        elif step < 0 and raw > 0:
            raw -= self.duration
        return target, raw


def load_show(path: Path) -> Show:
    """Read and validate a TOML show file.

    Args:
        path: Filesystem path to a UTF-8 TOML show description.

    Returns:
        Immutable show metadata.

    Raises:
        ShowError: The file cannot be parsed or has invalid required values.
    """
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ShowError(f"cannot load show {path}: {error}") from error
    return _from_mapping(data)


def demo_show() -> Show:
    """Load the bundled media-free demo reel."""
    resource = files("clangor_visualis_machina").joinpath("demo/reel.toml")
    try:
        data = tomllib.loads(resource.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ShowError(f"bundled demo reel is invalid: {error}") from error
    return _from_mapping(data)


def _from_mapping(data: dict[str, object]) -> Show:
    """Validate a parsed show table and normalize its fields."""
    if not isinstance(data, dict):
        raise ShowError("show file must contain a TOML table")
    title = data.get("title")
    detail = data.get("detail", "")
    duration = data.get("duration")
    tempo = data.get("tempo", 0)
    programs = data.get("programs")
    if not isinstance(title, str) or not title.strip():
        raise ShowError("show title must be a non-empty string")
    if not isinstance(detail, str):
        raise ShowError("show detail must be a string")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        raise ShowError("show duration must be a positive number of seconds")
    if not isinstance(tempo, int) or isinstance(tempo, bool) or tempo < 0:
        raise ShowError("show tempo must be a non-negative integer")
    if (
        not isinstance(programs, list)
        or not programs
        or not all(isinstance(p, str) for p in programs)
    ):
        raise ShowError("show programs must be a non-empty list of program IDs")
    unknown = set(programs) - PROGRAMS
    if unknown:
        raise ShowError(f"unknown programs: {', '.join(sorted(unknown))}")
    return Show(title.strip(), detail.strip(), float(duration), tempo, tuple(programs))

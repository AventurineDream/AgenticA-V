"""Normalize bundled composition data into fast, seekable visualizer queries.

Native extraction calls normalize_track once, retaining JSON-safe score sidecars;
Score builds read-only numpy note arrays. No audio, drawing, or archive I/O lives here.
"""

from __future__ import annotations

import bisect
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

NOTE = np.dtype(
    [
        ("onset", "f4"),
        ("gate", "f4"),
        ("midi", "f4"),
        ("vel", "f4"),
        ("pan", "f4"),
        ("kind", "u1"),
        ("voice", "u1"),
    ]
)
_EMPTY = np.empty(0, dtype=NOTE)
_EMPTY.flags.writeable = False
_GM_DRUMS = {36: "kick", 38: "snare", 37: "rim", 42: "hat", 46: "hat"}
_AQUATIC_KINDS = ("note", "pad", "grain", "kick", "snare", "hat", "tom", "rim")
_AQUATIC_VOICES = ("foundation", "upper", "lower", "harmony")


@dataclass(frozen=True, slots=True)
class Section:
    """A named, half-open musical span in seconds, with density/intensity 0..1."""

    name: str
    start_s: float
    end_s: float
    mode: str
    intensity: float


@dataclass(frozen=True)
class Score:
    """Movement-local notes and structure, independent of the playback clock.

    Notes use NOTE and must be sorted by onset. Kinds/voices reserve index zero
    for the empty name. Methods return read-only arrays; inputs are not mutated.
    """

    notes: Mapping[str, np.ndarray]
    kinds: tuple[str, ...]
    voices: tuple[str, ...]
    sections: tuple[Section, ...]
    bpm: float | None
    meter: tuple[int, int] | None
    markers: Mapping[str, float]
    motifs: tuple[Any, ...]
    _onsets: Mapping[str, np.ndarray] = field(init=False, repr=False, compare=False)
    _max_gate: Mapping[str, float] = field(init=False, repr=False, compare=False)
    _section_starts: tuple[float, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_onsets", {p: n["onset"] for p, n in self.notes.items()})
        object.__setattr__(
            self,
            "_max_gate",
            {p: float(n["gate"].max()) if len(n) else 0.0 for p, n in self.notes.items()},
        )
        object.__setattr__(self, "_section_starts", tuple(s.start_s for s in self.sections))

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Score:
        """Build arrays from normalize_track's JSON-safe sidecar payload.

        Args:
            payload: Events grouped by part, name tables, and musical metadata.

        Returns:
            An empty, usable score when the payload has no composition events.

        Raises:
            ValueError: Numeric rows or meter have an invalid representation.
        """
        notes = {}
        for part, rows in payload.get("events", {}).items():
            array = np.asarray([tuple(row) for row in rows], dtype=NOTE)
            array = array[np.argsort(array["onset"], kind="stable")]
            array.flags.writeable = False
            notes[part] = array
        sections = tuple(
            sorted(
                (
                    Section(
                        str(s.get("name", "")),
                        float(s.get("start", 0)),
                        float(s.get("end", 0)),
                        str(s.get("mode", "")),
                        float(s.get("intensity", 0.5)),
                    )
                    for s in payload.get("sections", ())
                ),
                key=lambda s: s.start_s,
            )
        )
        meter = payload.get("meter")
        return cls(
            notes,
            tuple(payload.get("kinds", ("",))),
            tuple(payload.get("voices", ("",))),
            sections,
            payload.get("bpm"),
            tuple(meter) if meter else None,
            dict(payload.get("markers", {})),
            tuple(payload.get("motifs", ())),
        )

    def level(self, part, t, *, decay_s=0.3, kind=None, voice=None) -> float:
        """Return tanh-squashed exponentially decaying note velocity.

        Args:
            part: Instrument/part name; unknown names yield zero.
            t: Movement-local seconds.
            decay_s: Positive exponential decay time in seconds.
            kind: Optional kind name to isolate, e.g. kick or flute.
            voice: Optional named score voice to isolate.

        Returns:
            A nonnegative envelope below one; gates do not cut off this tail.

        Raises:
            ValueError: decay_s is not positive and finite.
        """
        if decay_s <= 0 or not math.isfinite(decay_s):
            raise ValueError("decay_s must be positive and finite")
        # At 20 time constants a note contributes <2.1e-9 of its velocity.
        # Restricting the slice bounds work per frame, even late in a long score.
        notes = self.recent(part, t, decay_s * 20)
        if not len(notes):
            return 0.0
        if kind is not None:
            if kind not in self.kinds:
                return 0.0
            notes = notes[notes["kind"] == self.kinds.index(kind)]
        if voice is not None:
            if voice not in self.voices:
                return 0.0
            notes = notes[notes["voice"] == self.voices.index(voice)]
        return math.tanh(float(np.sum(notes["vel"] * np.exp((notes["onset"] - t) / decay_s))))

    def recent(self, part, t, window_s) -> np.ndarray:
        """Return notes starting in (t-window_s, t], all times in seconds.

        Unknown parts and nonpositive windows return an empty NOTE array.
        """
        if part not in self.notes or window_s <= 0:
            return _EMPTY
        onsets = self._onsets[part]
        start, end = np.searchsorted(onsets, (t - window_s, t), side="right")
        return self.notes[part][start:end]

    def sounding(self, part, t) -> np.ndarray:
        """Return read-only notes with onset <= t < onset+gate, t in seconds."""
        if part not in self.notes:
            return _EMPTY
        onsets = self._onsets[part]
        start, end = np.searchsorted(onsets, (t - self._max_gate[part], t), side="right")
        notes = self.notes[part][start:end]
        result = notes[t < notes["onset"] + notes["gate"]]
        result.flags.writeable = False
        return result

    def section(self, t) -> Section | None:
        """Return the section containing local seconds t, or None in a gap/tail."""
        index = bisect.bisect_right(self._section_starts, t) - 1
        if index >= 0 and t < self.sections[index].end_s:
            return self.sections[index]
        return None


def _meter(value: Any) -> list[int] | None:
    if isinstance(value, str):
        match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", value)
        return [int(match[1]), int(match[2])] if match else None
    return list(value) if isinstance(value, (list, tuple)) and len(value) == 2 else None


def _aquatic_palette(html: str, number: int) -> list[str]:
    match = re.search(r"const\s+palette\s*=\s*\[(.*?)\]\s*;", html, re.DOTALL)
    if match:
        rows = re.findall(r"\[([^\[\]]+)\]", match[1])
        if 0 <= number - 1 < len(rows):
            colors = re.findall(r"#[0-9a-fA-F]{6}\b", rows[number - 1])
            if len(colors) == 4:
                return colors
    return ["#e9e3c7", "#bb8eb1", "#82d7d4", "#183a61"]


def _radiance_markers(html: str) -> dict[str, float]:
    # Read the score-reader expression, not unrelated renderer smooth() calls.
    expression = re.search(r"const\s+radiance\s*=.{0,80}?\?\s*(.*?):\s*0", html, re.DOTALL)
    if expression:
        pairs = re.findall(r"smooth\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*time\s*\)", expression[1])
        if len(pairs) >= 2:
            return {
                "radiance_on": float(pairs[0][0]),
                "radiance_full": float(pairs[0][1]),
                "radiance_off": float(pairs[1][0]),
            }
    return {"radiance_on": 168.0, "radiance_full": 185.0, "radiance_off": 240.0}


def normalize_track(family: str, track: Mapping[str, Any], html: str = "") -> dict[str, Any]:
    """Normalize the bundled score layouts into a JSON-safe payload.

    Args:
        family: coupon, aquatic, forest, pocket, rooms, or undertow; unknown stays empty.
        track: Original movement metadata/events; aquatic kinds/voices can be
            supplied from the root object under the same keys.
        html: Original page for aquatic palettes and rooms radiance timing.

    Returns:
        Events grouped by part as NOTE-order rows; tables reserve empty index 0.
        Metadata includes palette, sections, BPM/meter, markers, and motifs.
        Forest has no explicit BPM/meter: neither is invented from its bars.
        Missing page patterns use a subdued aquatic palette or known radiance arc.
    """
    kinds, voices = [""], [""]
    events: dict[str, list[list[Any]]] = {}

    def index(table: list[str], name: Any) -> int:
        name = str(name or "")
        if name not in table:
            table.append(name)
        return table.index(name)

    def add(part, onset, gate, midi, vel, pan=0, kind="", voice=""):
        events.setdefault(str(part), []).append(
            [
                float(onset),
                float(gate),
                float(midi),
                float(vel),
                float(pan),
                index(kinds, kind),
                index(voices, voice),
            ]
        )

    raw = track.get("events", ())
    if family == "forest":
        for part, onset, gate, midi, vel, pan in raw:
            add(
                part,
                onset,
                gate,
                midi,
                vel,
                pan,
                _GM_DRUMS.get(int(midi), "") if part == "drums" else "",
            )
    elif family in ("pocket", "undertow"):
        # Source rows are objects whose times are already seconds, timing offsets included.
        for row in raw:
            part = str(row["part"])
            if part == "drums":
                kind = _GM_DRUMS.get(int(row["midi"]), "")
            else:
                kind = str(row.get("kind", ""))
            add(
                part,
                row["time"],
                row["duration"],
                row["midi"],
                row["velocity"],
                row.get("pan", 0),
                kind,
                row.get("voice", ""),
            )
    elif family == "aquatic":
        source_kinds = track.get("kinds", _AQUATIC_KINDS)
        source_voices = track.get("voices", _AQUATIC_VOICES)
        # Retain the root tables, even names unused in this movement. Source
        # indices shift by one because NOTE reserves zero for an unnamed event.
        for name in source_kinds:
            index(kinds, name)
        for name in source_voices:
            index(voices, name)
        if isinstance(raw, Mapping):
            for part, rows in raw.items():
                for onset, gate, midi, vel, pan, kind, voice in rows:
                    add(
                        part,
                        onset,
                        gate,
                        midi,
                        vel,
                        pan,
                        source_kinds[int(kind)],
                        source_voices[int(voice)],
                    )
    elif family == "rooms":
        for row in raw:
            kind = row.get("kind", "")
            if row.get("part") == "wind":
                kind = {73: "flute", 71: "clarinet"}.get(row.get("program"), kind)
            add(
                row["part"],
                row["time"],
                row["duration"],
                row["midi"],
                row["velocity"],
                row.get("pan", 0),
                kind,
                row.get("voice", ""),
            )
    for rows in events.values():
        rows.sort(key=lambda row: row[0])
    sections = [
        {
            **s,
            "name": str(s.get("name", "")),
            "start": float(s.get("start", 0)),
            "end": float(s.get("end", 0)),
            "mode": str(s.get("mode") or s.get("role") or ""),
            "intensity": float(s.get("intensity", 0.5)),
        }
        for s in track.get("sections", ())
    ]
    number = int(track.get("number", 1))
    palette = list(track.get("palette") or track.get("color") or ())
    if family == "aquatic":
        palette = _aquatic_palette(html, number)
    markers = {}
    if family == "aquatic" and track.get("major_first_f_sharp") is not None:
        markers["major_onset"] = float(track["major_first_f_sharp"])
    if family == "rooms" and number == 6:
        markers.update(_radiance_markers(html))
    meter = _meter(track.get("meter"))
    if meter is None and family == "aquatic":
        # A free opening has no prevailing meter at t=0. Later changes remain
        # in the normalized section metadata rather than being flattened away.
        source_sections = track.get("sections", ())
        if source_sections:
            meter = _meter(source_sections[0].get("meter"))
    return {
        "events": events,
        "kinds": kinds,
        "voices": voices,
        "sections": sections,
        "bpm": float(track["bpm"]) if track.get("bpm") else None,
        "meter": meter,
        "palette": palette,
        "markers": markers,
        "motifs": track.get("motifs", []),
        "duration": float(track.get("duration") or 0),
    }

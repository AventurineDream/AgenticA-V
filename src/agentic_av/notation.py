"""Bar arithmetic for the music written in track docs.

Track docs (docs/spec/band-album-spec.md §9) write form tables, chord charts, rhythm grids and ABC
heads as plain text. The registry validator uses these helpers to prove that every bar holds its
meter, that a chord chart matches the form, and that a stated length matches bars and tempo. All
durations are exact ``Fraction`` values in whole notes, so 7/8 bars and triplets never round. The
ABC support is the spec's subset, not a full ABC 2.1 parser: anything outside it is reported, never
guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction


class NotationError(ValueError):
    """Raised when a single notation value (meter, tempo, form cell) cannot be read."""


@dataclass(frozen=True)
class Meter:
    """A time signature of ``num`` beats of ``1/den`` notes per bar."""

    num: int
    den: int

    @property
    def length(self) -> Fraction:
        """Bar length in whole notes."""
        return Fraction(self.num, self.den)

    @property
    def compound(self) -> bool:
        """Whether beats group in threes (6/8, 9/8, 12/8), which changes ABC's tuplet defaults."""
        return self.num % 3 == 0 and self.num > 3 and self.den >= 8

    @property
    def text(self) -> str:
        """The meter written as ``num/den``."""
        return f"{self.num}/{self.den}"


@dataclass(frozen=True)
class Tempo:
    """A tempo in ABC ``Q:`` form: ``bpm`` beats per minute, each ``unit`` of a whole note."""

    unit: Fraction
    bpm: Fraction


@dataclass(frozen=True)
class FormSection:
    """One row of a track's form table.

    Attributes:
        label: Section label, unique in the form (``A1``).
        bars: Bar count, or None for a free-time section.
        meter: Section meter, or None for a free-time section.
        tempo: Tempo override for this section, or None to use the track tempo.
        seconds: Length of a free-time section in seconds; None for metered sections.
        open_space: The form table's open-space cell, as written.
    """

    label: str
    bars: int | None
    meter: Meter | None
    tempo: Tempo | None
    seconds: Fraction | None
    open_space: str


_METER = re.compile(r"^(\d+(?:\+\d+)*)/(\d+)$")
_TEMPO = re.compile(r"^(\d+)/(\d+)=(\d+(?:\.\d+)?)$")
_CLOCK = re.compile(r"^(\d+):([0-5]\d)$")
_FREE_BARS = re.compile(r"^(\d+(?:\.\d+)?)\s*s$")


def parse_meter(text: str) -> Meter:
    """Read a meter such as ``4/4``, ``7/8``, ``2+2+3/8``, ``C`` or ``C|``.

    Args:
        text: The meter as written.

    Returns:
        The meter; additive numerators are summed (``2+2+3/8`` is 7/8).

    Raises:
        NotationError: If the text is not a meter with a power-of-two denominator.
    """
    compact = "".join(text.split())
    if compact == "C":
        return Meter(4, 4)
    if compact == "C|":
        return Meter(2, 2)
    match = _METER.match(compact)
    if match is None:
        raise NotationError(f"{text.strip()!r} is not a meter like 4/4 or 7/8")
    num = sum(int(part) for part in match.group(1).split("+"))
    den = int(match.group(2))
    # Denominators name note values, so only powers of two are meters.
    if num == 0 or den == 0 or den & (den - 1):
        raise NotationError(f"{text.strip()!r} is not a meter like 4/4 or 7/8")
    return Meter(num, den)


def parse_tempo(text: str) -> Tempo:
    """Read a tempo in ABC ``Q:`` form, such as ``1/4=88`` or ``3/8=60``.

    Args:
        text: The tempo as written, without the ``Q:`` prefix.

    Returns:
        The tempo.

    Raises:
        NotationError: If the text is not ``unit=bpm`` with a positive unit and bpm.
    """
    match = _TEMPO.match("".join(text.split()))
    if match is None:
        raise NotationError(f"{text.strip()!r} is not a tempo like 1/4=88")
    num, den, bpm = int(match.group(1)), int(match.group(2)), Fraction(match.group(3))
    if num == 0 or den == 0 or bpm == 0:
        raise NotationError(f"{text.strip()!r} is not a tempo like 1/4=88")
    return Tempo(Fraction(num, den), bpm)


def bar_seconds(meter: Meter, tempo: Tempo) -> Fraction:
    """Return how long one bar of ``meter`` lasts at ``tempo``, in seconds."""
    return meter.length / tempo.unit * 60 / tempo.bpm


def parse_clock(text: str) -> int:
    """Read an ``m:ss`` length as whole seconds.

    Raises:
        NotationError: If the text is not ``m:ss`` with seconds below 60.
    """
    match = _CLOCK.match(text.strip())
    if match is None:
        raise NotationError(f"{text.strip()!r} is not a length like 4:31")
    return int(match.group(1)) * 60 + int(match.group(2))


def parse_form_section(label: str, bars: str, meter: str, open_space: str) -> FormSection:
    """Read one form-table row (spec §9.1).

    Args:
        label: Section cell.
        bars: Bars cell: a whole number, or seconds (``20s``) for a free-time section.
        meter: Meter cell: ``n/d``, optionally ``@ unit=bpm`` for a tempo change, or ``free``.
        open_space: Open-space cell, kept as written.

    Returns:
        The parsed section.

    Raises:
        NotationError: If a cell cannot be read or free time and bar counts are mixed.
    """
    bars_text, meter_text = bars.strip(), meter.strip()
    if meter_text.lower() == "free":
        free = _FREE_BARS.match(bars_text)
        if free is None:
            raise NotationError(f"free section {label!r} needs its length in seconds, like 20s")
        return FormSection(label, None, None, None, Fraction(free.group(1)), open_space)
    if not bars_text.isdigit() or int(bars_text) == 0:
        raise NotationError(f"section {label!r} needs a whole number of bars, not {bars_text!r}")
    meter_part, _, tempo_part = meter_text.partition("@")
    tempo = parse_tempo(tempo_part) if tempo_part.strip() else None
    return FormSection(label, int(bars_text), parse_meter(meter_part), tempo, None, open_space)


def form_seconds(sections: list[FormSection], tempo: Tempo) -> Fraction:
    """Return the playing time of a form: bars at each section's tempo plus free-time seconds."""
    total = Fraction(0)
    for section in sections:
        if section.seconds is not None:
            total += section.seconds
        elif section.meter is not None and section.bars is not None:
            total += bar_seconds(section.meter, section.tempo or tempo) * section.bars
    return total


# ---------------------------------------------------------------------------------------------
# Chord charts (spec §9.2)

_CHORD_TOKEN = re.compile(r"^(?:[A-G][#b]?[^\s|]*|%|N\.?C\.?)$")
_CHART_ROW = re.compile(r"^(?P<label>[^|=\s][^|=]*?)\s*(?P<bars>\|.*)$")
_CHART_ALIAS = re.compile(r"^(?P<label>[^|=\s][^|=]*?)\s*=\s*(?P<source>[^|=]+?)\s*$")


def check_chord_chart(text: str) -> tuple[dict[str, int], list[str]]:
    """Count each section's bars in a ``chords`` block and report malformed lines.

    Args:
        text: Contents of the fenced block.

    Returns:
        A mapping of section label to bar count (aliases resolved), and the problems found.
    """
    bars: dict[str, int] = {}
    problems: list[str] = []
    current: str | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        alias = _CHART_ALIAS.match(line)
        if alias:
            label, source = alias.group("label").strip(), alias.group("source").strip()
            if source not in bars:
                problems.append(f"chord line {number}: {label} = {source}, but {source} is unset")
            elif label in bars:
                problems.append(f"chord line {number}: section {label} is charted twice")
            else:
                bars[label] = bars[source]
            current = None
            continue
        if line.startswith("|"):
            if current is None:
                problems.append(f"chord line {number}: continuation with no section above it")
                continue
            label, cells = current, line
        else:
            row = _CHART_ROW.match(line)
            if row is None:
                problems.append(f"chord line {number}: expected 'Label | chord | … |': {line!r}")
                continue
            label, cells = row.group("label").strip(), row.group("bars")
            if label in bars:
                problems.append(f"chord line {number}: section {label} is charted twice")
                continue
            bars[label] = 0
            current = label
        segments = [segment.strip() for segment in cells.split("|")]
        # Leading and trailing pipes produce empty edge segments; empty inner ones are empty bars.
        if segments and not segments[0]:
            segments = segments[1:]
        if segments and not segments[-1]:
            segments = segments[:-1]
        for segment in segments:
            if not segment:
                problems.append(f"chord line {number}: empty bar in section {label}")
                continue
            for token in segment.split():
                if not _CHORD_TOKEN.match(token):
                    problems.append(f"chord line {number}: {token!r} is not a chord, % or N.C.")
            bars[label] += 1
    return bars, problems


# ---------------------------------------------------------------------------------------------
# Rhythm grids (spec §9.3)

_RHYTHM_HEADER = re.compile(
    r"^meter:\s*(?P<meter>[\d+]+/\d+)\s*(?:\((?P<group>[\d+\s]+)\))?\s+step:\s*(?P<step>\d+/\d+)$"
)
_RHYTHM_ROW = re.compile(r"^(?P<name>[^|]+?)\s*(?P<cells>\|.*)$")
_RHYTHM_CELLS = frozenset("xXo-.")


def check_rhythm(text: str) -> list[str]:
    """Check a ``rhythm`` block: every bar has exactly meter ÷ step cells of known symbols.

    Args:
        text: Contents of the fenced block.

    Returns:
        The problems found; empty when the grid adds up.
    """
    problems: list[str] = []
    per_bar: int | None = None
    rows = 0
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        header = _RHYTHM_HEADER.match(line)
        if header:
            try:
                meter = parse_meter(header.group("meter"))
            except NotationError as error:
                problems.append(f"rhythm line {number}: {error}")
                per_bar = None
                continue
            group = header.group("group")
            if group and sum(int(part) for part in group.split("+")) != meter.num:
                problems.append(
                    f"rhythm line {number}: grouping ({group}) does not add up to {meter.num}"
                )
            step_num, step_den = (int(part) for part in header.group("step").split("/"))
            cells = meter.length / Fraction(step_num, step_den) if step_num and step_den else None
            if cells is None or cells.denominator != 1:
                problems.append(f"rhythm line {number}: a {meter.text} bar is not whole steps")
                per_bar = None
                continue
            per_bar = int(cells)
            continue
        row = _RHYTHM_ROW.match(line)
        if row is None:
            problems.append(f"rhythm line {number}: expected 'name | x . x . |', got {line!r}")
            continue
        if per_bar is None:
            problems.append(f"rhythm line {number}: needs a 'meter: n/d  step: 1/n' line above it")
            continue
        rows += 1
        segments = row.group("cells").split("|")[1:]
        if segments and not segments[-1].strip():
            segments = segments[:-1]
        for bar_number, segment in enumerate(segments, 1):
            cells_text = "".join(segment.split())
            unknown = sorted(set(cells_text) - _RHYTHM_CELLS)
            if unknown:
                problems.append(f"rhythm line {number}: unknown cells {''.join(unknown)!r}")
            if len(cells_text) != per_bar:
                problems.append(
                    f"rhythm line {number} ({row.group('name')}), bar {bar_number}: "
                    f"{len(cells_text)} cells, needs {per_bar}"
                )
    if rows == 0 and not problems:
        problems.append("rhythm block has no rows")
    return problems


# ---------------------------------------------------------------------------------------------
# ABC heads (spec §9.4)

_FIELD_LINE = re.compile(r"^([A-Za-z]):(.*)$")
_INLINE_FIELD = re.compile(r"\[([A-Za-z]):([^\]]*)\]")
_BARLINE = re.compile(r"\[\||:*\|+[\]:]*|:{2,}")
_ENDING = re.compile(r"\[?\d+(?:[,-]\d+)*")
_TUPLET = re.compile(r"\((\d)(?::(\d*))?(?::(\d*))?")
_NOTE = re.compile(r"(?:\^\^|\^|__|_|=)?[A-Ga-g][',]*")
_LENGTH = re.compile(r"(\d*)(/*)(\d*)")
_DIGITS = re.compile(r"\d*")
_REST = frozenset("zx")
_BAR_REST = frozenset("ZX")
_SKIPPED = frozenset(" \t`.~y$\\)-")
_REQUIRED_HEADERS = ("X", "T", "M", "L", "K")


@dataclass
class _Bar:
    held: Fraction
    meter: Meter
    unit: Fraction
    line: int


@dataclass
class _Voice:
    meter: Meter
    unit: Fraction
    bars: list[_Bar] = field(default_factory=list)
    held: Fraction = Fraction(0)
    started: bool = False
    line: int = 0
    last: Fraction | None = None
    next_factor: Fraction = Fraction(1)
    tuplet_left: int = 0
    tuplet_factor: Fraction = Fraction(1)

    def add(self, duration: Fraction, line: int) -> None:
        if not self.started:
            self.started, self.line = True, line
        duration *= self.next_factor
        self.next_factor = Fraction(1)
        if self.tuplet_left:
            duration *= self.tuplet_factor
            self.tuplet_left -= 1
        self.held += duration
        self.last = duration

    def close(self) -> None:
        if self.started:
            self.bars.append(_Bar(self.held, self.meter, self.unit, self.line))
        self.held, self.started, self.last = Fraction(0), False, None
        self.next_factor, self.tuplet_left = Fraction(1), 0


def _length(text: str, pos: int) -> tuple[Fraction | None, int]:
    """Read an ABC length multiplier at ``pos``; None means a malformed or zero length."""
    match = _LENGTH.match(text, pos)
    assert match is not None  # every group is optional, so the pattern always matches
    digits, slashes, divisor = match.groups()
    if not digits and not slashes:
        return Fraction(1), pos
    num = int(digits) if digits else 1
    if slashes and divisor:
        if len(slashes) > 1:
            return None, match.end()
        den = int(divisor)
    else:
        den = 2 ** len(slashes)
    if num == 0 or den == 0:
        return None, match.end()
    return Fraction(num, den), match.end()


def _tuplet_q(p: int, meter: Meter) -> int:
    """ABC 2.1's default 'in the time of' count for a ``(p`` tuplet."""
    if p in (2, 4, 8):
        return 3
    if p in (3, 6):
        return 2
    return 3 if meter.compound else 2


class _AbcScan:
    """Walks one ABC tune body, voice by voice, collecting bars and problems."""

    def __init__(self, label: str, meter: Meter, unit: Fraction) -> None:
        self.label = label
        self.meter, self.unit = meter, unit
        self.voices: dict[str, _Voice] = {}
        self.voice = self.switch("1")
        self.problems: list[str] = []

    def switch(self, name: str) -> _Voice:
        if name not in self.voices:
            self.voices[name] = _Voice(self.meter, self.unit)
        self.voice = self.voices[name]
        return self.voice

    def problem(self, line: int, message: str) -> None:
        self.problems.append(f"{self.label}, line {line}: {message}")

    def field(self, key: str, value: str, line: int) -> None:
        if key == "M":
            try:
                self.voice.meter = parse_meter(value)
            except NotationError as error:
                self.problem(line, str(error))
        elif key == "L":
            try:
                meter = parse_meter(value)
            except NotationError:
                self.problem(line, f"L:{value.strip()} is not a note length like 1/8")
            else:
                self.voice.unit = meter.length
        elif key == "V":
            name = value.split()[0] if value.split() else "1"
            self.switch(name)
        elif key in "wW":
            self.problem(line, "lyrics lines are not allowed; albums are instrumental")

    def scan(self, text: str, line: int) -> None:
        pos, end = 0, len(text)
        while pos < end:
            char = text[pos]
            if char == "%":
                return
            if char in _SKIPPED:
                pos += 1
            elif char == "&":
                self.problem(line, "'&' voice overlays are not allowed; use V: voices")
                pos += 1
            elif char in '"!+{':
                closer = {'"': '"', "!": "!", "+": "+", "{": "}"}[char]
                stop = text.find(closer, pos + 1)
                if stop < 0:
                    self.problem(line, f"unclosed {char}")
                    return
                pos = stop + 1
            elif char == "(":
                tuplet = _TUPLET.match(text, pos)
                if tuplet:
                    p = int(tuplet.group(1))
                    q = int(tuplet.group(2)) if tuplet.group(2) else _tuplet_q(p, self.voice.meter)
                    r = int(tuplet.group(3)) if tuplet.group(3) else p
                    self.voice.tuplet_factor, self.voice.tuplet_left = Fraction(q, p), r
                    pos = tuplet.end()
                else:
                    pos += 1  # slur
            elif char in "<>":
                run = len(text[pos:]) - len(text[pos:].lstrip(char))
                pos += run
                if self.voice.last is None:
                    self.problem(line, f"'{char}' has no note before it in the bar")
                    continue
                short = Fraction(1, 2**run)
                long_ = 2 - short
                before, after = (long_, short) if char == ">" else (short, long_)
                self.voice.held += self.voice.last * (before - 1)
                self.voice.next_factor = after
            elif char == "[" and text.startswith("[|", pos):
                self.voice.close()
                pos += 2
            elif char == "[" and _ENDING.match(text, pos) and text[pos + 1 : pos + 2].isdigit():
                ending = _ENDING.match(text, pos)
                assert ending is not None
                pos = ending.end()
            elif char == "[" and _INLINE_FIELD.match(text, pos):
                inline = _INLINE_FIELD.match(text, pos)
                assert inline is not None
                self.field(inline.group(1), inline.group(2), line)
                pos = inline.end()
            elif char == "[":
                pos = self.chord(text, pos, line)
            elif char in "|:":
                barline = _BARLINE.match(text, pos)
                if barline is None:
                    self.problem(line, "a lone ':' is not a bar line")
                    pos += 1
                    continue
                self.voice.close()
                pos = barline.end()
                ending = _ENDING.match(text, pos)
                if ending and ending.group(0)[:1].isdigit():
                    pos = ending.end()
            elif char in _REST:
                duration, pos = _length(text, pos + 1)
                self.timed(duration, line)
            elif char in _BAR_REST:
                digits = _DIGITS.match(text, pos + 1)
                assert digits is not None  # \d* matches the empty string too
                count_text = digits.group(0)
                pos += 1 + len(count_text)
                if self.voice.started:
                    self.problem(line, f"'{char}' bar rest inside a bar that already has notes")
                    continue
                for _ in range(int(count_text) if count_text else 1):
                    self.voice.bars.append(
                        _Bar(self.voice.meter.length, self.voice.meter, self.voice.unit, line)
                    )
            elif _NOTE.match(text, pos):
                note = _NOTE.match(text, pos)
                assert note is not None
                duration, pos = _length(text, note.end())
                self.timed(duration, line)
            elif char.isalpha():
                self.problem(line, f"'{char}' is not allowed in music; write decorations as !name!")
                pos += 1
            else:
                self.problem(line, f"unsupported ABC symbol {char!r}")
                pos += 1

    def timed(self, duration: Fraction | None, line: int) -> None:
        if duration is None:
            self.problem(line, "malformed note length")
            return
        self.voice.add(duration * self.voice.unit, line)

    def chord(self, text: str, pos: int, line: int) -> int:
        stop = text.find("]", pos)
        if stop < 0:
            self.problem(line, "unclosed chord '['")
            return len(text)
        inner = text[pos + 1 : stop]
        first = _NOTE.search(inner)
        if first is None:
            self.problem(line, f"chord [{inner}] has no notes")
            return stop + 1
        inner_length, _ = _length(inner, first.end())
        outer_length, after = _length(text, stop + 1)
        if inner_length is None or outer_length is None:
            self.problem(line, "malformed note length in chord")
            return after
        self.voice.add(inner_length * outer_length * self.voice.unit, line)
        return after

    def judge(self) -> None:
        for voice in self.voices.values():
            voice.close()
        many = len([voice for voice in self.voices.values() if voice.bars]) > 1
        counts = {name: len(voice.bars) for name, voice in self.voices.items() if voice.bars}
        if len(set(counts.values())) > 1:
            # Voices play the same tune side by side, so a missing bar in one hand is a mistake.
            listed = ", ".join(f"{name} {count}" for name, count in counts.items())
            self.problems.append(f"{self.label}: voices have different bar counts ({listed})")
        for name, voice in self.voices.items():
            if not voice.bars:
                continue
            where = f"{self.label}, voice {name}" if many else self.label
            bars = voice.bars
            pickup = bars[0].held < bars[0].meter.length and len(bars) > 1
            for index, bar in enumerate(bars):
                need = bar.meter.length
                if bar.held == need:
                    continue
                if index == 0 and pickup:
                    if bars[-1].held + bar.held != bars[-1].meter.length:
                        self.problems.append(
                            f"{where}: the pickup bar holds {_units(bar)} of L:{_frac(bar.unit)}, "
                            f"so the last bar must hold the rest of a {bar.meter.text} bar"
                        )
                    continue
                if index == len(bars) - 1 and pickup:
                    continue  # completes the pickup; checked with the first bar
                self.problems.append(
                    f"{where}, bar {index + 1} (line {bar.line}): holds {_units(bar)} of "
                    f"L:{_frac(bar.unit)} but {bar.meter.text} needs {_units(bar, need)}"
                )


def _frac(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _units(bar: _Bar, held: Fraction | None = None) -> str:
    return _frac((bar.held if held is None else held) / bar.unit)


def check_abc(text: str, label: str = "abc") -> list[str]:
    """Check an ABC block against the spec subset and count every bar of every voice.

    Args:
        text: Contents of the fenced block.
        label: Name used in problem messages, such as the block's position.

    Returns:
        The problems found; empty when the header is complete and every bar adds up.
    """
    lines = text.splitlines()
    headers: dict[str, str] = {}
    body_start = None
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        match = _FIELD_LINE.match(line)
        if match is None:
            break
        key, value = match.group(1), match.group(2).strip()
        headers.setdefault(key, value)
        if key == "K":
            body_start = index + 1
            break
    title = headers.get("T")
    where = f"{label} ({title})" if title else label
    missing = [key for key in _REQUIRED_HEADERS if key not in headers]
    if missing or body_start is None:
        absent = ", ".join(f"{key}:" for key in missing) or "K: last"
        return [f"{where}: header needs X:, T:, M:, L: and K: (missing {absent})"]
    try:
        meter = parse_meter(headers["M"])
        unit = parse_meter(headers["L"]).length
    except NotationError as error:
        return [f"{where}: {error}"]
    scan = _AbcScan(where, meter, unit)
    for offset, raw in enumerate(lines[body_start:], body_start + 1):
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        field_line = _FIELD_LINE.match(line)
        if field_line:
            scan.field(field_line.group(1), field_line.group(2), offset)
            continue
        scan.scan(line, offset)
    scan.judge()
    if not scan.problems and not any(voice.bars for voice in scan.voices.values()):
        return [f"{where}: no bars"]
    return scan.problems

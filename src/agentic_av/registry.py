"""Validate band, visual group, album and track docs against the band-album spec.

bands/, visual-groups/ and albums/ hold the project's canonical record of who makes each album and
how (docs/spec/band-album-spec.md). This module reads those docs (Markdown with a TOML card) and
reports every rule the spec makes checkable: card fields, section order, member counts, text limits,
references between docs, the 3x2 take loop, credits, and the bar arithmetic in notation.py.
``python -m agentic_av.registry`` runs it over directory roots; tests/test_registry.py runs it in
CI, so a doc that breaks the spec fails the gate. Stdlib only (tomllib): checking a doc needs
nothing beyond Python.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

from agentic_av import notation
from agentic_av.catalog import format_clock

KINDS = ("band", "visual-group", "album", "track")
"""Doc kinds, as named in templates/ and validate_template()."""

DIRECTION_LIMIT = 220
"""Characters allowed in an album direction, a previous-album review or a swarm seed (spec §1.4)."""

BLURB_LIMIT = 160
"""Characters allowed in an album's library blurb (spec §2)."""

_PERSONA_WORDS = (60, 140)
_DESCRIPTION_WORDS = (60, 160)
_CONCEPT_WORDS = (80, 300)
_ALBUM_SECONDS = (25 * 60, 30 * 60)
# A stated track length may fall short of the bar sum by rounding, or run long by a ring-out tail.
_LENGTH_SLACK = (5, 20)
_TRACK_REVIEW_ITEMS = 9
_ALBUM_REVIEW_ITEMS = 7
_MIN_PROSE_WORDS = 15

_SECTIONS = {
    "band": ("Members", "Description", "Sound", "Discography", "Provenance"),
    "visual-group": ("Members", "Description", "Visual language", "Discography", "Provenance"),
    "album": (
        "Concept",
        "Tracklist",
        "Mastery",
        "Cover",
        "Library blurb",
        "Self-review",
        "Provenance",
    ),
    "track": (
        "Composition passes",
        "Composition",
        "Recording",
        "Mastery",
        "Visuals",
        "Self-review",
    ),
}
_COMPOSITION = ("Form", "Harmony", "Core rhythms", "Heads", "Lyrics")
_RECORDING = ("Round 1", "Round 2", "Band decision")
_VISUALS = ("Round 1", "Round 2", "Group decision", "Scene")
_FORM_HEADER = ("Section", "Bars", "Meter", "Texture and intensity", "Open space")
_TRACKLIST_HEADER = ("#", "Title", "Length", "Key", "Meter", "Tempo", "Composers")
_BAND_DISCOGRAPHY = ("ID", "Title", "Year", "Length", "Tracks", "Made with")
_GROUP_DISCOGRAPHY = ("Band", "ID", "Title", "Year", "Scenes")
_SCENE_TABLE = ("Source", "Visual behavior")
_RESERVED_PARTS = ("composition", "mastering", "visuals")
_NO_OPEN_SPACE = frozenset({"", "-", "\u2013", "\u2014", "none", "n/a"})

_BAND_ID = re.compile(r"^B-\d{2,3}$")
_GROUP_ID = re.compile(r"^V-\d{2,3}$")
_ALBUM_ID = re.compile(r"^A-\d{2}$")
_FROM_ID = re.compile(r"^[BV]-\d{2,3}$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MODEL = re.compile(r"^[a-z0-9][a-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:+-]*$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_DASH = r"\s+[\u2014\u2013-]\s+"
_PASS = re.compile(rf"^Pass\s+(?P<number>\d+){_DASH}(?P<name>.+)$")
_SLOT = re.compile(rf"^(?P<member>.+?){_DASH}(?P<part>.+)$")
_TAKE = re.compile(r"^Take\s+(?P<number>\d):\s*(?P<text>.*)$")
_PICK = re.compile(
    r"^Picked by\s+(?P<who>.+?):\s*Take\s+(?P<take>\d)\b\s*[\u2014\u2013-]?\s*(?P<why>.*)$"
)
_BAND_CHOICE = re.compile(
    rf"^(?P<member>.+?){_DASH}(?P<part>.+?):\s*Round\s+(?P<round>\d),\s*Take\s+(?P<take>\d)\b"
)
_GROUP_CHOICE = re.compile(r"^(?P<member>.+?):\s*Round\s+(?P<round>\d),\s*Take\s+(?P<take>\d)\b")
_LABELED = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s*(?P<value>.*)$")
_CHECKBOX = re.compile(r"^\[(?P<mark>[ xX])\]\s+\S")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^(`{3,}|~{3,})\s*([\w+-]*)")
_BULLET = re.compile(r"^\s{0,3}[-*]\s+(.*)$")
# Albums are instrumental for now (spec §1.1), so no member may list a voice as an instrument.
_VOICE = re.compile(r"\b(?:voice|vocals?|sing(?:er|ing)?|voicebank|rap(?:per|ping)?)\b", re.I)


@dataclass(frozen=True, order=True)
class Problem:
    """One spec violation found in a doc.

    Attributes:
        path: The doc's path as discovered (relative when the root was relative).
        line: 1-based line of the offending text, or 0 when it concerns the whole doc.
        message: What is wrong, phrased so the author can fix it.
    """

    path: str
    line: int
    message: str

    def __str__(self) -> str:
        """Format as ``path:line: message``, the form editors and terminals link."""
        if self.line:
            return f"{self.path}:{self.line}: {self.message}"
        return f"{self.path}: {self.message}"


# ---------------------------------------------------------------------------------------------
# Markdown and card parsing


@dataclass
class _Section:
    title: str
    level: int
    line: int
    lines: list[tuple[int, str]] = field(default_factory=list)
    children: list[_Section] = field(default_factory=list)

    def child(self, title: str) -> _Section | None:
        return next((section for section in self.children if section.title == title), None)


@dataclass
class _Doc:
    path: str
    root: _Section
    title: str | None = None
    card: dict[str, Any] | None = None
    card_line: int = 0

    @property
    def sections(self) -> list[_Section]:
        return self.root.children

    def section(self, title: str) -> _Section | None:
        return self.root.child(title)


@dataclass
class _Context:
    template: bool
    problems: list[Problem] = field(default_factory=list)
    bands: dict[str, _Doc] = field(default_factory=dict)
    groups: dict[str, _Doc] = field(default_factory=dict)

    def add(self, doc: _Doc, line: int, message: str) -> None:
        self.problems.append(Problem(doc.path, line, message))


def _parse(path: str, text: str, ctx: _Context) -> _Doc:
    """Split a doc into its title, TOML card and heading tree; comments are dropped first."""
    # Comments become blank lines so every reported line number still matches the file.
    text = _COMMENT.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    root = _Section("", 0, 0)
    doc = _Doc(path, root)
    stack = [root]
    fence: str | None = None
    card_lines: list[str] | None = None
    card_state = "before"
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if fence is not None:
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
                if card_state == "open" and card_lines is not None:
                    _load_card(doc, "\n".join(card_lines), ctx)
                    card_state = "done"
            elif card_state == "open" and card_lines is not None:
                card_lines.append(raw)
            stack[-1].lines.append((number, raw))
            continue
        opening = _FENCE.match(stripped)
        if opening:
            fence = opening.group(1)
            if card_state == "before":
                if opening.group(2) == "toml" and len(stack) == 1:
                    card_state, card_lines, doc.card_line = "open", [], number
                else:
                    card_state = "done"
            stack[-1].lines.append((number, raw))
            continue
        heading = _HEADING.match(raw)
        if heading:
            level, title = len(heading.group(1)), heading.group(2).strip()
            if level == 1:
                if doc.title is None:
                    doc.title = title
                else:
                    ctx.add(doc, number, "a doc has one '# Title' line")
                continue
            if card_state == "before":
                card_state = "done"
            section = _Section(title, level, number)
            while stack[-1].level >= level:
                stack.pop()
            stack[-1].children.append(section)
            stack.append(section)
            continue
        stack[-1].lines.append((number, raw))
    if doc.title is None:
        ctx.add(doc, 0, "missing the '# Title' line")
    if doc.card is None and card_state != "open":
        ctx.add(doc, doc.card_line, "missing the card: a ```toml block before the first section")
    return doc


def _load_card(doc: _Doc, text: str, ctx: _Context) -> None:
    try:
        doc.card = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        ctx.add(doc, doc.card_line, f"the card is not valid TOML: {error}")


def _blocks(section: _Section | None) -> list[tuple[str, str, int]]:
    """Fenced blocks written directly in a section: (tag, contents, opening line)."""
    found: list[tuple[str, str, int]] = []
    if section is None:
        return found
    fence: str | None = None
    tag, start, buffer = "", 0, []
    for number, raw in section.lines:
        stripped = raw.strip()
        if fence is None:
            opening = _FENCE.match(stripped)
            if opening:
                fence, tag, start, buffer = opening.group(1), opening.group(2), number, []
        elif stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
            found.append((tag, "\n".join(buffer), start))
            fence = None
        else:
            buffer.append(raw)
    return found


def _prose(section: _Section | None) -> list[tuple[int, str]]:
    """A section's own lines outside fenced blocks."""
    kept: list[tuple[int, str]] = []
    if section is None:
        return kept
    fence: str | None = None
    for number, raw in section.lines:
        stripped = raw.strip()
        if fence is None:
            opening = _FENCE.match(stripped)
            if opening:
                fence = opening.group(1)
                continue
            kept.append((number, raw))
        elif stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
            fence = None
    return kept


def _paragraphs(section: _Section | None) -> list[tuple[int, str]]:
    """Blank-line separated prose paragraphs, excluding tables and list items.

    A list item's wrapped lines belong to the item (as in ``_bullets``), not to a paragraph.
    """
    found: list[tuple[int, str]] = []
    current: list[str] = []
    start = 0
    open_item = False
    for number, raw in [*_prose(section), (0, "")]:
        stripped = raw.strip()
        bullet = _BULLET.match(raw) is not None
        if not stripped or bullet or stripped.startswith("|") or open_item:
            if current:
                found.append((start, " ".join(current)))
            current = []
            open_item = bullet or (open_item and bool(stripped) and not stripped.startswith("|"))
            continue
        if not current:
            start = number
        current.append(stripped)
    return found


def _bullets(section: _Section | None) -> list[tuple[int, str]]:
    """Top-level list items with wrapped continuation lines joined on."""
    found: list[tuple[int, str]] = []
    open_item = False
    for number, raw in _prose(section):
        bullet = _BULLET.match(raw)
        if bullet:
            found.append((number, bullet.group(1).strip()))
            open_item = True
        elif raw.strip() and open_item and not raw.strip().startswith("|"):
            line, text = found[-1]
            found[-1] = (line, f"{text} {raw.strip()}")
        else:
            open_item = False
    return found


def _table(section: _Section | None) -> tuple[tuple[str, ...], list[tuple[int, list[str]]]] | None:
    """The first Markdown table in a section: its header and data rows with line numbers."""
    rows: list[tuple[int, list[str]]] = []
    for number, raw in _prose(section):
        stripped = raw.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.replace("\\|", "\0").strip("|").split("|")]
            rows.append((number, [cell.replace("\0", "|") for cell in cells]))
        elif rows:
            break
    if len(rows) < 2:
        return None
    header = tuple(rows[0][1])
    body = [row for row in rows[2:] if not all(set(cell) <= set(":-") for cell in row[1])]
    return header, body


def _words(text: str) -> int:
    return len(text.split())


def _plain(cell: str) -> str:
    """Table cell text without Markdown emphasis or code marks."""
    return " ".join(re.sub(r"[*_`]", "", cell).split())


def slugify(name: str) -> str:
    """Return the spec's slug for a name: lowercase ASCII words joined by single hyphens.

    Args:
        name: A band, visual group, album or track name.

    Returns:
        The slug, e.g. ``Buy One, Haunt One Free`` → ``buy-one-haunt-one-free``. Apostrophes are
        dropped rather than split on, so ``Don't`` becomes ``dont``.
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"['\u2019]", "", ascii_name.lower())
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")


# ---------------------------------------------------------------------------------------------
# Card schemas


@dataclass(frozen=True)
class _Field:
    kind: str
    required: bool = True
    choices: tuple[Any, ...] = ()
    pattern: re.Pattern[str] | None = None
    count: tuple[int, int] | None = None
    empty_ok: bool = False


_BAND_FIELDS = {
    "id": _Field("str", pattern=_BAND_ID),
    "name": _Field("str"),
    "slug": _Field("str", pattern=_SLUG),
    "status": _Field("str", choices=("active", "retired")),
    "genres": _Field("list", count=(2, 3)),
    "instrumental": _Field("bool", choices=(True,)),
    "house_visual_group": _Field("str", required=False, pattern=_GROUP_ID),
    "label": _Field("str", required=False),
    "house_engineer": _Field("str", required=False),
    "production_layers": _Field("list", required=False, count=(0, 12)),
}
_BAND_MEMBER_FIELDS = {
    "name": _Field("str"),
    "roles": _Field("list", count=(1, 2)),
    "instruments": _Field("list", required=False, count=(1, 6)),
    "influences": _Field("list", count=(2, 5)),
    "from": _Field("str", required=False, pattern=_FROM_ID),
}
_BAND_PROCESS_FIELDS = {
    "composer_rotation": _Field("list", required=False),
    "recording_order": _Field("list", required=False),
    "refinement_order": _Field("list", required=False),
}
_GROUP_FIELDS = {
    "id": _Field("str", pattern=_GROUP_ID),
    "name": _Field("str"),
    "slug": _Field("str", pattern=_SLUG),
    "status": _Field("str", choices=("active", "retired")),
    "house_band": _Field("str", required=False, pattern=_BAND_ID),
}
_GROUP_MEMBER_FIELDS = {
    "name": _Field("str"),
    "medium": _Field("str"),
    "responsibility": _Field("str"),
    "influences": _Field("list", count=(2, 5)),
    "from": _Field("str", required=False, pattern=_FROM_ID),
}
_GROUP_PROCESS_FIELDS = {"order": _Field("list", required=False)}
_ALBUM_FIELDS = {
    "id": _Field("str", pattern=_ALBUM_ID),
    "band": _Field("str", pattern=_BAND_ID),
    "visual_group": _Field("str", pattern=_GROUP_ID),
    "title": _Field("str"),
    "slug": _Field("str", pattern=_SLUG),
    "scope": _Field("str", choices=("album", "test")),
    "status": _Field("str", choices=("draft", "final")),
    "date": _Field("date"),
    "instrumental": _Field("bool", choices=(True,)),
    "rendered": _Field("bool"),
    "recording": _Field("str", choices=("by-album", "by-track")),
    "round1_order": _Field("list", count=(2, 99)),
    "round2_order": _Field("list", count=(2, 99)),
    "visual_round1_order": _Field("list", count=(2, 3)),
    "visual_round2_order": _Field("list", count=(2, 3)),
    "mastered_by": _Field("str"),
    "made_with": _Field("list", count=(1, 99)),
    "harness": _Field("str", required=False),
    "tracks": _Field("list", count=(1, 99)),
}
_COMMISSION_FIELDS = {
    "direction": _Field("str", empty_ok=True),
    "reviews": _Field("tables", required=False),
}
_REVIEW_FIELDS = {"album": _Field("str", pattern=_ALBUM_ID), "text": _Field("str")}
_TRACK_FIELDS = {
    "album": _Field("str", pattern=_ALBUM_ID),
    "band": _Field("str", pattern=_BAND_ID),
    "number": _Field("int"),
    "title": _Field("str"),
    "slug": _Field("str", pattern=_SLUG),
    "key": _Field("str"),
    "meter": _Field("str"),
    "tempo": _Field("str"),
    "length": _Field("str"),
    "composers": _Field("list", count=(1, 99)),
}
_CREDIT_FIELDS = {
    "member": _Field("str"),
    "part": _Field("str"),
    "model": _Field("str", pattern=_MODEL),
}
_KIND_TEXT = {
    "str": "a non-empty string",
    "bool": "true or false",
    "int": "a whole number",
    "list": "a list of non-empty strings",
    "date": "a YYYY-MM-DD date",
    "tables": "a list of tables",
}


def _kind_ok(kind: str, value: Any, empty_ok: bool) -> bool:
    if kind == "str":
        return isinstance(value, str) and (empty_ok or bool(value.strip()))
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "list":
        return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)
    if kind == "date":
        return isinstance(value, date) or (isinstance(value, str) and bool(value.strip()))
    return isinstance(value, list) and all(isinstance(v, dict) for v in value)


def _check_fields(
    ctx: _Context, doc: _Doc, table: Any, where: str, schema: dict[str, _Field]
) -> dict[str, Any]:
    """Check one card table against its schema; returns the table, or {} if it is not a table."""
    if not isinstance(table, dict):
        ctx.add(doc, doc.card_line, f"card {where} must be a table")
        return {}
    for key, spec in schema.items():
        if key not in table:
            if spec.required:
                ctx.add(doc, doc.card_line, f"card {where} is missing `{key}`")
            continue
        value = table[key]
        if not _kind_ok(spec.kind, value, spec.empty_ok):
            ctx.add(doc, doc.card_line, f"card {where} `{key}` must be {_KIND_TEXT[spec.kind]}")
            continue
        if spec.choices and value not in spec.choices:
            choices = " or ".join(repr(choice).lower() for choice in spec.choices)
            ctx.add(doc, doc.card_line, f"card {where} `{key}` must be {choices}")
        if spec.count and not spec.count[0] <= len(value) <= spec.count[1]:
            low, high = spec.count
            ctx.add(doc, doc.card_line, f"card {where} `{key}` needs {low} to {high} entries")
        if ctx.template:
            continue
        if spec.pattern and not spec.pattern.match(value):
            ctx.add(doc, doc.card_line, f"card {where} `{key}` = {value!r} is not well formed")
        if spec.kind == "date" and isinstance(value, str) and not _ISO_DATE.match(value):
            ctx.add(doc, doc.card_line, f"card {where} `{key}` must be YYYY-MM-DD")
    for key in table:
        if key not in schema:
            ctx.add(doc, doc.card_line, f"card {where} has unknown key `{key}`")
    return table


def _card_tables(
    ctx: _Context, doc: _Doc, tables: dict[str, tuple[str, bool]]
) -> dict[str, Any] | None:
    """Check the card's top-level tables: name → (kind 'table' | 'tables', required)."""
    if doc.card is None:
        return None
    for name, (kind, required) in tables.items():
        if name not in doc.card:
            if required:
                ctx.add(doc, doc.card_line, f"card is missing [{name}]")
            continue
        value = doc.card[name]
        if kind == "table" and not isinstance(value, dict):
            ctx.add(doc, doc.card_line, f"card [{name}] must be a table")
        if kind == "tables" and not (
            isinstance(value, list) and all(isinstance(v, dict) for v in value)
        ):
            ctx.add(doc, doc.card_line, f"card [[{name}]] must be a list of tables")
    for name in doc.card:
        if name not in tables:
            ctx.add(doc, doc.card_line, f"card has unknown table [{name}]")
    return doc.card


def _str(table: dict[str, Any], key: str) -> str:
    value = table.get(key)
    return value if isinstance(value, str) else ""


def _strs(table: dict[str, Any], key: str) -> list[str]:
    value = table.get(key)
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


# ---------------------------------------------------------------------------------------------
# Section checks shared by every kind


def _check_sections(ctx: _Context, doc: _Doc, kind: str) -> None:
    expected = _SECTIONS[kind]
    titles = [section.title for section in doc.sections]
    for section in doc.sections:
        if section.title not in expected:
            ctx.add(doc, section.line, f"unknown section '## {section.title}'")
        elif titles.count(section.title) > 1:
            ctx.add(doc, section.line, f"section '## {section.title}' appears twice")
    for title in expected:
        if title not in titles:
            ctx.add(doc, 0, f"missing section '## {title}'")
    present = [title for title in titles if title in expected]
    if present != [title for title in expected if title in present]:
        ctx.add(doc, 0, f"sections must come in this order: {', '.join(expected)}")


def _check_children(
    ctx: _Context, doc: _Doc, section: _Section | None, expected: Sequence[str]
) -> None:
    if section is None:
        return
    titles = [child.title for child in section.children]
    if titles != list(expected):
        wanted = ", ".join(f"### {title}" for title in expected)
        ctx.add(doc, section.line, f"'## {section.title}' needs exactly: {wanted}")


def _one_paragraph(
    ctx: _Context, doc: _Doc, section: _Section | None, what: str, words: tuple[int, int]
) -> None:
    if section is None:
        return
    paragraphs = _paragraphs(section)
    if _bullets(section) or _table(section) or len(paragraphs) != 1:
        ctx.add(doc, section.line, f"{what} must be one paragraph")
        return
    count = _words(paragraphs[0][1])
    if not ctx.template and not words[0] <= count <= words[1]:
        ctx.add(doc, section.line, f"{what} is {count} words; it needs {words[0]} to {words[1]}")


def _labeled(
    ctx: _Context, doc: _Doc, section: _Section | None, required: Sequence[str]
) -> dict[str, str]:
    """Collect '- **Label:** value' bullets and report missing required labels."""
    found: dict[str, str] = {}
    if section is None:
        return found
    for _, text in _bullets(section):
        match = _LABELED.match(text)
        if match:
            found[match.group("label").strip()] = match.group("value").strip()
    for label in required:
        if not found.get(label):
            ctx.add(doc, section.line, f"'## {section.title}' needs a '- **{label}:** …' bullet")
    return found


def _check_prose(ctx: _Context, doc: _Doc, section: _Section | None, what: str) -> None:
    if section is None:
        return
    text = " ".join(line.strip() for _, line in _prose(section))
    if not text.strip():
        ctx.add(doc, section.line, f"{what} is empty")
    elif not ctx.template and _words(text) < _MIN_PROSE_WORDS:
        ctx.add(doc, section.line, f"{what} needs at least {_MIN_PROSE_WORDS} words")


def _check_provenance(ctx: _Context, doc: _Doc) -> None:
    section = doc.section("Provenance")
    if section is not None and not _bullets(section):
        ctx.add(doc, section.line, "'## Provenance' needs at least one bullet")


def _check_self_review(ctx: _Context, doc: _Doc, minimum: int) -> None:
    section = doc.section("Self-review")
    if section is None:
        return
    marks = [
        (line, match.group("mark"))
        for line, text in _bullets(section)
        if (match := _CHECKBOX.match(text))
    ]
    if len(marks) < minimum:
        ctx.add(doc, section.line, f"'## Self-review' needs the template's {minimum} items")
    if not ctx.template:
        for line, mark in marks:
            if mark == " ":
                ctx.add(doc, line, "unchecked self-review item: fix the doc, then check it")


def _check_order(
    ctx: _Context, doc: _Doc, order: list[str], expected: Sequence[str], where: str
) -> None:
    if sorted(order) != sorted(expected) or len(set(order)) != len(order):
        ctx.add(doc, doc.card_line, f"card {where} must list each of {', '.join(expected)} once")


# ---------------------------------------------------------------------------------------------
# Bands and visual groups


def _check_members(
    ctx: _Context, doc: _Doc, members: list[dict[str, Any]], schema: dict[str, _Field]
) -> list[str]:
    names: list[str] = []
    for index, member in enumerate(members, 1):
        _check_fields(ctx, doc, member, f"[[members]] #{index}", schema)
        name = _str(member, "name")
        if name in names:
            ctx.add(doc, doc.card_line, f"two members are named {name!r}")
        elif name:
            names.append(name)
    return names


def _check_personas(ctx: _Context, doc: _Doc, names: list[str]) -> None:
    section = doc.section("Members")
    if section is None:
        return
    if [child.title for child in section.children] != names:
        wanted = ", ".join(names)
        ctx.add(doc, section.line, f"'## Members' needs '### <name>' for {wanted}, in order")
    for child in section.children:
        _one_paragraph(ctx, doc, child, f"the persona of {child.title}", _PERSONA_WORDS)


def _discography(ctx: _Context, doc: _Doc, header: tuple[str, ...]) -> list[tuple[int, list[str]]]:
    section = doc.section("Discography")
    if section is None:
        return []
    table = _table(section)
    if table is None or table[0] != header:
        ctx.add(doc, section.line, f"'## Discography' needs a table: {' | '.join(header)}")
        return []
    rows = []
    for line, cells in table[1]:
        if len(cells) != len(header):
            ctx.add(doc, line, f"discography rows need {len(header)} cells")
        else:
            rows.append((line, cells))
    return rows


def _check_band(doc: _Doc, ctx: _Context) -> None:
    _check_sections(ctx, doc, "band")
    card = _card_tables(
        ctx,
        doc,
        {"band": ("table", True), "members": ("tables", True), "process": ("table", False)},
    )
    names: list[str] = []
    if card is not None:
        band = _check_fields(ctx, doc, card.get("band", {}), "[band]", _BAND_FIELDS)
        members = _dicts(card.get("members"))
        names = _check_members(ctx, doc, members, _BAND_MEMBER_FIELDS)
        musicians, composers = [], []
        for member in members:
            roles, name = _strs(member, "roles"), _str(member, "name")
            unknown = sorted(set(roles) - {"musician", "composer"})
            if unknown or len(set(roles)) != len(roles):
                ctx.add(doc, doc.card_line, f"{name}: roles are 'musician' and/or 'composer'")
            if "musician" in roles:
                musicians.append(name)
                if not _strs(member, "instruments"):
                    ctx.add(doc, doc.card_line, f"{name} is a musician and needs `instruments`")
                for instrument in _strs(member, "instruments"):
                    if _VOICE.search(instrument):
                        ctx.add(
                            doc, doc.card_line, f"{name}: no voice parts; albums are instrumental"
                        )
            elif "instruments" in member:
                ctx.add(doc, doc.card_line, f"{name} has instruments but not the musician role")
            if "composer" in roles:
                composers.append(name)
        if len(musicians) < 2:
            ctx.add(doc, doc.card_line, "a band needs at least two musicians (spec §1.1)")
        if not set(musicians) & set(composers):
            ctx.add(doc, doc.card_line, "at least one musician must also be a composer (spec §1.1)")
        process = card.get("process")
        if process is not None:
            process = _check_fields(ctx, doc, process, "[process]", _BAND_PROCESS_FIELDS)
            orders = (
                ("composer_rotation", composers),
                ("recording_order", musicians),
                ("refinement_order", musicians),
            )
            for key, expected in orders:
                if key in process:
                    _check_order(ctx, doc, _strs(process, key), expected, f"[process] `{key}`")
        if not ctx.template:
            _check_identity(ctx, doc, band, "bands")
            group_id = _str(band, "house_visual_group")
            group = ctx.groups.get(group_id)
            if group_id and group is None:
                ctx.add(doc, doc.card_line, f"house visual group {group_id} has no doc")
            elif group is not None and group.card is not None:
                house = _str(group.card.get("visual_group", {}), "house_band")
                if house and house != _str(band, "id"):
                    ctx.add(doc, doc.card_line, f"{group_id} names {house} as its house band")
    _check_personas(ctx, doc, names)
    _one_paragraph(ctx, doc, doc.section("Description"), "the description", _DESCRIPTION_WORDS)
    _labeled(ctx, doc, doc.section("Sound"), ("Core sound", "Keep", "Avoid"))
    for line, cells in _discography(ctx, doc, _BAND_DISCOGRAPHY):
        album_id, _, year, length, tracks, made_with = cells
        if not _ALBUM_ID.match(album_id) or not year.isdigit() or not tracks.isdigit():
            ctx.add(doc, line, "discography row needs an A-NN id, a year and a track count")
        try:
            notation.parse_clock(length)
        except notation.NotationError as error:
            ctx.add(doc, line, str(error))
        for model in (part.strip() for part in made_with.split(",")):
            if model != "not recorded" and not _MODEL.match(model):
                ctx.add(doc, line, f"made with {model!r}: use provider/model or 'not recorded'")
    _check_provenance(ctx, doc)


def _check_group(doc: _Doc, ctx: _Context) -> None:
    _check_sections(ctx, doc, "visual-group")
    card = _card_tables(
        ctx,
        doc,
        {"visual_group": ("table", True), "members": ("tables", True), "process": ("table", False)},
    )
    names: list[str] = []
    if card is not None:
        group = _check_fields(
            ctx, doc, card.get("visual_group", {}), "[visual_group]", _GROUP_FIELDS
        )
        names = _check_members(ctx, doc, _dicts(card.get("members")), _GROUP_MEMBER_FIELDS)
        if not 2 <= len(names) <= 3:
            ctx.add(doc, doc.card_line, "a visual group has two or three members (spec §1.2)")
        process = card.get("process")
        if process is not None:
            process = _check_fields(ctx, doc, process, "[process]", _GROUP_PROCESS_FIELDS)
            if "order" in process:
                _check_order(ctx, doc, _strs(process, "order"), names, "[process] `order`")
        if not ctx.template:
            _check_identity(ctx, doc, group, "visual-groups")
            band_id = _str(group, "house_band")
            if band_id and band_id not in ctx.bands:
                ctx.add(doc, doc.card_line, f"house band {band_id} has no doc")
    _check_personas(ctx, doc, names)
    _one_paragraph(ctx, doc, doc.section("Description"), "the description", _DESCRIPTION_WORDS)
    _labeled(ctx, doc, doc.section("Visual language"), ("Motifs", "Palette", "Motion", "Avoid"))
    for line, cells in _discography(ctx, doc, _GROUP_DISCOGRAPHY):
        band_id, album_id, _, year, scenes = cells
        if not (_BAND_ID.match(band_id) and _ALBUM_ID.match(album_id)):
            ctx.add(doc, line, "discography row needs a B-NN band and an A-NN album")
        if not year.isdigit() or not scenes.isdigit():
            ctx.add(doc, line, "discography row needs a year and a scene count")
    _check_provenance(ctx, doc)


def _check_identity(ctx: _Context, doc: _Doc, table: dict[str, Any], folder: str) -> None:
    """Name, slug and file name agree (spec §2, §4)."""
    ident, name, slug = _str(table, "id"), _str(table, "name"), _str(table, "slug")
    if name and slug and slug != slugify(name):
        ctx.add(doc, doc.card_line, f"slug should be {slugify(name)!r} for {name!r}")
    if doc.title and name and doc.title != name:
        ctx.add(doc, 0, f"the '# Title' should be the name, {name!r}")
    path = Path(doc.path)
    if ident and slug and (path.name != f"{ident}-{slug}.md" or path.parent.name != folder):
        ctx.add(doc, 0, f"file should be {folder}/{ident}-{slug}.md")


# ---------------------------------------------------------------------------------------------
# Albums and tracks


@dataclass
class _AlbumScope:
    """What a track needs from its album: the album card plus the band and group cards."""

    album: dict[str, Any]
    band: dict[str, Any]
    band_members: dict[str, list[str]]
    instruments: dict[str, list[str]]
    house_engineer: str
    group_members: list[str]


@dataclass
class _TrackSummary:
    number: int
    title: str
    length: str
    seconds: int | None
    key: str
    meter: str
    tempo: str
    composers: list[str]
    models: set[str]
    scene: str


def _check_album_dir(album_dir: Path, ctx: _Context) -> None:
    album_path = album_dir / "album.md"
    if not album_path.is_file():
        ctx.problems.append(Problem(str(album_dir), 0, "album folder has no album.md"))
        return
    doc = _parse(str(album_path), album_path.read_text(encoding="utf-8"), ctx)
    listed = _check_album(doc, ctx, album_dir)
    for track_path in sorted((album_dir / "tracks").glob("*.md")):
        if track_path.resolve() not in listed:
            ctx.problems.append(
                Problem(str(track_path), 0, "track doc is not listed in its album card's `tracks`")
            )


def _check_album(doc: _Doc, ctx: _Context, album_dir: Path | None) -> set[Path]:
    """Check an album doc and, outside template mode, every track it lists."""
    _check_sections(ctx, doc, "album")
    listed: set[Path] = set()
    card = _card_tables(ctx, doc, {"album": ("table", True), "commission": ("table", True)})
    album: dict[str, Any] = {}
    if card is not None:
        album = _check_fields(ctx, doc, card.get("album", {}), "[album]", _ALBUM_FIELDS)
        commission = _check_fields(
            ctx, doc, card.get("commission", {}), "[commission]", _COMMISSION_FIELDS
        )
        direction = _str(commission, "direction")
        if len(direction) > DIRECTION_LIMIT:
            ctx.add(doc, doc.card_line, f"the direction is {len(direction)} characters; max 220")
        for index, review in enumerate(_dicts(commission.get("reviews")), 1):
            _check_fields(ctx, doc, review, f"[commission] review #{index}", _REVIEW_FIELDS)
            text, reviewed = _str(review, "text"), _str(review, "album")
            if len(text) > DIRECTION_LIMIT:
                ctx.add(doc, doc.card_line, f"review #{index} is {len(text)} characters; max 220")
            if not ctx.template and reviewed >= _str(album, "id"):
                ctx.add(doc, doc.card_line, f"review #{index} must be of a previous album")
        for first, second in (
            ("round1_order", "round2_order"),
            ("visual_round1_order", "visual_round2_order"),
        ):
            if first in album and second in album:
                _check_order(ctx, doc, _strs(album, second), _strs(album, first), second)
    paragraphs = _paragraphs(doc.section("Concept"))
    concept = doc.section("Concept")
    if concept is not None:
        words = sum(_words(text) for _, text in paragraphs)
        if not 1 <= len(paragraphs) <= 3:
            ctx.add(doc, concept.line, "the concept is one to three paragraphs")
        elif not ctx.template and not _CONCEPT_WORDS[0] <= words <= _CONCEPT_WORDS[1]:
            ctx.add(doc, concept.line, f"the concept is {words} words; it needs 80 to 300")
    _check_prose(ctx, doc, doc.section("Mastery"), "'## Mastery'")
    cover = _labeled(ctx, doc, doc.section("Cover"), ("A", "B", "C", "Chosen"))
    chosen = re.match(
        r"^(?P<letter>[ABC])\b\s*[\u2014\u2013-]?\s*(?P<why>.*)$", cover.get("Chosen", "")
    )
    if cover.get("Chosen") and (chosen is None or _words(chosen.group("why")) < 2):
        ctx.add(doc, 0, "'**Chosen:**' needs A, B or C and a reason")
    blurb = _paragraphs(doc.section("Library blurb"))
    blurb_section = doc.section("Library blurb")
    if blurb_section is not None:
        if len(blurb) != 1:
            ctx.add(doc, blurb_section.line, "the library blurb is one line")
        elif len(blurb[0][1]) > BLURB_LIMIT:
            length = len(blurb[0][1])
            ctx.add(doc, blurb[0][0], f"the library blurb is {length} characters; max 160")
    _check_self_review(ctx, doc, _ALBUM_REVIEW_ITEMS)
    _check_provenance(ctx, doc)
    if ctx.template or album_dir is None or not album:
        return listed
    scope = _album_scope(ctx, doc, album)
    summaries: list[_TrackSummary] = []
    for number, relative in enumerate(_strs(album, "tracks"), 1):
        track_path = (album_dir / relative).resolve()
        listed.add(track_path)
        if not track_path.is_file():
            ctx.add(doc, doc.card_line, f"track doc {relative} does not exist")
            continue
        track_doc = _parse(str(album_dir / relative), track_path.read_text(encoding="utf-8"), ctx)
        summary = _check_track(track_doc, ctx, scope, number)
        if summary is not None:
            summaries.append(summary)
    _check_album_against_tracks(ctx, doc, album, album_dir, summaries)
    return listed


def _album_scope(ctx: _Context, doc: _Doc, album: dict[str, Any]) -> _AlbumScope | None:
    band_doc = ctx.bands.get(_str(album, "band"))
    group_doc = ctx.groups.get(_str(album, "visual_group"))
    if band_doc is None or band_doc.card is None:
        ctx.add(doc, doc.card_line, f"band {_str(album, 'band')} has no valid doc")
        return None
    if group_doc is None or group_doc.card is None:
        ctx.add(doc, doc.card_line, f"visual group {_str(album, 'visual_group')} has no valid doc")
        return None
    band = band_doc.card.get("band", {}) if isinstance(band_doc.card.get("band"), dict) else {}
    band_members = {
        _str(member, "name"): _strs(member, "roles")
        for member in _dicts(band_doc.card.get("members"))
    }
    instruments = {
        _str(member, "name"): _strs(member, "instruments")
        for member in _dicts(band_doc.card.get("members"))
    }
    group_members = [_str(member, "name") for member in _dicts(group_doc.card.get("members"))]
    musicians = [name for name, roles in band_members.items() if "musician" in roles]
    for name in _strs(album, "round1_order"):
        if name not in musicians:
            ctx.add(doc, doc.card_line, f"round1_order: {name} is not a musician in the band")
    _check_order(
        ctx, doc, _strs(album, "visual_round1_order"), group_members, "visual_round1_order"
    )
    engineer = _str(band, "house_engineer")
    mastered_by = _str(album, "mastered_by")
    if mastered_by and mastered_by not in band_members and mastered_by != engineer:
        ctx.add(doc, doc.card_line, "mastered_by must be a band member or the house engineer")
    return _AlbumScope(album, band, band_members, instruments, engineer, group_members)


def _check_album_against_tracks(
    ctx: _Context,
    doc: _Doc,
    album: dict[str, Any],
    album_dir: Path,
    summaries: list[_TrackSummary],
) -> None:
    band_doc = ctx.bands.get(_str(album, "band"))
    band = band_doc.card.get("band", {}) if band_doc and band_doc.card else {}
    ident, slug, title = _str(album, "id"), _str(album, "slug"), _str(album, "title")
    if title and slug and slug != slugify(title):
        ctx.add(doc, doc.card_line, f"slug should be {slugify(title)!r} for {title!r}")
    if doc.title and title and doc.title != title:
        ctx.add(doc, 0, f"the '# Title' should be the album title, {title!r}")
    band_folder = f"{_str(album, 'band')}-{_str(band, 'slug') if isinstance(band, dict) else ''}"
    if album_dir.parent.name != band_folder:
        ctx.add(doc, 0, f"album folder should sit in albums/{band_folder}/")
    if album_dir.name != f"{ident}-{slug}":
        ctx.add(doc, 0, f"album folder should be named {ident}-{slug}")
    table = _table(doc.section("Tracklist"))
    tracklist = doc.section("Tracklist")
    if table is None or table[0] != _TRACKLIST_HEADER:
        line = tracklist.line if tracklist else 0
        ctx.add(doc, line, f"'## Tracklist' needs a table: {' | '.join(_TRACKLIST_HEADER)}")
    else:
        rows = table[1]
        if len(rows) != len(summaries):
            line = tracklist.line if tracklist else 0
            ctx.add(doc, line, "the tracklist needs one row per track")
        for (line, cells), track in zip(rows, summaries, strict=False):
            expected = [
                str(track.number),
                track.title,
                track.length,
                track.key,
                track.meter,
                track.tempo,
            ]
            if [_plain(cell) for cell in cells[:6]] != expected or _names(cells[-1]) != set(
                track.composers
            ):
                ctx.add(doc, line, f"tracklist row {track.number} does not match its track card")
    models = set(_strs(album, "made_with"))
    for track in summaries:
        missing = track.models - models
        if missing:
            ctx.add(doc, doc.card_line, f"made_with is missing {', '.join(sorted(missing))}")
    scenes = [track.scene for track in summaries if track.scene]
    for scene in sorted({scene for scene in scenes if scenes.count(scene) > 1}):
        ctx.add(doc, 0, f"scene {scene!r} is used by more than one track")
    if _str(album, "scope") == "album" and all(t.seconds is not None for t in summaries):
        total = sum(t.seconds or 0 for t in summaries)
        if not _ALBUM_SECONDS[0] <= total <= _ALBUM_SECONDS[1]:
            ctx.add(
                doc, 0, f"the album runs {format_clock(total)}; scope album needs 25:00 to 30:00"
            )
    if _str(album, "scope") == "album" and _str(album, "status") == "final" and band_doc:
        rows = _discography(_Context(template=True), band_doc, _BAND_DISCOGRAPHY)
        listed = {cells[0] for _, cells in rows}
        if ident not in listed:
            ctx.add(doc, 0, f"{ident} is final but missing from the band's discography")


def _names(cell: str) -> set[str]:
    return {name.strip() for name in re.split(r",|&|\band\b", _plain(cell)) if name.strip()}


def _check_track(
    doc: _Doc, ctx: _Context, scope: _AlbumScope | None, number: int | None
) -> _TrackSummary | None:
    """Check one track doc; returns what the album's tracklist and totals need."""
    _check_sections(ctx, doc, "track")
    card = _card_tables(ctx, doc, {"track": ("table", True), "credits": ("tables", True)})
    if card is None:
        return None
    track = _check_fields(ctx, doc, card.get("track", {}), "[track]", _TRACK_FIELDS)
    credits = _dicts(card.get("credits"))
    for index, credit in enumerate(credits, 1):
        _check_fields(ctx, doc, credit, f"[[credits]] #{index}", _CREDIT_FIELDS)
    composers = _strs(track, "composers")
    slots: list[tuple[str, str]] = []
    for credit in credits:
        member, part = _str(credit, "member"), _str(credit, "part")
        if part and part not in _RESERVED_PARTS:
            if (member, part) in slots:
                ctx.add(doc, doc.card_line, f"{member} — {part} is credited twice")
            else:
                slots.append((member, part))
    players = list(dict.fromkeys(member for member, _ in slots))
    if len(players) < 2:
        ctx.add(doc, doc.card_line, "a track needs at least two recording members (spec §8)")
    by_part = {
        part: [_str(c, "member") for c in credits if _str(c, "part") == part]
        for part in _RESERVED_PARTS
    }
    if sorted(by_part["composition"]) != sorted(composers):
        ctx.add(doc, doc.card_line, "each composer needs one `composition` credit, and only them")
    if len(by_part["mastering"]) != 1:
        ctx.add(doc, doc.card_line, "a track has exactly one `mastering` credit")
    visual_members = by_part["visuals"]
    if not 2 <= len(set(visual_members)) == len(visual_members) <= 3:
        ctx.add(doc, doc.card_line, "credit each visual group member once with part `visuals`")
    if scope is not None:
        _check_track_against_album(ctx, doc, track, scope, slots, by_part, number)
    tempo = None
    try:
        tempo = notation.parse_tempo(_str(track, "tempo"))
        notation.parse_meter(_str(track, "meter"))
    except notation.NotationError as error:
        ctx.add(doc, doc.card_line, f"card [track]: {error}")
    _check_passes(ctx, doc, composers)
    computed = _check_composition(ctx, doc, tempo)
    seconds = None
    try:
        seconds = notation.parse_clock(_str(track, "length"))
    except notation.NotationError as error:
        if not ctx.template:
            ctx.add(doc, doc.card_line, f"card [track] `length`: {error}")
    if not ctx.template and computed is not None and seconds is not None:
        low, high = computed - _LENGTH_SLACK[0], computed + _LENGTH_SLACK[1]
        if not low <= seconds <= high:
            ctx.add(
                doc,
                doc.card_line,
                f"length {format_clock(seconds)} does not match the form: bars and tempo give "
                f"{format_clock(round(computed))} (allowed {format_clock(max(0, round(low)))} to "
                f"{format_clock(round(high))})",
            )
    orders = scope.album if scope else {}
    recording = doc.section("Recording")
    _check_children(ctx, doc, recording, _RECORDING)
    band_pool = set(scope.band_members) if scope else None
    if recording is not None:
        for title, key in (("Round 1", "round1_order"), ("Round 2", "round2_order")):
            _check_round(
                ctx, doc, recording.child(title), slots, _strs(orders, key), band_pool, "the band"
            )
        _check_decision(ctx, doc, recording.child("Band decision"), slots, with_part=True)
    _check_prose(ctx, doc, doc.section("Mastery"), "'## Mastery'")
    visuals = doc.section("Visuals")
    _check_children(ctx, doc, visuals, _VISUALS)
    group_slots = [(member, "") for member in visual_members]
    group_pool = set(scope.group_members) if scope else None
    scene = ""
    if visuals is not None:
        for title, key in (("Round 1", "visual_round1_order"), ("Round 2", "visual_round2_order")):
            _check_round(
                ctx,
                doc,
                visuals.child(title),
                group_slots,
                _strs(orders, key),
                group_pool,
                "the group",
            )
        _check_decision(ctx, doc, visuals.child("Group decision"), group_slots, with_part=False)
        scene = _check_scene(ctx, doc, visuals.child("Scene"))
    _check_self_review(ctx, doc, _TRACK_REVIEW_ITEMS)
    return _TrackSummary(
        number=track.get("number") if isinstance(track.get("number"), int) else 0,
        title=_str(track, "title"),
        length=_str(track, "length"),
        seconds=seconds,
        key=_str(track, "key"),
        meter=_str(track, "meter"),
        tempo=_str(track, "tempo"),
        composers=composers,
        models={_str(credit, "model") for credit in credits if _str(credit, "model")},
        scene=scene,
    )


def _check_track_against_album(
    ctx: _Context,
    doc: _Doc,
    track: dict[str, Any],
    scope: _AlbumScope,
    slots: list[tuple[str, str]],
    by_part: dict[str, list[str]],
    number: int | None,
) -> None:
    album = scope.album
    for key, value in (("album", _str(album, "id")), ("band", _str(album, "band"))):
        if _str(track, key) != value:
            ctx.add(doc, doc.card_line, f"card [track] `{key}` must be {value}")
    title, slug = _str(track, "title"), _str(track, "slug")
    if title and slug and slug != slugify(title):
        ctx.add(doc, doc.card_line, f"slug should be {slugify(title)!r} for {title!r}")
    if doc.title and title and doc.title != title:
        ctx.add(doc, 0, f"the '# Title' should be the track title, {title!r}")
    if number is not None:
        if track.get("number") != number:
            ctx.add(doc, doc.card_line, f"card [track] `number` must be {number} (album position)")
        if Path(doc.path).name != f"{number:02d}-{slug}.md":
            ctx.add(doc, 0, f"file should be tracks/{number:02d}-{slug}.md")
    for name in _strs(track, "composers"):
        if "composer" not in scope.band_members.get(name, []):
            ctx.add(doc, doc.card_line, f"composer {name} is not a composer in the band")
    for member, part in slots:
        if "musician" not in scope.band_members.get(member, []):
            ctx.add(doc, doc.card_line, f"{member} — {part}: not a musician in the band")
        elif part not in scope.instruments.get(member, []):
            ctx.add(
                doc, doc.card_line, f"{member} — {part}: not one of their band-card instruments"
            )
        elif member not in _strs(album, "round1_order"):
            ctx.add(doc, doc.card_line, f"{member} plays but is missing from the album's orders")
    for member in by_part["mastering"]:
        if member != _str(album, "mastered_by"):
            ctx.add(doc, doc.card_line, f"mastering credit must be {_str(album, 'mastered_by')}")
    if sorted(by_part["visuals"]) != sorted(scope.group_members):
        ctx.add(doc, doc.card_line, "every visual group member needs a `visuals` credit")


def _check_passes(ctx: _Context, doc: _Doc, composers: list[str]) -> None:
    section = doc.section("Composition passes")
    if section is None:
        return
    counts = dict.fromkeys(composers, 0)
    for index, child in enumerate(section.children, 1):
        match = _PASS.match(child.title)
        if match is None or int(match.group("number")) != index:
            ctx.add(doc, child.line, f"expected '### Pass {index} — <composer>'")
            continue
        name = match.group("name").strip()
        if name not in counts:
            ctx.add(doc, child.line, f"{name} is not one of this track's composers")
            continue
        counts[name] += 1
        if not ctx.template and _words(" ".join(t for _, t in _prose(child))) < 8:
            ctx.add(doc, child.line, "a pass says what was written or changed, and why")
    for name, count in counts.items():
        if not 2 <= count <= 3:
            logged = f"{count} pass" if count == 1 else f"{count} passes"
            ctx.add(doc, section.line, f"{name} logged {logged}; composers do two or three")


def _check_composition(ctx: _Context, doc: _Doc, tempo: notation.Tempo | None) -> Fraction | None:
    """Check the five composition parts; returns the form's playing time when it can be read."""
    section = doc.section("Composition")
    if section is None:
        return None
    _check_children(ctx, doc, section, _COMPOSITION)
    form = _check_form(ctx, doc, section.child("Form"))
    harmony = section.child("Harmony")
    charts = [block for block in _blocks(harmony) if block[0] == "chords"]
    if harmony is not None and len(charts) != 1:
        ctx.add(doc, harmony.line, "'### Harmony' needs exactly one ```chords block")
    elif charts and form is not None:
        bars, problems = notation.check_chord_chart(charts[0][1])
        for problem in problems:
            ctx.add(doc, charts[0][2], problem)
        metered = {s.label: s.bars for s in form if s.bars is not None}
        for label, count in metered.items():
            if label not in bars:
                ctx.add(doc, charts[0][2], f"the chord chart has no line for section {label}")
            elif bars[label] != count:
                ctx.add(
                    doc,
                    charts[0][2],
                    f"section {label} has {count} bars in the form but {bars[label]} in the chart",
                )
        free = {s.label for s in form if s.bars is None}
        for label in bars:
            if label not in metered and label not in free:
                ctx.add(doc, charts[0][2], f"chart section {label} is not in the form")
    rhythms = section.child("Core rhythms")
    rhythm_blocks = [b for b in _blocks(rhythms) if b[0] in ("rhythm", "abc")]
    if rhythms is not None and not rhythm_blocks:
        ctx.add(doc, rhythms.line, "'### Core rhythms' needs a ```rhythm or ```abc block")
    heads = section.child("Heads")
    head_blocks = [b for b in _blocks(heads) if b[0] == "abc"]
    if heads is not None and not head_blocks:
        ctx.add(doc, heads.line, "'### Heads' needs at least one ```abc block")
    for tag, text, line in [*rhythm_blocks, *head_blocks]:
        problems = (
            notation.check_rhythm(text)
            if tag == "rhythm"
            else notation.check_abc(text, f"abc block at line {line}")
        )
        for problem in problems:
            ctx.add(doc, line, problem)
    lyrics = section.child("Lyrics")
    if lyrics is not None and not " ".join(t for _, t in _paragraphs(lyrics)).lower().startswith(
        "none"
    ):
        ctx.add(doc, lyrics.line, "albums are instrumental: '### Lyrics' is 'None — instrumental.'")
    if form is None or tempo is None:
        return None
    return notation.form_seconds(form, tempo)


def _check_form(
    ctx: _Context, doc: _Doc, section: _Section | None
) -> list[notation.FormSection] | None:
    if section is None:
        return None
    table = _table(section)
    if table is None or table[0] != _FORM_HEADER:
        ctx.add(doc, section.line, f"'### Form' needs a table: {' | '.join(_FORM_HEADER)}")
        return None
    form: list[notation.FormSection] = []
    for line, cells in table[1]:
        if len(cells) != len(_FORM_HEADER):
            ctx.add(doc, line, f"form rows need {len(_FORM_HEADER)} cells")
            continue
        label, bars, meter, _, open_space = (_plain(cell) for cell in cells)
        if any(existing.label == label for existing in form):
            ctx.add(doc, line, f"form section {label} appears twice; number repeats (A1, A2)")
            continue
        try:
            form.append(notation.parse_form_section(label, bars, meter, open_space))
        except notation.NotationError as error:
            ctx.add(doc, line, str(error))
    if not form:
        ctx.add(doc, section.line, "the form has no sections")
        return None
    if all(s.open_space.strip().lower() in _NO_OPEN_SPACE for s in form):
        ctx.add(doc, section.line, "at least one section names its open space (spec §9.1)")
    return form


def _check_round(
    ctx: _Context,
    doc: _Doc,
    section: _Section | None,
    slots: list[tuple[str, str]],
    order: list[str],
    pool: set[str] | None,
    collective: str,
) -> None:
    """One take round: a subsection per slot, in order, each with three takes and a pick."""
    if section is None:
        return
    seen: list[tuple[str, str]] = []
    with_part = any(part for _, part in slots)
    for child in section.children:
        if with_part:
            match = _SLOT.match(child.title)
            if match is None:
                ctx.add(doc, child.line, "expected '#### <member> — <part>'")
                continue
            slot = (match.group("member").strip(), match.group("part").strip())
        else:
            slot = (child.title.strip(), "")
        if slot not in slots:
            ctx.add(doc, child.line, f"{child.title!r} is not credited on this track")
        elif slot in seen:
            ctx.add(doc, child.line, f"{child.title!r} appears twice in {section.title}")
        else:
            seen.append(slot)
        _check_takes(ctx, doc, child, slot[0], pool, collective)
    missing = [slot for slot in slots if slot not in seen]
    if missing:
        names = ", ".join(f"{m} — {p}" if p else m for m, p in missing)
        ctx.add(doc, section.line, f"{section.title} is missing takes for {names}")
    members = list(dict.fromkeys(member for member, _ in seen))
    expected = [name for name in order if name in members]
    if order and members != expected:
        wanted = ", ".join(expected)
        ctx.add(doc, section.line, f"{section.title} must follow the album order: {wanted}")


def _check_takes(
    ctx: _Context, doc: _Doc, section: _Section, member: str, pool: set[str] | None, collective: str
) -> None:
    bullets = _bullets(section)
    if len(bullets) != 4:
        ctx.add(doc, section.line, "a take block is three '- Take N:' bullets and a '- Picked by'")
        return
    texts = []
    for number, (line, text) in enumerate(bullets[:3], 1):
        take = _TAKE.match(text)
        if take is None or int(take.group("number")) != number:
            ctx.add(doc, line, f"expected '- Take {number}: …'")
            continue
        texts.append(take.group("text").strip().lower())
        if not ctx.template and _words(take.group("text")) < 4:
            ctx.add(doc, line, "describe the take: what a listener would hear")
    if len(set(texts)) != len(texts):
        ctx.add(doc, section.line, "the three takes must differ")
    line, text = bullets[3]
    pick = _PICK.match(text)
    if pick is None or not 1 <= int(pick.group("take")) <= 3:
        ctx.add(doc, line, "expected '- Picked by <member>: Take N — <reason>'")
        return
    who = pick.group("who").strip()
    if who == member:
        ctx.add(doc, line, f"{member} cannot pick their own take; the next member does")
    elif who.lower() != collective and pool is not None and who not in pool:
        ctx.add(doc, line, f"{who} is not a member who can pick ({collective} or a member)")
    if _words(pick.group("why")) < 2:
        ctx.add(doc, line, "give the reason for the pick")


def _check_decision(
    ctx: _Context,
    doc: _Doc,
    section: _Section | None,
    slots: list[tuple[str, str]],
    with_part: bool,
) -> None:
    if section is None:
        return
    chosen: set[tuple[str, str]] = set()
    pattern = _BAND_CHOICE if with_part else _GROUP_CHOICE
    for line, text in _bullets(section):
        match = pattern.match(text)
        if match is None:
            example = "<member> — <part>: " if with_part else "<member>: "
            ctx.add(doc, line, f"expected '- {example}Round N, Take N'")
            continue
        slot = (match.group("member").strip(), match.group("part").strip() if with_part else "")
        if slot not in slots:
            ctx.add(doc, line, f"{text.split(':')[0]!r} is not credited on this track")
        elif slot in chosen:
            ctx.add(doc, line, f"{text.split(':')[0]!r} is decided twice")
        chosen.add(slot)
        if not 1 <= int(match.group("round")) <= 2 or not 1 <= int(match.group("take")) <= 3:
            ctx.add(doc, line, "rounds are 1 or 2 and takes 1 to 3")
    missing = [slot for slot in slots if slot not in chosen]
    if missing:
        names = ", ".join(f"{m} — {p}" if p else m for m, p in missing)
        ctx.add(doc, section.line, f"{section.title} has no choice for {names}")
    reasons = " ".join(text for _, text in _paragraphs(section))
    if not reasons.strip() or (not ctx.template and _words(reasons) < 10):
        ctx.add(doc, section.line, f"{section.title} needs the reasons for the combination")


def _check_scene(ctx: _Context, doc: _Doc, section: _Section | None) -> str:
    if section is None:
        return ""
    found = _labeled(ctx, doc, section, ("Scene", "Label", "Palette", "Picture", "Motion"))
    scene, label = found.get("Scene", "").strip("`"), found.get("Label", "")
    if scene and not _SLUG.match(scene):
        ctx.add(doc, section.line, f"scene {scene!r} must be a slug like perihelion-rings")
    if label and (label != label.upper() or not re.search(r"[A-Z]", label)):
        ctx.add(doc, section.line, "the scene label is upper case, like ARRIVAL / RINGS OPEN")
    palette = [color.strip().strip("`") for color in found.get("Palette", "").split(",")]
    if found.get("Palette") and (len(palette) != 3 or not all(_HEX.match(c) for c in palette)):
        ctx.add(doc, section.line, "the palette is three #rrggbb colors")
    motion = found.get("Motion", "").lower()
    if motion and not ("reduced" in motion and "still" in motion):
        ctx.add(doc, section.line, "'**Motion:**' covers full, reduced and still motion")
    table = _table(section)
    if table is None or table[0] != _SCENE_TABLE or len(table[1]) < 2:
        ctx.add(doc, section.line, "the scene needs a 'Source | Visual behavior' table, 2+ rows")
    return scene


# ---------------------------------------------------------------------------------------------
# Entry points


def _discover(root: Path) -> Iterator[tuple[str, Path]]:
    for kind, folder in (("band", "bands"), ("visual-group", "visual-groups")):
        for path in sorted((root / folder).glob("*.md")):
            if path.name != "README.md":
                yield kind, path
    for album_dir in sorted((root / "albums").glob("*/*")):
        if album_dir.is_dir():
            yield "album", album_dir


def _validate(roots: Sequence[Path]) -> tuple[list[Problem], int]:
    ctx = _Context(template=False)
    found = [item for root in roots for item in _discover(root)]
    people: list[tuple[str, _Doc]] = []
    for kind, path in found:
        if kind == "album":
            continue
        doc = _parse(str(path), path.read_text(encoding="utf-8"), ctx)
        people.append((kind, doc))
        table_name = "band" if kind == "band" else "visual_group"
        table = doc.card.get(table_name) if doc.card else None
        ident = _str(table, "id") if isinstance(table, dict) else ""
        index = ctx.bands if kind == "band" else ctx.groups
        if ident in index:
            ctx.add(doc, 0, f"{ident} is also defined in {index[ident].path}")
        elif ident:
            index[ident] = doc
    for kind, doc in people:
        (_check_band if kind == "band" else _check_group)(doc, ctx)
    for kind, path in found:
        if kind == "album":
            _check_album_dir(path, ctx)
    return sorted(ctx.problems), len(found)


def validate_roots(roots: Sequence[Path]) -> list[Problem]:
    """Validate every band, visual group and album doc under the given roots.

    Args:
        roots: Directories that may contain ``bands/``, ``visual-groups/`` and ``albums/``.
            References (an album's band, a band's house group) resolve across all roots, so a
            generated album can be checked in its own folder against the repository's bands.

    Returns:
        Every problem found, sorted by path and line; empty when all docs meet the spec.
    """
    return _validate(roots)[0]


def validate_template(kind: str, text: str) -> list[Problem]:
    """Check that a template (or a template embedded in a prompt) has its kind's structure.

    Placeholder values are allowed: word counts, ID formats, file names, cross-doc references,
    the stated track length and unchecked self-review boxes are not checked. Structure, card keys
    and types, take and decision formats and every notation example still are, so a template
    always shows a doc shape the validator accepts.

    Args:
        kind: One of ``KINDS``.
        text: The template's Markdown.

    Returns:
        The problems found, with path ``<kind template>``.

    Raises:
        ValueError: If ``kind`` is not one of ``KINDS``.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown doc kind {kind!r}; expected one of {', '.join(KINDS)}")
    ctx = _Context(template=True)
    doc = _parse(f"<{kind} template>", text, ctx)
    if kind == "band":
        _check_band(doc, ctx)
    elif kind == "visual-group":
        _check_group(doc, ctx)
    elif kind == "album":
        _check_album(doc, ctx, None)
    else:
        _check_track(doc, ctx, None, None)
    return sorted(ctx.problems)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the validator from the command line.

    Args:
        argv: Arguments after the program name; defaults to ``sys.argv[1:]``.

    Returns:
        0 when every doc meets the spec, 1 when any problem was printed.
    """
    parser = argparse.ArgumentParser(
        prog="python -m agentic_av.registry",
        description="Check band, visual group and album docs against docs/spec/band-album-spec.md.",
    )
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        default=[Path(".")],
        help="folders holding bands/, visual-groups/ and albums/ (default: current folder)",
    )
    args = parser.parse_args(argv)
    problems, checked = _validate(args.roots)
    for problem in problems:
        print(problem)
    noun = "problem" if len(problems) == 1 else "problems"
    print(f"{checked} docs and album folders checked, {len(problems)} {noun}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

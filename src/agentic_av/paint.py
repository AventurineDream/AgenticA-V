"""Compose the player, stage, meter, gallery, and help into terminal cells.

Both `preview` and the interactive TTY runner call `compose`, keeping their
layout identical. Frames are fixed-size, single-column character grids.
Color stages paint two field samples per cell; no-color stages use density
glyphs only. The key legend is reserved in the row budget so it is not
clipped off a full frame. Show text is normalized before cells are built:
controls become spaces, combining marks and zero-width Hangul jamo are
removed, and wide, fullwidth, and regional-indicator characters become one
cell, so a title cannot steer the cursor, stall a row, or wrap it.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from agentic_av.colorutil import mix, parse_hex, to_xterm256
from agentic_av.field import PROGRAM_LABELS, sample
from agentic_av.palette import Palette
from agentic_av.show import Show

DENSITY = " ░▒▓█"
# 4x4 Bayer matrix. Flat NO_COLOR fields otherwise collapse into solid bands.
_BAYER = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


@dataclass(frozen=True, slots=True)
class Cell:
    """One terminal column and its optional foreground/background colors.

    ``char`` is one column. Wide characters, regional indicators, and
    combining marks are normalized before a cell is built. Zero-width Hangul
    jamo are removed rather than stored.
    """

    char: str = " "
    fg: str = ""
    bg: str = ""


@dataclass(frozen=True, slots=True)
class FrameRequest:
    """Complete immutable input to the fixed-grid player renderer.

    Times and duration are seconds; dimensions are terminal character cells.
    """

    show: Show
    palette: Palette
    themes: tuple[Palette, ...]
    width: int
    height: int
    position_s: float = 0.0
    playing: bool = True
    rate: float = 1.0
    program: str = "garden"
    program_index: int = 0
    theme_index: int = 0
    mode: str = "play"
    motion: str = "full"
    field_time_s: float = 0.0
    color_mode: str = "truecolor"
    sync_note: str = ""


# ASCII, not an ambiguous glyph. □ and U+FFFD are East Asian Width A, so
# using either as the stand-in would shift the same fixed row this protects.
_WIDE_PLACEHOLDER = "?"
# Variation selectors are Mn with combining class 0, so combining() alone
# would leave a zero-column mark in a cell. Mc is a combining mark too.
_COMBINING_CATEGORIES = frozenset({"Mn", "Me", "Mc"})


def _printable(text: str) -> str:
    """Replace controls so show text cannot move the cursor or inject escapes.

    ESC, CR, TAB, and other non-printable characters become spaces. Raw mode
    does not translate them, and preview must not emit them either.
    """
    return "".join(char if char.isprintable() else " " for char in text)


def _single_column(text: str) -> str:
    """Map text onto one column per cell before either text path builds cells.

    Both ``_text_row`` and ``_put`` call this, so a positioned title cannot
    bypass it. Combining marks and class-0 variation selectors are dropped.
    Zero-width Hangul jamo are dropped too: U+1160-U+11FF, U+D7B0-U+D7C6,
    U+D7CB-U+D7FB, and the halfwidth filler U+FFA0. They are printable and
    not combining, but a terminal gives them no column and stops the rest
    of the text run. East Asian wide and fullwidth characters become one
    placeholder. Regional indicators U+1F1E6-U+1F1FF are East Asian Width
    Neutral, but each is two columns (a pair is a flag), so they use the
    same placeholder. Ambiguous UI glyphs (box drawing, density, arrows,
    middle dot) stay themselves. Controls are already spaces.
    """
    normalized: list[str] = []
    for char in _printable(text):
        category = unicodedata.category(char)
        if unicodedata.combining(char) or category in _COMBINING_CATEGORIES:
            continue
        # EAW misses regional indicators (Neutral, wcwidth 2). A pair is a flag.
        if unicodedata.east_asian_width(char) in {"W", "F"} or "\U0001f1e6" <= char <= "\U0001f1ff":
            normalized.append(_WIDE_PLACEHOLDER)
            continue
        # wcwidth 0 and combining class 0, so the mark check misses them.
        # pyte stops draw() on that combination and truncates the row.
        if (
            "\u1160" <= char <= "\u11ff"
            or "\ud7b0" <= char <= "\ud7c6"
            or "\ud7cb" <= char <= "\ud7fb"
            or char == "\uffa0"
        ):
            continue
        normalized.append(char)
    return "".join(normalized)


def _text_row(text: str, width: int, fg: str, bg: str) -> list[Cell]:
    """Fit one-column text into a row, padding with background.

    The single-column normalizer runs first, so a clipped title cannot
    wrap the row, stall the cursor, or inject escapes.
    """
    clipped = _single_column(text)[: max(width, 0)]
    return [Cell(char, fg, bg) for char in clipped] + [Cell(" ", fg, bg)] * max(
        0, width - len(clipped)
    )


def _put(row: list[Cell], start: int, text: str, fg: str, bg: str) -> None:
    """Write clipped one-column text at a zero-based column in an existing row.

    Uses the same normalizer as ``_text_row``. Positioned titles must not
    bypass it.
    """
    for offset, char in enumerate(_single_column(text)):
        index = start + offset
        if 0 <= index < len(row):
            row[index] = Cell(char, fg, bg)


def _status(request: FrameRequest) -> str:
    """Build the compact state cluster for the top rail."""
    state = "playing" if request.playing else "paused"
    bits = [state]
    if request.rate != 1:
        bits.append(f"{request.rate:g}x")
    if request.motion != "full":
        bits.append(request.motion)
    if request.sync_note:
        bits.insert(0, "sync" if request.sync_note == "ok" else "sync?")
    return " · ".join(bits)


def _header(request: FrameRequest) -> list[Cell]:
    """Paint the wordmark, theme name, and transport state without overlap."""
    p = request.palette
    width = request.width
    row = _text_row("", width, p.foreground, p.background)
    if width < 8:
        _put(row, 0, "AAV"[:width], p.accent, p.background)
        return row
    _put(row, 0, "AAV", p.accent, p.background)
    status = _status(request)
    state_color = p.success if request.playing else p.warning
    theme = request.palette.name.split(" · ", 1)[0].upper()
    status_at = max(4, width - len(status))
    _put(row, status_at, status[: width - status_at], state_color, p.background)
    room = status_at - 4
    if room >= len(theme) + 3:
        theme_at = status_at - len(theme) - 3
        _put(row, theme_at, theme, p.foreground, p.background)
        _put(row, status_at - 2, "·", p.border, p.background)
    elif room >= 3:
        _put(row, 4, theme[: room - 1], p.foreground, p.background)
    return row


def _plate(request: FrameRequest, rows: int) -> list[list[Cell]]:
    """Paint the show title and current scene as a quiet two-column plate."""
    p = request.palette
    width = request.width
    label = PROGRAM_LABELS.get(request.program, request.program.title())
    kicker = f"{request.program_index + 1:02d}  {label}"
    title_row = _text_row("", width, p.foreground, p.background)
    title = request.show.title
    if len(title) + len(kicker) + 2 <= width:
        _put(title_row, 0, title, p.foreground, p.background)
        _put(title_row, width - len(kicker), kicker, p.accent, p.background)
    else:
        _put(title_row, 0, (title or label)[:width], p.foreground, p.background)
    if rows < 2:
        return [title_row]
    tempo = f"{request.show.tempo} BPM" if request.show.tempo else ""
    bits = [bit for bit in (request.show.detail, tempo, p.mood) if bit]
    detail = "  ·  ".join(bits)
    return [title_row, _text_row(detail, width, p.muted, p.background)]


def _shade(palette: Palette, luminance: float, hue: float, gain: float = 1.0) -> str:
    """Map luminance from shadow to highlight without bleaching the rails.

    Midtones carry the scene color. The endpoints stay on the ink/paper
    roles so a light theme cannot invert into a gray haze.
    """
    lum = max(0.0, min(1.0, luminance * gain))
    grade = lum * lum * (3 - 2 * lum)
    hue_color = mix(palette.accent, palette.accent2, hue)
    if palette.dark:
        shadow, highlight = palette.stage, palette.foreground
    else:
        shadow, highlight = palette.foreground, palette.background
    mid = mix(mix(shadow, highlight, 0.45), hue_color, 0.8)
    if grade < 0.5:
        return mix(shadow, mid, grade * 2)
    return mix(mid, highlight, (grade - 0.5) * 2)


def _vignette(nx: float, ny: float) -> float:
    """Darken the field edge so the picture sits inside the frame."""
    distance = ((nx - 0.5) ** 2 + ((ny - 0.5) * 1.28) ** 2) ** 0.5
    return max(0.5, 1.0 - max(0.0, distance - 0.2) * 0.95)


def _density_glyph(luminance: float, x: int, y: int) -> str:
    """Map luminance to a dithered density glyph for no-color frames."""
    jitter = (_BAYER[y & 3][x & 3] / 16 - 0.5) * 0.16
    graded = max(0.0, min(0.999, luminance + jitter))
    return DENSITY[int(graded * len(DENSITY))]


def _field_row(
    width: int,
    y: int,
    rows: int,
    request: FrameRequest,
    palette: Palette,
    gain: float,
) -> list[Cell]:
    """Paint one terminal row as two field samples.

    A single sample on a flat stage background reads as horizontal stripes.
    The upper sample is the foreground of ``▀``; the lower sample is the
    background. No-color mode dither-maps the average into density glyphs.
    """
    if width <= 0:
        return []
    rows = max(rows, 1)
    shimmer = request.motion == "full"
    cells: list[Cell] = []
    for x in range(width):
        nx = (x + 0.5) / width
        ny0 = (y + 0.25) / rows
        ny1 = (y + 0.75) / rows
        lum0, hue0 = sample(request.program, nx, ny0, request.field_time_s, shimmer=shimmer)
        lum1, hue1 = sample(request.program, nx, ny1, request.field_time_s, shimmer=shimmer)
        if request.color_mode == "none":
            lum = (lum0 * _vignette(nx, ny0) + lum1 * _vignette(nx, ny1)) * 0.5
            cells.append(Cell(_density_glyph(lum * gain, x, y), "", ""))
            continue
        top = _shade(palette, lum0 * _vignette(nx, ny0), hue0, gain)
        bottom = _shade(palette, lum1 * _vignette(nx, ny1), hue1, gain)
        cells.append(Cell("▀", top, bottom))
    return cells


def _stage(width: int, height: int, request: FrameRequest, gain: float) -> list[list[Cell]]:
    """Render a framed half-block stage or a dithered monochrome stage.

    Field time is read from the request so gallery cards and the stage share
    one clock.
    """
    p = request.palette
    if height <= 0:
        return []
    if width < 12 or height < 4:
        return [
            _text_row("stage needs more space", width, p.muted, p.background) for _ in range(height)
        ]
    label = f" {PROGRAM_LABELS.get(request.program, request.program.title())} "
    top = [Cell(char, p.border, p.background) for char in "╭" + "─" * (width - 2) + "╮"]
    for index, char in enumerate(label[: max(0, width - 4)]):
        if index + 2 < width - 1:
            top[index + 2] = Cell(char, p.accent, p.background)
    rows = [top]
    picture_h = height - 2
    picture_w = width - 2
    for y in range(picture_h):
        picture = _field_row(picture_w, y, picture_h, request, p, gain)
        rows.append(
            [Cell("│", p.border, p.background), *picture, Cell("│", p.border, p.background)]
        )
    bottom = [Cell(char, p.border, p.background) for char in "╰" + "─" * (width - 2) + "╯"]
    if request.motion != "full" and width > len(request.motion) + 6:
        note = f" {request.motion} "
        start = width - len(note) - 2
        for offset, char in enumerate(note):
            bottom[start + offset] = Cell(char, p.muted, p.background)
    rows.append(bottom)
    return rows


def _meter_ink(palette: Palette, level: int) -> str:
    """Color a meter step so peaks use the theme's warning and error roles."""
    if level >= 7:
        return palette.error
    if level >= 5:
        return palette.warning
    return palette.meter


def _meter_row(request: FrameRequest) -> list[Cell]:
    """Paint a stereo field-energy meter derived from the current scene."""
    p = request.palette
    width = request.width
    row = _text_row("", width, p.muted, p.background)
    if width < 28:
        return row
    bars = max(4, min(16, (width - 16) // 2))
    levels: list[int] = []
    shimmer = request.motion == "full"
    for side in (0, 1):
        for index in range(bars):
            x = (side * 0.5) + (index + 0.5) / bars * 0.5
            samples = [
                sample(request.program, x, y, request.field_time_s, shimmer=shimmer)[0]
                for y in (0.22, 0.5, 0.78)
            ]
            energy = sum(samples) / len(samples)
            levels.append(max(1, min(8, int(energy * 9))))
    glyphs = "▁▂▃▄▅▆▇█" if request.color_mode != "none" else "._-:=+*#"
    cursor = 0

    def paint(text: str, color: str) -> None:
        nonlocal cursor
        _put(row, cursor, text, color, p.background)
        cursor += len(text)

    paint("L ", p.muted)
    for level in levels[:bars]:
        ink = "" if request.color_mode == "none" else _meter_ink(p, level)
        paint(glyphs[level - 1], ink or p.meter)
    paint("  ", p.muted)
    for level in levels[bars:]:
        ink = "" if request.color_mode == "none" else _meter_ink(p, level)
        paint(glyphs[level - 1], ink or p.meter)
    paint(" R", p.muted)
    return row


def _clock(seconds: float) -> str:
    """Format a non-negative show position as M:SS or H:MM:SS."""
    whole = max(0, int(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _transport(request: FrameRequest) -> list[Cell]:
    """Paint a seek rule with chapter ticks and fixed-width time labels."""
    p, width = request.palette, request.width
    row = _text_row("", width, p.foreground, p.background)
    if width < 15:
        return row
    duration = request.show.duration
    position = max(0.0, min(duration, request.position_s))
    mono = request.color_mode == "none"
    mark = (">" if request.playing else ":") if mono else ("▶" if request.playing else "Ⅱ")
    left = f"{mark} "
    right = f"{_clock(position)}  -{_clock(duration - position)}"
    right_width = min(len(right), max(5, width // 3))
    right = right[-right_width:]
    bar_start = len(left)
    bar_width = max(1, width - len(left) - len(right) - 1)
    _put(row, 0, left, p.accent, p.background)
    _put(row, width - len(right), right, p.muted, p.background)
    played = min(bar_width - 1, int(position / duration * bar_width)) if duration else 0
    chapters = max(1, len(request.show.programs))
    for index in range(bar_width):
        boundary = index > 0 and int(index * chapters / bar_width) != int(
            (index - 1) * chapters / bar_width
        )
        if index == played:
            char, color = (">" if mono else "●", p.accent)
        elif boundary:
            char, color = ("|", p.muted)
        elif index < played:
            char, color = ("=" if mono else "━", p.progress)
        else:
            char, color = ("-" if mono else "─", p.border)
        _put(row, bar_start + index, char, color, p.background)
    return row


def _hint(request: FrameRequest) -> list[Cell]:
    """Paint the short keyboard legend, adapting to narrow terminals."""
    p = request.palette
    if request.width < 42:
        text = "space play/pause   arrows seek   t theme   q quit"
    else:
        text = "space  play/pause    ←→  seek    t  theme    m  motion    ?  guide    q  quit"
    return _text_row(text, request.width, p.muted, p.background)


def _help(request: FrameRequest, height: int) -> list[list[Cell]]:
    """Render a help plate whose key column stays aligned.

    Centering each line on its own ragged the columns. The block is padded
    to one width, then centered as a whole.
    """
    p, width = request.palette, request.width
    if height <= 0:
        return []
    entries = (
        ("KEYBOARD", ""),
        ("", ""),
        ("space", "play or pause"),
        ("left / right", "seek five seconds"),
        ("j / k", "previous or next scene"),
        ("t", "cycle themes"),
        ("shift-t", "theme gallery"),
        ("1-9", "choose a built-in theme"),
        ("o", "sync omarchy now"),
        ("m", "full, reduced, or still"),
        ("[ / ]", "playback rate"),
        ("esc", "return to the stage"),
        ("q", "leave the player"),
    )
    lines = [key if not action else f"{key:<14}{action}" for key, action in entries]
    plate = min(width, max(len(line) for line in lines))
    pad = max(0, (width - plate) // 2)
    offset = max(0, (height - len(lines)) // 2)
    result = []
    for index in range(height):
        src = index - offset
        if not 0 <= src < len(lines):
            result.append(_text_row("", width, p.foreground, p.background))
            continue
        color = p.accent if lines[src] == "KEYBOARD" else p.foreground
        if not lines[src].strip():
            color = p.background
        text = f"{' ' * pad}{lines[src][:plate].ljust(plate)}"
        result.append(_text_row(text, width, color, p.background))
    return result


def _role_chips(theme: Palette, color_mode: str, bg: str) -> list[Cell]:
    """Paint accent, second accent, meter, and success as solid chips."""
    chips: list[Cell] = []
    for color in (theme.accent, theme.accent2, theme.meter, theme.success):
        if chips:
            chips.append(Cell(" ", theme.muted, bg))
        if color_mode == "none":
            chips.append(Cell("▀", "", ""))
        else:
            chips.append(Cell("▀", color, color))
    return chips


def _theme_card(request: FrameRequest, theme: Palette, selected: bool) -> list[list[Cell]]:
    """Paint one gallery card: name, role chips, and a miniature field."""
    width = request.width
    bg = theme.background
    name_fg = theme.accent if selected else theme.foreground
    name = f"{'▌' if selected else ' '} {theme.name.upper()}"
    row = _text_row("", width, theme.foreground, bg)
    _put(row, 0, name[:width], name_fg, bg)
    chips = _role_chips(theme, request.color_mode, bg)
    chip_at = width - len(chips)
    if chip_at >= min(len(name), width) + 1:
        for offset, cell in enumerate(chips):
            row[chip_at + offset] = cell
        mood = theme.mood
        mood_at = chip_at - len(mood) - 1
        if mood_at >= min(len(name), width) + 1:
            _put(row, mood_at, mood, theme.muted, bg)
    inset = 2 if width >= 20 else 0
    art_w = max(0, width - inset * 2)
    art_rows: list[list[Cell]] = []
    pad = Cell(" ", theme.foreground, bg)
    for y in range(2):
        art = _field_row(art_w, y, 2, request, theme, 1.0)
        line = [pad] * inset + art + [pad] * max(0, width - inset - len(art))
        line = (line + [pad] * width)[:width]
        if selected and line:
            line[0] = Cell("▌", theme.accent, bg)
        art_rows.append(line)
    return [row, *art_rows]


def _gallery(request: FrameRequest, height: int) -> list[list[Cell]]:
    """Render theme cards with real miniature art, scrolling to the selection."""
    p, width = request.palette, request.width
    if height <= 0:
        return []
    blank = _text_row("", width, p.foreground, p.background)
    if not request.themes:
        return [blank for _ in range(height)]
    # Negative means no built-in is selected. Modulo would highlight the last card.
    count = len(request.themes)
    selected = request.theme_index if 0 <= request.theme_index < count else -1
    lines = [
        _text_row(
            "THEME ATLAS    j/k select    enter apply    esc back",
            width,
            p.muted,
            p.background,
        )
    ]
    card_h = 3
    capacity = max(0, (height - len(lines)) // card_h)
    if capacity == 0:
        start = 0 if selected < 0 else max(0, min(count - 1, selected))
        visible = request.themes[start : start + max(0, height - 1)]
        for offset, theme in enumerate(visible):
            mark = "▌" if selected >= 0 and start + offset == selected else " "
            label = f"{mark} {theme.name.upper()}"
            lines.append(_text_row(label, width, theme.accent, p.background))
        return (lines + [blank] * height)[:height]
    start = 0 if selected < 0 else max(0, min(count - capacity, selected - capacity // 2))
    for index in range(start, min(count, start + capacity)):
        lines.extend(_theme_card(request, request.themes[index], index == selected))
    return (lines + [blank] * height)[:height]


def _chrome_budget(height: int) -> tuple[int, int, int, int]:
    """Reserve plate, meter, transport, and hint rows that will actually fit.

    The hint used to be appended after the frame was already full, then
    sliced away. Reserving it here is what keeps the legend on screen.

    Returns:
        Plate rows, meter rows, transport rows, and hint rows.
    """
    plate = 2 if height >= 8 else (1 if height >= 4 else 0)
    spare = height - 1 - plate
    transport = 1 if spare >= 6 else 0
    spare -= transport
    meter = 1 if spare >= 8 else 0
    spare -= meter
    hint = 1 if spare >= 7 else 0
    return plate, meter, transport, hint


def compose(request: FrameRequest) -> list[list[Cell]]:
    """Return an exact `height` by `width` player frame.

    Very small terminals receive a reduced but still valid frame; every row
    remains exactly `width` single-column cells for safe cursor painting.
    """
    width, height = max(1, request.width), max(1, request.height)
    p = request.palette
    plate, meter, transport, hint = _chrome_budget(height)
    rows = [_header(request)]
    if plate:
        rows.extend(_plate(request, plate)[:plate])
    stage_h = max(0, height - len(rows) - meter - transport - hint)
    gain = 1.0 if request.playing else 0.58
    if request.mode == "help":
        body = _help(request, stage_h)
    elif request.mode == "gallery":
        body = _gallery(request, stage_h)
    else:
        body = _stage(width, stage_h, request, gain)
    rows.extend(body[:stage_h])
    pad = _text_row("", width, p.foreground, p.background)
    rows.extend([pad] * max(0, height - meter - transport - hint - len(rows)))
    if meter:
        rows.append(_meter_row(request))
    if transport:
        rows.append(_transport(request))
    if hint:
        rows.append(_hint(request))
    rows = rows[:height]
    rows.extend([pad] * (height - len(rows)))
    return [
        row[:width] + [Cell(" ", p.foreground, p.background)] * max(0, width - len(row))
        for row in rows
    ]


def render_plain(rows: list[list[Cell]]) -> str:
    """Convert a composed frame to plain text, stripping all color metadata."""
    return "\n".join("".join(cell.char for cell in row) for row in rows)


def _ansi_color(value: str, mode: str, *, foreground: bool) -> str:
    """Build one foreground/background ANSI color setting."""
    if mode == "truecolor":
        rgb = parse_hex(value)
        if rgb is None:
            return ""
        channel = 38 if foreground else 48
        return f"\x1b[{channel};2;{rgb[0]};{rgb[1]};{rgb[2]}m"
    if mode == "256":
        channel = 38 if foreground else 48
        return f"\x1b[{channel};5;{to_xterm256(value)}m"
    return ""


def render_ansi(rows: list[list[Cell]], mode: str = "truecolor") -> str:
    """Serialize cells to ANSI truecolor, 256-color, or no-color text."""
    output: list[str] = []
    for row in rows:
        parts: list[str] = []
        last_fg = last_bg = None
        for cell in row:
            if mode == "none":
                parts.append(cell.char)
                continue
            if cell.fg != last_fg:
                parts.append(_ansi_color(cell.fg, mode, foreground=True))
                last_fg = cell.fg
            if cell.bg != last_bg:
                parts.append(_ansi_color(cell.bg, mode, foreground=False))
                last_bg = cell.bg
            parts.append(cell.char)
        if mode != "none":
            parts.append("\x1b[0m")
        output.append("".join(parts))
    return "\n".join(output)

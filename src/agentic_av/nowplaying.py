"""Compose the native player's now-playing presentation around the album stage.

`native.py` owns playback, clocks, input, and the single synchronized write per
frame. This module returns the bytes for everything around the scene: the cover
panel and its caption, the loading splash, the movement title card, and the two
transport rows. Every function is pure. Each one takes sizes, colors, and state,
and returns cursor-addressed bytes without touching the terminal. All text passes
through paint's one-column normalizer, so a title can never wrap a row or inject
escapes.

Color roles: the UI theme (`Palette`) owns text and chrome backgrounds. One album
accent, taken from the cover or the movement palette, colors the progress rail, the
state label, the caption title, and the title card kicker. The accent is lifted until it reaches
`_MIN_ACCENT_CONTRAST` against the theme background. No-color mode emits no SGR.

Sizes are character cells. Rows are one-based terminal rows and columns are
zero-based offsets, matching `Stage` and `render_cover`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from agentic_av.colorutil import contrast_ratio, mix, normalize_hex, to_hex
from agentic_av.paint import Cell, _ansi_color, _single_column, _text_row, render_ansi
from agentic_av.palette import Palette
from agentic_av.tty import _terminal_frame
from agentic_av.viz.cover import render_cover
from agentic_av.viz.glyphs import Cells

# Cover panel: two margin columns before it and two gap columns after it, at most
# 40% of the width. It shrinks to fit that share and the caption, but is omitted
# rather than drawn shorter than _MIN_COVER_ROWS or squeezing the stage below
# _MIN_STAGE_COLS.
_COVER_SHARE = 0.4
_COVER_MARGIN = 2
_COVER_GAP = 2
_MIN_STAGE_COLS = 30
_MIN_COVER_ROWS = 6
# A spacer row plus the album title and the artist under the cover.
_CAPTION_ROWS = 3
# WCAG's 3:1 for large text and graphics: the rail and the kicker are both.
_MIN_ACCENT_CONTRAST = 3.0
# The loading splash cover uses at most this share of the terminal height.
_SPLASH_SHARE = 0.55
# Movement title card: wall seconds on screen, fade length, and the smallest stage
# that shows it. It is information, not motion, so reduced and still show it unfaded.
TITLE_CARD_S = 4.0
_TITLE_FADE_S = 0.6
_TITLE_MIN_ROWS = 8
_TITLE_MIN_COLS = 24
# How much the card darkens the picture beneath its text at full opacity.
_SCRIM = 0.7
# The rail's filled part brightens toward the playhead in this many color steps;
# few steps keep runs long, so render_ansi emits few SGR changes per frame.
_RAIL_STEPS = 8
# Below this terminal height the rail is dropped and status takes the only spare row.
RAIL_MIN_ROWS = 10
_KEY_HINTS = ("space pause  ←/→ seek  n/p movement  m motion  g glyphs  q back", "q back")
_WAY_OUT = "q back"


@dataclass(frozen=True, slots=True)
class Panel:
    """Terminal placement with a one-based top row and zero-based left column.

    Attributes:
        top: One-based terminal row of the panel's top edge.
        left: Zero-based column offset of the panel's left edge.
        cols: Panel width in character cells.
        rows: Panel height in character cells.
    """

    top: int
    left: int
    cols: int
    rows: int


@dataclass(frozen=True, slots=True)
class Layout:
    """Column split of the canvas rows between the stage and an optional cover.

    Attributes:
        stage_left: Zero-based column offset of the stage's first cell.
        stage_cols: Stage width in character cells.
        cover: Panel for the album cover, or None when there is nothing to show.
        caption: Two rows under the cover for its title and artist, or None when
            the canvas is too short to give them room.
    """

    stage_left: int
    stage_cols: int
    cover: Panel | None
    caption: Panel | None = None


def layout(width: int, canvas_rows: int, aspect: float, ratio: float | None) -> Layout:
    """Place the framed cover left of the stage, or give the stage the whole canvas.

    The panel keeps the image's own proportions. A panel `cols` wide and `rows`
    tall spans `cols` by `rows * aspect` cell-widths of physical area, so its width
    over height equals `cols / (rows * aspect)`. The caption is dropped before the
    cover shrinks below `_MIN_COVER_ROWS`. The cover and caption are centered
    together in the canvas rows. If the cover would fall below `_MIN_COVER_ROWS`,
    or the stage below `_MIN_STAGE_COLS`, no panel is drawn.

    Args:
        width: Terminal width in character cells, positive.
        canvas_rows: Rows shared by the stage and the panel, positive.
        aspect: Cell height divided by cell width, positive.
        ratio: Cover width divided by height, positive; None when there is no cover.

    Returns:
        The split for this terminal size.
    """
    whole = Layout(stage_left=0, stage_cols=width, cover=None)
    if ratio is None or canvas_rows < _MIN_COVER_ROWS:
        return whole
    max_cols = min(int(width * _COVER_SHARE), width - _COVER_MARGIN - _COVER_GAP - _MIN_STAGE_COLS)
    captioned = canvas_rows - _CAPTION_ROWS >= _MIN_COVER_ROWS
    room = canvas_rows - _CAPTION_ROWS if captioned else canvas_rows
    rows = min(room, int(max_cols / (aspect * ratio)))
    if rows < _MIN_COVER_ROWS:
        return whole
    cols = min(max_cols, int(rows * aspect * ratio))
    if cols < 1:
        # A very tall, narrow cover can round to no columns at all.
        return whole
    block = rows + (_CAPTION_ROWS if captioned else 0)
    top = 1 + (canvas_rows - block) // 2
    stage_left = _COVER_MARGIN + cols + _COVER_GAP
    return Layout(
        stage_left=stage_left,
        stage_cols=width - stage_left,
        cover=Panel(top=top, left=_COVER_MARGIN, cols=cols, rows=rows),
        caption=(
            Panel(top=top + rows + 1, left=_COVER_MARGIN, cols=cols, rows=_CAPTION_ROWS - 1)
            if captioned
            else None
        ),
    )


def cover_tier(tier: str) -> str:
    """Return the mosaic tier that draws a cover.

    ASCII stays ASCII for consoles. Every other tier draws covers with half blocks:
    they are the most widely rendered glyphs, and each cell's two exact colors suit
    photographs better than finer two-color mosaics.

    Args:
        tier: The stage's budgeted tier key.

    Returns:
        ``"ascii"`` or ``"half"``.
    """
    return "ascii" if tier == "ascii" else "half"


def legible(color: str, background: str, foreground: str) -> str:
    """Lift `color` toward `foreground` until it reads against `background`.

    Args:
        color: Candidate ``#rrggbb``.
        background: Theme background ``#rrggbb`` the color sits on.
        foreground: Theme text ``#rrggbb``, the direction of the lift.

    Returns:
        The least-mixed color, in tenths, that reaches `_MIN_ACCENT_CONTRAST`,
        or `foreground` itself if no mix does.
    """
    for step in range(11):
        candidate = mix(color, foreground, step / 10)
        if contrast_ratio(candidate, background) >= _MIN_ACCENT_CONTRAST:
            return candidate
    return foreground


def album_accent(
    cover_rgb: tuple[int, int, int] | None, movement_palette: Sequence[str], palette: Palette
) -> str:
    """Choose the chrome accent for the playing movement.

    Args:
        cover_rgb: `cover_accent` of the album cover, or None without a cover.
        movement_palette: The movement's scene colors; the last is its highlight.
        palette: Active UI theme.

    Returns:
        A legible ``#rrggbb``: the cover's color if there is one, else the
        movement's highlight, else the theme accent.
    """
    if cover_rgb is not None:
        raw = to_hex(cover_rgb)
    else:
        raw = (normalize_hex(movement_palette[-1]) if movement_palette else None) or palette.accent
    return legible(raw, palette.background, palette.foreground)


def _clip(text: str, width: int) -> str:
    """Normalize text to one column per character and end it with … if it is cut."""
    clean = _single_column(text)
    if width <= 0:
        return ""
    return clean if len(clean) <= width else clean[: width - 1] + "…"


def _text_at(row: int, col: int, text: str, fg: str, color_mode: str) -> bytes:
    """Place already-clipped text at a one-based row and zero-based column.

    No background is set, so the text sits on whatever the terminal shows there.
    """
    if not text:
        return b""
    place = f"\x1b[{row};{col + 1}H"
    if color_mode == "none":
        return (place + text).encode()
    return (place + _ansi_color(fg, color_mode, foreground=True) + text + "\x1b[0m").encode()


def _centered(row: int, left: int, cols: int, text: str, fg: str, color_mode: str) -> bytes:
    """Clip text to `cols` and center it within the span that starts at `left`."""
    clipped = _clip(text, cols)
    return _text_at(row, left + (cols - len(clipped)) // 2, clipped, fg, color_mode)


def _spaced(text: str, room: int) -> str:
    """Letter-space an uppercase title when it fits in `room`; else return it plain."""
    spaced = " ".join(_single_column(text).upper())
    return spaced if len(spaced) <= room else text


def canvas_prefix(
    plan: Layout,
    cover: np.ndarray | None,
    canvas_rows: int,
    tier: str,
    color_mode: str,
    *,
    title: str,
    artist: str,
    palette: Palette,
    accent: str,
) -> bytes:
    """Return the bytes that repaint the cover panel and caption after a change.

    The canvas rows are erased first, because a previous layout may have left stage
    pixels in the margin, panel, and gap columns. Color modes reset SGR before
    erasing, so an erased cell takes the default background and not the last stage
    cell's color. The stage rewrites its own columns in the same frame, since the
    caller invalidated its row state.

    Args:
        plan: Current column split.
        cover: Prepared or decoded cover, or None.
        canvas_rows: Rows shared by the stage and the panel, positive.
        tier: The stage's budgeted tier; the cover uses `cover_tier` of it.
        color_mode: ``truecolor``, ``256``, or ``none``.
        title: Album title for the caption.
        artist: Album artist for the caption.
        palette: Active UI theme; the artist line uses its muted role.
        accent: Legible album accent for the caption title.

    Returns:
        Cursor-addressed bytes for the caller's synchronized frame. Empty when the
        layout has no cover.
    """
    panel = plan.cover
    if panel is None or cover is None:
        return b""
    reset = b"" if color_mode == "none" else b"\x1b[0m"
    erase = reset + b"".join(b"\x1b[%d;1H\x1b[2K" % row for row in range(1, canvas_rows + 1))
    art = render_cover(
        cover,
        cols=panel.cols,
        rows=panel.rows,
        tier=cover_tier(tier),
        color_mode=color_mode,
        top=panel.top,
        left=panel.left,
    )
    caption = plan.caption
    if caption is not None:
        art += _centered(caption.top, caption.left, caption.cols, title, accent, color_mode)
        art += _centered(
            caption.top + 1, caption.left, caption.cols, artist, palette.muted, color_mode
        )
    return erase + art


def status_row(height: int, width: int, text: str, palette: Palette, color_mode: str) -> bytes:
    """Paint one theme-colored text row on the terminal's last row.

    Args:
        height: Terminal height in rows, positive.
        width: Terminal width in character cells, positive.
        text: Message; clipped to the width.
        palette: Active UI theme.
        color_mode: ``truecolor``, ``256``, or ``none``.

    Returns:
        Cursor-addressed bytes.
    """
    row = _text_row(_clip(text, width), width, palette.foreground, palette.background)
    return f"\x1b[{height};1H".encode() + render_ansi([row], color_mode).encode()


def splash(
    *,
    title: str,
    artist: str,
    cover: np.ndarray | None,
    ratio: float | None,
    width: int,
    height: int,
    aspect: float,
    tier: str,
    palette: Palette,
    accent: str,
    color_mode: str,
    status: str,
) -> bytes:
    """Clear the terminal and compose the loading screen: cover, title, and status.

    The cover is centered and takes at most `_SPLASH_SHARE` of the height. The album
    title, letter-spaced when it fits, and the artist sit under it. The cover is
    omitted when it cannot reach `_MIN_COVER_ROWS`, and the text is clipped before it
    can overflow. The last row carries `status` in the transport's colors.

    Args:
        title: Album title.
        artist: Album artist.
        cover: Prepared or decoded cover, or None.
        ratio: Cover width divided by height; None without a cover.
        width: Terminal width in character cells, positive.
        height: Terminal height in rows, positive.
        aspect: Cell height divided by cell width.
        tier: Requested mosaic tier; the cover uses `cover_tier` of it.
        palette: Active UI theme.
        accent: Legible album accent for the title.
        color_mode: ``truecolor``, ``256``, or ``none``.
        status: Loading message for the last row.

    Returns:
        A full-screen frame, starting with a home and clear-to-end.
    """
    reset = b"" if color_mode == "none" else b"\x1b[0m"
    out = [reset + b"\x1b[H\x1b[J"]
    canvas = height - 1
    cover_rows = cover_cols = 0
    if cover is not None and ratio:
        rows = min(int(height * _SPLASH_SHARE), canvas - 3, int((width - 4) / (aspect * ratio)))
        if rows >= _MIN_COVER_ROWS:
            cover_rows, cover_cols = rows, max(1, int(rows * aspect * ratio))
    text_rows = min(2, max(0, canvas))
    block = cover_rows + (1 if cover_rows else 0) + text_rows
    row = 1 + max(0, canvas - block) // 2
    if cover_rows:
        out.append(
            render_cover(
                cover,
                cols=cover_cols,
                rows=cover_rows,
                tier=cover_tier(tier),
                color_mode=color_mode,
                top=row,
                left=(width - cover_cols) // 2,
            )
        )
        row += cover_rows + 1
    lines = ((_spaced(title, width - 4), accent), (artist, palette.muted))
    for text, color in lines[:text_rows]:
        out.append(_centered(row, 0, width, text, color, color_mode))
        row += 1
    out.append(status_row(height, width, status, palette, color_mode))
    return b"".join(out)


def title_card(
    cells: Cells | None,
    plan: Layout,
    canvas_rows: int,
    *,
    number: int,
    count: int,
    title: str,
    age_s: float,
    fade: bool,
    palette: Palette,
    accent: str,
    color_mode: str,
) -> bytes:
    """Overlay the movement's number and title on the stage's lower left.

    The card sits on a scrim that darkens the picture beneath it, so it reads over
    any scene without hiding it. It is drawn after the stage in the same frame and
    redrawn every frame while it lasts. The caller repaints the stage once it
    expires. With `fade`, text and scrim ease in and out over `_TITLE_FADE_S`;
    otherwise the card simply appears and leaves.

    Args:
        cells: The stage's latest fitted cells, which supply the colors under the
            card; None before the first picture.
        plan: Current layout, which gives the stage's columns.
        canvas_rows: Stage height in rows.
        number: One-based movement number.
        count: Movements in the album.
        title: Movement title.
        age_s: Wall seconds since the movement opened.
        fade: Ease the card in and out (truecolor, full motion).
        palette: Active UI theme; the title uses its foreground.
        accent: Legible album accent for the kicker.
        color_mode: ``truecolor``, ``256``, or ``none``.

    Returns:
        Cursor-addressed bytes, or empty bytes when the card has expired, the stage
        is too small, or there is no picture yet.
    """
    if (
        cells is None
        or not 0 <= age_s < TITLE_CARD_S
        or canvas_rows < _TITLE_MIN_ROWS
        or plan.stage_cols < _TITLE_MIN_COLS
    ):
        return b""
    room = plan.stage_cols - 6
    lines = ((_clip(f"MOVEMENT {number} OF {count}", room), accent), (_clip(title, room), ""))
    plate = max(len(text) for text, _ in lines) + 4
    alpha = 1.0
    if fade:
        edge = min(age_s, TITLE_CARD_S - age_s) / _TITLE_FADE_S
        edge = min(1.0, max(0.0, edge))
        alpha = edge * edge * (3 - 2 * edge)
    out: list[str] = []
    for offset, (text, color) in enumerate(lines):
        line_row = canvas_rows - 2 + offset
        cell_row = line_row - 1
        if not 0 <= cell_row < cells.fg.shape[0]:
            continue
        padded = f"  {text}".ljust(plate)[: max(0, cells.fg.shape[1] - 2)]
        out.append(f"\x1b[{line_row};{plan.stage_left + 3}H")
        if color_mode == "none":
            out.append(padded)
            continue
        # One vectorized pass per line; only the SGR formatting stays per run.
        span = slice(2, 2 + len(padded))
        under = (cells.fg[cell_row, span].astype(np.float32) + cells.bg[cell_row, span]) / 2
        scrim = under * (1 - _SCRIM * alpha)
        target = np.array(_rgb(color or palette.foreground), dtype=np.float32)
        ink = scrim + (target - scrim) * alpha
        pairs = np.concatenate([ink, scrim], axis=1).round().astype(np.uint8).tolist()
        last = None
        for char, pair in zip(padded, pairs, strict=True):
            if pair != last:
                out.append(
                    _ansi_color(to_hex(tuple(pair[:3])), color_mode, foreground=True)
                    + _ansi_color(to_hex(tuple(pair[3:])), color_mode, foreground=False)
                )
                last = pair
            out.append(char)
        out.append("\x1b[0m")
    return "".join(out).encode()


def _rgb(value: str) -> tuple[int, int, int]:
    """Parse a normalized ``#rrggbb`` palette role."""
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def status_parts(
    width: int,
    *,
    playing: bool,
    clock: str,
    position: str,
    title: str,
    scene: str,
    motion: str,
    note: str,
) -> list[tuple[str, str]]:
    """Fit the status row as styled runs that keep the state, clock, and way out.

    Bundled titles make the full row over 110 columns, so at 80 the middle
    (position, title, and scene) is cut first and ends with …. A note replaces the
    key hint. It then gives way to the plain way out before it can push the clock
    off-screen, and at the narrowest the way out wins over the clock.

    Args:
        width: Terminal width in character cells, positive.
        playing: Playing or paused; both state labels take nine columns.
        clock: Elapsed and total time, already formatted.
        position: Movement position such as ``2/6``, or empty.
        title: Movement title.
        scene: Section or scene label, plus any tier detail.
        motion: ``full``, ``reduced``, or ``still``; anything but full is shown.
        note: Transport note, or empty.

    Returns:
        ``(text, role)`` runs whose texts join to at most `width` columns. Roles
        are ``state``, ``clock``, ``title``, ``dim``, ``hint``, and ``note``.
    """
    state = "▸ PLAYING" if playing else "❚❚ PAUSED"
    left = [(" ", "dim"), (state, "state"), ("  ", "dim"), (clock, "clock")]
    middle = [("  ", "dim")]
    if position:
        middle.append((f"{position}  ", "dim"))
    middle += [(_single_column(title), "title"), (f" · {_single_column(scene)}", "dim")]
    if motion != "full":
        middle.append((f" · motion {motion}", "dim"))
    rights = (
        [[(_single_column(note), "note"), (f"  {_WAY_OUT}", "hint")], [(_WAY_OUT, "hint")]]
        if note
        else [[(hint, "hint")] for hint in _KEY_HINTS]
    )
    used = sum(len(text) for text, _ in left)
    right = rights[-1]
    for candidate in rights:
        if used + sum(len(text) for text, _ in candidate) + 4 <= width:
            right = candidate
            break
    right_len = sum(len(text) for text, _ in right)
    room = width - used - right_len - 2
    if room <= 0:
        # Too narrow for the middle: keep state and clock, then plain way out, as
        # long as they fit; at the narrowest the way out wins over the clock.
        for parts in (
            [*left, ("  ", "dim"), *right],
            [*left, (" ", "dim"), (_WAY_OUT, "hint")],
            [(" ", "dim"), (_WAY_OUT, "hint")],
        ):
            if sum(len(text) for text, _ in parts) <= width:
                return parts
        return [(_WAY_OUT[:width], "hint")]
    fitted: list[tuple[str, str]] = []
    left_room = room
    if sum(len(text) for text, _ in middle) > room:
        left_room = room - 1
    for text, role in middle:
        if left_room <= 0:
            break
        fitted.append((text[:left_room], role))
        left_room -= len(text)
    if sum(len(text) for text, _ in middle) > room:
        fitted.append(("…", "dim"))
    gap = width - used - sum(len(text) for text, _ in fitted) - right_len - 1
    return [*left, *fitted, (" " * gap, "dim"), *right, (" ", "dim")]


def _rail(
    width: int, progress: float, ticks: set[int], accent: str, palette: Palette
) -> list[Cell]:
    """Build the progress rail: a brightening heavy line, a half-cell head, and ticks.

    Section ticks rise from the line (┴, ┻) instead of spanning the whole cell, so
    they read as ruler marks rather than full-height bars.
    """
    exact = min(1.0, max(0.0, progress)) * width
    filled = int(exact)
    head = filled < width and exact - filled >= 0.5
    dim = mix(palette.background, accent, 0.35)
    steps = [mix(dim, accent, step / _RAIL_STEPS) for step in range(1, _RAIL_STEPS + 1)]
    track = mix(palette.background, palette.muted, 0.6)
    cells = []
    for col in range(width):
        if col < filled:
            color = steps[(col * _RAIL_STEPS) // max(1, filled)]
            char = "┻" if col in ticks else "━"
        elif col == filled and head:
            color, char = accent, "╸"
        elif col in ticks:
            color, char = palette.muted, "┴"
        else:
            color, char = track, "─"
        cells.append(Cell(char, color, palette.background))
    return cells


def transport(
    width: int,
    height: int,
    *,
    progress: float,
    ticks: set[int],
    parts: list[tuple[str, str]],
    palette: Palette,
    accent: str,
    color_mode: str,
) -> bytes:
    """Paint the transport: the rail above the status row when height allows.

    Args:
        width: Terminal width in character cells, positive.
        height: Terminal height in rows, positive; the rail needs `RAIL_MIN_ROWS`.
        progress: Movement progress from 0 to 1.
        ticks: Rail columns that mark section starts.
        parts: Styled runs from `status_parts`.
        palette: Active UI theme.
        accent: Legible album accent for the rail and the state label.
        color_mode: ``truecolor``, ``256``, or ``none``.

    Returns:
        Cursor-addressed bytes for the last one or two rows.
    """
    roles = {
        "state": accent,
        "clock": palette.foreground,
        "title": palette.foreground,
        "dim": palette.muted,
        "hint": palette.muted,
        "note": palette.warning,
    }
    status: list[Cell] = []
    for text, role in parts:
        status += [Cell(char, roles[role], palette.background) for char in text]
    status = status[:width] + _text_row("", width - len(status), palette.muted, palette.background)
    rows = [status]
    if height >= RAIL_MIN_ROWS:
        rows.insert(0, _rail(width, progress, ticks, accent, palette))
    top = height - len(rows) + 1
    return f"\x1b[{top};1H".encode() + _terminal_frame(render_ansi(rows, color_mode)).encode()

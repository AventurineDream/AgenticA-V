"""Interactive terminal album library, native playback dispatch, and cache helpers.

`cli.py` calls `run_library` for bare `aav play`. The frame is a fixed
character grid painted with the active palette; `NO_COLOR` is the renderer's
no-color mode, and a `>` mark keeps the selection visible without color.
Enter hands the selected movement to `native.play_native`, which plays the
album's audio-reactive mosaic scene and audio in this terminal. Shared cache
helpers keep packaged assets read-only and publish extracted files atomically.
"""

from __future__ import annotations

import os
import select
import signal
import sys
import tempfile
import termios
import textwrap
import tty
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from agentic_av import __version__
from agentic_av.catalog import (
    CatalogEntry,
    bundled_assets,
    catalog_entries,
    credit_line,
    format_clock,
    movement_duration_s,
    sort_entries_by,
)
from agentic_av.paint import Cell, _put, _single_column, _text_row, render_ansi
from agentic_av.palette import Palette
from agentic_av.tty import KeyDecoder, _on_sigterm, _PlayerTerminatedError, _size, _terminal_frame


class AlbumError(RuntimeError):
    """A bundled album or cache asset cannot be read or safely addressed."""


def read_bundled_album(asset: str) -> bytes:
    """Read one packaged gzip album without writing it.

    Args:
        asset: Basename from the public catalog.

    Returns:
        Compressed bytes.

    Raises:
        AlbumError: `asset` is not in the public catalog, or it cannot be read.
    """
    if asset not in bundled_assets():
        raise AlbumError(f"album asset {asset!r} is not in the public catalog")
    resource = files("agentic_av").joinpath("albums", asset)
    try:
        return resource.read_bytes()
    except OSError as error:
        raise AlbumError(f"bundled album {asset} is unreadable: {error}") from error


_STEM_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
_CACHE_GENERATION = "track-start-1"


def _asset_stem(asset_name: str) -> str:
    """Return a safe cache filename stem derived from a packaged archive name."""
    if asset_name != Path(asset_name).name:
        raise AlbumError(f"refusing unsafe album asset name {asset_name!r}")
    suffix = ".html.gz"
    stem = asset_name[: -len(suffix)] if asset_name.endswith(suffix) else asset_name
    if not stem or stem in {".", ".."} or any(char not in _STEM_CHARS for char in stem):
        raise AlbumError(f"refusing unsafe album asset name {asset_name!r}")
    return stem


def album_cache_dir(
    cache_home: Path | None = None, *, env: Mapping[str, str] | None = None
) -> Path:
    """Return the stable root for extracted album media and score caches.

    The historical directory name is retained so native-only playback can reuse
    warm caches created before the browser shortcut was removed.

    Args:
        cache_home: Override for the XDG cache home. When omitted, `$XDG_CACHE_HOME`
            is used, then `~/.cache`.
        env: Environment for the XDG lookup. Defaults to the process environment.

    Returns:
        `<cache home>/agentic-av/<package version>/track-start-1`. The directory
        is not created.
    """
    if cache_home is None:
        variables = os.environ if env is None else env
        configured = variables.get("XDG_CACHE_HOME", "").strip()
        cache_home = Path(configured) if configured else Path.home() / ".cache"
    return cache_home / "agentic-av" / __version__ / _CACHE_GENERATION


def _atomic_write(path: Path, payload: bytes) -> None:
    """Publish cache bytes atomically, syncing the file and its parent directory.

    Raises:
        OSError: The cache directory cannot be created or the file cannot be
            published.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


@dataclass
class LibraryState:
    """Selection and overlays for the interactive album library.

    Attributes:
        selected: Index into the currently sorted catalog.
        show_help: Whether the help plate covers the list.
        note: Status line shown above the key hints.
        sort_mode: Current ordering, either band or album.
    """

    selected: int = 0
    show_help: bool = False
    note: str = ""
    sort_mode: str = "band"


_KEY_ACTIONS = {
    "j": "next",
    "J": "next",
    "down": "next",
    "k": "prev",
    "K": "prev",
    "up": "prev",
    "home": "first",
    "g": "first",
    "end": "last",
    "G": "last",
    "enter": "open",
    "s": "sort",
    "S": "sort",
    "?": "help",
    "esc": "esc",
    "q": "quit",
    "Q": "quit",
    "quit": "quit",
}


def apply_library_key(state: LibraryState, key: str, *, count: int) -> str:
    """Apply one library key.

    j/k and the arrow keys move and wrap. Enter plays the selected movement
    natively; `s` toggles band/album order. Neither sorting nor navigation
    fires while help is open. q and Ctrl-C quit even from help. Escape closes
    help and does not quit the list.

    Args:
        state: Selection and overlay, mutated in place.
        key: Action name from the key decoder.
        count: Number of movements. Zero disables opening and movement.

    Returns:
        ``quit``, ``open``, ``sort``, or ``stay``.
    """
    action = _KEY_ACTIONS.get(key)
    if action is None:
        return "stay"
    if action == "quit":
        return "quit"
    if state.show_help:
        if action in {"esc", "help"}:
            state.show_help = False
        return "stay"
    if action == "help":
        state.show_help = True
        return "stay"
    if action == "esc":
        return "stay"
    if action == "sort":
        state.sort_mode = "album" if state.sort_mode == "band" else "band"
        return "sort"
    if count <= 0:
        state.selected = 0
        return "stay"
    if action == "open":
        state.selected %= count
        return action
    if action == "next":
        state.selected = (state.selected + 1) % count
    elif action == "prev":
        state.selected = (state.selected - 1) % count
    elif action == "first":
        state.selected = 0
    elif action == "last":
        state.selected = count - 1
    return "stay"


def _resort_preserving_selection(
    entries: Sequence[CatalogEntry], selected: int, mode: str
) -> tuple[tuple[CatalogEntry, ...], int]:
    """Reorder library rows without changing the highlighted movement.

    Args:
        entries: Current order.
        selected: Current zero-based row.
        mode: New ``band`` or ``album`` order.

    Returns:
        The sorted rows and the selected movement's new index.
    """
    if not entries:
        return (), 0
    focused = entries[selected % len(entries)]
    ordered = sort_entries_by(entries, mode)
    index = next(
        i
        for i, entry in enumerate(ordered)
        if entry.album.asset == focused.album.asset and entry.track.number == focused.track.number
    )
    return ordered, index


def _blank(width: int, palette: Palette) -> list[Cell]:
    return _text_row("", width, palette.foreground, palette.background)


def _chrome(height: int, *, has_note: bool) -> tuple[int, int, int]:
    """Reserve header, note, and hint rows without consuming the selection.

    The album heading sits in the track list, so no pinned row is reserved.

    Returns:
        Header, note, and hint row counts. The remaining rows are the track
        window, and it is at least one when `height` is positive.
    """
    if height <= 1:
        return 0, 0, 0
    spare = height - 1
    hint = 1 if spare >= 1 else 0
    spare -= hint
    header = 1 if spare >= 1 else 0
    spare -= header
    note = 1 if has_note and spare >= 1 else 0
    return header, note, hint


def _display_lines(entries: Sequence[CatalogEntry]) -> list[tuple[str, int]]:
    """Return group and track rows pointing at catalog indexes."""
    lines: list[tuple[str, int]] = []
    previous: tuple[str, str, str] | None = None
    for index, entry in enumerate(entries):
        album = entry.album
        identity = (album.artist, album.band, album.title)
        if identity != previous:
            lines.append(("group", index))
            previous = identity
        lines.append(("track", index))
    return lines


def _window_start(focus: int, size: int, total: int) -> int:
    """Choose a window that contains `focus`.

    Args:
        focus: Line index that must stay visible.
        size: Visible line count.
        total: Full line count.

    Returns:
        Inclusive start index. Empty when `size` is 0.
    """
    if size <= 0 or total <= 0:
        return 0
    if total <= size:
        return 0
    start = max(0, min(focus - size // 3, total - size))
    if focus < start:
        start = focus
    if focus >= start + size:
        start = focus - size + 1
    return start


def _help_lines() -> tuple[str, ...]:
    """Return the native playback and library controls for the help plate."""
    return (
        "LIBRARY",
        "",
        "Enter plays the selected movement in the terminal.",
        "",
        "j / down      next track",
        "k / up        previous track",
        "home / end    first or last track",
        "s             toggle band / album order",
        "?             this guide",
        "esc           close this guide",
        "q             leave the library",
    )


def _help_frame(width: int, height: int, palette: Palette) -> list[list[Cell]]:
    """Paint a top-aligned help plate of exactly `height` rows."""
    lines = _help_lines()
    rows: list[list[Cell]] = []
    for index in range(height):
        if index >= len(lines):
            rows.append(_blank(width, palette))
            continue
        text = lines[index]
        if text == "LIBRARY":
            color = palette.accent
        elif "click Play" in text:
            color = palette.warning
        elif not text.strip():
            color = palette.background
        else:
            color = palette.foreground
        rows.append(_text_row(text, width, color, palette.background))
    return rows


def _header_row(
    width: int,
    palette: Palette,
    *,
    selected: int,
    count: int,
    sort_mode: str,
    theme_label: str,
) -> list[Cell]:
    """Paint the wordmark, position, sort mode, and theme without overlapping."""
    row = _blank(width, palette)
    if width < 8:
        _put(row, 0, "AAV"[:width], palette.accent, palette.background)
        return row
    _put(row, 0, "AAV LIBRARY", palette.accent, palette.background)
    theme = theme_label.split(" · ", 1)[0].upper()
    theme_at = max(0, width - len(theme) - 1)
    if theme and theme_at >= 12:
        _put(row, theme_at, theme, palette.muted, palette.background)
    counter = f"{selected + 1}/{count}" if count else "0/0"
    sort_label = f"{sort_mode.upper()} SORT"
    room_end = theme_at if theme and theme_at >= 12 else width
    sort_at = max(12, room_end - len(sort_label) - 1)
    if sort_at + len(sort_label) <= room_end:
        _put(row, sort_at, sort_label, palette.muted, palette.background)
        room_end = sort_at - 1
    if 12 + len(counter) < room_end:
        _put(row, 12, counter, palette.muted, palette.background)
    return row


def _group_row(width: int, palette: Palette, entry: CatalogEntry) -> list[Cell]:
    """Paint an album heading: credit on the left, album duration on the right.

    The heading is the only place an album is named, so the duration rides on
    it. A separate pinned row repeated the same credit above the list.
    """
    text = f" {credit_line(entry.album)}"
    row = _text_row(text, width, palette.accent, palette.background)
    duration = format_clock(entry.album.duration_s)
    used = len(_single_column(text))
    if width - used >= len(duration) + 2:
        _put(row, width - len(duration) - 1, duration, palette.muted, palette.background)
    return row


def _track_row(
    width: int,
    palette: Palette,
    entry: CatalogEntry,
    *,
    selected: bool,
) -> list[Cell]:
    """Paint one movement. The `>` mark is the no-color selection cue."""
    fg = palette.foreground
    bg = palette.selection if selected else palette.background
    mark = ">" if selected else " "
    number = f"{entry.track.number:02d}"
    start = format_clock(entry.track.start_s)
    title = entry.track.title
    if width >= 56:
        left = f"{mark} {number}  {start:>6}  {title}"
    elif width >= 24:
        left = f"{mark} {number}  {title}"
    elif width >= 2:
        left = f"{mark}{title}"
    else:
        left = mark
    row = _text_row(left, width, fg, bg)
    duration = format_clock(max(0.0, movement_duration_s(entry.album, entry.track)))
    used = len(_single_column(left))
    duration_fg = palette.foreground if selected else palette.muted
    if width - used >= len(duration) + 2:
        _put(row, width - len(duration) - 1, duration, duration_fg, bg)
    return row


def _hint_text(width: int) -> str:
    """Choose a key legend that fits without clipping the quit key."""
    wide = "j/k select    s sort band/album    enter play    ? help    q quit"
    mid = "j/k select  s sort  enter play  ? help  q quit"
    short = "j/k s enter ? q"
    if width >= len(wide):
        return wide
    if width >= len(mid):
        return mid
    return short[:width]


def compose_library(
    entries: Sequence[CatalogEntry],
    selected: int,
    width: int,
    height: int,
    palette: Palette,
    *,
    show_help: bool = False,
    note: str = "",
    theme_label: str = "",
    sort_mode: str = "band",
    panel_start: int | None = None,
) -> list[list[Cell]]:
    """Return an exact `height` by `width` library frame.

    A wide layout may reserve a blank right-side panel for separately rendered
    cover art and description; the track list remains in the left region.
    Very small terminals keep the selected movement and drop chrome from the
    bottom up. Track and panel text go through `_text_row`, so titles and blurbs
    cannot inject escapes or widen a row. Non-positive sizes are raised to 1.

    Args:
        entries: Movements in the active band or album order.
        selected: Selected row, wrapped when the list is non-empty.
        width: Columns.
        height: Rows.
        palette: Active role set. The `>` mark remains in no-color mode.
        show_help: Replace the list with the help plate.
        note: Status line above the hint, dropped when the row does not fit.
        theme_label: Theme name shown on the header.
        sort_mode: ``band`` or ``album``, displayed in the header.
        panel_start: First zero-based column of the optional right-hand panel.

    Returns:
        A frame whose dimensions match the raised width and height.
    """
    width, height = max(1, width), max(1, height)
    if show_help:
        return _help_frame(width, height, palette)
    list_width = max(1, min(width, panel_start if panel_start is not None else width))
    count = len(entries)
    index = 0 if count == 0 else selected % count
    header, note_rows, hint = _chrome(height, has_note=bool(note))
    rows: list[list[Cell]] = []
    if header:
        rows.append(
            _header_row(
                list_width,
                palette,
                selected=index,
                count=count,
                sort_mode=sort_mode,
                theme_label=theme_label or palette.name,
            )
        )
    if not count:
        rows.append(_text_row(" No public albums", list_width, palette.muted, palette.background))
    body = height - header - note_rows - hint
    lines = _display_lines(entries)
    focus = next(
        (
            line_index
            for line_index, (kind, entry_index) in enumerate(lines)
            if kind == "track" and entry_index == index
        ),
        0,
    )
    start = _window_start(focus, body, len(lines))
    for kind, entry_index in lines[start : start + body]:
        entry = entries[entry_index]
        if kind == "group":
            rows.append(_group_row(list_width, palette, entry))
        else:
            rows.append(_track_row(list_width, palette, entry, selected=entry_index == index))
    while len(rows) < height - note_rows - hint:
        rows.append(_blank(list_width, palette))
    if note_rows:
        rows.append(_text_row(f" {note}", list_width, palette.warning, palette.background))
    if hint:
        rows.append(
            _text_row(_hint_text(list_width), list_width, palette.muted, palette.background)
        )
    pad = _blank(list_width, palette)
    rows = rows[:height]
    rows.extend(pad for _ in range(height - len(rows)))
    return [
        row[:list_width]
        + [Cell(" ", palette.foreground, palette.background)] * (width - list_width)
        for row in rows
    ]


def _library_panel_bytes(
    entry: CatalogEntry,
    pixels: object | None,
    *,
    panel_start: int,
    width: int,
    height: int,
    palette: Palette,
    color_mode: str,
) -> bytes:
    """Render highlighted-album art and its blurb in the reserved right panel.

    Args:
        entry: Highlighted song's album.
        pixels: Verified cover pixels, or None when unavailable.
        panel_start: First zero-based panel column.
        width: Terminal columns.
        height: Terminal rows.
        palette: Active theme roles.
        color_mode: ``truecolor``, ``256``, or ``none``.

    Returns:
        Cursor-addressed bytes over the already-painted blank panel.
    """
    from agentic_av.viz.cover import render_cover

    panel_width = width - panel_start
    if panel_width < 14 or height < 12:
        return b""
    title = entry.album.title
    title_row = _text_row(
        textwrap.shorten(title, width=panel_width, placeholder="…"),
        panel_width,
        palette.accent,
        palette.background,
    )
    out = [
        f"{chr(27)}[2;{panel_start + 1}H".encode() + render_ansi([title_row], color_mode).encode()
    ]
    top = 3
    description_top = top
    if pixels is not None:
        rows = min(12, max(6, (height - 8) // 2))
        cols = min(panel_width - 2, rows * 2)
        if rows >= 6 and cols >= 12:
            left = panel_start + (panel_width - cols) // 2
            out.append(
                render_cover(
                    pixels,
                    cols=cols,
                    rows=rows,
                    tier="half",
                    color_mode=color_mode,
                    top=top,
                    left=left,
                )
            )
            description_top = top + rows + 1
    if pixels is None:
        description_top += 1
        out.append(
            f"{chr(27)}[{top};{panel_start + 1}H".encode()
            + render_ansi(
                [_text_row("Art unavailable", panel_width, palette.muted, palette.background)],
                color_mode,
            ).encode()
        )
    description = entry.album.description or "No album description available."
    lines = textwrap.wrap(
        description, width=max(1, panel_width - 2), break_long_words=True, break_on_hyphens=False
    )
    for offset, line in enumerate(lines[: max(0, height - description_top + 1)]):
        row = _text_row(f" {line}", panel_width, palette.foreground, palette.background)
        out.append(
            f"{chr(27)}[{description_top + offset};{panel_start + 1}H".encode()
            + render_ansi([row], color_mode).encode()
        )
    return b"".join(out)


class _TTY:
    """Raw-mode alternate screen for the interactive album library.

    `leave` is idempotent and restores the terminal when the library exits.
    """

    def __init__(self, source: object, target: object) -> None:
        """Remember the streams. Raw mode starts only in `enter`.

        Args:
            source: TTY input with `fileno`.
            target: TTY output with `write` and `flush`.
        """
        self._fd = source.fileno()
        self._target = target
        self._original = None
        self._raw = False
        self._alt = False

    def enter(self) -> None:
        """Enable raw mode and the alternate screen."""
        if self._original is None:
            self._original = termios.tcgetattr(self._fd)
        if not self._raw:
            tty.setraw(self._fd)
            self._raw = True
        if not self._alt:
            self._target.write("\x1b[?1049h\x1b[?25l")
            self._target.flush()
            self._alt = True

    def leave(self) -> None:
        """Restore canonical mode and the primary screen.

        Safe when `enter` never succeeded, and safe to call twice.
        """
        if self._raw and self._original is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._original)
            self._raw = False
        if self._alt:
            self._target.write("\x1b[0m\x1b[?25h\x1b[?1049l")
            self._target.flush()
            self._alt = False


def run_library(
    palette: Palette,
    color_mode: str,
    *,
    theme_label: str = "",
    motion: str = "full",
    glyphs: str = "auto",
    input_stream: object | None = None,
    output_stream: object | None = None,
    cache_home: Path | None = None,
    entries: Sequence[CatalogEntry] | None = None,
) -> int:
    """Run the album library until q or Ctrl-C.

    The `s` key switches band/album ordering while keeping the same movement
    selected. At 72 columns by 16 rows, the highlighted album's art and
    description occupy a panel beside the track list. Enter plays natively;
    q and Ctrl-C exit; Escape closes help and does not quit the library.

    Side effects: Enters raw terminal mode, writes frames, and may launch
        native audio when Enter selects a movement.

    Args:
        palette: Active palette. Roles color the frame; `color_mode` decides
            whether those colors are emitted.
        color_mode: ``truecolor``, ``256``, or ``none``.
        theme_label: Header label. Defaults to the palette name.
        motion: ``full``, ``reduced``, or ``still`` for native playback.
        glyphs: Native mosaic tier; ``auto`` honors AAV_GLYPHS and terminal hints.
        input_stream: Optional TTY for tests.
        output_stream: Optional TTY for tests.
        cache_home: XDG cache home override.
        entries: Catalog override. Defaults to the bundled public catalog.

    Returns:
        Zero after the terminal is restored, including after SIGTERM.

    Raises:
        RuntimeError: Input or output is not an interactive terminal.
        CatalogError: The bundled catalog is inconsistent.
    """
    # Imported here: `native` imports this module for its cache helpers.
    from agentic_av.native import NativeError, play_native
    from agentic_av.viz.cover import ArtworkError, load_cover

    source = input_stream or sys.stdin
    target = output_stream or sys.stdout
    if not source.isatty() or not target.isatty():
        raise RuntimeError("interactive library needs a TTY; use `aav tracks` for the catalog")
    catalog = sort_entries_by(tuple(catalog_entries() if entries is None else entries), "band")
    state = LibraryState()
    cover_cache: dict[str, object | None] = {}
    panel_cache: dict[tuple[str, int, int, int, str], bytes] = {}
    term = _TTY(source, target)
    previous = signal.getsignal(signal.SIGTERM)
    decoder = KeyDecoder()
    try:
        signal.signal(signal.SIGTERM, _on_sigterm)
        term.enter()
        active = True
        dirty = True
        last_size = (-1, -1)
        while active:
            width, height = _size(source.fileno())
            if dirty or (width, height) != last_size:
                panel_start = width * 5 // 8 if width >= 72 and height >= 16 else None
                pixels = None
                selected_entry = catalog[state.selected] if catalog else None
                if panel_start is not None and selected_entry is not None and not state.show_help:
                    key = selected_entry.album.asset
                    if key not in cover_cache:
                        if selected_entry.album.cover is None:
                            cover_cache[key] = None
                        else:
                            try:
                                cover_cache[key] = load_cover(
                                    selected_entry.album.cover.asset,
                                    selected_entry.album.cover.sha256,
                                )
                            except ArtworkError:
                                cover_cache[key] = None
                    pixels = cover_cache[key]
                frame = render_ansi(
                    compose_library(
                        catalog,
                        state.selected,
                        width,
                        height,
                        palette,
                        show_help=state.show_help,
                        note=state.note,
                        theme_label=theme_label or palette.name,
                        sort_mode=state.sort_mode,
                        panel_start=panel_start if not state.show_help else None,
                    ),
                    color_mode,
                )
                panel = b""
                if panel_start is not None and selected_entry is not None and not state.show_help:
                    panel_key = (
                        selected_entry.album.asset,
                        panel_start,
                        width,
                        height,
                        color_mode,
                    )
                    if panel_key not in panel_cache:
                        panel_cache[panel_key] = _library_panel_bytes(
                            selected_entry,
                            pixels,
                            panel_start=panel_start,
                            width=width,
                            height=height,
                            palette=palette,
                            color_mode=color_mode,
                        )
                    panel = panel_cache[panel_key]
                target.write("\x1b[H" + _terminal_frame(frame) + "\x1b[J")
                if panel:
                    target.write(panel.decode("utf-8"))
                target.flush()
                dirty = False
                last_size = (width, height)
            remaining = decoder.hold_remaining()
            timeout = 0.25 if remaining is None else min(0.25, remaining)
            readable, _, _ = select.select([source.fileno()], [], [], timeout)
            keys = decoder.feed(os.read(source.fileno(), 64)) if readable else decoder.flush()
            for key in keys:
                action = apply_library_key(state, key, count=len(catalog))
                if action == "sort":
                    catalog, state.selected = _resort_preserving_selection(
                        catalog, state.selected, state.sort_mode
                    )
                dirty = True
                if action == "quit":
                    active = False
                    break
                if action == "open":
                    entry = catalog[state.selected]
                    try:
                        play_native(
                            entry,
                            catalog,
                            palette,
                            color_mode,
                            motion=motion,
                            glyphs=glyphs,
                            input_stream=source,
                            output_stream=target,
                            cache_home=cache_home,
                        )
                        state.note = ""
                    except (AlbumError, NativeError, OSError) as error:
                        state.note = str(error)
                    last_size = (-1, -1)
                    break
    except (_PlayerTerminatedError, KeyboardInterrupt):
        pass
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            term.leave()
        finally:
            signal.signal(signal.SIGTERM, previous)
    return 0

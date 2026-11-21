"""Interactive album library, native playback dispatch, and browser deep link.

`cli.py` calls `run_library` for bare `aav play`. The frame is a fixed
character grid painted with the active palette; `NO_COLOR` is the renderer's
no-color mode, and a `>` mark keeps the selection visible without color.
Enter hands the selected movement to `native.play_native`, which plays the
album's audio-reactive mosaic scene and audio in this terminal. `o` instead restores
canonical terminal mode, materializes one bundled `.html.gz` into the
versioned XDG cache, and opens that copy in the default browser. The
compressed package asset is never rewritten. The injected script seeks
`#audio` from a numeric `start` query after metadata loads and does not
call `play()`; browser autoplay policy still requires a Play click.
"""

from __future__ import annotations

import gzip
import hashlib
import math
import os
import select
import signal
import sys
import tempfile
import termios
import textwrap
import tty
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Protocol

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

# Bump when the injected script's contract changes. The filename also hashes
# the script bytes, so an edited script is not served from an older file if
# this revision is forgotten. The directory is the generation a person can wipe.
SCRIPT_REVISION = "1"
TRACK_START_ID = "aav-track-start"
_HAVE_METADATA = 1

_TRACK_START_SCRIPT = f"""<script id="{TRACK_START_ID}">
(function () {{
  var raw = new URLSearchParams(location.search).get("start");
  var start = Number(raw);
  if (!Number.isFinite(start) || start < 0) return;
  var audio = document.getElementById("audio");
  if (!audio) return;
  var arm = function () {{
    audio.currentTime = start;
    var seek = document.getElementById("seek");
    if (seek) seek.value = String(start);
  }};
  if (audio.readyState >= {_HAVE_METADATA}) arm();
  else audio.addEventListener("loadedmetadata", arm);
}})();
</script>
"""


class AlbumError(RuntimeError):
    """A bundled album cannot be prepared or opened in the browser."""


class TerminalGate(Protocol):
    """A terminal that can leave raw mode before a child inherits it."""

    def leave(self) -> None:
        """Restore canonical mode, echo, the cursor, and the primary screen."""

    def enter(self) -> None:
        """Return to raw mode and the alternate screen after a browser launch."""


def track_start_script() -> str:
    """Return the script inserted before ``</body>``.

    The script reads a numeric `start` query parameter, sets `#audio`
    `currentTime` after metadata is available, and updates `#seek` when that
    element exists. It does not call `play()` and does not set autoplay.
    Setting `#seek` does not dispatch `input`: several bundled players treat
    that event as a user gesture and would start playback.

    Returns:
        An HTML script element. ASCII only, so it cannot change the page encoding.
    """
    return _TRACK_START_SCRIPT


def inject_track_start(html: str, script: str | None = None) -> str:
    """Insert the track-start script immediately before the last ``</body>``.

    Args:
        html: Decoded album document. Not modified in place.
        script: Override for tests. Defaults to `track_start_script`.

    Returns:
        A new document. A document that already contains the script id is
        returned unchanged so a second inject cannot stack seekers.

    Raises:
        AlbumError: The document has no closing body tag. Refusing to append
            keeps a truncated archive from gaining a script the browser will
            ignore, and keeps the failure out of the cache.
    """
    payload = track_start_script() if script is None else script
    if f'id="{TRACK_START_ID}"' in html:
        return html
    index = html.lower().rfind("</body>")
    if index < 0:
        raise AlbumError("album HTML has no </body>; the track-start script was not injected")
    prefix = "" if index == 0 or html[index - 1] == "\n" else "\n"
    return f"{html[:index]}{prefix}{payload}\n{html[index:]}"


def album_cache_dir(
    cache_home: Path | None = None, *, env: Mapping[str, str] | None = None
) -> Path:
    """Return the versioned directory for materialized album HTML.

    Args:
        cache_home: Override for the XDG cache home. Tests pass a temp
            directory. When omitted, `$XDG_CACHE_HOME` is used, then
            `~/.cache`.
        env: Environment for the XDG lookup. Defaults to the process environment.

    Returns:
        `<cache home>/agentic-av/<package version>/track-start-<revision>`.
        The directory is not created.
    """
    if cache_home is None:
        variables = os.environ if env is None else env
        configured = variables.get("XDG_CACHE_HOME", "").strip()
        cache_home = Path(configured) if configured else Path.home() / ".cache"
    return cache_home / "agentic-av" / __version__ / f"track-start-{SCRIPT_REVISION}"


_STEM_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")


def _asset_stem(asset_name: str) -> str:
    """Return a cache filename stem, rejecting paths that could escape the cache."""
    if asset_name != Path(asset_name).name:
        raise AlbumError(f"refusing unsafe album asset name {asset_name!r}")
    suffix = ".html.gz"
    stem = asset_name[: -len(suffix)] if asset_name.endswith(suffix) else asset_name
    if not stem or stem in {".", ".."} or any(char not in _STEM_CHARS for char in stem):
        raise AlbumError(f"refusing unsafe album asset name {asset_name!r}")
    return stem


def _published(path: Path) -> bool:
    """Report whether a cache file looks like a finished injected document."""
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size < 64:
        return False
    with path.open("rb") as handle:
        handle.seek(max(0, size - 4096))
        tail = handle.read().lower()
    return b"aav-track-start" in tail and b"</body>" in tail


def _atomic_write(path: Path, payload: bytes) -> None:
    """Publish `payload` by renaming a complete temp file in the same directory.

    A crash before the rename leaves a `.partial` file, never a short HTML
    file at `path`. The rename is atomic on the same filesystem.

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


def materialize_html(gz_bytes: bytes, asset_name: str, cache_home: Path | None = None) -> Path:
    """Decompress album HTML, inject the seek script, and publish it atomically.

    The cache name includes the package version, the script revision, a hash
    of the gzip bytes, and a hash of the script. A repeat call with the same
    bytes reuses a complete file and does not decompress again. This function
    does not open or write the packaged asset; the caller passes bytes.

    Args:
        gz_bytes: Compressed HTML. Not modified.
        asset_name: Basename used only as the cache stem.
        cache_home: XDG cache home override. None uses the process default.

    Returns:
        Path of the cached `.html` file.

    Raises:
        AlbumError: The bytes are not gzip UTF-8 HTML, the asset name is
            unsafe, or the document has no ``</body>``.
        OSError: The cache file cannot be published.
    """
    stem = _asset_stem(asset_name)
    script = track_start_script()
    source_digest = hashlib.sha256(gz_bytes).hexdigest()[:16]
    script_digest = hashlib.sha256(script.encode("utf-8")).hexdigest()[:8]
    dest = album_cache_dir(cache_home) / f"{stem}-{source_digest}-{script_digest}.html"
    if _published(dest):
        return dest
    try:
        text = gzip.decompress(gz_bytes).decode("utf-8")
    except gzip.BadGzipFile as error:
        raise AlbumError(f"{asset_name} is not a gzip HTML album") from error
    except UnicodeDecodeError as error:
        raise AlbumError(f"{asset_name} is not UTF-8 HTML") from error
    html = inject_track_start(text, script)
    _atomic_write(dest, html.encode("utf-8"))
    return dest


def format_start(start_s: float) -> str:
    """Format a movement start for the `start` query parameter.

    Catalog values are decimal seconds with at most six fractional digits.
    Six digits round-trips those literals. A wider binary value is still
    emitted in fixed point, never scientific notation, so `Number()` in the
    page sees a finite decimal.

    Args:
        start_s: Start offset in seconds.

    Returns:
        A numeric token such as ``77.5715`` or ``0``.

    Raises:
        AlbumError: `start_s` is negative or not finite.
    """
    if not math.isfinite(start_s) or start_s < 0:
        raise AlbumError(f"track start must be a non-negative number of seconds, not {start_s!r}")
    text = f"{start_s:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def track_url(path: Path, start_s: float) -> str:
    """Build a file URL that opens `path` at `start_s` seconds.

    Args:
        path: Materialized HTML file, not the compressed asset.
        start_s: Movement start in seconds.

    Returns:
        `path` as a file URI plus a `start` query.

    Raises:
        AlbumError: `start_s` cannot be formatted.
    """
    return f"{path.as_uri()}?start={format_start(start_s)}"


def open_track(
    path: Path,
    start_s: float,
    *,
    opener: Callable[[str], object] | None = None,
) -> str:
    """Open a materialized album in the default browser.

    Args:
        path: Cached HTML file.
        start_s: Movement start in seconds, passed as the `start` query.
        opener: Launcher receiving the URL. Defaults to `webbrowser.open`,
            which honors the default browser and `$BROWSER`. Tests inject this.
            A return of False is failure; None is treated as success because
            some launchers do not return a bool.

    Returns:
        The URL passed to the launcher.

    Raises:
        AlbumError: The start is invalid, or the browser did not open.
    """
    url = track_url(path, start_s)
    launch = webbrowser.open if opener is None else opener
    try:
        opened = launch(url)
    except (OSError, webbrowser.Error) as error:
        raise AlbumError(f"could not open the default browser: {error}") from error
    if opened is False:
        raise AlbumError("the default browser did not open the album")
    return url


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


def prepare_track(
    entry: CatalogEntry,
    cache_home: Path | None = None,
    source: bytes | None = None,
) -> Path:
    """Materialize the album that owns `entry`.

    Args:
        entry: Movement being opened. The album asset name selects the file.
        cache_home: XDG cache home override.
        source: Compressed bytes. When omitted, the packaged asset is read.
            Tests pass a tiny gzip so they do not rewrite or expand the
            bundled archives.

    Returns:
        Cached HTML path.

    Raises:
        AlbumError: The asset is unknown, unreadable, or not injectable HTML.
    """
    data = read_bundled_album(entry.album.asset) if source is None else source
    return materialize_html(data, entry.album.asset, cache_home)


def open_selected_and_resume(
    terminal: TerminalGate,
    entry: CatalogEntry,
    *,
    cache_home: Path | None = None,
    opener: Callable[[str], object] | None = None,
    source: bytes | None = None,
) -> str:
    """Leave raw mode, open the movement, then return the terminal to raw mode.

    `leave` runs before decompression and before the browser. xdg-open and a
    terminal browser inherit the TTY; launching them from raw mode eats input
    and prints off-column. `enter` runs even when materialize or the browser
    fails, so the library can show the error. If `leave` itself fails, raw
    mode is not re-entered.

    Args:
        terminal: Raw-mode owner. Must implement `leave` and `enter`.
        entry: Movement to open.
        cache_home: XDG cache home override.
        opener: Browser launcher. Defaults to the system default browser.
        source: Optional compressed HTML override for tests.

    Returns:
        The URL opened in the browser.

    Raises:
        AlbumError: The album could not be prepared or opened. The terminal
            has been returned to raw mode unless `leave` failed.
        OSError: Publishing the cache file failed, after the same restore.
    """
    terminal.leave()
    try:
        path = prepare_track(entry, cache_home, source)
        return open_track(path, entry.track.start_s, opener=opener)
    finally:
        terminal.enter()


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
    "o": "open_browser",
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

    j/k and the arrow keys move the selection and wrap. Enter asks the
    caller to play the selected movement natively; `o` asks for the browser
    page. `s` toggles band/album order. Neither sorting nor navigation fires
    while help is open. q and Ctrl-C quit even from help. Escape closes help
    and does not quit the list.

    Args:
        state: Selection and overlay, mutated in place.
        key: Action name from the key decoder.
        count: Number of movements. Zero disables open and movement.

    Returns:
        ``quit``, ``open``, ``open_browser``, ``sort``, or ``stay``.
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
    if action in {"open", "open_browser"}:
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
    """Return help text, with the playback summary before the key list.

    Short terminals top-align this list, so what Enter and `o` do stays on
    screen when the key column does not fit.
    """
    return (
        "LIBRARY",
        "",
        "Enter plays the album's code-only visuals and audio here.",
        "o opens the synchronized web page instead; click Play there.",
        "",
        "j / down      next track",
        "k / up        previous track",
        "home / end    first or last track",
        "s             toggle band / album order",
        "enter         play the selected movement in the terminal",
        "o             open the album page in the browser",
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
    wide = "j/k select    s sort band/album    enter play    o browser    ? help    q quit"
    mid = "j/k select  s sort  enter play  o web  ? help  q quit"
    short = "j/k s enter o ? q"
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
    """Raw-mode alternate screen that can be left before a browser launch.

    `leave` is idempotent. Launching a browser from raw mode is unsafe: the
    child inherits that state.
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
    opener: Callable[[str], object] | None = None,
    cache_home: Path | None = None,
    entries: Sequence[CatalogEntry] | None = None,
) -> int:
    """Run the album library until q or Ctrl-C.

    The `s` key switches band/album ordering while keeping the same movement
    selected. At 72 columns by 16 rows, the highlighted album's art and
    description occupy a panel beside the track list. Enter plays natively;
    `o` opens the web page.

    Side effects: Enters raw terminal mode, writes frames, and may launch
        native audio or a browser in response to the selected keys.

    Args:
        palette: Active palette. Roles color the frame; `color_mode` decides
            whether those colors are emitted.
        color_mode: ``truecolor``, ``256``, or ``none``.
        theme_label: Header label. Defaults to the palette name.
        motion: ``full``, ``reduced``, or ``still`` for native playback.
        glyphs: Native mosaic tier; ``auto`` honors AAV_GLYPHS and terminal hints.
        input_stream: Optional TTY for tests.
        output_stream: Optional TTY for tests.
        opener: Browser launcher override.
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
                if action in {"open", "open_browser"}:
                    entry = catalog[state.selected]
                    try:
                        if action == "open_browser":
                            open_selected_and_resume(
                                term,
                                entry,
                                cache_home=cache_home,
                                opener=opener,
                            )
                            state.note = f"Opened {entry.track.title} - click Play in the browser"
                        else:
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

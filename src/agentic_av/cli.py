"""Command-line interface for the album library, themes, and visual play.

`tracks` prints the public catalog without a TTY. Bare `play` opens the
album library. `demo`, and `play` with `--show` or `--scene`, keep the
abstract visual player. The library never rewrites bundled album archives
or Omarchy configuration.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from agentic_av.omarchy import load_omarchy
from agentic_av.paint import FrameRequest, compose, render_ansi, render_plain
from agentic_av.palette import Palette, PaletteError, builtin_palettes
from agentic_av.session import Session
from agentic_av.show import PROGRAMS, ShowError, demo_show, load_show
from agentic_av.transport import Playhead


def color_mode(env: dict[str, str] | None = None, *, stdout_tty: bool | None = None) -> str:
    """Choose truecolor, xterm-256, or no-color output from terminal hints.

    256-color mode is used only when ``TERM`` contains ``256color``. ``xterm``
    and ``linux`` without that capability, and an empty ``TERM``, are no-color
    unless ``COLORTERM`` advertises truecolor.

    Args:
        env: Environment mapping; defaults to the live process environment.
        stdout_tty: Optional TTY status override for testing.

    Returns:
        One of ``truecolor``, ``256``, or ``none``.
    """
    variables = os.environ if env is None else env
    if "NO_COLOR" in variables or variables.get("TERM", "") == "dumb":
        return "none"
    is_tty = sys.stdout.isatty() if stdout_tty is None else stdout_tty
    if not is_tty:
        return "none"
    if variables.get("COLORTERM", "").casefold() in {"truecolor", "24bit"}:
        return "truecolor"
    term = variables.get("TERM", "")
    # An advertised 256-color capability is required. Any other non-empty TERM
    # used to fall through to 256 and tint xterm/linux previews.
    return "256" if "256color" in term else "none"


def _resolve_theme(name: str) -> tuple[Palette, str, object | None, str]:
    """Resolve a built-in palette or live Omarchy request."""
    if name.casefold() in {"omarchy", "sync", "system"}:
        try:
            resolved = load_omarchy()
            return resolved.palette, "omarchy", resolved, "ok"
        except PaletteError as error:
            return builtin_palettes()[0], "tungsten", None, str(error)
    for palette in builtin_palettes():
        if palette.name == name.casefold():
            return palette, palette.name, None, ""
    available = ", ".join(palette.name for palette in builtin_palettes())
    raise PaletteError(f"unknown theme {name!r}; built-ins: {available}, omarchy")


def _make_parser() -> argparse.ArgumentParser:
    """Build the CLI parser with shared options and focused subcommands."""
    parser = argparse.ArgumentParser(
        prog="aav",
        description=(
            "Terminally Agentic A/V. Open a bundled album in the browser, "
            "or play abstract visual programs."
        ),
        epilog=(
            "Library: j/k select, enter opens the browser (click Play there), "
            "? help, q quit. Visual: space play/pause, arrows seek, t themes, "
            "m motion, ? help, q quit."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("play", "demo", "tracks", "themes", "preview", "gallery"),
        default="play",
        help="play opens the album library unless --show or --scene is set",
    )
    parser.add_argument(
        "--theme",
        default=os.environ.get("AAV_THEME", "omarchy"),
        help="theme name, or omarchy for live sync",
    )
    parser.add_argument(
        "--show",
        type=Path,
        help="TOML show for the visual player; with play, skips the album library",
    )
    parser.add_argument(
        "--scene",
        choices=sorted(PROGRAMS),
        help="force one abstract visual program; with play, skips the album library",
    )
    parser.add_argument("--at", type=float, default=0.0, help="preview position in seconds")
    parser.add_argument("--width", type=int, default=80, help="preview columns")
    parser.add_argument("--height", type=int, default=24, help="preview rows")
    parser.add_argument(
        "--motion", choices=("full", "reduced", "still"), default="full", help="visual motion level"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="use density glyphs without ANSI colors"
    )
    return parser


def _load_requested_show(path: Path | None):
    """Choose the demo reel or parse the user's explicitly selected show."""
    return load_show(path) if path else demo_show()


def _request(session: Session, width: int, height: int, *, mode: str = "play") -> FrameRequest:
    """Build a paint request and commit one visual-time step.

    Preview sessions are paused, so the step is zero and `--at` stays put.
    Reduced motion continues from that time instead of rescaling it.
    Still motion keeps the program selected at the held picture.
    """
    position = session.playhead.position
    index, program = session.visual_program()
    return FrameRequest(
        show=session.show,
        palette=session.palette,
        themes=session.themes,
        width=width,
        height=height,
        position_s=position,
        playing=session.playhead.playing,
        rate=session.playhead.rate,
        program=session.show.programs[index] if session.mode == "play" else program,
        program_index=index,
        theme_index=session.gallery_index,
        mode=mode,
        motion=session.motion,
        field_time_s=session.advance_visual_time(),
        color_mode=session.color_mode,
        sync_note=session.omarchy_note,
    )


def _session(args: argparse.Namespace, show) -> Session:
    """Construct an initial session without persisting any user setting."""
    palette, theme_id, omarchy, note = _resolve_theme(args.theme)
    mode = "none" if args.no_color else color_mode()
    if args.no_color:
        mode = "none"
    playhead = Playhead(show.duration, position_s=args.at % show.duration, playing=False)
    if args.command in {"play", "demo"}:
        playhead.toggle()
    if args.scene:
        show = type(show)(show.title, show.detail, show.duration, show.tempo, (args.scene,))
    themes = builtin_palettes()
    return Session(
        show,
        playhead,
        palette,
        theme_id,
        themes,
        mode,
        args.motion,
        field_time_s=playhead.position,
        motion_anchor_s=playhead.position,
        omarchy=omarchy,
        omarchy_note="ok" if omarchy else ("unavailable" if note else ""),
    )


def _themes(session: Session) -> int:
    """List available palettes and report whether Omarchy sync is available."""
    print("AAV THEMES   /   select with t or Shift-T while playing\n")
    for index, palette in enumerate(builtin_palettes(), start=1):
        default = "  ← default" if palette.name == session.palette.name else ""
        print(f" {index:>2}  {palette.name.upper():<12} {palette.mood}{default}")
    try:
        current = load_omarchy()
        print(f"  O  omarchy     live · {current.slug} ({current.palette.name})")
    except PaletteError as error:
        print(f"  O  omarchy     unavailable ({error})")
    return 0


def _preview(session: Session, args: argparse.Namespace, *, gallery: bool = False) -> int:
    """Print one composed frame or the complete theme gallery."""
    if args.width < 1 or args.height < 1:
        print("aav: width and height must be positive", file=sys.stderr)
        return 2
    if gallery:
        rows: list[list] = []
        # Contact sheet of stages. In-player Shift-T is the scrolling atlas.
        for index, palette in enumerate(builtin_palettes()):
            session.palette = palette
            session.gallery_index = index
            request = _request(session, args.width, max(12, args.height), mode="play")
            rows.extend(compose(request))
        print(
            render_plain(rows)
            if session.color_mode == "none"
            else render_ansi(rows, session.color_mode)
        )
        return 0
    request = _request(session, args.width, args.height)
    rows = compose(request)
    print(
        render_plain(rows)
        if session.color_mode == "none"
        else render_ansi(rows, session.color_mode)
    )
    return 0


def _uses_album_library(args: argparse.Namespace) -> bool:
    """Return whether this invocation opens the album library.

    Bare `play` is the library. `--show` and `--scene` stay on the visual
    player so an existing show file keeps its contract.
    """
    return args.command == "play" and args.show is None and args.scene is None


def _open_library(args: argparse.Namespace) -> int:
    """Resolve the palette and run the interactive album library.

    Args:
        args: Parsed CLI arguments. `--theme` and `--no-color` apply.

    Returns:
        Zero after the library restores the terminal.

    Raises:
        PaletteError: The requested theme name is unknown.
        RuntimeError: Standard input or output is not a TTY.
    """
    palette, _theme_id, _omarchy, _note = _resolve_theme(args.theme)
    mode = "none" if args.no_color else color_mode()
    from agentic_av.library import run_library

    return run_library(palette, mode, theme_label=palette.name)


def _tracks() -> int:
    """Print the sorted public catalog without a TTY or a browser launch."""
    from agentic_av.catalog import format_catalog

    print(format_catalog())
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch `aav` commands; return a process exit code.

    Args:
        argv: Optional argument sequence; defaults to the process command line.

    Returns:
        Zero for success, 2 for invalid input or unavailable interactive mode.
    """
    parser = _make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "tracks":
            return _tracks()
        if _uses_album_library(args):
            return _open_library(args)
        show = _load_requested_show(args.show)
        session = _session(args, show)
        if args.command == "themes":
            return _themes(session)
        if args.command == "preview":
            return _preview(session, args)
        if args.command == "gallery":
            return _preview(session, args, gallery=True)
        from agentic_av.tty import run_player

        return run_player(session)
    except (PaletteError, ShowError, OSError, RuntimeError, ValueError) as error:
        print(f"aav: {error}", file=sys.stderr)
        return 2

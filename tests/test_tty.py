"""Raw input parsing, terminal frames, and player key actions."""

from pathlib import Path

from agentic_av.omarchy import OmarchyTheme
from agentic_av.palette import builtin_palette, builtin_palettes, palette_from_omarchy
from agentic_av.session import Session
from agentic_av.show import Show
from agentic_av.transport import Playhead
from agentic_av.tty import _handle, _terminal_frame, parse_keys


def test_parse_keys_handles_navigation_and_multiple_actions() -> None:
    assert parse_keys(b" \x1b[D\x1b[Ct?q\x03") == [" ", "left", "right", "t", "?", "q", "quit"]
    assert parse_keys(b"\x1b[A\x1b[B\r") == ["up", "down", "enter"]
    assert parse_keys(b"\x1b") == ["esc"]


def test_tty_frame_uses_carriage_return_line_feeds() -> None:
    assert _terminal_frame("first\nsecond\n") == "first\r\nsecond\r\n"


class _Clock:
    """Deterministic monotonic clock for key-action tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        """Return injected monotonic time in seconds."""
        return self.now


def _live_palette():
    return palette_from_omarchy(
        {"background": "#111111", "foreground": "#eeeeee", "accent": "#336699"},
        "live",
    )


def _session(
    *,
    name: str = "tungsten",
    palette=None,
    theme_id: str | None = None,
    motion: str = "full",
    duration: float = 96.0,
    programs: tuple[str, ...] = ("garden", "aperture"),
    position: float = 0.0,
    playing: bool = False,
    field_time: float | None = None,
):
    show = Show("Reel", "study", duration, 0, programs)
    clock = _Clock()
    head = Playhead(duration, position_s=position, playing=playing, _clock=clock)
    chosen = palette if palette is not None else builtin_palette(name)
    session = Session(
        show,
        head,
        chosen,
        theme_id or name,
        builtin_palettes(),
        "none",
        motion,
        field_time_s=position if field_time is None else field_time,
        motion_anchor_s=position,
    )
    return session, head, clock


def test_quit_leaves_help_and_gallery_while_esc_returns() -> None:
    """Q and Ctrl-C exit overlays; Esc returns to the stage."""
    session, _, _ = _session()
    session.mode = "help"
    assert _handle(session, "q") is False
    session.mode = "gallery"
    assert parse_keys(b"\x03") == ["quit"]
    assert _handle(session, "quit") is False
    session.mode = "help"
    assert _handle(session, "esc") is True
    assert session.mode == "play"
    session.mode = "gallery"
    assert _handle(session, "esc") is True
    assert session.mode == "play"
    session.mode = "help"
    assert _handle(session, "backspace") is True
    assert session.mode == "play"
    assert _handle(session, "q") is False


def test_gallery_index_follows_builtin_and_live_palette() -> None:
    """The first theme key continues from the active built-in, or starts at the first."""
    themes = builtin_palettes()
    session, _, _ = _session(name="phosphor")
    phosphor = next(i for i, theme in enumerate(themes) if theme.name == "phosphor")
    assert session.gallery_index == phosphor
    assert _handle(session, "t") is True
    assert session.palette.name == "broadcast"
    live, _, _ = _session(palette=_live_palette(), theme_id="omarchy")
    assert live.gallery_index == -1
    assert _handle(live, "t") is True
    assert live.palette.name == "tungsten"
    assert live.gallery_index == 0
    assert _handle(live, "9") is True
    assert live.palette.name == "void"


def test_gallery_enter_without_selection_keeps_live_palette() -> None:
    """Enter must not wrap a missing selection onto the last built-in."""
    live = _live_palette()
    session, _, _ = _session(palette=live, theme_id="omarchy")
    session.mode = "gallery"
    assert session.gallery_index == -1
    assert _handle(session, "enter") is True
    assert session.palette.name == live.name
    assert session.theme_id == "omarchy"
    assert session.mode == "play"
    assert session.palette.name != builtin_palettes()[-1].name


def test_gallery_navigation_selects_from_no_builtin() -> None:
    """Down from no selection starts at the first card; up starts at the last."""
    session, _, _ = _session(palette=_live_palette(), theme_id="omarchy")
    session.mode = "gallery"
    assert _handle(session, "down") is True
    assert session.gallery_index == 0
    assert _handle(session, "enter") is True
    assert session.palette.name == "tungsten"
    assert session.mode == "play"
    session, _, _ = _session(palette=_live_palette(), theme_id="omarchy")
    session.mode = "gallery"
    assert _handle(session, "k") is True
    assert session.gallery_index == len(session.themes) - 1
    assert _handle(session, "enter") is True
    assert session.palette.name == "void"
    session.mode = "gallery"
    session.gallery_index = len(session.themes) - 1
    assert _handle(session, "j") is True
    assert session.gallery_index == 0


def test_omarchy_sync_clears_builtin_selection(monkeypatch) -> None:
    """After a live sync, the next theme key starts at the first built-in."""
    live = _live_palette()
    theme = OmarchyTheme(live, "live", Path("colors.toml"), "1")
    monkeypatch.setattr("agentic_av.tty.load_omarchy", lambda: theme)
    session, _, _ = _session(name="carbon")
    carbon = next(i for i, item in enumerate(session.themes) if item.name == "carbon")
    assert session.gallery_index == carbon
    assert _handle(session, "o") is True
    assert session.gallery_index == -1
    assert session.theme_id == "omarchy"
    assert session.palette.name == live.name
    assert _handle(session, "t") is True
    assert session.palette.name == "tungsten"


def test_still_space_keeps_held_picture_while_seeks_update_it() -> None:
    """Pause and resume must not replace a still picture with the playhead."""
    session, head, clock = _session(
        motion="still",
        position=1.0,
        playing=True,
        programs=("garden",),
    )
    clock.now = 6.0
    assert abs(head.position - 7.0) < 1e-6
    assert _handle(session, " ") is True
    assert head.playing is False
    assert abs(session.field_time_s - 1.0) < 1e-6
    assert _handle(session, " ") is True
    assert head.playing is True
    assert abs(session.field_time_s - 1.0) < 1e-6
    assert _handle(session, "right") is True
    assert abs(session.field_time_s - head.position) < 1e-6
    assert abs(head.position - 12.0) < 1e-6
    assert _handle(session, "k") is True
    assert head.position == 0
    assert abs(session.field_time_s - head.position) < 1e-6


def test_short_show_seeks_keep_direction() -> None:
    """Right and left keep their direction when the show is ten seconds or shorter."""
    session, head, _ = _session(duration=10.0, position=6.0, programs=("garden",))
    assert _handle(session, "right") is True
    assert abs(head.position - 1.0) < 1e-6
    assert abs(session.field_time_s - 11.0) < 1e-6
    session, head, _ = _session(duration=10.0, position=1.0, programs=("garden",))
    assert _handle(session, "left") is True
    assert abs(head.position - 6.0) < 1e-6
    assert abs(session.field_time_s - (1.0 - 5.0)) < 1e-6
    session, head, _ = _session(duration=96.0, position=10.0)
    assert _handle(session, "right") is True
    assert abs(session.field_time_s - 15.0) < 1e-6
    assert _handle(session, "left") is True
    assert abs(session.field_time_s - 10.0) < 1e-6


def test_one_program_chapter_keys_follow_direction() -> None:
    """Next moves forward and previous backward even when both land on the only start."""
    session, head, _ = _session(duration=8.0, position=5.0, programs=("garden",))
    assert _handle(session, "k") is True
    assert head.position == 0
    assert abs(session.field_time_s - 8.0) < 1e-6
    session, head, _ = _session(duration=8.0, position=5.0, programs=("garden",))
    assert _handle(session, "j") is True
    assert head.position == 0
    assert abs(session.field_time_s - 0.0) < 1e-6
    session, head, _ = _session(duration=8.0, position=1.0, programs=("garden", "aperture"))
    assert _handle(session, "j") is True
    assert abs(head.position - 4.0) < 1e-6
    assert session.field_time_s < 1.0

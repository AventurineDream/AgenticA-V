"""Fixed-grid painting, motion programs, and monotonic playhead contracts."""

from agentic_av.colorutil import relative_luminance
from agentic_av.field import PROGRAM_LABELS, sample
from agentic_av.paint import FrameRequest, _shade, compose, render_ansi, render_plain
from agentic_av.palette import builtin_palette, builtin_palettes, palette_from_omarchy
from agentic_av.session import Session
from agentic_av.show import Show, ShowError, demo_show, load_show
from agentic_av.transport import Playhead
from agentic_av.tty import _terminal_frame


class Clock:
    """Deterministic monotonic clock for transport tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        """Return injected monotonic time in seconds."""
        return self.now


def test_show_program_selection_and_validation(tmp_path) -> None:
    show = demo_show()
    assert show.program_at(0) == (0, "garden")
    assert show.program_at(24) == (1, "aperture")
    assert show.program_at(show.duration) == (0, "garden")
    path = tmp_path / "bad.toml"
    path.write_text('title="x"\nduration=0\nprograms=["gone"]', encoding="utf-8")
    try:
        load_show(path)
    except ShowError as error:
        assert "positive" in str(error)
    else:
        raise AssertionError("invalid show was accepted")


def test_playhead_pause_seek_rate_and_loop() -> None:
    clock = Clock()
    head = Playhead(10, _clock=clock)
    clock.now = 3
    assert head.position == 3
    head.toggle()
    clock.now = 20
    assert head.position == 3
    head.seek(9)
    assert head.position == 2
    head.toggle()
    clock.now = 22
    assert head.position == 4
    head.set_rate(2)
    clock.now = 23
    assert head.position == 6
    head.seek_to(99)
    assert head.position == 0


def test_each_scene_has_spatial_structure_and_reduced_detail() -> None:
    for program in PROGRAM_LABELS:
        points = [sample(program, x / 19, y / 8, 2.5) for x in range(20) for y in range(9)]
        assert len({round(lum, 2) for lum, _ in points}) > 10
        assert len({round(hue, 2) for _, hue in points}) > 10
    assert sample("garden", 0.4, 0.6, 4, shimmer=False) != sample("garden", 0.4, 0.6, 4)


def test_stage_grade_respects_light_and_dark_palette_ends() -> None:
    """Light themes resolve to ink-and-paper contrast instead of gray haze."""
    for palette in (builtin_palette("newsprint"), builtin_palette("phosphor")):
        shadow = relative_luminance(_shade(palette, 0.02, 0.3))
        highlight = relative_luminance(_shade(palette, 0.98, 0.3))
        assert shadow < highlight


def test_frame_dimensions_at_small_and_standard_sizes() -> None:
    show = demo_show()
    for width, height in ((40, 12), (80, 24), (100, 40), (1, 1)):
        request = FrameRequest(show, builtin_palette("phosphor"), builtin_palettes(), width, height)
        rows = compose(request)
        assert len(rows) == height
        assert all(len(row) == width for row in rows)


def test_mono_preview_has_no_ansi_and_preserves_dimensions() -> None:
    show = demo_show()
    request = FrameRequest(
        show, builtin_palette("newsprint"), builtin_palettes(), 64, 20, color_mode="none"
    )
    rows = compose(request)
    output = render_ansi(rows, "none")
    assert "\x1b[" not in output
    assert len(output.splitlines()) == 20
    assert all(len(line) == 64 for line in output.splitlines())
    assert any(char in output for char in "░▒▓█")


def test_truecolor_and_256_color_preview_use_palette_accent() -> None:
    show = demo_show()
    palette = builtin_palette("phosphor")
    request = FrameRequest(show, palette, builtin_palettes(), 72, 22)
    ansi = render_ansi(compose(request), "truecolor")
    assert "\x1b[38;2;134;245;172m" in ansi
    quantized = render_ansi(compose(request), "256")
    assert "\x1b[38;5;" in quantized


def test_gallery_shows_each_real_palette_art() -> None:
    show = demo_show()
    request = FrameRequest(
        show, builtin_palette("tungsten"), builtin_palettes(), 72, 40, mode="gallery"
    )
    plain = render_plain(compose(request))
    assert "TUNGSTEN" in plain
    assert "PHOSPHOR" in plain
    assert len(plain.splitlines()) == 40


def test_color_stage_paints_both_halves_of_each_cell() -> None:
    """Color cells carry an upper and lower sample, not a flat stage stripe."""
    show = demo_show()
    palette = builtin_palette("phosphor")
    request = FrameRequest(
        show,
        palette,
        builtin_palettes(),
        80,
        24,
        program="aperture",
        field_time_s=2.0,
    )
    picture = [cell for row in compose(request) for cell in row if cell.char == "▀"]
    assert len(picture) > 100
    assert any(cell.fg and cell.bg and cell.fg != cell.bg for cell in picture)
    assert any(cell.bg != palette.stage for cell in picture)


def test_standard_frame_keeps_the_key_legend() -> None:
    """The legend is reserved in the row budget, not sliced off a full frame."""
    show = demo_show()
    plain = render_plain(
        compose(FrameRequest(show, builtin_palette("void"), builtin_palettes(), 80, 24))
    )
    assert "play/pause" in plain
    assert len(plain.splitlines()) == 24
    assert all(len(line) == 80 for line in plain.splitlines())


def test_transport_marks_scene_boundaries() -> None:
    show = demo_show()
    plain = render_plain(
        compose(FrameRequest(show, builtin_palette("carbon"), builtin_palettes(), 80, 24))
    )
    assert "|" in plain


def test_gallery_cards_paint_each_theme_accent() -> None:
    """Cards use the theme's own accent, not only the surrounding chrome."""
    show = demo_show()
    request = FrameRequest(
        show,
        builtin_palette("tungsten"),
        builtin_palettes(),
        72,
        40,
        mode="gallery",
        field_time_s=2.0,
    )
    rows = compose(request)
    plain = render_plain(rows)
    ansi = render_ansi(rows, "truecolor")
    assert "TUNGSTEN" in plain
    assert "PHOSPHOR" in plain
    assert "VOID" in plain
    assert "\x1b[38;2;134;245;172m" in ansi
    assert len(plain.splitlines()) == 40


def test_scenes_keep_distinct_motifs() -> None:
    """Aperture is radial, scan has a sweep, and tide keeps a horizontal crest."""
    center = sample("aperture", 0.5, 0.5, 2.0)[0]
    edge = sample("aperture", 0.0, 0.5, 2.0)[0]
    assert center > edge + 0.4
    scan = [sample("scan", x / 39, 0.45, 2.0)[0] for x in range(40)]
    assert max(scan) > sum(scan) / len(scan) + 0.3
    bright = [max(range(16), key=lambda y: sample("tide", x / 7, y / 15, 2.0)[0]) for x in range(8)]
    assert max(bright) - min(bright) <= 8


def test_motion_changes_do_not_jump_the_picture() -> None:
    """Reduced motion slows from the current frame; leaving still does not skip."""
    clock = Clock()
    show = demo_show()
    head = Playhead(show.duration, _clock=clock)
    session = Session(show, head, builtin_palette("carbon"), "carbon", builtin_palettes(), "none")
    clock.now = 10
    assert abs(session.advance_visual_time() - 10) < 1e-6
    session.commit_motion("reduced")
    assert abs(session.advance_visual_time() - 10) < 1e-6
    clock.now = 15
    reduced = session.advance_visual_time()
    assert abs(reduced - (10 + 5 * 0.22)) < 1e-6
    session.commit_motion("still")
    clock.now = 30
    assert abs(session.advance_visual_time() - reduced) < 1e-6
    session.commit_motion("full")
    assert abs(session.advance_visual_time() - reduced) < 1e-6
    clock.now = 31
    assert abs(session.advance_visual_time() - (reduced + 1)) < 1e-6


def test_known_seek_scales_with_motion_and_ignores_wrap_heuristic() -> None:
    """A forward seek on a short show stays forward; reduced motion scales it."""
    show = Show("Short", "", 8.0, 0, ("garden",))
    head = Playhead(8.0, position_s=6.0, playing=False)
    session = Session(
        show,
        head,
        builtin_palette("tungsten"),
        "tungsten",
        builtin_palettes(),
        "none",
        field_time_s=6.0,
        motion_anchor_s=6.0,
    )
    session.seek_field(5)
    assert abs(head.position - 3.0) < 1e-6
    assert abs(session.field_time_s - 11.0) < 1e-6
    session.motion = "reduced"
    session.seek_field(5)
    assert abs(session.field_time_s - (11.0 + 5 * 0.22)) < 1e-6


def test_unseeked_loop_wrap_still_advances_field_time() -> None:
    """Playback across the loop boundary keeps moving the picture forward."""
    clock = Clock()
    show = Show("Loop", "", 10.0, 0, ("garden",))
    head = Playhead(10.0, position_s=9.0, playing=True, _clock=clock)
    session = Session(
        show,
        head,
        builtin_palette("tungsten"),
        "tungsten",
        builtin_palettes(),
        "none",
        field_time_s=9.0,
        motion_anchor_s=9.0,
    )
    clock.now = 2.0
    assert abs(head.position - 1.0) < 1e-6
    assert abs(session.advance_visual_time() - 11.0) < 1e-6


def test_unselected_gallery_does_not_mark_the_last_theme() -> None:
    """A live palette must not highlight the last built-in via index wrap."""
    live = palette_from_omarchy(
        {"background": "#111111", "foreground": "#eeeeee", "accent": "#336699"},
        "live",
    )
    show = demo_show()
    plain = render_plain(
        compose(
            FrameRequest(
                show,
                live,
                builtin_palettes(),
                72,
                40,
                mode="gallery",
                theme_index=-1,
                field_time_s=2.0,
            )
        )
    )
    assert "▌" not in plain
    assert "TUNGSTEN" in plain
    assert "VOID" in plain
    marked = render_plain(
        compose(
            FrameRequest(
                show,
                builtin_palette("void"),
                builtin_palettes(),
                72,
                40,
                mode="gallery",
                theme_index=8,
                field_time_s=2.0,
            )
        )
    )
    assert any("▌" in line and "VOID" in line for line in marked.splitlines())


def test_show_text_controls_cannot_reach_preview_or_raw_output() -> None:
    """ESC, CR, and TAB in title and detail stay out of cells and terminal frames."""
    show = Show("bad\x1b[2J\r\ttitle", "line\r\n\x1b[H\tdetail", 12.0, 0, ("garden",))
    rows = compose(
        FrameRequest(
            show,
            builtin_palette("tungsten"),
            builtin_palettes(),
            64,
            16,
            color_mode="none",
        )
    )
    chars = "".join(cell.char for row in rows for cell in row)
    assert "\x1b" not in chars
    assert "\r" not in chars
    assert "\t" not in chars
    plain = render_plain(rows).splitlines()
    assert "bad" in plain[1] and "title" in plain[1]
    assert "detail" in plain[2]
    assert "\x1b" not in plain[1] and "\r" not in plain[1] and "\t" not in plain[1]
    assert "\x1b" not in plain[2] and "\r" not in plain[2] and "\t" not in plain[2]
    ansi = render_ansi(rows, "truecolor")
    assert "\x1b[2J" not in ansi
    assert "\x1b[H" not in ansi
    assert "\r" not in ansi
    assert "\t" not in ansi
    raw = _terminal_frame(render_ansi(rows, "none"))
    assert "\x1b" not in raw
    assert "\t" not in raw
    assert "\r\n" in raw
    assert "\r" not in raw.replace("\r\n", "")

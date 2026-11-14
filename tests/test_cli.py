"""CLI environment detection, theme listing, and preview dispatch."""

from agentic_av.cli import color_mode, main


def test_color_mode_honors_no_color_and_terminal_capabilities() -> None:
    assert (
        color_mode({"TERM": "xterm-256color", "COLORTERM": "truecolor"}, stdout_tty=True)
        == "truecolor"
    )
    assert color_mode({"TERM": "xterm-256color"}, stdout_tty=True) == "256"
    assert color_mode({"TERM": "xterm", "NO_COLOR": ""}, stdout_tty=True) == "none"
    assert color_mode({"TERM": "dumb"}, stdout_tty=True) == "none"
    assert color_mode({"TERM": "xterm-256color"}, stdout_tty=False) == "none"
    assert color_mode({"TERM": "xterm"}, stdout_tty=True) == "none"
    assert color_mode({"TERM": "linux"}, stdout_tty=True) == "none"
    assert color_mode({}, stdout_tty=True) == "none"


def test_theme_list_and_plain_preview(capsys) -> None:
    assert main(["themes", "--theme", "phosphor", "--no-color"]) == 0
    listed = capsys.readouterr().out
    assert "PHOSPHOR" in listed
    assert "omarchy" in listed
    assert (
        main(["preview", "--theme", "void", "--no-color", "--width", "40", "--height", "12"]) == 0
    )
    frame = capsys.readouterr().out
    assert "AAV" in frame
    assert "\x1b[" not in frame
    assert len(frame.splitlines()) == 12


def test_unknown_theme_returns_actionable_error(capsys) -> None:
    assert main(["preview", "--theme", "made-up", "--no-color"]) == 2
    assert "unknown theme" in capsys.readouterr().err


def test_gallery_command_prints_each_theme_stage(capsys) -> None:
    """`aav gallery` is a contact sheet of stages, not nine copies of the atlas."""
    assert (
        main(["gallery", "--theme", "tungsten", "--no-color", "--width", "48", "--height", "12"])
        == 0
    )
    frame = capsys.readouterr().out
    for name in (
        "TUNGSTEN",
        "PHOSPHOR",
        "BROADCAST",
        "NEWSPRINT",
        "SIGNAL",
        "GLACIER",
        "CARBON",
        "MARIGOLD",
        "VOID",
    ):
        assert name in frame
    assert "THEME ATLAS" not in frame
    assert frame.count("Signal Garden") >= 9
    assert any(char in frame for char in "░▒▓█")
    assert "\x1b[" not in frame
    assert len(frame.splitlines()) == 108


def test_preview_strips_control_characters_from_show_text(tmp_path, capsys) -> None:
    """Preview output must not honor ESC, CR, or TAB from a show file."""
    path = tmp_path / "show.toml"
    path.write_text(
        'title = "bad\\u001b[2Jtitle"\n'
        'detail = "has\\t\\r tab"\n'
        "duration = 12\n"
        'programs = ["garden"]\n',
        encoding="utf-8",
    )
    assert (
        main(["preview", "--show", str(path), "--no-color", "--width", "64", "--height", "12"]) == 0
    )
    frame = capsys.readouterr().out
    assert "\x1b" not in frame
    assert "\t" not in frame
    assert "\r" not in frame
    assert "bad" in frame and "title" in frame
    assert "has" in frame and "tab" in frame

"""Visible terminal placement when show text is not one column wide."""

import pyte

from agentic_av.paint import FrameRequest, compose, render_ansi
from agentic_av.palette import builtin_palette, builtin_palettes
from agentic_av.show import Show
from agentic_av.tty import _terminal_frame

WIDTH = 80
HEIGHT = 24


def test_wide_and_combining_show_text_keeps_eighty_columns() -> None:
    """A VT must keep title and detail on their rows when text is not one column.

    The bytes fed here are the raw-mode frame, not a reconstruction of the
    cell grid. Wide CJK, fullwidth, emoji, combining marks, and controls are
    in the show text; the assertions are what the emulator displays.
    """
    title = "Cue中😀\u0301End\x1b[2J\tX"
    detail = "cafe\u0301\uff21文tail\rHIDE"
    show = Show(title, detail, 12.0, 0, ("garden",))
    rows = compose(
        FrameRequest(
            show,
            builtin_palette("tungsten"),
            builtin_palettes(),
            WIDTH,
            HEIGHT,
            color_mode="truecolor",
        )
    )
    frame = _terminal_frame(render_ansi(rows, "truecolor"))
    screen = pyte.Screen(WIDTH, HEIGHT)
    pyte.Stream(screen).feed("\x1b[H" + frame + "\x1b[J")
    display = screen.display

    assert len(display) == HEIGHT
    assert all(len(line) == WIDTH for line in display)
    cells = [[screen.buffer[row][column].data for column in range(WIDTH)] for row in range(HEIGHT)]
    assert all(cell != "" for row in cells for cell in row)
    assert all("\x1b" not in line and "\r" not in line and "\t" not in line for line in display)

    assert cells[0][0:3] == ["A", "A", "V"]
    assert "TUNGSTEN" in display[0]
    assert "·" in display[0]
    assert "playing" in display[0]

    title_cells = cells[1]
    assert title_cells[0:3] == ["C", "u", "e"]
    assert title_cells[5:8] == ["E", "n", "d"]
    assert title_cells[9:12] == ["[", "2", "J"]
    assert title_cells[13] == "X"
    assert title_cells[3] == title_cells[4]
    assert len(title_cells[3]) == 1
    assert title_cells[3] not in {" ", "中", "😀"}
    assert "中" not in display[1]
    assert "😀" not in display[1]
    assert "\u0301" not in display[1]
    assert title_cells[63:] == list("01  Signal Garden")

    detail_cells = cells[2]
    assert detail_cells[0:4] == ["c", "a", "f", "e"]
    assert detail_cells[6:10] == ["t", "a", "i", "l"]
    assert detail_cells[11:15] == ["H", "I", "D", "E"]
    assert detail_cells[4] == detail_cells[5] == title_cells[3]
    assert "文" not in display[2]
    assert "\uff21" not in display[2]
    assert "é" not in display[2]
    assert "\u0301" not in display[2]
    assert "velvet" in display[2]
    assert "·" in display[2]

    assert cells[3][0] == "╭"
    assert cells[3][WIDTH - 1] == "╮"
    assert "▶" in display[22]
    assert "←→" in display[23]

"""Parse emitted terminal bytes to verify glyphs, colors, diffing, and SGR state."""

import re

import numpy as np
import pytest

from clangor_visualis_machina.colorutil import to_xterm256
from clangor_visualis_machina.viz.encode import FrameEncoder, _quantize, displayed_cells
from clangor_visualis_machina.viz.glyphs import TIERS, Cells, fit
from clangor_visualis_machina.viz.png import rasterize


def _parse(data):
    text = data.decode("utf-8")
    grid = {}
    row = col = 1
    fg = bg = None
    offset = 0
    while offset < len(text):
        if text[offset] == "\x1b":
            match = re.match(r"\x1b\[([0-9;]*)([Hm])", text[offset:])
            assert match, repr(text[offset : offset + 30])
            params = [int(p) for p in match[1].split(";")]
            if match[2] == "H":
                row, col = params
            elif params == [0]:
                fg = bg = None
            else:
                assert params[0] in (38, 48)
                assert params[1] in (2, 5)
                value = tuple(params[2:]) if params[1] == 2 else params[2]
                if params[0] == 38:
                    fg = value
                else:
                    bg = value
            offset += match.end()
        else:
            grid[row, col] = (text[offset], fg, bg)
            col += 1
            offset += 1
    return grid


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("mode", ["truecolor", "256", "none"])
def test_round_trip_all_cells_and_modes(tier, mode):
    spec = TIERS[tier]
    rng = np.random.default_rng(42)
    cells = fit(
        rng.random((3 * spec.sub_h, 7 * spec.sub_w, 3), dtype=np.float32), tier, mono=mode == "none"
    )
    # Include spaces and a repeated foreground separated by a space: the fg
    # register must survive an omitted space foreground, not compare adjacent RGB.
    cells.glyph[0, :3] = (1, 0, 1)
    cells.fg[0, 0] = cells.fg[0, 2] = (3, 89, 201)
    encoder = FrameEncoder(mode)
    data = encoder.encode(cells, top=4)
    parsed = _parse(data)
    if mode == "none":
        assert b"m" not in data and b"\x1b[0m" not in data
    foreground = _quantize(cells.fg) if mode == "256" else cells.fg
    background = _quantize(cells.bg) if mode == "256" else cells.bg
    for row in range(3):
        for col in range(7):
            char, fg, bg = parsed[row + 4, col + 1]
            assert char == spec.glyphs[cells.glyph[row, col]]
            if mode != "none":
                assert bg == (
                    int(background[row, col, 0]) if mode == "256" else tuple(background[row, col])
                )
                if char != " ":
                    assert fg == (
                        int(foreground[row, col, 0])
                        if mode == "256"
                        else tuple(foreground[row, col])
                    )
            else:
                assert fg is bg is None
    assert encoder.encode(cells, top=4) == b""
    assert len(_parse(encoder.encode(cells, top=5))) == 21
    encoder.invalidate()
    assert len(_parse(encoder.encode(cells, top=4))) == 21


def test_row_diff_and_mutable_input():
    cells = fit(np.zeros((8, 8, 3), dtype=np.float32), "half")
    encoder = FrameEncoder("truecolor")
    encoder.encode(cells)
    cells.bg[1, 2] = 100
    result = encoder.encode(cells)
    assert set(row for row, _ in _parse(result)) == {2}
    assert b"\x1b[2J" not in result


def test_xterm_zero_dither_matches_scalar_reference():
    rng = np.random.default_rng(12)
    colors = np.concatenate(
        (
            rng.integers(0, 256, (1000, 3), dtype=np.uint8),
            # Dark muted colors exercise the same-hue cube substitution.
            rng.integers(0, 120, (1000, 3), dtype=np.uint8),
            np.repeat(np.arange(256, dtype=np.uint8)[:, None], 3, axis=1),
        )
    )
    expected = [to_xterm256(f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}") for c in colors]
    np.testing.assert_array_equal(_quantize(colors, dither=False)[:, 0], expected)


def test_dither_keeps_a_flat_muted_field_on_one_cube_color():
    """The dithered 256 path does not speckle a flat violet with grays or blues."""
    field = np.empty((8, 8, 3), dtype=np.uint8)
    field[:] = (43, 27, 55)
    assert set(_quantize(field).ravel().tolist()) == {54}


def test_sgr_runs_and_space_foreground():
    glyph = np.array([[0, 1, 0, 1]], dtype=np.uint16)
    color = np.full((1, 4, 3), 100, dtype=np.uint8)
    cells = Cells("half", False, glyph, color, color.copy())
    data = FrameEncoder("truecolor").encode(cells)
    assert data.count(b"38;2") == 1
    assert data.count(b"48;2") == 1
    assert data.endswith(b"\x1b[0m")


def test_bad_mode():
    with pytest.raises(ValueError):
        FrameEncoder("pink")


@pytest.mark.parametrize("mode", ["truecolor", "256", "none"])
def test_diff_invalidation_resize_and_position(mode):
    cells = fit(np.full((8, 6, 3), 0.1, dtype=np.float32), "octant", mono=mode == "none")
    encoder = FrameEncoder(mode)
    first = encoder.encode(cells)
    assert first
    assert encoder.encode(cells) == b""
    encoder.invalidate()
    assert encoder.encode(cells) == first
    moved = encoder.encode(cells, top=5)
    assert set(row for row, _col in _parse(moved)) == {5, 6}
    cells.glyph[1, 0] = 1 if cells.glyph[1, 0] != 1 else 2
    diff = encoder.encode(cells, top=5)
    assert set(row for row, _col in _parse(diff)) == {6}
    smaller = fit(np.zeros((4, 2, 3), dtype=np.float32), "octant", mono=mode == "none")
    assert encoder.encode(smaller)


def test_mono_overrides_colored_encoder():
    cells = fit(np.full((4, 4, 3), 0.4, dtype=np.float32), "octant", mono=True)
    raw = FrameEncoder("truecolor").encode(cells)
    assert b"m" not in raw
    assert b"\x1b[0m" not in raw


def _xterm_rgb(index):
    assert 16 <= index <= 255
    if index >= 232:
        return (8 + (index - 232) * 10,) * 3
    levels = (0, 95, 135, 175, 215, 255)
    offset = index - 16
    return levels[offset // 36], levels[(offset // 6) % 6], levels[offset % 6]


def test_displayed_256_colors_match_encoded_stream_and_png():
    rng = np.random.default_rng(2027)
    glyphs = np.ones((8, 8), dtype=np.uint16)
    fg = rng.integers(0, 256, (8, 8, 3), dtype=np.uint8)
    bg = rng.integers(0, 256, (8, 8, 3), dtype=np.uint8)
    cells = Cells("half", False, glyphs, fg, bg)
    original_fg, original_bg = fg.copy(), bg.copy()
    preview = displayed_cells(cells, "256")
    stream = _parse(FrameEncoder("256").encode(cells))
    image = rasterize(preview, cell_px=(2, 4))
    assert preview.glyph is glyphs
    assert not preview.mono
    for row in range(8):
        for col in range(8):
            char, foreground, background = stream[row + 1, col + 1]
            assert char == "▀"
            expected_fg, expected_bg = _xterm_rgb(foreground), _xterm_rgb(background)
            np.testing.assert_array_equal(preview.fg[row, col], expected_fg)
            np.testing.assert_array_equal(preview.bg[row, col], expected_bg)
            np.testing.assert_array_equal(image[row * 4, col * 2], expected_fg)
            np.testing.assert_array_equal(image[row * 4 + 3, col * 2], expected_bg)
    np.testing.assert_array_equal(fg, original_fg)
    np.testing.assert_array_equal(bg, original_bg)


def test_displayed_256_retains_spatial_bayer_dither():
    glyphs = np.ones((4, 4), dtype=np.uint16)
    colors = np.full((4, 4, 3), 120, dtype=np.uint8)
    cells = Cells("half", False, glyphs, colors, colors.copy())
    preview = displayed_cells(cells, "256")
    assert len(np.unique(preview.fg.reshape(-1, 3), axis=0)) > 1
    quantized = _quantize(colors)[..., 0]
    expected = np.array(
        [_xterm_rgb(int(index)) for index in quantized.flat], dtype=np.uint8
    ).reshape(4, 4, 3)
    np.testing.assert_array_equal(preview.fg, expected)
    np.testing.assert_array_equal(preview.bg, expected)


def test_displayed_truecolor_identity_and_none_contrast():
    cells = Cells(
        "half",
        False,
        np.array([[1, 0]], dtype=np.uint16),
        np.full((1, 2, 3), 41, dtype=np.uint8),
        np.full((1, 2, 3), 42, dtype=np.uint8),
    )
    assert displayed_cells(cells, "truecolor") is cells
    preview = displayed_cells(cells, "none")
    assert preview.mono
    assert not cells.mono
    np.testing.assert_array_equal(preview.fg, 255)
    np.testing.assert_array_equal(preview.bg, 0)
    image = rasterize(preview, cell_px=(2, 4))
    np.testing.assert_array_equal(image[:2, :2], 255)
    np.testing.assert_array_equal(image[2:, :2], 0)
    np.testing.assert_array_equal(image[:, 2:], 0)
    np.testing.assert_array_equal(cells.fg, 41)
    np.testing.assert_array_equal(cells.bg, 42)


@pytest.mark.parametrize("mode", ["truecolor", "256", "none"])
def test_displayed_mono_input_stays_mono(mode):
    cells = fit(np.full((4, 4, 3), 0.4, dtype=np.float32), "octant", mono=True)
    preview = displayed_cells(cells, mode)
    assert preview.mono
    np.testing.assert_array_equal(rasterize(preview), rasterize(cells))


def test_displayed_invalid_mode():
    cells = fit(np.zeros((4, 2, 3), dtype=np.float32), "octant")
    with pytest.raises(ValueError, match="color mode"):
        displayed_cells(cells, "pink")

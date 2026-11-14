"""Palette roles, color math, and built-in visual treatments."""

from agentic_av.colorutil import contrast_ratio, mix, normalize_hex, parse_hex, to_xterm256
from agentic_av.palette import PaletteError, builtin_palette, builtin_palettes, palette_from_omarchy


def test_color_helpers_normalize_and_quantize() -> None:
    assert normalize_hex(" #AB12ef ") == "#ab12ef"
    assert normalize_hex("#abc") is None
    assert parse_hex("#badc0d") == (186, 220, 13)
    assert mix("#000000", "#ffffff", 0.5) == "#808080"
    assert to_xterm256("#000000") == 16
    assert to_xterm256("#ffffff") == 231


def test_xterm256_uses_real_cube_and_gray_levels() -> None:
    """Cube and gray indexes follow xterm's levels, not a uniform 0..255 scale."""
    assert to_xterm256("#5f0000") == 52
    assert to_xterm256("#eeeeee") == 255
    assert to_xterm256("#ffffff") == 231
    assert to_xterm256("#000000") == 16


def test_builtin_palettes_have_distinct_roles_and_readable_chrome() -> None:
    palettes = builtin_palettes()
    assert len(palettes) == 9
    assert len({palette.background for palette in palettes}) == len(palettes)
    assert all(contrast_ratio(p.foreground, p.background) >= 4.5 for p in palettes)
    assert builtin_palette("PHOSPHOR") == next(p for p in palettes if p.name == "phosphor")


def test_omarchy_requires_three_core_colors() -> None:
    try:
        palette_from_omarchy({"mode": "dark", "muted": "not-hex"}, "bad")
    except PaletteError as error:
        assert "background, foreground, and accent" in str(error)
    else:
        raise AssertionError("empty palette was accepted")

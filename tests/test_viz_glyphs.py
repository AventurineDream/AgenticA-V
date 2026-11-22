"""Cover mosaic tables, stable soft cells, dithering, and six-dimensional ASCII fit."""

import unicodedata

import numpy as np
import pytest

from clangor_visualis_machina.viz._ascii_shapes import SAMPLE_WEIGHTS, SHAPES
from clangor_visualis_machina.viz.glyphs import TIERS, fit


@pytest.mark.parametrize("name", TIERS)
def test_distinct_width_one_glyphs(name):
    glyphs = TIERS[name].glyphs
    assert len(glyphs) == len(set(glyphs))
    for glyph in glyphs:
        assert len(glyph) == 1
        assert not unicodedata.combining(glyph)
        if unicodedata.name(glyph, None) is not None:
            assert unicodedata.east_asian_width(glyph) not in ("W", "F")


@pytest.mark.parametrize(
    "tier,root,minimum", [("octant", "OCTANT", 16), ("sextant", "SEXTANT", 13)]
)
def test_named_mosaic_patterns(tier, root, minimum):
    if int(unicodedata.unidata_version.split(".")[0]) < minimum:
        pytest.skip("runtime Unicode database predates these symbols")
    seen = 0
    for pattern, char in enumerate(TIERS[tier].glyphs):
        name = unicodedata.name(char)
        if root + "-" in name:
            digits = name.split("-")[1]
            assert pattern == sum(1 << (int(digit) - 1) for digit in digits)
            seen += 1
    assert seen == (230 if tier == "octant" else 60)


def test_legacy_octant_equivalents():
    expected = {
        0: 32,
        255: 0x2588,
        1: 0x1CEA8,
        2: 0x1CEAB,
        64: 0x1CEA3,
        128: 0x1CEA0,
        3: 0x1FB82,
        63: 0x1FB85,
        192: 0x2582,
        252: 0x2586,
        15: 0x2580,
        240: 0x2584,
        85: 0x258C,
        170: 0x2590,
        5: 0x2598,
        10: 0x259D,
        80: 0x2596,
        160: 0x2597,
        165: 0x259A,
        90: 0x259E,
        95: 0x259B,
        175: 0x259C,
        245: 0x2599,
        250: 0x259F,
        20: 0x1FBE6,
        40: 0x1FBE7,
    }
    for pattern, code in expected.items():
        assert ord(TIERS["octant"].glyphs[pattern]) == code


@pytest.mark.parametrize("tier", ["quadrant", "half", "braille", "ascii"])
def test_other_tables_against_unicode(tier):
    for pattern, char in enumerate(TIERS[tier].glyphs):
        name = unicodedata.name(char)
        if tier == "ascii":
            assert ord(char) == pattern + 32
        elif tier == "braille":
            if pattern == 0:
                assert name == "SPACE"
            else:
                bits = (0, 3, 1, 4, 2, 5, 6, 7)
                dots = "".join(
                    str(dot + 1) for dot in sorted(bits[i] for i in range(8) if pattern & (1 << i))
                )
                assert name == "BRAILLE PATTERN DOTS-" + dots
        else:
            assert (
                name
                == {
                    " ": "SPACE",
                    "▀": "UPPER HALF BLOCK",
                    "▄": "LOWER HALF BLOCK",
                    "█": "FULL BLOCK",
                    "▘": "QUADRANT UPPER LEFT",
                    "▝": "QUADRANT UPPER RIGHT",
                    "▖": "QUADRANT LOWER LEFT",
                    "▗": "QUADRANT LOWER RIGHT",
                    "▌": "LEFT HALF BLOCK",
                    "▐": "RIGHT HALF BLOCK",
                    "▞": "QUADRANT UPPER RIGHT AND LOWER LEFT",
                    "▚": "QUADRANT UPPER LEFT AND LOWER RIGHT",
                    "▛": "QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER LEFT",
                    "▜": "QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER RIGHT",
                    "▙": "QUADRANT UPPER LEFT AND LOWER LEFT AND LOWER RIGHT",
                    "▟": "QUADRANT UPPER RIGHT AND LOWER LEFT AND LOWER RIGHT",
                }[char]
            )


@pytest.mark.parametrize("tier", [name for name in TIERS if name != "ascii"])
def test_every_binary_pattern(tier):
    spec = TIERS[tier]
    count = spec.sub_h * spec.sub_w
    patterns = np.arange(1 << count, dtype=np.uint16)
    bits = ((patterns[:, None] >> np.arange(count)) & 1).astype(np.float32)
    image = np.repeat(bits.reshape(-1, spec.sub_h, spec.sub_w, 1), 3, axis=-1)
    image = image.reshape(len(patterns) * spec.sub_h, spec.sub_w, 3)
    cells = fit(image, tier)
    expected = patterns.copy()
    expected[-1] = 0
    np.testing.assert_array_equal(cells.glyph[:, 0], expected)
    np.testing.assert_array_equal(cells.fg[1:-1], 255)
    np.testing.assert_array_equal(cells.bg[:-1], 0)
    np.testing.assert_array_equal(cells.bg[-1], 255)


@pytest.mark.parametrize("tier", ["octant", "sextant", "quadrant", "half"])
def test_soft_gradient_keeps_halves_and_no_shimmer(tier):
    spec = TIERS[tier]
    image = np.broadcast_to(
        np.linspace(0.2, 0.21, spec.sub_h, dtype=np.float32)[:, None, None],
        (spec.sub_h, spec.sub_w * 3, 3),
    ).copy()
    first, second = fit(image, tier), fit(image + 0.0001, tier)
    assert np.all(first.fg < first.bg)
    np.testing.assert_array_equal(first.glyph, second.glyph)
    assert np.all(first.glyph == (1 << (((spec.sub_h + 1) // 2) * spec.sub_w)) - 1)
    flat = fit(np.full_like(image, 0.2), tier)
    assert np.all(flat.glyph == 0)


@pytest.mark.parametrize("tier", TIERS)
def test_clips_and_preserves_input(tier):
    spec = TIERS[tier]
    image = np.full((spec.sub_h, spec.sub_w, 3), 2, dtype=np.float32)
    copy = image.copy()
    cells = fit(image, tier)
    np.testing.assert_array_equal(image, copy)
    assert cells.glyph.dtype == np.uint16
    assert cells.bg.dtype == np.uint8
    if tier != "braille":
        np.testing.assert_array_equal(cells.bg, 255)


def test_srgb_transfer_and_mono_determinism():
    from clangor_visualis_machina.viz.glyphs import _srgb

    values = np.array([0, 0.0031308, 0.01, 0.18, 0.5, 1], dtype=np.float32)
    expected = np.rint(
        255 * np.where(values <= 0.0031308, 12.92 * values, 1.055 * values ** (1 / 2.4) - 0.055)
    )
    np.testing.assert_allclose(_srgb(values), expected, atol=1)
    image = np.full((32, 16, 3), 0.18, dtype=np.float32)
    np.testing.assert_array_equal(
        fit(image, "octant", mono=True).glyph, fit(image, "octant", mono=True).glyph
    )
    assert len(np.unique(fit(image, "octant", mono=True).glyph)) > 1


def test_ascii_normalized_shape_vectors_and_orientation():
    shapes = np.asarray(SHAPES)
    assert shapes.shape == (95, 6)
    np.testing.assert_allclose(shapes.max(axis=0), 1, atol=1e-6)
    np.testing.assert_allclose(np.asarray(SAMPLE_WEIGHTS).sum(axis=0), 1, atol=1e-5)
    assert shapes[ord("L") - 32, 4] > shapes[ord("L") - 32, 1]
    image = np.zeros((3, 4, 3), dtype=np.float32)
    image[0, :2] = 1
    image[2, 2:] = 1
    cells = fit(image, "ascii")
    assert cells.glyph[0, 0] != cells.glyph[0, 1]


def test_bad_shape_rejected():
    with pytest.raises(ValueError, match="shape"):
        fit(np.zeros((3, 3, 3)), "octant")


def test_group_colors_average_in_linear_light():
    image = np.full((4, 2, 3), 0.02, dtype=np.float32)
    image[0, 0] = 0.4
    image[0, 1] = 0.8
    cells = fit(image, "octant")
    assert cells.glyph.item() == 3
    np.testing.assert_array_equal(cells.fg[0, 0], [203, 203, 203])
    np.testing.assert_array_equal(cells.bg[0, 0], [39, 39, 39])

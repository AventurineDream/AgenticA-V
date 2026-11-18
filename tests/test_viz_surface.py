"""Check isotropic surface geometry, coarse field sampling, and in-place composition."""

import numpy as np
import pytest

from agentic_av.viz import color
from agentic_av.viz.surface import Surface


@pytest.mark.parametrize("sub_w,sub_h", [(2, 4), (2, 3), (2, 2), (1, 2)])
def test_surface_pixel_centers_are_isotropic_and_roundtrip(sub_w, sub_h):
    surface = Surface(73, 29, sub_w, sub_h, cell_aspect=2.24)
    assert surface.rgb.shape == (29 * sub_h, 73 * sub_w, 3)
    assert surface.rgb.dtype == np.float32
    assert surface.half_w == 73 / (29 * 2.24)
    assert surface.pixel_area == surface.dx * surface.dy
    px, py = surface.px(surface.u, surface.v)
    np.testing.assert_allclose(px, np.broadcast_to(np.arange(surface.w), px.shape), atol=2e-5)
    np.testing.assert_allclose(
        py, np.broadcast_to(np.arange(surface.h)[:, None], py.shape), atol=2e-5
    )
    assert surface.u.dtype == surface.v.dtype == np.float32
    assert not surface.u.flags.writeable and not surface.v.flags.writeable
    assert surface.r is surface.r and surface.theta is surface.theta
    assert not surface.r.flags.writeable and not surface.theta.flags.writeable
    np.testing.assert_allclose(surface.r, np.hypot(surface.u, surface.v))


@pytest.mark.parametrize("args", [(0, 1, 2, 4), (1, 0, 2, 4), (1, 1, -1, 4), (1, 1, 2, 4, 0)])
def test_surface_rejects_invalid_geometry(args):
    with pytest.raises(ValueError):
        Surface(*args)


def test_coarse_coordinates_cached_and_upsample_preserves_range_and_shape():
    surface = Surface(19, 11, 2, 3)
    for factor in (1, 2, 4, 100):
        u, v = surface.coarse(factor)
        assert u is surface.coarse(factor)[0]
        assert u.shape == ((surface.h + factor - 1) // factor, (surface.w + factor - 1) // factor)
        assert not u.flags.writeable and not v.flags.writeable
        field = (u * 0.2 + v * 0.3 + 0.5).astype(np.float32)
        upsampled = surface.upsample(field)
        assert upsampled.shape == (surface.h, surface.w)
        assert upsampled.dtype == np.float32
        assert upsampled.min() >= field.min() - 1e-7
        assert upsampled.max() <= field.max() + 1e-7
        np.testing.assert_allclose(surface.upsample(np.full(u.shape, 0.37)), 0.37, atol=1e-7)
    u, v = surface.coarse(4)
    result = surface.upsample(u + 2 * v)
    np.testing.assert_allclose(
        result[4:-4, 4:-4], (surface.u + 2 * surface.v)[4:-4, 4:-4], atol=5e-7
    )
    with pytest.raises(ValueError):
        surface.coarse(0)
    with pytest.raises(ValueError):
        surface.upsample([])


def test_layers_are_owned_and_compositing_is_linear():
    surface = Surface(5, 3, 2, 4)
    layer = surface.layer()
    assert layer.dtype == np.float32
    layer.fill(0.5)
    assert not np.any(surface.layer())
    surface.fill([0.1, 0.2, 0.3])
    surface.add(layer, [0.2, 0.4, 0.6], gain=2)
    np.testing.assert_allclose(surface.rgb, np.broadcast_to([0.3, 0.6, 0.9], surface.rgb.shape))
    surface.screen(layer, [0.8, 0.4, 0.2])
    expected = 1 - (1 - np.array([0.3, 0.6, 0.9])) * (1 - np.array([0.4, 0.2, 0.1]))
    np.testing.assert_allclose(surface.rgb, np.broadcast_to(expected, surface.rgb.shape), atol=1e-7)
    surface.cover(0.25, [1, 0, 0])
    expected = expected * 0.75 + np.array([1, 0, 0]) * 0.25
    np.testing.assert_allclose(surface.rgb, np.broadcast_to(expected, surface.rgb.shape), atol=1e-7)
    surface.cover(2, "#ffffff")
    np.testing.assert_array_equal(surface.rgb, np.ones_like(surface.rgb))


def test_gradient_uses_scene_boundaries_and_oklab():
    surface = Surface(4, 4, 2, 4)
    surface.gradient("#000000", "#ffffff")
    t = (np.arange(surface.h) + 0.5) / surface.h
    np.testing.assert_allclose(surface.rgb[:, 0], color.mix("#000000", "#ffffff", t), atol=1e-6)
    surface.gradient("#000000", "#ffffff", mid="#ff0000", mid_at=0.25)
    assert np.all(np.isfinite(surface.rgb))
    with pytest.raises(ValueError):
        surface.gradient("#000000", "#ffffff", mid="#ff0000", mid_at=1)


def test_add_ramp_clips_coordinates_and_uses_nearest_entry():
    surface = Surface(2, 1, 2, 2)
    field = np.array([[-1, 0.25, 0.75, 2], [0, 0.25, 0.75, 1]], np.float32)
    table = color.ramp(["#000000", "#ffffff"], n=5)
    surface.add_ramp(field, table, gain=2)
    expected = table[np.rint(np.clip(field, 0, 1) * 4).astype(int)] * 2
    np.testing.assert_array_equal(surface.rgb, expected)

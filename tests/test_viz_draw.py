"""Check additive geometry, scene-space isotropy, seeded fields, and particle evolution."""

import numpy as np
import pytest

from clangor_visualis_machina.viz import draw
from clangor_visualis_machina.viz.surface import Surface


def test_points_conserve_weights_and_bilinear_centroid():
    surface = Surface(31, 17, 2, 4)
    rng = np.random.default_rng(9)
    x, y = rng.uniform(-0.5, 0.5, (2, 1000)).astype(np.float32)
    weight = rng.uniform(0, 2, len(x)).astype(np.float32)
    layer = surface.layer()
    draw.points(surface, layer, x, y, weight)
    np.testing.assert_allclose(layer.sum(), weight.sum(), rtol=1e-6)
    layer.fill(0)
    px, py = 20.25, 18.75
    draw.points(
        surface,
        layer,
        (px + 0.5) * surface.dx - surface.half_w,
        (py + 0.5) * surface.dy - 1,
        weight=2,
    )
    np.testing.assert_allclose(layer[18:20, 20:22], [[0.375, 0.125], [1.125, 0.375]], atol=4e-6)


def test_points_discard_offscreen_and_support_noncontiguous_layers():
    surface = Surface(3, 2, 2, 4)
    backing = np.zeros((surface.h, surface.w * 2), np.float32)
    layer = backing[:, ::2]
    draw.points(surface, layer, [0, 100, np.nan], [0, 0, 0], [2, 3, 4])
    np.testing.assert_allclose(layer.sum(), 2)
    assert not np.any(backing[:, 1::2])
    draw.points(surface, layer, -surface.half_w, -1, weight=4)
    np.testing.assert_allclose(layer.sum(), 3)


@pytest.mark.parametrize("sub_w,sub_h", [(2, 4), (2, 3), (2, 2), (1, 2)])
def test_circle_extents_match_physical_cell_aspect(sub_w, sub_h):
    surface = Surface(100, 50, sub_w, sub_h, cell_aspect=2.24)
    layer = draw.disc(surface, 0, 0, 0.45, soft=0)
    ys, xs = np.nonzero(layer)
    width = (xs.max() - xs.min() + 1) * surface.dx
    height = (ys.max() - ys.min() + 1) * surface.dy
    assert abs(width - height) <= 2 * max(surface.dx, surface.dy)
    np.testing.assert_allclose(
        (xs.max() - xs.min() + 1) / sub_w / ((ys.max() - ys.min() + 1) / sub_h),
        2.24,
        atol=0.17,
    )


def test_lines_energy_and_brightness_per_subpixel_length_at_two_grids():
    brightness = []
    for sub_w, sub_h in ((2, 4), (1, 2)):
        surface = Surface(90, 40, sub_w, sub_h)
        x = np.array([[-0.7, 0, 0.7]], np.float32)
        y = np.array([[0, 0, 0]], np.float32)
        layer = surface.layer()
        draw.lines(surface, layer, x, y, weight=np.array([0.6]))
        length = 1.4 / surface.dx
        np.testing.assert_allclose(layer.sum(), length * 0.6, rtol=2e-6)
        brightness.append(layer.sum() / length)
    np.testing.assert_allclose(brightness, [0.6, 0.6], atol=1e-6)


def test_polyline_vertex_weights_closed_and_segments_agree():
    surface = Surface(40, 25, 2, 4)
    x, y = np.array([[-0.5, 0.5, 0]]), np.array([[-0.2, -0.2, 0.5]])
    weights = np.array([[0.2, 0.6, 1.0]])
    layer = surface.layer()
    draw.lines(surface, layer, x, y, weights, closed=True)
    expected = surface.layer()
    for i in range(3):
        j = (i + 1) % 3
        draw.segments(
            surface,
            expected,
            x[0, i],
            y[0, i],
            x[0, j],
            y[0, j],
            (weights[0, i] + weights[0, j]) / 2,
        )
    np.testing.assert_allclose(layer.sum(), expected.sum(), rtol=1e-6)
    empty = surface.layer()
    draw.lines(surface, empty, [0], [0])
    draw.segments(surface, empty, [0, np.nan], 0, [0, 1], 0)
    assert not np.any(empty)


def test_strokes_clip_huge_geometry_without_resampling_the_invisible_part():
    surface = Surface(20, 10, 2, 4)
    layer = surface.layer()
    draw.segments(surface, layer, [-1e4, 1e4], [0, 0], [1e4, 2e4], [0, 0])
    assert np.all(np.isfinite(layer))
    np.testing.assert_allclose(layer.sum(), surface.w, rtol=0.01)


def test_soft_shapes_have_bounded_physical_coverage():
    surface = Surface(40, 20, 2, 4)
    for layer in (
        draw.disc(surface, 0, 0, 0.5),
        draw.ring(surface, 0, 0, 0.5, 0.1),
        draw.ring(surface, 0, 0, 0.5, 0.1, squash=0.4, angle=0.7),
    ):
        assert layer.dtype == np.float32
        assert 0 <= layer.min() <= layer.max() <= 1
        assert np.any((layer > 0) & (layer < 1))
    with pytest.raises(ValueError):
        draw.ring(surface, 0, 0, 1, 0.1, squash=0)


def test_noise_is_seeded_baked_and_seamlessly_periodic():
    noise = draw.Noise(17)
    u, v = np.meshgrid(
        np.linspace(-0.7, 0.7, 41, dtype=np.float32), np.linspace(-0.4, 0.4, 19, dtype=np.float32)
    )
    result = noise.fbm(u, v)
    assert result.dtype == np.float32
    assert 0 <= result.min() <= result.max() <= 1
    np.testing.assert_array_equal(result, draw.Noise(17).fbm(u, v))
    assert not np.array_equal(result, draw.Noise(18).fbm(u, v))
    np.testing.assert_allclose(result, noise.fbm(u + 1, v - 1), atol=2e-6)
    np.testing.assert_allclose(noise.fbm(0, v), noise.fbm(1, v), atol=1e-7)
    noise.fbm(u, v, octaves=3, lacunarity=1.7, gain=0.3)
    assert len(noise._tiles) == 2
    assert noise._tile(4, 2.0, 0.5) is noise._tile(4, 2.0, 0.5)
    np.testing.assert_allclose(noise.fbm(-1e-5, v), noise.fbm(1e-5, v), atol=5e-4)
    warped = noise.warped(u, v)
    assert warped.shape == result.shape and np.all(np.isfinite(warped))


def test_flow_deterministic_and_divergence_free_inside_texture_patch():
    flow = draw.Flow(19)
    x, y, t = np.array([0.132], np.float32), np.array([0.256], np.float32), 0.4
    vx, vy = flow.at(x, y, t)
    np.testing.assert_array_equal(vx, draw.Flow(19).at(x, y, t)[0])
    epsilon = 1e-4
    dvx_dx = (flow.at(x + epsilon, y, t)[0] - flow.at(x - epsilon, y, t)[0]) / (2 * epsilon)
    dvy_dy = (flow.at(x, y + epsilon, t)[1] - flow.at(x, y - epsilon, t)[1]) / (2 * epsilon)
    np.testing.assert_allclose(dvx_dx + dvy_dy, 0, atol=2e-3)
    assert vx.dtype == vy.dtype == np.float32


def test_particles_drag_is_frame_rate_independent_and_columns_are_owned():
    a, b = draw.Particles(100, 7), draw.Particles(100, 7)
    for particles in (a, b):
        particles.policy = "none"
        particles.vx.fill(0.7)
        particles.vy.fill(-0.2)
    a.step(2, drag=0.4)
    for _ in range(120):
        b.step(2 / 120, drag=0.4)
    np.testing.assert_allclose(a.x, b.x, atol=3e-6)
    np.testing.assert_allclose(a.y, b.y, atol=3e-6)
    np.testing.assert_allclose(a.vx, b.vx, atol=3e-6)
    column = a.add_column("mass", 2)
    assert column is a.columns["mass"]
    assert column.dtype == np.float32 and column.shape == a.x.shape
    with pytest.raises(ValueError):
        a.add_column("x")


def test_particles_wrap_respawn_and_zero_dt():
    particles = draw.Particles(20, 11)
    before = particles.x.copy()
    particles.step(0, flow=draw.Flow(3))
    np.testing.assert_array_equal(particles.x, before)
    particles.vx.fill(100)
    particles.step(1)
    assert np.all((particles.x >= -1) & (particles.x < 1))
    particles.policy = "respawn"
    particles.x[:3] = 2
    particles.life[3:6] = 0.1
    particles.vx.fill(0)
    particles.step(0.2)
    assert np.all((particles.x >= -1) & (particles.x < 1))
    np.testing.assert_array_equal(particles.age[:6], 0)
    particles.step(0.1, flow=(np.full(20, 0.1), np.zeros(20)))
    assert np.all(np.isfinite(particles.x))


def test_easing_endpoints_monotonicity_and_periodic_pulse():
    x = np.linspace(-0.2, 1.2, 101)
    for easing in (draw.ease_out, draw.ease_in_out):
        values = easing(x)
        assert values[0] == 0 and values[-1] == 1
        assert np.all(np.diff(values) >= 0)
    np.testing.assert_array_equal(draw.smoothstep(1, 1, [0, 1, 2]), [0, 1, 1])
    phase = np.linspace(0, 1, 100, dtype=np.float32)
    np.testing.assert_allclose(draw.pulse(phase), draw.pulse(phase + 1), atol=3e-6)
    assert draw.pulse(0) == 1

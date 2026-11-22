"""Check feedback stability, physical-time decay, transparent warps, and finishing effects."""

import math

import numpy as np
import pytest

from clangor_visualis_machina.viz import fx
from clangor_visualis_machina.viz.draw import Flow
from clangor_visualis_machina.viz.surface import Surface


@pytest.mark.parametrize("dt", [1 / 20, 1 / 60])
def test_feedback_decay_matches_half_life_at_two_frame_rates(dt):
    surface = Surface(12, 6, 2, 4)
    feedback = fx.Feedback(surface)
    surface.fill([0.2, 0.5, 0.9])
    feedback.apply(surface, dt, half_life_s=0.5)
    for _ in range(round(1 / dt)):
        surface.fill([0, 0, 0])
        feedback.apply(surface, dt, half_life_s=0.5)
    np.testing.assert_allclose(surface.rgb[0, 0], np.array([0.2, 0.5, 0.9]) * 0.25, rtol=5e-6)


def test_feedback_zero_motion_has_no_creeping_blur_over_2000_steps():
    surface = Surface(20, 10, 2, 4)
    initial = np.random.default_rng(9).random(surface.rgb.shape, dtype=np.float32)
    surface.rgb[:] = initial
    feedback = fx.Feedback(surface)
    feedback.apply(surface, 1 / 30, half_life_s=math.inf)
    for _ in range(2000):
        surface.rgb.fill(0)
        feedback.apply(surface, 1 / 30, half_life_s=math.inf)
    np.testing.assert_array_equal(surface.rgb, initial)
    feedback.reset()
    surface.rgb.fill(0)
    feedback.apply(surface, 1 / 30, half_life_s=1)
    assert not np.any(surface.rgb)


def test_feedback_finite_decay_stays_stable_over_2000_steps():
    surface = Surface(7, 4, 2, 4)
    feedback = fx.Feedback(surface)
    surface.fill([0.25, 0.5, 0.75])
    feedback.apply(surface, 1 / 30, half_life_s=40)
    for _ in range(2000):
        surface.rgb.fill(0)
        feedback.apply(surface, 1 / 30, half_life_s=40)
    expected = np.array([0.25, 0.5, 0.75]) * 0.5 ** ((2000 / 30) / 40)
    np.testing.assert_allclose(surface.rgb[0, 0], expected, rtol=1e-4)


def test_feedback_add_is_continuous_emission_and_zero_dt_never_accumulates():
    outputs = []
    for fps in (20, 60):
        surface = Surface(6, 4, 2, 4)
        feedback = fx.Feedback(surface)
        for _ in range(fps * 2):
            surface.fill([0.1, 0.2, 0.3])
            feedback.apply(surface, 1 / fps, half_life_s=0.7, mode="add")
        outputs.append(surface.rgb.copy())
        before = feedback._history.copy()
        for _ in range(20):
            surface.fill([0.1, 0.2, 0.3])
            feedback.apply(surface, 0, half_life_s=0.7, mode="add")
        np.testing.assert_array_equal(feedback._history, before)
    np.testing.assert_allclose(outputs[0], outputs[1], rtol=5e-6)
    rate = math.log(2) / 0.7
    np.testing.assert_allclose(
        outputs[0][0, 0], np.array([0.1, 0.2, 0.3]) * -math.expm1(-2 * rate) / rate, rtol=5e-6
    )


def test_feedback_bilinear_translation_and_transparent_border():
    surface = Surface(10, 5, 2, 4)
    feedback = fx.Feedback(surface)
    surface.rgb[7, 7] = [1, 0.5, 0.25]
    feedback.apply(surface, 1, half_life_s=math.inf)
    surface.rgb.fill(0)
    feedback.apply(surface, 1, half_life_s=math.inf, drift=(surface.dx * 0.5, 0))
    np.testing.assert_allclose(surface.rgb[7, 7:9, 0], [0.5, 0.5], atol=2e-6)
    np.testing.assert_allclose(surface.rgb.sum(axis=(0, 1)), [1, 0.5, 0.25], atol=3e-6)
    feedback.reset()
    surface.rgb.fill(0)
    surface.rgb[:, 0] = 1
    feedback.apply(surface, 1, half_life_s=math.inf)
    surface.rgb.fill(0)
    feedback.apply(surface, 1, half_life_s=math.inf, drift=(-surface.dx * 2, 0))
    assert surface.rgb.max() < 1e-5


def test_feedback_flow_support_and_shape_reset():
    surface = Surface(12, 8, 2, 4)
    feedback = fx.Feedback(surface)
    surface.rgb[10, 10] = 1
    feedback.apply(surface, 1 / 30, half_life_s=1)
    surface.rgb.fill(0)
    feedback.apply(surface, 1 / 30, half_life_s=1, flow=Flow(11), zoom=0.02, rotate=0.03)
    assert np.all(np.isfinite(surface.rgb)) and surface.rgb.max() > 0
    smaller = Surface(6, 4, 1, 2)
    feedback.apply(smaller, 1 / 30, half_life_s=1)
    assert not np.any(smaller.rgb)
    assert feedback._history.shape == smaller.rgb.shape


@pytest.mark.parametrize("shape", [(9, 13), (9, 13, 3), (1, 2), (1, 1, 3)])
@pytest.mark.parametrize("radius", [0, 1, 2, 15])
def test_blur_preserves_constants_without_channel_crosstalk(shape, radius):
    source = np.full(shape, 0.37, np.float32)
    if len(shape) == 3:
        source[..., 1] = 0.8
    result = fx.blur(source, radius)
    assert result.shape == shape and result.dtype == np.float32
    np.testing.assert_allclose(result, source, rtol=1e-6)
    assert not np.shares_memory(result, source)


def test_blur_impulse_is_separable_and_does_not_mutate_input():
    source = np.zeros((11, 11), np.float32)
    source[5, 5] = 1
    result = fx.blur(source, 2)
    np.testing.assert_allclose(result[3:8, 3:8], 1 / 25)
    np.testing.assert_allclose(result.sum(), 1)
    assert source.sum() == 1
    with pytest.raises(ValueError):
        fx.blur(source, -1)


def test_bloom_threshold_and_reusable_buffers():
    surface = Surface(8, 4, 2, 4)
    surface.fill([0.2, 0.2, 0.2])
    before = surface.rgb.copy()
    fx.bloom(surface)
    np.testing.assert_array_equal(surface.rgb, before)
    surface.rgb[8, 8] = [2, 1, 0.3]
    fx.bloom(surface)
    assert surface.rgb[8, 9, 0] > 0.2
    assert surface.rgb[8, 9, 2] == np.float32(0.2)
    cached = surface._fx_buffers["bloom"]
    fx.bloom(surface)
    assert surface._fx_buffers["bloom"] is cached


def test_vignette_and_grain_are_deterministic_bounded_and_in_place():
    a, b = Surface(16, 8, 2, 4), Surface(16, 8, 2, 4)
    for surface in (a, b):
        surface.fill([0.5, 0.5, 0.5])
        fx.grain(surface, 0.1, 11)
    np.testing.assert_array_equal(a.rgb, b.rgb)
    assert a.rgb.min() >= 0.45 and a.rgb.max() <= 0.55
    np.testing.assert_allclose(a.rgb.mean(), 0.5, atol=1e-7)
    a.fill([1, 1, 1])
    fx.vignette(a, 0.5)
    assert a.rgb[0, 0, 0] < a.rgb[a.h // 2, a.w // 2, 0]


def test_tone_map_has_soft_monotonic_shoulder_and_finite_range():
    surface = Surface(5, 1, 1, 2)
    values = np.array([-1, 0, 0.5, 1, 100], np.float32)
    surface.rgb[:] = values[None, :, None]
    fx.tone_map(surface)
    np.testing.assert_allclose(surface.rgb[0, :, 0], [0, 0, 1 / 3, 0.5, 100 / 101])
    assert np.all(np.diff(surface.rgb[0, :, 0]) >= 0)
    surface.rgb[0, 0] = [np.nan, np.inf, -np.inf]
    fx.tone_map(surface)
    np.testing.assert_array_equal(surface.rgb[0, 0], [0, 1, 0])
    assert np.all(np.isfinite(surface.rgb))
    fx.tone_map(surface, exposure=0)
    assert not np.any(surface.rgb)


def test_zero_velocity_field_has_exact_identity_sampling_and_reuses_maps():
    surface = Surface(8, 4, 2, 4)
    feedback = fx.Feedback(surface)
    initial = np.random.default_rng(5).random(surface.rgb.shape, dtype=np.float32)
    surface.rgb[:] = initial
    feedback.apply(surface, 1 / 30, half_life_s=math.inf)
    maps = feedback._maps
    for _ in range(2000):
        surface.rgb.fill(0)
        feedback.apply(surface, 1 / 30, half_life_s=math.inf, flow=(0, 0))
    np.testing.assert_array_equal(surface.rgb, initial)
    assert feedback._maps is maps

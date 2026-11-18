"""Exercise displayed-raster flash evidence, opposing pairs, red risk, and timing edges."""

import numpy as np
import pytest

from agentic_av.viz.safety import FlashMeter


def _swap(phase: int, shape: tuple[int, int] = (36, 60)) -> np.ndarray:
    """Trade equally sized bright/dark halves without changing canvas mean."""
    image = np.zeros((*shape, 3), dtype=np.uint8)
    image[:, : shape[1] // 2] = 255 if phase % 2 else 0
    image[:, shape[1] // 2 :] = 0 if phase % 2 else 255
    return image


def _strobe(meter: FlashMeter, *, hz: float = 4.0, swap: bool = False) -> None:
    for tick in range(91):
        phase = int(tick * 2 * hz / 30)
        image = _swap(phase) if swap else np.full((36, 60, 3), 255 * (phase % 2), np.uint8)
        meter.push(tick / 30, image)


def _kinds(meter: FlashMeter) -> set[str]:
    return {item["kind"] for item in meter.report()["violations"]}


def test_empty_and_static_meters_pass_with_independent_reports() -> None:
    meter = FlashMeter()
    assert meter.report() == {
        "passed": True,
        "worst_flash_count": 0,
        "max_affected_fraction": 0.0,
        "max_mean_delta_100ms": 0.0,
        "violations": [],
    }
    for tick in range(31):
        meter.push(tick / 30, np.full((3, 5, 3), 70, dtype=np.uint8))
    assert meter.report()["passed"]
    assert meter.report()["worst_flash_count"] == 0
    report = meter.report()
    report["violations"].append({"kind": "invented"})
    assert not meter.report()["violations"]


def test_full_strobe_over_three_hz_fails_at_30fps() -> None:
    meter = FlashMeter()
    _strobe(meter)
    report = meter.report()
    assert not report["passed"]
    assert report["worst_flash_count"] >= 4
    assert report["max_affected_fraction"] == 1.0
    assert {"luminance", "mean_delta"} <= _kinds(meter)


def test_constant_mean_opposing_regions_do_not_cancel() -> None:
    meter = FlashMeter()
    _strobe(meter, swap=True)
    assert not meter.report()["passed"]
    assert meter.report()["max_mean_delta_100ms"] < 1e-6
    assert "luminance" in _kinds(meter)


def test_constant_mean_within_block_checkerboard_does_not_cancel() -> None:
    meter = FlashMeter()
    y, x = np.indices((37, 61))
    pattern = (x + y) % 2
    for tick in range(61):
        phase = int(tick * 8 / 30) % 2
        image = np.repeat(((pattern ^ phase) * 255).astype(np.uint8)[..., None], 3, axis=2)
        meter.push(tick / 30, image)
    assert not meter.report()["passed"]
    assert "luminance" in _kinds(meter)
    assert meter.report()["max_mean_delta_100ms"] < 0.001


@pytest.mark.parametrize("colors", [((128, 0, 0), (0, 0, 0)), ((60, 0, 0), (0, 0, 101))])
def test_red_intensity_and_modern_ucs_strobes_fail(colors: tuple[tuple[int, ...], ...]) -> None:
    # The second case has <20/320 red-excess change and nearly fixed luminance:
    # it can only be caught by retaining the modern UCS chromaticity evidence.
    meter = FlashMeter()
    for tick in range(91):
        color = colors[int(tick * 8 / 30) % 2]
        meter.push(tick / 30, np.full((30, 48, 3), color, dtype=np.uint8))
    assert not meter.report()["passed"]
    assert "red" in _kinds(meter)
    if colors[0][0] == 60:
        assert meter.report()["max_mean_delta_100ms"] < 0.001
        assert "luminance" not in _kinds(meter)


def test_fast_red_pattern_cannot_be_hidden_by_averaging() -> None:
    meter = FlashMeter()
    colors = np.array([[60, 0, 0], [0, 0, 101]], dtype=np.uint8)
    pattern = np.indices((36, 60)).sum(axis=0) % 2
    for tick in range(61):
        meter.push(tick / 30, colors[pattern ^ (int(tick * 8 / 30) % 2)])
    assert not meter.report()["passed"]
    assert "red" in _kinds(meter)
    assert meter.report()["max_mean_delta_100ms"] < 1e-6


def test_slow_fade_has_no_opposing_pairs() -> None:
    meter = FlashMeter()
    for tick in range(301):
        meter.push(tick / 30, np.full((12, 20, 3), round(tick * 255 / 300), np.uint8))
    report = meter.report()
    assert report["passed"]
    assert report["worst_flash_count"] == 0
    assert report["max_mean_delta_100ms"] < 0.04


def test_small_localized_twinkle_passes_despite_high_pixel_flash_count() -> None:
    meter = FlashMeter()
    image = np.zeros((36, 60, 3), dtype=np.uint8)
    for tick in range(91):
        image[-1, -1] = 255 * (int(tick * 10 / 30) % 2)
        meter.push(tick / 30, image)
    report = meter.report()
    assert report["passed"]
    assert report["worst_flash_count"] >= 4
    assert report["max_affected_fraction"] == pytest.approx(1 / (12 * 20))


def test_boundary_patch_at_exact_area_threshold_is_not_dropped() -> None:
    meter = FlashMeter()
    image = np.zeros((36, 60, 3), dtype=np.uint8)
    # The final 6x10 pixels are exactly 25% of a 12x20 regional surrogate.
    for tick in range(61):
        image[-6:, -10:] = 255 * (int(tick * 8 / 30) % 2)
        meter.push(tick / 30, image)
    assert not meter.report()["passed"]
    assert "luminance" in _kinds(meter)
    assert meter.report()["max_affected_fraction"] == pytest.approx(0.25)
    assert meter.report()["max_mean_delta_100ms"] < 0.04


def test_moving_bright_patches_accumulate_regional_flash_events() -> None:
    meter = FlashMeter()
    image = np.zeros((36, 60, 3), dtype=np.uint8)
    states = []
    for y0, x0 in ((0, 0), (0, 10), (6, 0), (6, 10)):
        bright = image.copy()
        bright[y0 : y0 + 6, x0 : x0 + 10] = 255
        states.extend((bright, image.copy()))
    frames = [frame for state in (image, *states) for frame in (state.copy(),) * 3]
    for tick, frame in enumerate(frames):
        meter.push(tick / 30, frame)
    report = meter.report()
    assert not report["passed"]
    assert report["worst_flash_count"] >= 4
    assert report["max_mean_delta_100ms"] < 0.04


@pytest.mark.parametrize("shape", [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_small_canvases_remain_meaningful(shape: tuple[int, int]) -> None:
    meter = FlashMeter()
    for tick in range(61):
        meter.push(tick / 30, np.full((*shape, 3), 255 * (int(tick * 8 / 30) % 2), np.uint8))
    assert "luminance" in _kinds(meter)
    assert meter.report()["max_affected_fraction"] == 1.0


def test_sliding_boundary_exactly_three_hz_passes() -> None:
    meter = FlashMeter()
    _strobe(meter, hz=3, swap=True)
    assert meter.report()["passed"]
    assert meter.report()["worst_flash_count"] == 3


def test_sliding_window_is_not_aligned_to_whole_seconds() -> None:
    meter = FlashMeter()
    # Four flash completions straddle the whole-second boundary but fit in 0.9s.
    times = [0.5, 0.55, 0.6, 0.85, 0.9, 1.15, 1.2, 1.45, 1.5]
    for phase, t_s in enumerate(times):
        meter.push(t_s, _swap(phase))
    assert not meter.report()["passed"]
    assert meter.report()["worst_flash_count"] == 4


def test_multiframe_steps_and_turning_point_jitter_count_once() -> None:
    meter = FlashMeter()
    # Each transition takes two frames; the tiny dip at each peak must not reset
    # pairing or make a second event out of one rising/falling excursion.
    samples = [0, 100, 254, 255, 254, 255, 160, 0]
    for tick, level in enumerate(samples * 4):
        image = np.full((12, 20, 3), level, dtype=np.uint8)
        image[:, 10:] = 255 - level
        meter.push(tick / 30, image)
    assert meter.report()["worst_flash_count"] <= 4
    assert "luminance" in _kinds(meter)


def test_high_luminance_small_contrast_is_not_a_general_flash() -> None:
    meter = FlashMeter()
    for tick in range(61):
        level = 232 if int(tick * 8 / 30) % 2 else 255
        meter.push(tick / 30, np.full((3, 3, 3), level, np.uint8))
    assert "luminance" not in _kinds(meter)
    assert meter.report()["worst_flash_count"] == 0


def test_mean_guard_checks_all_sample_pairs_within_100ms() -> None:
    meter = FlashMeter()
    meter.push(0.0, np.zeros((2, 2, 3), np.uint8))
    meter.push(0.05, np.full((2, 2, 3), 40, np.uint8))
    meter.push(0.1, np.full((2, 2, 3), 60, np.uint8))
    assert not meter.report()["passed"]
    assert meter.report()["worst_flash_count"] == 0
    assert "mean_delta" in _kinds(meter)
    # Just outside the boundary there is no qualifying observed pair.
    outside = FlashMeter()
    outside.push(0.0, np.zeros((1, 1, 3), np.uint8))
    outside.push(0.100001, np.full((1, 1, 3), 255, np.uint8))
    assert outside.report()["passed"]


def test_expired_flashes_do_not_accumulate_across_long_gaps() -> None:
    meter = FlashMeter()
    for phase, t_s in enumerate([0.0, 0.2, 0.4, 3.0, 3.2, 6.0, 6.2, 9.0, 9.2]):
        meter.push(t_s, _swap(phase))
    assert meter.report()["passed"]
    assert meter.report()["worst_flash_count"] == 1


def test_input_validation_rejects_without_corrupting_state() -> None:
    meter = FlashMeter()
    image = np.zeros((3, 4, 3), np.uint8)
    meter.push(0.0, image)
    for t_s in [0.0, -1.0, float("nan"), float("inf")]:
        with pytest.raises(ValueError, match="timestamps"):
            meter.push(t_s, image)
    with pytest.raises(ValueError, match="shape"):
        meter.push(1.0, np.zeros((4, 4, 3), np.uint8))
    with pytest.raises(ValueError, match="shape"):
        meter.push(1.0, np.zeros((3, 4), np.uint8))
    with pytest.raises(ValueError, match="shape"):
        meter.push(1.0, np.zeros((0, 4, 3), np.uint8))
    with pytest.raises(TypeError, match="uint8"):
        meter.push(1.0, image.astype(np.float32))
    meter.push(1.0, image)
    assert meter.report()["passed"]


def test_noncontiguous_inputs_are_not_retained_or_mutated() -> None:
    meter = FlashMeter()
    source = np.zeros((6, 8, 3), np.uint8)
    view = source[::2, ::2]
    meter.push(0.0, view)
    assert not source.any()
    source[:] = 255
    meter.push(1 / 30, view)
    assert np.all(source == 255)
    meter.push(2 / 30, np.zeros_like(view))
    assert meter.report()["worst_flash_count"] == 1
    report = meter.report()
    report["violations"][0]["detail"] = "modified"
    assert meter.report()["violations"][0]["detail"] != "modified"

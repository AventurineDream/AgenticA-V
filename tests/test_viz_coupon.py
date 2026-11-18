"""Exercise Coupon's seven painters through pixel behavior and displayed flash-risk samples."""

from dataclasses import replace

import numpy as np
import pytest

from agentic_av.viz.albums.coupon import build_scene
from agentic_av.viz.audio import SILENT
from agentic_av.viz.fx import tone_map
from agentic_av.viz.glyphs import fit
from agentic_av.viz.png import rasterize
from agentic_av.viz.safety import FlashMeter
from agentic_av.viz.scene import Frame, Movement
from agentic_av.viz.surface import Surface

# Source tracks share one continuous recording, but each scene clock starts at zero.
_TRACKS = (
    ("arrival", "Customs at the Edge of Saturn", 77.5715, 84, ("#ebb476", "#a9d5c0", "#dd745c")),
    ("friction", "Rosin in the Subwoofer", 121.2, 150, ("#d6f77b", "#e689e2", "#b3ddec")),
    ("commerce", "Saturn Has a Dollar Store", 103, 160, ("#f4a35d", "#ddf899", "#ee86a8")),
    ("pursuit", "Mall Cop on the Astral Plane", 116.344875, 174, ("#ff826b", "#86dddd", "#eddfb1")),
    ("memory", "The Violin Remembers Earth", 89.00025, 96, ("#d7e9d4", "#8eccc7", "#b4a8df")),
    (
        "gravity",
        "Return Policy for a Black Hole",
        115.714375,
        140,
        ("#bd94ed", "#faaf65", "#db7296"),
    ),
    ("return", "We Kept the Receipt", 98.9997936507937, 128, ("#efd395", "#a6e0a6", "#ebaeb2")),
)


@pytest.fixture(params=range(7), ids=[track[0] for track in _TRACKS])
def movement(request):
    """Supply real movement metadata with a stable, independent seed."""
    index = request.param
    key, title, duration, bpm, palette = _TRACKS[index]
    return Movement("coupon", index, 7, title, key, key, duration, palette, bpm, None, 713 + index)


def _frame(tau=12.0, *, t=None, dt=1 / 30, energy=1.0, levels=SILENT):
    return Frame(tau if t is None else t, tau, dt, energy, 0.5, levels, None, None, None)


def _loud(t):
    return replace(
        SILENT,
        bands=np.linspace(0.3, 1, 7, dtype=np.float32),
        bass=0.9,
        mid=0.7,
        treble=0.8,
        loud=0.8,
        slow_bass=0.6,
        slow_loud=0.6,
        kick=0.9,
        hat=0.9,
        snare=0.7,
        beat=t * 2.9,
        travel=t * 0.8,
        drive=t * 0.6,
        balance=1.0,
    )


def _render(scene, surface, frame):
    scene.render(surface, frame)
    assert surface.rgb.dtype == np.float32
    assert np.isfinite(surface.rgb).all()
    assert np.min(surface.rgb) >= 0
    return surface.rgb.copy()


def test_silent_is_finished_nonblank_and_animates(movement):
    surface = Surface(80, 24, 2, 4)
    scene = build_scene(movement)
    first = _render(scene, surface, _frame(3))
    second = _render(scene, surface, _frame(5))
    assert np.ptp(first) > 0.025
    assert np.count_nonzero(first.max(axis=-1) > 0.02) > 15
    assert not np.array_equal(first, second)


def test_seeded_sequences_are_deterministic(movement):
    left, right = build_scene(movement), build_scene(movement)
    a, b = Surface(62, 20, 2, 4), Surface(62, 20, 2, 4)
    for t in (0, 0.1, 0.5, 1.0, 1.6):
        frame = _frame(t, dt=0.1, levels=_loud(t))
        np.testing.assert_array_equal(_render(left, a, frame), _render(right, b, frame))


def test_zero_dt_holds_pixels_even_when_audio_changes(movement):
    surface = Surface(64, 20, 2, 4)
    scene = build_scene(movement)
    image = _render(scene, surface, _frame(levels=_loud(12)))
    for t in (12.1, 15, 95):
        held = _render(scene, surface, _frame(t, dt=0, levels=_loud(t)))
        np.testing.assert_array_equal(image, held)


def test_still_ignores_audio_time_progress_and_integrators(movement):
    a, b = Surface(64, 20, 2, 4), Surface(64, 20, 2, 4)
    frame = _frame(9, t=1, dt=0, energy=0)
    other = replace(frame, t=1000, progress=1, levels=_loud(1000))
    np.testing.assert_array_equal(
        _render(build_scene(movement), a, frame), _render(build_scene(movement), b, other)
    )


def test_resize_and_seek_reset_history(movement):
    scene = build_scene(movement)
    surface = Surface(62, 20, 2, 4)
    for t in (0, 0.5, 1):
        _render(scene, surface, _frame(t, dt=0.5, levels=_loud(t)))
    scene.seek()
    frame = _frame(4, levels=_loud(4))
    actual = _render(scene, surface, frame)
    expected = _render(build_scene(movement), Surface(62, 20, 2, 4), frame)
    np.testing.assert_array_equal(actual, expected)
    resized = Surface(27, 13, 1, 2)
    scene.resize(resized)
    image = _render(scene, resized, frame)
    assert image.shape == (26, 27, 3)
    assert np.ptp(image) > 0.01


def test_arc_has_distinct_compositions(movement):
    images = []
    for at in (0.1, 0.5, 0.9):
        surface = Surface(80, 24, 2, 4)
        images.append(_render(build_scene(movement), surface, _frame(movement.duration_s * at)))
    assert np.mean(np.abs(images[0] - images[1])) > 0.0001
    assert np.mean(np.abs(images[1] - images[2])) > 0.0001


def test_audio_changes_surface_geometry(movement):
    surface = Surface(72, 24, 2, 4)
    silent = _render(build_scene(movement), surface, _frame(20))
    heard = _render(build_scene(movement), surface, _frame(20, levels=_loud(20)))
    assert not np.array_equal(silent, heard)


@pytest.mark.parametrize("energy,rate", [(1.0, 1.0), (0.35, 0.22)])
@pytest.mark.parametrize("fixture", ["174bpm", "fast", "stereo"])
def test_displayed_adversarial_flash_risk(movement, energy, rate, fixture):
    """Measure fitted octants, not canvas means; this is not WCAG certification."""
    scene = build_scene(movement)
    surface = Surface(72, 24, 2, 4)
    meter = FlashMeter()
    for index in range(121):
        t = index / 30
        hz = 2.9 if fixture == "174bpm" else 4
        kick = float((t * hz) % 1 < 0.20)
        tremolo = float((t * 12) % 1 < 0.5)
        hat = float((t * 8) % 1 < 0.25)
        bands = np.array([tremolo, kick, 1 - kick, kick, hat, 1 - hat, hat], dtype=np.float32)
        levels = replace(
            _loud(t),
            bands=bands,
            kick=kick,
            snare=1 - kick,
            hat=hat,
            balance=(-1 if int(t * 5) % 2 else 1) if fixture == "stereo" else 0,
        )
        frame = _frame(
            20 + t * rate, t=20 + t, dt=rate / 30, energy=energy, levels=levels.calmed(energy)
        )
        scene.render(surface, frame)
        tone_map(surface)
        displayed = rasterize(fit(surface.rgb, "octant"), cell_px=(2, 4))
        meter.push(t, displayed)
    report = meter.report()
    assert report["passed"], report


def test_unknown_scene_is_rejected(movement):
    with pytest.raises(ValueError, match="Unknown Coupon scene"):
        build_scene(replace(movement, scene="unknown"))


@pytest.mark.parametrize("palette", [(), ("#123456",)])
def test_incomplete_metadata_retains_scene_palette(movement, palette):
    surface = Surface(48, 16, 2, 4)
    image = _render(build_scene(replace(movement, palette=palette)), surface, _frame())
    assert np.ptp(image) > 0.01

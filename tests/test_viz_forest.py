"""Exercise all six forest painters, held clocks and rasterized flash-risk fixtures."""

from dataclasses import replace

import numpy as np
import pytest

from agentic_av.viz.albums.forest import build_scene
from agentic_av.viz.audio import SILENT
from agentic_av.viz.fx import tone_map
from agentic_av.viz.glyphs import fit
from agentic_av.viz.png import rasterize
from agentic_av.viz.safety import FlashMeter
from agentic_av.viz.scene import Frame, Movement
from agentic_av.viz.score import NOTE, Score, Section
from agentic_av.viz.surface import Surface

_CHAPTERS = (
    ("root", "Under Six Feet of Moss", 312, 60, ("#0b2119", "#496f43", "#a3b67b")),
    ("rain", "Rain Has Teeth", 264, 108, ("#062425", "#317b67", "#b8d895")),
    ("spiral", "The Root Ball Turns", 252, 112, ("#111d12", "#657849", "#bec388")),
    ("canopy", "Cedar Lung", 300, 70, ("#091f1f", "#38726a", "#d0b98e")),
    ("spores", "Nurse Log, Open Hand", 228, 80, ("#142620", "#588672", "#cfdbb1")),
    ("river", "The Ground Moves Anyway", 324, 80, ("#0e2319", "#678954", "#d3aa63")),
)


def _movement(index):
    scene, title, duration, bpm, palette = _CHAPTERS[index]
    return Movement(
        "forest",
        index,
        6,
        title,
        scene,
        title,
        duration,
        palette,
        bpm,
        (7, 4) if index == 2 else (4, 4),
        303303 + index,
    )


def _frame(tau=10, *, dt=1 / 30, energy=1, **changes):
    frame = Frame(tau, tau, dt, energy, tau / 300, SILENT, None, None, None)
    return replace(frame, **changes)


def _score(energy=1, alternating=False):
    onsets = np.arange(0, 5, 0.1 if alternating else 0.125)
    notes = np.array(
        [
            (
                t,
                0.12,
                48 + index % 36,
                energy * 0.95,
                (-1 if index % 2 else 1) if alternating else 0,
                0,
                0,
            )
            for index, t in enumerate(onsets)
        ],
        dtype=NOTE,
    )
    return Score(
        {part: notes for part in ("harp", "reeds", "guitar", "bass", "drums")},
        ("",),
        ("",),
        (),
        174,
        (4, 4),
        {},
        (),
    )


@pytest.mark.parametrize("index", range(6))
def test_deterministic_finite_silent_and_animated(index):
    movement = _movement(index)
    a, b = build_scene(movement), build_scene(movement)
    sa, sb = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    images = []
    for t in (10, 11, movement.duration_s * 0.5, movement.duration_s * 0.9):
        frame = _frame(t)
        a.render(sa, frame)
        b.render(sb, frame)
        np.testing.assert_array_equal(sa.rgb, sb.rgb)
        assert sa.rgb.dtype == np.float32
        assert np.isfinite(sa.rgb).all()
        assert sa.rgb.max() - sa.rgb.min() > 0.015
        assert np.count_nonzero(sa.rgb) > sa.rgb.size * 0.3
        images.append(sa.rgb.copy())
    assert not np.array_equal(images[0], images[1])
    assert np.mean(np.abs(images[0] - images[-1])) > 0.0001


@pytest.mark.parametrize("index", range(6))
def test_hold_resize_and_seek(index):
    scene = build_scene(_movement(index))
    surface = Surface(72, 20, 2, 4)
    scene.render(surface, _frame())
    held = surface.rgb.copy()
    for t in (11, 500, 1000):
        scene.render(surface, _frame(10, dt=0, t=t, score=_score(), progress=0.99))
        np.testing.assert_array_equal(surface.rgb, held)
    small = Surface(31, 12, 1, 2)
    scene.resize(small)
    scene.render(small, _frame(20))
    assert np.isfinite(small.rgb).all()
    scene.seek()
    fresh = build_scene(_movement(index))
    other = Surface(31, 12, 1, 2)
    frame = _frame(31, dt=0, energy=0)
    scene.render(small, frame)
    fresh.render(other, frame)
    np.testing.assert_array_equal(small.rgb, other.rgb)


@pytest.mark.parametrize("index", range(6))
def test_zero_energy_ignores_audio_score_section_and_progress(index):
    movement = _movement(index)
    a, b = build_scene(movement), build_scene(movement)
    sa, sb = Surface(60, 18, 2, 4), Surface(60, 18, 2, 4)
    hostile = replace(
        SILENT,
        bands=np.ones(7, dtype=np.float32),
        bass=1,
        mid=1,
        treble=1,
        slow_bass=1,
        kick=1,
        snare=1,
        hat=1,
        beat=1e6,
        travel=1e6,
        drive=1e6,
    )
    for tau in (0, 10, 20):
        a.render(
            sa,
            _frame(
                tau,
                energy=0,
                t=999,
                progress=1,
                levels=hostile,
                score=_score(),
                section=Section("union", 0, 9999, "union", 1),
            ),
        )
        b.render(sb, _frame(tau, energy=0, t=0, progress=0))
        np.testing.assert_array_equal(sa.rgb, sb.rgb)


@pytest.mark.parametrize("index", range(6))
def test_scored_instruments_deform_each_chapter(index):
    movement = _movement(index)
    a, b = build_scene(movement), build_scene(movement)
    sa, sb = Surface(60, 18, 2, 4), Surface(60, 18, 2, 4)
    score = _score()
    for tick in range(30):
        t = tick / 30
        a.render(sa, _frame(t, score=score, section=Section("union", 0, 10, "union", 0.94)))
        b.render(sb, _frame(t))
    assert np.mean(np.abs(sa.rgb - sb.rgb)) > 0.00001


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("energy, rate", [(1, 1), (0.35, 0.22)])
@pytest.mark.parametrize("fixture", ["174bpm", "fast", "alternating"])
def test_adversarial_rasterized_output(index, energy, rate, fixture):
    scene = build_scene(_movement(index))
    surface = Surface(80, 24, 2, 4)
    meter = FlashMeter()
    score = _score(energy, alternating=fixture == "alternating")
    for tick in range(76):
        t = tick / 30
        kick_hz = 174 / 60 if fixture == "174bpm" else 4
        kick = float((t * kick_hz) % 1 < 0.24)
        hat = float((t * 8) % 1 < 0.3)
        bass = 0.5 + 0.5 * np.sin(t * 2 * np.pi * 12)
        levels = replace(
            SILENT,
            bands=np.full(7, bass, dtype=np.float32),
            bass=bass,
            mid=kick,
            treble=hat,
            slow_bass=0.5,
            slow_loud=0.5,
            kick=kick,
            snare=1 - kick,
            hat=hat,
            beat=t * kick_hz,
            travel=t,
            drive=t,
            balance=(-1 if int(t * 5) % 2 else 1),
        ).calmed(energy)
        frame = _frame(
            t * rate,
            dt=rate / 30,
            energy=energy,
            t=t,
            levels=levels,
            score=score,
            section=Section("union", 0, 10, "union", energy),
        )
        scene.render(surface, frame)
        assert np.isfinite(surface.rgb).all()
        tone_map(surface)
        displayed = rasterize(fit(surface.rgb, "octant"), cell_px=(2, 4))
        meter.push(t, displayed)
    report = meter.report()
    assert report["passed"], report


def test_unknown_scene_is_rejected():
    with pytest.raises(ValueError, match="unknown forest scene"):
        build_scene(replace(_movement(0), scene="unknown"))

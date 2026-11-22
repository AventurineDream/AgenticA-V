"""Exercise The Forest Has a Pocket's six painters: holds, determinism, score response.

Score fixtures pass through `normalize_track("pocket", ...)`, the same path native extraction
uses, so these tests cover the pocket event layout as well as the picture behavior.
"""

from dataclasses import replace

import numpy as np
import pytest

from clangor_visualis_machina.viz.albums import forest
from clangor_visualis_machina.viz.albums.pocket import build_scene
from clangor_visualis_machina.viz.audio import SILENT
from clangor_visualis_machina.viz.fx import tone_map
from clangor_visualis_machina.viz.glyphs import fit
from clangor_visualis_machina.viz.png import rasterize
from clangor_visualis_machina.viz.safety import FlashMeter
from clangor_visualis_machina.viz.scene import Frame, Movement
from clangor_visualis_machina.viz.score import Score, Section, normalize_track
from clangor_visualis_machina.viz.surface import Surface

_PALETTE = ("#091c18", "#497453", "#d0b575")
# Scene, title, duration, bpm, palette, meter: the source JSON's tracks 1-6.
_CHAPTERS = (
    ("root", "A Root Learns the Offbeat", 272, 88, _PALETTE, (4, 4)),
    ("rain", "Rain in the Hinges", 260, 108, ("#072024", "#4f9181", "#e3bd7d"), (4, 4)),
    ("spiral", "Bark, Bent Light", 252, 80, ("#151d12", "#73804d", "#c59166"), (4, 4)),
    ("canopy", "The Canopy Has Elbows", 292, 96, ("#102623", "#4d9580", "#e1c695"), (4, 4)),
    ("spores", "Five Spaces for a Fern", 208, 72, ("#12251e", "#739484", "#d6d9ad"), (5, 4)),
    ("river", "The Forest Has a Pocket", 320, 100, ("#0b221b", "#65956e", "#e4b365"), (4, 4)),
)


def _movement(index):
    scene, title, duration, bpm, palette, meter = _CHAPTERS[index]
    return Movement(
        "pocket", index, 6, title, scene, scene, duration, palette, bpm, meter, 404000 + index
    )


def _frame(tau=10, *, dt=1 / 30, energy=1, **changes):
    frame = Frame(tau, tau, dt, energy, tau / 300, SILENT, None, None, None)
    return replace(frame, **changes)


def _score(scale=1.0, spacing=0.125):
    """Build a pocket score: bass, harp, guitar and drum rows plus rain noise, in seconds."""
    rows = []
    for index, onset in enumerate(np.arange(0, 5, spacing)):
        onset = float(onset)
        rows.append(
            {
                "part": "bass",
                "kind": "note",
                "time": onset,
                "duration": 0.2,
                "midi": 36 + index % 12,
                "velocity": 0.9 * scale,
                "pan": 0,
                "voice": "pocket-root",
            }
        )
        rows.append(
            {
                "part": "harp",
                "kind": "note",
                "time": onset,
                "duration": 0.6,
                "midi": 60 + index % 24,
                "velocity": 0.7 * scale,
                "pan": 0.2,
                "voice": "held-center",
            }
        )
        rows.append(
            {
                "part": "guitar",
                "kind": "note",
                "time": onset,
                "duration": 0.3,
                "midi": 48 + index % 12,
                "velocity": 0.6 * scale,
                "pan": -0.2,
                "voice": "clipped-fuzz-answer",
            }
        )
        rows.append(
            {
                "part": "drums",
                "kind": "hit",
                "time": onset,
                "duration": 0.05,
                "midi": (36, 38, 42, 46)[index % 4],
                "velocity": 0.6 * scale,
                "pan": 0,
                "voice": "hat",
            }
        )
    rows.append(
        {
            "part": "rain",
            "kind": "noise",
            "time": 0.0,
            "duration": 5.0,
            "midi": 0,
            "velocity": 0.2 * scale,
            "pan": 0,
            "voice": "original-rain",
        }
    )
    payload = normalize_track(
        "pocket",
        {
            "events": rows,
            "bpm": 96,
            "meter": "4/4",
            "palette": list(_PALETTE),
            "sections": [{"name": "union", "start": 0, "end": 10, "intensity": 0.8}],
        },
    )
    return Score.from_payload(payload)


@pytest.mark.parametrize("index", range(6))
def test_deterministic_finite_and_animated(index):
    movement = _movement(index)
    a, b = build_scene(movement), build_scene(movement)
    sa, sb = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    images = []
    for tau in (10, 11, movement.duration_s * 0.5, movement.duration_s * 0.9):
        frame = _frame(tau)
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
        kick=1,
        snare=1,
        hat=1,
        slow_bass=1,
        travel=1,
    )
    for tau in (10, 11, 30):
        a.render(
            sa,
            _frame(
                tau,
                energy=0,
                levels=hostile,
                score=_score(),
                section=Section("union", 0, 10, "union", 1.0),
                progress=0.99,
            ),
        )
        b.render(sb, _frame(tau, energy=0))
        np.testing.assert_array_equal(sa.rgb, sb.rgb)


@pytest.mark.parametrize("index", range(6))
def test_scored_notes_mark_each_chapter(index):
    movement = _movement(index)
    a, b = build_scene(movement), build_scene(movement)
    sa, sb = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    for _ in range(30):
        a.render(sa, _frame(100, t=2.0, score=_score()))
        b.render(sb, _frame(100, t=2.0))
    assert np.mean(np.abs(sa.rgb - sb.rgb)) > 0.00001


def test_pocket_chapters_do_not_reuse_the_forest_painter():
    """Same scene key and metadata: the A-02 root differs from the A-01 forest root."""
    movement = _movement(0)
    sa, sb = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    build_scene(movement).render(sa, _frame(40))
    forest.build_scene(replace(movement, family="forest")).render(sb, _frame(40))
    assert np.mean(np.abs(sa.rgb - sb.rgb)) > 0.001


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("energy, rate", [(1, 1), (0.35, 0.22)])
@pytest.mark.parametrize("fixture", ["174bpm", "fast", "alternating"])
def test_adversarial_rasterized_output(index, energy, rate, fixture):
    scene = build_scene(_movement(index))
    surface = Surface(80, 24, 2, 4)
    meter = FlashMeter()
    score = _score(energy, spacing=0.1 if fixture == "alternating" else 0.125)
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
    with pytest.raises(ValueError, match="unknown pocket scene"):
        build_scene(replace(_movement(0), scene="unknown"))

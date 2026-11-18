"""Exercise all six aquatic paintings, clocks, score reactions and fitted flash-risk guards."""

from dataclasses import replace

import numpy as np
import pytest

from agentic_av.viz.albums.aquatic import build_scene
from agentic_av.viz.audio import SILENT
from agentic_av.viz.fx import tone_map
from agentic_av.viz.glyphs import fit
from agentic_av.viz.png import rasterize
from agentic_av.viz.safety import FlashMeter
from agentic_av.viz.scene import Frame, Movement
from agentic_av.viz.score import Score, Section
from agentic_av.viz.surface import Surface

_TITLES = (
    "An Uneven Kindness",
    "The Bass Asked First",
    "Current Without a Shore",
    "Where the Downbeat Went Under",
    "Two Notes, Then Air",
    "The Water Learns Major",
)
_DURATIONS = (268, 252, 300, 288, 232, 280)
_BPMS = (84, 108, 72, 96, 66, 84)


def _movement(index):
    return Movement(
        "aquatic",
        index,
        6,
        _TITLES[index],
        "",
        "",
        _DURATIONS[index],
        (),
        _BPMS[index],
        (4, 4),
        1024 + index,
    )


def _frame(tau=0.0, *, dt=1 / 30, energy=1.0, t=None, levels=SILENT, score=None):
    return Frame(
        tau if t is None else t,
        tau,
        dt,
        energy,
        tau / 300,
        levels,
        None,
        score,
        None if score is None else score.section(tau),
    )


def _score(kind="alternating", energy=1.0):
    piano = []
    drums = []
    bass = []
    frequency = 2.9 if kind == "realistic" else 4
    for n in range(48):
        t = n / 5
        side = n % 2
        piano.append([t, 0.3, 52 + 24 * side, energy * 0.95, side * 2 - 1, 1, 1 + side])
    for t in np.arange(0, 10, 1 / frequency):
        drums.append([float(t), 0.1, 36, energy, 0, 2, 0])
        bass.append([float(t), 0.2, 28, energy, 0, 1, 0])
    for t in np.arange(0, 10, 0.125):
        drums.append([float(t), 0.04, 80, energy, 0, 3, 0])
    return Score.from_payload(
        {
            "events": {
                "piano": piano,
                "drums": drums,
                "bass": bass,
                "texture": [[0, 10, 65, energy, 0, 4, 0]],
            },
            "kinds": ["", "note", "kick", "hat", "pad"],
            "voices": ["", "upper", "lower"],
            "sections": [{"name": "adversarial", "start": 0, "end": 10, "intensity": energy}],
            "motifs": [{"notes": [[0, 60], [0.2, 72], [0.4, 55]], "start": 0, "end": 0.4}],
            "markers": {"major_onset": 144.48697},
        }
    )


def _loud(t, kind):
    if kind == "alternating":
        amount = float(int(t * 5) % 2)
    elif kind == "realistic":
        amount = float((t * 2.9) % 1 < 0.25)
    else:
        amount = float((t * 12) % 1 < 0.5)
    return replace(
        SILENT,
        bands=np.full(7, amount, dtype=np.float32),
        bass=amount,
        mid=amount,
        treble=amount,
        loud=amount,
        slow_bass=0.5,
        slow_loud=0.5,
        slow_centroid=0.5,
        flux=amount,
        centroid=amount,
        kick=amount,
        snare=amount,
        hat=float((t * 8) % 1 < 0.3),
        beat=t * 4,
        travel=t * 2,
        drive=t * 3,
        balance=amount * 2 - 1,
        width=amount,
    )


@pytest.mark.parametrize("index", range(6))
def test_silent_finite_deterministic_and_animated(index):
    a, b = build_scene(_movement(index)), build_scene(_movement(index))
    sa, sb = Surface(60, 18, 2, 4), Surface(60, 18, 2, 4)
    initial = None
    for tick in range(16):
        f = _frame(tick / 10, dt=0.1)
        a.render(sa, f)
        b.render(sb, f)
        assert np.isfinite(sa.rgb).all()
        assert sa.rgb.dtype == np.float32
        np.testing.assert_array_equal(sa.rgb, sb.rgb)
        if initial is None:
            initial = sa.rgb.copy()
    assert sa.rgb.max() - sa.rgb.min() > 0.005
    assert np.max(np.abs(sa.rgb - initial)) > 0.0001


@pytest.mark.parametrize("index", range(6))
def test_zero_dt_holds_even_when_audio_changes(index):
    scene = build_scene(_movement(index))
    surface = Surface(54, 16, 2, 4)
    scene.render(surface, _frame(40))
    expected = surface.rgb.copy()
    for t in (41, 120, 200):
        scene.render(surface, _frame(40, dt=0, t=t, levels=_loud(t, "dense"), score=_score()))
        np.testing.assert_array_equal(surface.rgb, expected)


@pytest.mark.parametrize("index", range(6))
def test_energy_zero_ignores_every_audio_clock_and_signal(index):
    a, b = build_scene(_movement(index)), build_scene(_movement(index))
    sa, sb = Surface(48, 15, 2, 4), Surface(48, 15, 2, 4)
    score = replace(_score(), markers={"major_onset": 0})
    for tau in (0, 0.1, 0.2):
        a.render(sa, _frame(tau, energy=0, t=0))
        noisy = _frame(tau, energy=0, t=4.8, levels=_loud(4.8, "dense"), score=score)
        noisy = replace(noisy, progress=0.95, section=Section("loud", 0, 999, "union", 1))
        b.render(sb, noisy)
        np.testing.assert_array_equal(sa.rgb, sb.rgb)


@pytest.mark.parametrize("index", range(6))
def test_resize_seek_and_still_first_composition(index):
    scene = build_scene(_movement(index))
    old = Surface(45, 14, 2, 4)
    scene.render(old, _frame(1))
    scene.render(old, _frame(2))
    scene.seek()
    scene.render(old, _frame(0, dt=0, energy=0))
    fresh = build_scene(_movement(index))
    expected = Surface(45, 14, 2, 4)
    fresh.render(expected, _frame(0, dt=0, energy=0))
    np.testing.assert_array_equal(old.rgb, expected.rgb)
    assert old.rgb.max() - old.rgb.min() > 0.005
    for cols, rows, sw, sh in ((1, 1, 1, 2), (37, 19, 1, 2), (66, 12, 2, 4)):
        resized = Surface(cols, rows, sw, sh)
        scene.resize(resized)
        scene.render(resized, _frame(0, dt=0, energy=0))
        assert np.isfinite(resized.rgb).all()


@pytest.mark.parametrize("index", range(6))
def test_scores_move_local_shapes_and_picture_arc(index):
    silent, scored = build_scene(_movement(index)), build_scene(_movement(index))
    a, b = Surface(60, 18, 2, 4), Surface(60, 18, 2, 4)
    silent.render(a, _frame(1))
    scored.render(b, _frame(1, levels=_loud(1, "dense"), score=_score()))
    assert np.max(np.abs(a.rgb - b.rgb)) > 0.0001
    images = []
    for fraction in (0.1, 0.5, 0.9):
        silent.seek()
        silent.render(a, _frame(_DURATIONS[index] * fraction))
        images.append(a.rgb.copy())
    assert np.mean(np.abs(images[0] - images[1])) > 0.00005
    assert np.mean(np.abs(images[1] - images[2])) > 0.00005


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("energy,rate", [(1.0, 1.0), (0.35, 0.22)])
@pytest.mark.parametrize("kind", ["realistic", "dense", "alternating"])
def test_fitted_raster_adversarial_flash_regression(index, energy, rate, kind):
    scene = build_scene(_movement(index))
    surface = Surface(48, 14, 2, 4)
    score = _score(kind, energy)
    meter = FlashMeter()
    for tick in range(91):
        t = tick / 30
        scene.render(
            surface,
            _frame(
                t * rate,
                t=t,
                dt=rate / 30,
                energy=energy,
                levels=_loud(t, kind).calmed(energy),
                score=score,
            ),
        )
        tone_map(surface)
        meter.push(t, rasterize(fit(surface.rgb, "octant"), cell_px=(2, 4)))
    report = meter.report()
    assert report["passed"], report


def test_factory_rejects_unknown_movement():
    with pytest.raises(ValueError, match=r"0\.\.5"):
        build_scene(replace(_movement(0), index=6))

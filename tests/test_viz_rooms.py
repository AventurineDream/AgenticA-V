"""Exercise all six rooms as painted images, including held state and fitted flash risk."""

from dataclasses import replace

import numpy as np
import pytest

from clangor_visualis_machina.viz.albums.rooms import build_scene
from clangor_visualis_machina.viz.audio import SILENT
from clangor_visualis_machina.viz.fx import tone_map
from clangor_visualis_machina.viz.glyphs import fit
from clangor_visualis_machina.viz.png import rasterize
from clangor_visualis_machina.viz.safety import FlashMeter
from clangor_visualis_machina.viz.scene import Frame, Movement
from clangor_visualis_machina.viz.score import Score, Section
from clangor_visualis_machina.viz.surface import Surface

_KEYS = ("aperture", "crossing", "orbit", "lattice", "void", "dawn")
_TITLES = (
    "Copper Gravity",
    "Two Shadows Pass",
    "The Bell Is a Body",
    "Salt Geometry",
    "An Empty Room Stays Warm",
    "Antenna for the Unlit",
)
_DURATIONS = (288, 252, 276, 264, 240, 300)
_PALETTES = (
    ("#10141f", "#557b88", "#d5ae78"),
    ("#101b24", "#3a7580", "#e2c07c"),
    ("#111522", "#627c91", "#c7a1c7"),
    ("#171322", "#805c78", "#e6bd83"),
    ("#121823", "#607583", "#d9ad85"),
    ("#111522", "#526d83", "#e2c48d"),
)


def _movement(key):
    i = _KEYS.index(key)
    return Movement(
        "rooms",
        i,
        6,
        _TITLES[i],
        key,
        key.upper(),
        _DURATIONS[i],
        _PALETTES[i],
        (64, 108, 56, 84, 60, 80)[i],
        ((4, 4), (7, 8), (5, 4), (3, 4), (4, 4), (4, 4))[i],
        4001 + i,
    )


def _frame(t=0, *, tau=None, dt=1 / 30, energy=1, levels=SILENT, score=None):
    return Frame(t, t if tau is None else tau, dt, energy, t / 300, levels, None, score, None)


def _score(rate=4, energy=1):
    rows = [
        [float(t), 0.14, 42 + i % 40, energy, -1 if i % 2 else 1, 1, i % 7]
        for i, t in enumerate(np.arange(0, 210, 1 / rate))
    ]
    return Score.from_payload(
        {
            "events": {p: rows for p in ("mallet", "bell", "wind", "bass", "drums", "air")},
            "kinds": ["", "clarinet"],
            "voices": [
                "",
                "head",
                "foundation",
                "late-flute",
                "changed-return",
                "glass-counterline",
                "mallet-pulse",
            ],
            "markers": {"radiance_on": 168, "radiance_full": 185, "radiance_off": 240},
        }
    )


@pytest.mark.parametrize("key", _KEYS)
def test_silent_is_finite_dark_and_composed(key):
    scene = build_scene(_movement(key))
    surface = Surface(96, 27, 2, 4, 2.24)
    scene.resize(surface)
    scene.render(surface, _frame(30))
    assert surface.rgb.dtype == np.float32
    assert np.isfinite(surface.rgb).all()
    assert np.ptp(surface.rgb) > 0.01
    luminance = surface.rgb @ np.array([0.2126, 0.7152, 0.0722])
    assert np.mean(luminance < 0.025) >= 0.80
    assert surface.rgb.max() > surface.rgb.mean() * 4


@pytest.mark.parametrize("key", _KEYS)
def test_seeded_sequence_and_full_animation(key):
    surfaces = [Surface(64, 18, 2, 4) for _ in range(2)]
    scenes = [build_scene(_movement(key)) for _ in range(2)]
    first = None
    for t in (10, 40, 90):
        for scene, surface in zip(scenes, surfaces, strict=True):
            scene.render(surface, _frame(t))
        np.testing.assert_array_equal(surfaces[0].rgb, surfaces[1].rgb)
        if first is None:
            first = surfaces[0].rgb.copy()
    assert not np.array_equal(first, surfaces[0].rgb)


@pytest.mark.parametrize("key", _KEYS)
def test_zero_dt_holds_state_and_seek_resets(key):
    scene = build_scene(_movement(key))
    surface = Surface(64, 18, 2, 4)
    score = _score()
    for i in range(20):
        scene.render(surface, _frame(20 + i / 30, score=score))
    held = surface.rgb.copy()
    frame = _frame(20 + 19 / 30, dt=0, score=score)
    for _ in range(5):
        scene.render(surface, frame)
        np.testing.assert_array_equal(surface.rgb, held)
    scene.seek()
    scene.render(surface, _frame(15, score=score))
    fresh = build_scene(_movement(key))
    other = Surface(64, 18, 2, 4)
    fresh.render(other, _frame(15, score=score))
    np.testing.assert_array_equal(surface.rgb, other.rgb)
    for cols, rows in ((1, 1), (31, 9), (100, 30)):
        resized = Surface(cols, rows, 1, 2)
        scene.resize(resized)
        scene.render(resized, _frame(15))
        assert np.isfinite(resized.rgb).all()


@pytest.mark.parametrize("reset", ["seek", "resize"])
def test_paused_musical_snapshot_initializes_without_simulating(reset):
    score = _score(rate=4)
    surface = Surface(64, 18, 2, 4)
    scene = build_scene(_movement("orbit"))
    scene.resize(surface)
    scene.render(surface, _frame(1, score=None))

    if reset == "seek":
        scene.seek()
    else:
        scene.resize(surface)

    scene.render(surface, _frame(2, dt=0, score=score))
    expected = Surface(64, 18, 2, 4)
    fresh = build_scene(_movement("orbit"))
    fresh.resize(expected)
    fresh.render(expected, _frame(2, dt=0, score=score))
    np.testing.assert_array_equal(surface.rgb, expected.rgb)


@pytest.mark.parametrize("key", _KEYS)
def test_still_ignores_audio_time_progress_sections_and_integrators(key):
    scene = build_scene(_movement(key))
    surface = Surface(64, 18, 2, 4)
    scene.render(surface, _frame(10, tau=65, dt=0, energy=0))
    held = surface.rgb.copy()
    loud = replace(
        SILENT, bass=1, mid=1, treble=1, kick=1, hat=1, beat=1000, travel=1000, drive=1000
    )
    for t in (100, 190, 290):
        frame = replace(
            _frame(t, tau=65, dt=0, energy=0, levels=loud, score=_score()),
            section=Section("bright", 0, 300, "radiant", 1),
            progress=t / 300,
        )
        scene.render(surface, frame)
        np.testing.assert_array_equal(surface.rgb, held)


@pytest.mark.parametrize("key", _KEYS)
def test_music_changes_the_material_not_only_the_clock(key):
    silent = build_scene(_movement(key))
    musical = build_scene(_movement(key))
    a, b = Surface(64, 18, 2, 4), Surface(64, 18, 2, 4)
    score = _score()
    for i in range(40):
        t = 80 + i / 30
        silent.render(a, _frame(t))
        musical.render(b, _frame(t, score=score))
    assert np.max(np.abs(a.rgb - b.rgb)) > 0.0001


@pytest.mark.parametrize("key", _KEYS)
@pytest.mark.parametrize("energy,rate", [(1, 1), (0.35, 0.22)])
@pytest.mark.parametrize("fixture", ["174bpm", "fast", "alternating"])
def test_fitted_adversarial_inputs_have_no_regional_risk(key, energy, rate, fixture):
    scene = build_scene(_movement(key))
    surface = Surface(64, 18, 2, 4, 2.24)
    meter = FlashMeter()
    hz = {"174bpm": 2.9, "fast": 4, "alternating": 5}[fixture]
    score = _score(hz, energy)
    for i in range(91):
        t = 179 + i / 30
        bass = float(np.sin(2 * np.pi * 12 * t) > 0)
        kick = float((t * hz) % 1 < 0.17)
        hat = float((t * 8) % 1 < 0.2)
        levels = replace(
            SILENT,
            bass=bass,
            mid=kick,
            treble=hat,
            loud=bass,
            kick=kick,
            hat=hat,
            slow_bass=0.5,
            slow_loud=0.5,
            bands=np.full(7, bass, np.float32),
            beat=t * hz,
            travel=t,
            drive=t,
            balance=(-1 if int(t * 5) % 2 else 1),
        )
        scene.render(
            surface,
            _frame(
                t,
                tau=t * rate,
                energy=energy,
                dt=rate / 30,
                levels=levels.calmed(energy),
                score=score,
            ),
        )
        tone_map(surface)
        cells = fit(surface.rgb, "octant")
        meter.push(i / 30, rasterize(cells, cell_px=(2, 4)))
    assert meter.report()["passed"], meter.report()


def test_unknown_scene_is_rejected():
    with pytest.raises(ValueError, match="Unknown rooms scene"):
        build_scene(replace(_movement("aperture"), scene="not-a-room"))

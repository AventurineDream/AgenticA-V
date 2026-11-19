"""Exercise Coupon Seance A-02's six haunt painters: holds, determinism, score response.

Score fixtures pass through `normalize_track("haunt", ...)`, the same path native extraction
uses, so these tests cover the object-row layout as well as the picture behavior.
"""

import itertools
from dataclasses import replace

import numpy as np
import pytest

from agentic_av.viz.albums import coupon
from agentic_av.viz.albums.haunt import build_scene
from agentic_av.viz.audio import SILENT
from agentic_av.viz.fx import tone_map
from agentic_av.viz.glyphs import fit
from agentic_av.viz.png import rasterize
from agentic_av.viz.safety import FlashMeter
from agentic_av.viz.scene import Frame, Movement
from agentic_av.viz.score import Score, Section, normalize_track
from agentic_av.viz.surface import Surface

# Scene, label, duration, bpm, palette (bg, warm, cool), meter: the album's tracks 1-6.
_CHAPTERS = (
    ("perihelion", "ARRIVAL / RINGS OPEN", 271, 88, ("#120d24", "#f0b45a", "#7fd8e6"), (4, 4)),
    ("haunt-free", "BARGAIN / BOWED WALTZ", 259, 104, ("#170f1f", "#e98aa6", "#d9d0ff"), (3, 4)),
    ("aisle", "PURSUIT / CROOKED GRID", 254, 120, ("#0d1418", "#c6f25b", "#ff7a3d"), (7, 8)),
    ("coin-return", "MEMORY / GHOST LINE", 286, 66, ("#0b0f1e", "#b9c7ff", "#ffd27a"), (4, 4)),
    ("layaway", "GRAVITY / DYING STAR", 256, 112, ("#1a0b0b", "#ff6b4a", "#f7d9a8"), (5, 4)),
    ("change", "RETURN / ORBIT REOPENS", 277, 104, ("#0e1420", "#9fe3b0", "#f3c969"), (4, 4)),
)
# Coupon movement whose page colours match each haunt chapter's painter in spirit.
_COUPON_PAIRS = (
    ("perihelion", "arrival"),
    ("haunt-free", "friction"),
    ("aisle", "pursuit"),
    ("coin-return", "memory"),
    ("layaway", "gravity"),
    ("change", "return"),
)


def _movement(index):
    scene, label, duration, bpm, palette, meter = _CHAPTERS[index]
    return Movement(
        "haunt", index, 6, label, scene, label, duration, palette, bpm, meter, 505000 + index
    )


def _frame(tau=10, *, dt=1 / 30, energy=1, **changes):
    frame = Frame(tau, tau, dt, energy, tau / 300, SILENT, None, None, None)
    return replace(frame, **changes)


def _score(scale=1.0, spacing=0.125):
    """Build a haunt score: bass, keys, ether, violin and tube rows, in seconds."""
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
                "voice": "walk",
            }
        )
        rows.append(
            {
                "part": "keys",
                "kind": "note",
                "time": onset,
                "duration": 0.6,
                "midi": 60 + index % 24,
                "velocity": 0.7 * scale,
                "pan": 0.2,
                "voice": "side-slip" if index % 3 == 0 else "comp",
            }
        )
        rows.append(
            {
                "part": "violin",
                "kind": "note",
                "time": onset,
                "duration": 0.4,
                "midi": 64 + index % 16,
                "velocity": 0.6 * scale,
                "pan": -0.2,
                "voice": "head",
            }
        )
        if index % 4 == 0:
            rows.append(
                {
                    "part": "ether",
                    "kind": "note",
                    "time": onset,
                    "duration": 0.1,
                    "midi": 80 + index % 12,
                    "velocity": 0.6 * scale,
                    "pan": 0.3,
                    "voice": "blip",
                }
            )
    rows.append(
        {
            "part": "tube",
            "kind": "noise",
            "time": 0.0,
            "duration": 5.0,
            "midi": 0,
            "velocity": 0.2 * scale,
            "pan": 0,
            "voice": "fluorescent tube and room air",
        }
    )
    payload = normalize_track(
        "haunt",
        {
            "events": rows,
            "bpm": 96,
            "meter": "4/4",
            "color": list(_CHAPTERS[0][4]),
            "sections": [{"name": "union", "start": 0, "end": 10, "intensity": 0.8}],
        },
    )
    return Score.from_payload(payload)


def _render(index, tau, **changes):
    surface = Surface(80, 24, 2, 4)
    build_scene(_movement(index)).render(surface, _frame(tau, **changes))
    return surface.rgb.copy()


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


def test_each_scene_paints_a_distinct_picture():
    # Every chapter must read differently from every other one at the same picture time.
    images = [_render(index, 40) for index in range(6)]
    for a, b in itertools.combinations(range(6), 2):
        assert np.mean(np.abs(images[a] - images[b])) > 0.005


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
        slow_loud=1,
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


@pytest.mark.parametrize("index", range(6))
def test_a_bass_and_keys_onset_never_steps_the_picture_brightness(index):
    # Audio moves geometry, not beat-synchronized light. Smoothed envelopes may swell the
    # light, but no single 30 fps frame across one loud bass and keys onset may carry a
    # step: a frame change over 1% of the light must stay under a third of the total swing.
    rows = [
        {
            "part": part,
            "kind": "note",
            "time": 5.0,
            "duration": 0.5,
            "midi": midi,
            "velocity": 1.0,
            "pan": 0,
            "voice": "comp",
        }
        for part, midi in (("bass", 40), ("keys", 64))
    ]
    payload = normalize_track(
        "haunt",
        {
            "events": rows,
            "bpm": 88,
            "meter": "4/4",
            "color": list(_CHAPTERS[0][4]),
            "sections": [{"name": "a", "start": 0, "end": 10, "intensity": 0.5}],
        },
    )
    score = Score.from_payload(payload)
    scene = build_scene(_movement(index))
    surface = Surface(80, 24, 2, 4)
    light = []
    for step in range(12):
        t = 4.9 + step / 30
        scene.render(surface, _frame(10 + step / 30, t=t, score=score))
        light.append(float(surface.rgb.sum()))
    light = np.asarray(light)
    steps = np.abs(np.diff(light))
    stepped = (steps > 0.01 * light[:-1]) & (steps > np.ptp(light) / 3)
    assert not stepped.any(), light


def test_aisle_lean_flips_on_each_seven_eight_bar():
    # At 120 quarter-note BPM a 7/8 bar lasts 1.75 s; the lean must flip there, not at 3.5 s.
    def image(tau):
        surface = Surface(80, 24, 2, 4)
        build_scene(_movement(2)).render(surface, _frame(tau))
        return surface.rgb

    within = np.mean(np.abs(image(1.6) - image(1.7)))
    across = np.mean(np.abs(image(1.7) - image(1.8)))
    assert across > 20 * within


@pytest.mark.parametrize("haunt_scene, coupon_scene", _COUPON_PAIRS)
def test_haunt_chapters_do_not_reuse_the_coupon_painters(haunt_scene, coupon_scene):
    """Same palette and seed: each haunt chapter must not match its A-01 counterpart."""
    index = [c[0] for c in _CHAPTERS].index(haunt_scene)
    movement = _movement(index)
    sa, sb = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    build_scene(movement).render(sa, _frame(40))
    coupon_movement = replace(movement, family="coupon", scene=coupon_scene)
    coupon.build_scene(coupon_movement).render(sb, _frame(40))
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
    with pytest.raises(ValueError, match="unknown haunt scene"):
        build_scene(replace(_movement(0), scene="unknown"))

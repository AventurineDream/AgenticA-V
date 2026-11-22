"""Exercise Instruments for Measuring Dusk's six painters: holds, determinism, score response.

Score fixtures pass through `normalize_track("dusk", ...)`, the same path native extraction
uses, so these tests cover the dusk event layout as well as the picture behaviour. The
rooms comparisons pin that the A-02 instruments do not reuse the A-01 sculptures.
"""

from dataclasses import replace

import numpy as np
import pytest

from clangor_visualis_machina.viz.albums import rooms
from clangor_visualis_machina.viz.albums.dusk import build_scene
from clangor_visualis_machina.viz.audio import SILENT
from clangor_visualis_machina.viz.fx import tone_map
from clangor_visualis_machina.viz.glyphs import fit
from clangor_visualis_machina.viz.png import rasterize
from clangor_visualis_machina.viz.safety import FlashMeter
from clangor_visualis_machina.viz.scene import Frame, Movement
from clangor_visualis_machina.viz.score import Score, Section, normalize_track
from clangor_visualis_machina.viz.surface import Surface

# Scene, label, duration, bpm, palette [room, warm, cool], meter: the source JSON's tracks 1-6.
_CHAPTERS = (
    ("survey", "APERTURE / THE CELL RETURNS", 276, 76, ("#0b1220", "#c98a5a", "#7f9cc7"), (4, 4)),
    ("sheets", "CROSSING SHEETS / TWO REEDS", 270, 100, ("#0d1018", "#b88cc9", "#d29a62"), (6, 8)),
    ("bell", "BELL / SLOW DECAY", 277, 54, ("#0a0f1c", "#9fb6e0", "#e0b07a"), (3, 4)),
    ("faults", "SALT FAULTS / THE FLOOR MOVES", 273, 96, ("#0c0f14", "#d07a4e", "#8fa8b8"), (7, 4)),
    ("warm-room", "WARM ROOM / OPEN AIR", 250, 100, ("#121018", "#e3b58a", "#b7a6dc"), (5, 4)),
    (
        "transmission",
        "TRANSMISSION / ANTENNA LIT",
        250,
        138,
        ("#0a1018", "#e09a5c", "#9ec3d6"),
        (11, 8),
    ),
)
# The A-01 rooms sculpture with the closest role for each A-02 chapter, for separation checks.
_ROOMS_COUNTERPART = {
    "survey": "aperture",
    "sheets": "crossing",
    "bell": "orbit",
    "faults": "lattice",
    "warm-room": "void",
    "transmission": "dawn",
}


def _movement(index):
    scene, label, duration, bpm, palette, meter = _CHAPTERS[index]
    return Movement(
        "dusk", index, 6, label, scene, scene, duration, palette, bpm, meter, 505000 + index
    )


def _frame(tau=10, *, dt=1 / 30, energy=1, **changes):
    frame = Frame(tau, tau, dt, energy, tau / 300, SILENT, None, None, None)
    return replace(frame, **changes)


def _score(scale=1.0, spacing=0.125):
    """Build a dusk score: bass, marimba, vibes, percussion, reeds and room air, in seconds."""
    rows = []
    for index, onset in enumerate(np.arange(0, 5, spacing)):
        onset = float(onset)
        rows.append(
            {
                "part": "bass",
                "kind": "note",
                "time": onset,
                "duration": 0.2,
                "midi": 38 + index % 12,
                "velocity": 0.9 * scale,
                "pan": 0,
                "voice": "pedal",
            }
        )
        rows.append(
            {
                "part": "marimba",
                "kind": "note",
                "time": onset,
                "duration": 0.3,
                "midi": 60 + (index * 5) % 12,
                "velocity": 0.7 * scale,
                "pan": 0.2,
                "voice": "cell",
            }
        )
        rows.append(
            {
                "part": "vibes",
                "kind": "note",
                "time": onset,
                "duration": 1.2,
                "midi": 72 + index % 7,
                "velocity": 0.6 * scale,
                "pan": -0.1,
                "voice": "bells",
            }
        )
        rows.append(
            {
                "part": "perc",
                "kind": "hit",
                "time": onset,
                "duration": 0.05,
                "midi": (60, 62, 69, 75, 80)[index % 5],
                "velocity": (0.5 if index % 2 else 0.3) * scale,
                "pan": 0,
                "voice": "layer-0",
            }
        )
        rows.append(
            {
                "part": "clarinet",
                "kind": "note",
                "time": onset,
                "duration": 0.4,
                "midi": 55 + index % 9,
                "velocity": 0.6 * scale,
                "pan": -0.2,
                "voice": "head",
            }
        )
        rows.append(
            {
                "part": "flute",
                "kind": "note",
                "time": onset,
                "duration": 0.5,
                "midi": 79 + index % 5,
                "velocity": 0.5 * scale,
                "pan": 0.3,
                "voice": "head",
            }
        )
    rows.append(
        {
            "part": "air",
            "kind": "noise",
            "time": 0.0,
            "duration": 5.0,
            "midi": 0,
            "velocity": 0.2 * scale,
            "pan": 0,
            "voice": "room air",
        }
    )
    payload = normalize_track(
        "dusk",
        {
            "events": rows,
            "bpm": 96,
            "meter": "7/4",
            "color": list(_CHAPTERS[0][4]),
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


@pytest.mark.parametrize("index", range(6))
def test_an_onset_never_steps_the_picture_brightness(index):
    # Audio moves geometry, not beat-synchronized light. Smoothed envelopes may swell the
    # light, but no single 30 fps frame across one loud onset in every part may carry a
    # step: a frame change over 1% of the light must stay under a third of the total swing.
    parts = (("bass", 40), ("marimba", 64), ("vibes", 76), ("clarinet", 60), ("flute", 81))
    rows = [
        {
            "part": part,
            "kind": "note",
            "time": 5.0,
            "duration": 0.5,
            "midi": midi,
            "velocity": 1.0,
            "pan": 0,
            "voice": "head",
        }
        for part, midi in parts
    ]
    rows.append(
        {
            "part": "perc",
            "kind": "hit",
            "time": 5.0,
            "duration": 0.05,
            "midi": 69,
            "velocity": 1.0,
            "pan": 0,
            "voice": "layer-0",
        }
    )
    payload = normalize_track(
        "dusk",
        {
            "events": rows,
            "bpm": 96,
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
        scene.render(surface, _frame(10 + step / 30, t=4.9 + step / 30, score=score))
        light.append(float(surface.rgb.sum()))
    light = np.asarray(light)
    assert np.ptp(light) > 0, "the onset never reached the picture"
    steps = np.abs(np.diff(light))
    stepped = (steps > 0.01 * light[:-1]) & (steps > np.ptp(light) / 3)
    assert not stepped.any(), light


def _one_note_score(part, time, velocity, midi=60, kind="note", voice="head"):
    payload = normalize_track(
        "dusk",
        {
            "events": [
                {
                    "part": part,
                    "kind": kind,
                    "time": time,
                    "duration": 0.4,
                    "midi": midi,
                    "velocity": velocity,
                    "pan": 0,
                    "voice": voice,
                }
            ],
            "bpm": 96,
            "meter": "4/4",
            "color": list(_CHAPTERS[0][4]),
            "sections": [{"name": "a", "start": 0, "end": 20, "intensity": 0.5}],
        },
    )
    return Score.from_payload(payload)


def test_bell_slow_ring_wraps_without_a_light_step():
    # The slow ring restarts every six picture seconds; its light must be near zero at the wrap.
    scene = build_scene(_movement(2))
    surface = Surface(80, 24, 2, 4)
    light = []
    for tau in (5.9, 5.95, 6.0, 6.05, 6.1):
        scene.render(surface, _frame(tau))
        light.append(float(surface.rgb.sum()))
    assert np.max(np.abs(np.diff(light))) < 0.01 * min(light)


def test_mast_accent_still_rings_under_reduced_motion():
    # Stage scales velocities by energy; a 0.49 accent at reduced energy (0.35) must still ring.
    energy = 0.35
    score = _one_note_score("perc", 5.0, 0.49 * energy, midi=69, kind="hit", voice="fill")
    with_hit, without = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    build_scene(_movement(5)).render(with_hit, _frame(10, t=5.5, energy=energy, score=score))
    build_scene(_movement(5)).render(without, _frame(10, t=5.5, energy=energy))
    assert np.mean(np.abs(with_hit.rgb - without.rgb)) > 1e-5


def test_sheet_bend_holds_through_a_rest_instead_of_snapping():
    # A high clarinet note bends its sheet; when it leaves the 6 s window the bend must hold.
    score = _one_note_score("clarinet", 0.0, 0.8, midi=96)
    scene = build_scene(_movement(1))
    surface = Surface(80, 24, 2, 4)
    images = []
    for step in range(200):
        t = step / 30
        scene.render(surface, _frame(10 + t, t=t, score=score))
        if step in (177, 179, 181):
            images.append(surface.rgb.copy())
    # Frame 180 is t = 6.0 s, where the note leaves the window.
    before = np.mean(np.abs(images[1] - images[0]))
    across = np.mean(np.abs(images[2] - images[1]))
    assert across < 3 * before + 1e-4


def test_dusk_chapters_are_distinct_pictures():
    """Each chapter draws its own instrument, not a recoloured copy of another."""
    images = []
    for index in range(6):
        surface = Surface(80, 24, 2, 4)
        build_scene(_movement(index)).render(surface, _frame(40))
        images.append(surface.rgb.copy())
    for i in range(6):
        for j in range(i + 1, 6):
            assert np.mean(np.abs(images[i] - images[j])) > 0.002, (i, j)


@pytest.mark.parametrize("index", range(6))
def test_dusk_chapters_do_not_reuse_the_rooms_painter(index):
    """The A-02 instrument for each chapter differs from its nearest A-01 sculpture."""
    movement = _movement(index)
    sa, sb = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    build_scene(movement).render(sa, _frame(40))
    room = replace(movement, family="rooms", scene=_ROOMS_COUNTERPART[movement.scene])
    rooms.build_scene(room).render(sb, _frame(40))
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
    with pytest.raises(ValueError, match="unknown dusk scene"):
        build_scene(replace(_movement(0), scene="unknown"))

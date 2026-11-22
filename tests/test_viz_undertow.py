"""Exercise DC2's six native paintings with independent hands and real Stage contracts.

Tiny object-row scores follow the same normalizer as bundled extraction. Tests measure
visible pictures, exact holds, seek reconstruction and conservative rasterized flash risk;
no media playback, desktop session, network or package archive is needed.
"""

from dataclasses import replace

import numpy as np
import pytest

from clangor_visualis_machina.viz.albums.undertow import build_scene
from clangor_visualis_machina.viz.audio import SILENT
from clangor_visualis_machina.viz.fx import tone_map
from clangor_visualis_machina.viz.glyphs import fit
from clangor_visualis_machina.viz.png import rasterize
from clangor_visualis_machina.viz.safety import FlashMeter
from clangor_visualis_machina.viz.scene import Frame, Movement
from clangor_visualis_machina.viz.score import Score, Section, normalize_track
from clangor_visualis_machina.viz.surface import Surface

_SCENES = ("seam", "shoal", "shelf", "fault", "hollow", "estuary")
_DURATIONS = (268, 248, 292, 276, 232, 316)
_PALETTE = ("#07151b", "#337778", "#d4ccb0")


def _movement(index):
    return Movement(
        "undertow",
        index,
        6,
        "DC2",
        _SCENES[index],
        _SCENES[index],
        _DURATIONS[index],
        _PALETTE,
        84,
        None,
        2200 + index,
    )


def _frame(tau=60, **changes):
    return replace(Frame(2, tau, 1 / 30, 1, 0.3, SILENT, None, None, None), **changes)


def _score(voice=None, scale=1):
    rows = []
    for i, onset in enumerate(np.arange(0, 5, 0.125)):
        specs = (
            ("piano", "note", "right", 72),
            ("piano", "note", "left", 50),
            ("bass", "note", "question", 38),
            ("drums", "hit", "kick", 36),
            ("drums", "hit", "snare", 38),
            ("memory", "noise", "piano-memory", 72),
        )
        for part, kind, name, pitch in specs:
            if voice is not None and name != voice:
                continue
            rows.append(
                dict(
                    part=part,
                    kind=kind,
                    voice=name,
                    time=float(onset),
                    duration=0.6,
                    midi=pitch + (i % 3 if part == "piano" else 0),
                    velocity=0.65 * scale,
                    pan=0,
                )
            )
    return Score.from_payload(normalize_track("undertow", {"events": rows}))


@pytest.mark.parametrize("index", range(6))
def test_pictures_are_seeded_finite_and_move_without_fabricated_audio(index):
    """Silent fallback remains a composed, moving painting rather than a frozen blank."""
    a, b = build_scene(_movement(index)), build_scene(_movement(index))
    sa, sb = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    pictures = []
    for tau in (20, 21, 120, 220):
        a.render(sa, _frame(tau))
        b.render(sb, _frame(tau))
        np.testing.assert_array_equal(sa.rgb, sb.rgb)
        assert sa.rgb.dtype == np.float32 and np.isfinite(sa.rgb).all()
        assert np.ptp(sa.rgb) > 0.015
        pictures.append(sa.rgb.copy())
    assert not np.array_equal(pictures[0], pictures[1])
    assert np.mean(np.abs(pictures[0] - pictures[-1])) > 0.0001


@pytest.mark.parametrize("index", range(6))
def test_hold_resize_and_seek_reconstruct_complete_pictures(index):
    """Held pixels ignore arriving music; resize/seek cannot retain a stale-size image."""
    scene = build_scene(_movement(index))
    surface = Surface(72, 20, 2, 4)
    scene.render(surface, _frame(score=_score()))
    held = surface.rgb.copy()
    for t in (11, 500, 1000):
        scene.render(surface, _frame(dt=0, t=t, score=_score(), progress=0.99))
        np.testing.assert_array_equal(surface.rgb, held)
    small = Surface(31, 12, 1, 2)
    scene.resize(small)
    scene.render(small, _frame(20, score=_score()))
    assert small.rgb.shape == (24, 31, 3) and np.isfinite(small.rgb).all()
    scene.seek()
    fresh, other = build_scene(_movement(index)), Surface(31, 12, 1, 2)
    scene.render(small, _frame(31, score=_score()))
    fresh.render(other, _frame(31, score=_score()))
    np.testing.assert_array_equal(small.rgb, other.rgb)


@pytest.mark.parametrize("index", range(6))
def test_zero_energy_ignores_score_audio_and_section(index):
    """Still/zero-energy geometry cannot accidentally follow uncalmed incoming signals."""
    a, b = build_scene(_movement(index)), build_scene(_movement(index))
    sa, sb = Surface(60, 18, 2, 4), Surface(60, 18, 2, 4)
    hostile = replace(
        SILENT,
        bass=1,
        mid=1,
        treble=1,
        kick=1,
        snare=1,
        hat=1,
        slow_bass=1,
        travel=100,
        bands=np.ones(7, dtype=np.float32),
    )
    for tau in (10, 11, 30):
        a.render(
            sa,
            _frame(
                tau,
                energy=0,
                levels=hostile,
                score=_score(),
                section=Section("union", 0, 10, "union", 1),
                progress=0.99,
            ),
        )
        b.render(sb, _frame(tau, energy=0))
        np.testing.assert_array_equal(sa.rgb, sb.rgb)


@pytest.mark.parametrize("index", range(6))
def test_piano_hands_have_distinct_visible_routes(index):
    """Changing the scored speaker changes the painting even with identical audio envelopes."""
    a, b = build_scene(_movement(index)), build_scene(_movement(index))
    sa, sb = Surface(80, 24, 2, 4), Surface(80, 24, 2, 4)
    right, left = _score("right"), _score("left")
    for _ in range(30):
        a.render(sa, _frame(score=right))
        b.render(sb, _frame(score=left))
    assert np.mean(np.abs(sa.rgb - sb.rgb)) > 0.00001
    assert np.max(np.abs(sa.rgb - sb.rgb)) > 0.02


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("energy,rate", [(1, 1), (0.35, 0.22)])
def test_fast_attacks_do_not_flash_rasterized_paintings(index, energy, rate):
    """Adversarial envelopes exercise the same conservative regional heuristic as playback."""
    scene = build_scene(_movement(index))
    surface = Surface(80, 24, 2, 4)
    meter = FlashMeter()
    score = _score(scale=energy)
    for tick in range(76):
        t = tick / 30
        pulse = float((t * 4) % 1 < 0.24)
        levels = replace(
            SILENT,
            bass=pulse,
            mid=1 - pulse,
            treble=pulse,
            slow_bass=0.5,
            kick=pulse,
            snare=1 - pulse,
            hat=pulse,
        ).calmed(energy)
        scene.render(
            surface, _frame(t * rate, dt=rate / 30, t=t, energy=energy, levels=levels, score=score)
        )
        tone_map(surface)
        meter.push(t, rasterize(fit(surface.rgb, "octant"), cell_px=(2, 4)))
    report = meter.report()
    assert report["passed"], report


def test_six_chapters_are_distinct_compositions():
    """The six keys select different spatial designs, not palette-only variations."""
    pictures = []
    for index in range(6):
        surface = Surface(80, 24, 2, 4)
        build_scene(_movement(index)).render(surface, _frame())
        pictures.append(surface.rgb.copy())
    for i, image in enumerate(pictures):
        for other in pictures[i + 1 :]:
            assert np.mean(np.abs(image - other)) > 0.001


def test_unknown_scene_is_rejected():
    """A malformed known-album scene cannot silently fall back to a different composition."""
    with pytest.raises(ValueError, match="unknown undertow scene"):
        build_scene(replace(_movement(0), scene="unknown"))


def test_a_dense_counterhand_cannot_erase_the_other_hands_note():
    """A quiet right-hand mark survives more than twenty newer left-hand attacks."""
    left = [
        dict(
            part="piano",
            kind="note",
            time=1.8 + i * 0.003,
            duration=0.1,
            midi=50 + i % 3,
            velocity=0.6,
            voice="left",
        )
        for i in range(40)
    ]
    right = dict(
        part="piano", kind="note", time=0.8, duration=0.4, midi=74, velocity=0.6, voice="right"
    )
    images = []
    for rows in (left, [right, *left]):
        scene, surface = build_scene(_movement(0)), Surface(100, 32, 2, 4)
        score = Score.from_payload(normalize_track("undertow", {"events": rows}))
        # A fresh zero step leaves deformation at rest, isolating visible note marks.
        scene.render(surface, _frame(dt=0, score=score))
        images.append(surface.rgb.copy())
    assert np.max(np.abs(images[0] - images[1])) > 0.001


@pytest.mark.parametrize("index", range(6))
def test_authoritative_score_does_not_turn_cymbals_into_piano_motion(index):
    """Whole-mix treble and mids cannot move silent scored piano hands."""
    score = _score("question")
    a, b = build_scene(_movement(index)), build_scene(_movement(index))
    sa, sb = Surface(60, 18, 2, 4), Surface(60, 18, 2, 4)
    loud_bands = replace(SILENT, mid=1, treble=1)
    for _ in range(20):
        a.render(sa, _frame(score=score, levels=loud_bands))
        b.render(sb, _frame(score=score))
    np.testing.assert_array_equal(sa.rgb, sb.rgb)

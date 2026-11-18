"""Cover held pictures, score calming, seeks, tier changes, and picture-time crossfades."""

from dataclasses import replace

import numpy as np
import pytest

from agentic_av.viz.scene import Movement, Scene
from agentic_av.viz.score import Score
from agentic_av.viz.stage import Stage


class RecordingScene(Scene):
    """Expose deliberately stateful painting so accidental held renders are visible."""

    def __init__(self, movement):
        super().__init__(movement)
        self.frames = []
        self.seeks = 0
        self.resizes = 0

    def resize(self, surface):
        """Record canvas lifecycle calls."""
        self.resizes += 1

    def seek(self):
        """Count discontinuity resets."""
        self.seeks += 1

    def render(self, surface, frame):
        """Paint a temporal marker with an intentionally accumulating counter."""
        self.frames.append(frame)
        surface.fill((0.02 + len(self.frames) * 0.01, frame.progress * 0.1, 0.03))


def _movement():
    return Movement("unknown", 0, 1, "Test", "ribbons", "Ribbons", 60, (), 120, (4, 4), 13)


def _stage(monkeypatch):
    scenes = []

    def factory(movement):
        scene = RecordingScene(movement)
        scenes.append(scene)
        return scene

    monkeypatch.setattr("agentic_av.viz.stage.build_scene", factory)
    stage = Stage(12, 5, tier="octant", color_mode="truecolor")
    stage.open(_movement(), None, None)
    return stage, scenes


def test_requires_open_and_valid_clocks():
    stage = Stage(12, 5, tier="half", color_mode="none")
    with pytest.raises(RuntimeError):
        stage.frame(0, 0, motion="full")
    stage.open(_movement(), None, None)
    with pytest.raises(ValueError):
        stage.frame(0, float("nan"), motion="full")


@pytest.mark.parametrize("motion", ["full", "reduced", "still"])
def test_zero_dt_never_accumulates_feedback(monkeypatch, motion):
    stage, scenes = _stage(monkeypatch)
    stage.frame(4, 4, motion=motion)
    picture = stage.surface.rgb.copy()
    assert stage.frame(20, 4, motion=motion) == b""
    np.testing.assert_array_equal(stage.surface.rgb, picture)
    assert len(scenes[0].frames) == 1


def test_still_freezes_all_inputs_but_redraws_on_resize(monkeypatch):
    stage, scenes = _stage(monkeypatch)
    stage.frame(4, 4, motion="still")
    original = scenes[0].frames[-1]
    stage.frame(50, 50, motion="still")
    assert len(scenes[0].frames) == 1
    stage.resize(16, 6)
    assert stage.frame(55, 100, motion="still")
    assert scenes[0].frames[-1] == replace(original, dt=0)
    assert stage.cells.glyph.shape == (6, 16)
    assert scenes[0].seeks == 0


def test_seek_discontinuity_and_tier_resize(monkeypatch):
    stage, scenes = _stage(monkeypatch)
    for tau in (0, 0.1, 3, 2):
        stage.frame(tau, tau, motion="full")
    assert scenes[0].seeks == 2
    assert scenes[0].frames[-1].dt == 0
    stage.set_tier("half")
    stage.frame(2, 2, motion="full")
    assert stage.surface.rgb.shape == (10, 12, 3)
    assert stage.cells.tier == "half"


def test_reduced_score_velocities_and_sections_are_calmed_once(monkeypatch):
    stage, scenes = _stage(monkeypatch)
    score = Score.from_payload(
        {
            "events": {"bass": [[0, 2, 60, 1, 0, 0, 0]]},
            "sections": [{"name": "A", "start": 0, "end": 60, "intensity": 0.8}],
        }
    )
    stage.open(_movement(), None, score)
    stage.frame(0, 0, motion="reduced")
    frame = scenes[-1].frames[-1]
    assert frame.energy == 0.35
    assert frame.score.notes["bass"]["vel"][0] == pytest.approx(0.35)
    assert frame.section.intensity == pytest.approx(0.28)
    assert score.notes["bass"]["vel"][0] == 1


def test_crossfade_uses_picture_dt_and_does_not_advance_when_held(monkeypatch):
    stage, scenes = _stage(monkeypatch)
    stage.frame(0, 0, motion="full")
    old = stage.surface.rgb.copy()
    stage.open(_movement(), None, None)
    stage.frame(10, 10, motion="full")
    np.testing.assert_array_equal(stage.surface.rgb, old)
    stage.frame(10.5, 10.5, motion="full")
    middle = stage.surface.rgb.copy()
    stage.frame(30, 10.5, motion="full")
    np.testing.assert_array_equal(stage.surface.rgb, middle)
    assert len(scenes[-1].frames) == 2
    stage.frame(11.5, 11.5, motion="full")
    assert stage._fade_from is None
    assert not np.array_equal(stage.surface.rgb, middle)


def test_reduced_open_cuts_instead_of_crossfading(monkeypatch):
    stage, _ = _stage(monkeypatch)
    stage.frame(0, 0, motion="reduced")
    stage.open(_movement(), None, None)
    stage.frame(20, 20, motion="reduced")
    assert stage._fade_from is None


def test_explicit_seek_releases_still_snapshot(monkeypatch):
    stage, scenes = _stage(monkeypatch)
    stage.frame(4, 0, motion="still")
    stage.seek()
    stage.frame(40, 0, motion="still")
    assert scenes[0].seeks == 1
    assert scenes[0].frames[-1].t == 40
    assert scenes[0].frames[-1].dt == 0

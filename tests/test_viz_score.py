"""Tiny authored fixtures cover score queries and the bundled event layouts."""

import math

import numpy as np
import pytest

from agentic_av.viz.score import NOTE, Score, normalize_track


def test_score_queries_and_half_open_boundaries():
    score = Score.from_payload(
        {
            "events": {
                "piano": [
                    [1, 2, 60, 0.5, -0.2, 1, 1],
                    [0, 0.5, 72, 0.2, 0.3, 2, 2],
                    [2, 0.5, 64, 0.7, 0, 1, 2],
                ]
            },
            "kinds": ["", "note", "pad"],
            "voices": ["", "upper", "lower"],
            "sections": [
                {"name": "opening", "start": 0, "end": 2, "mode": "solo", "intensity": 0.3},
                {"name": "answer", "start": 3, "end": 5, "mode": "union", "intensity": 0.9},
            ],
            "bpm": 120,
            "meter": [4, 4],
            "markers": {"turn": 3},
            "motifs": [],
        }
    )
    assert score.notes["piano"].dtype == NOTE
    assert not score.notes["piano"].flags.writeable
    assert score.bpm == 120 and score.meter == (4, 4)
    assert score.markers["turn"] == 3
    np.testing.assert_array_equal(score.recent("piano", 2, 1)["onset"], [2])
    np.testing.assert_array_equal(score.recent("piano", 2, 2)["onset"], [1, 2])
    np.testing.assert_array_equal(score.sounding("piano", 2)["onset"], [1, 2])
    np.testing.assert_array_equal(score.sounding("piano", 2.5)["onset"], [1])
    for result in (score.recent("piano", 2, 1), score.sounding("piano", 2)):
        assert not result.flags.writeable
        with pytest.raises(ValueError):
            result["vel"][0] = 0
    assert not score.sounding("piano", 3).flags.writeable
    assert not score.sounding("piano", 3).size
    assert score.level("piano", 2) == pytest.approx(
        math.tanh(0.7 + 0.5 * math.exp(-1 / 0.3) + 0.2 * math.exp(-2 / 0.3))
    )
    assert score.level("piano", 2, kind="note", voice="upper") == pytest.approx(
        math.tanh(0.5 * math.exp(-1 / 0.3))
    )
    assert score.level("piano", 2, kind="unknown") == 0
    assert score.level("piano", -1) == 0
    assert score.level("missing", 2) == 0
    assert score.recent("missing", 2, 1).dtype == NOTE
    assert not score.sounding("missing", 2).size
    assert score.section(0).name == "opening"
    assert score.section(1.999).mode == "solo"
    assert score.section(2) is None
    assert score.section(3).intensity == 0.9
    assert score.section(5) is None
    with pytest.raises(ValueError):
        score.level("piano", 1, decay_s=0)


def test_forest_tuple_layout_and_gm_drums():
    payload = normalize_track(
        "forest",
        {
            "events": [
                ["harp", 2, 1, 72, 0.5, -0.2],
                ["drums", 1, 0.1, 36, 0.8, 0],
                ["drums", 2, 0.1, 38, 0.6, 0],
                ["drums", 3, 0.1, 37, 0.4, 0],
                ["drums", 4, 0.1, 46, 0.3, 0],
            ],
            "color": ["#112233", "#445566", "#778899"],
            "sections": [
                {"name": "union", "start": 0, "end": 5, "mode": "union", "intensity": 0.8}
            ],
        },
    )
    score = Score.from_payload(payload)
    assert payload["palette"] == ["#112233", "#445566", "#778899"]
    assert score.bpm is None and score.meter is None
    assert score.kinds[0] == score.voices[0] == ""
    assert score.level("drums", 1, kind="kick") == pytest.approx(math.tanh(0.8))
    assert [score.kinds[i] for i in score.notes["drums"]["kind"]] == ["kick", "snare", "rim", "hat"]
    assert score.notes["harp"]["midi"][0] == 72


@pytest.mark.parametrize("family", ["pocket", "undertow"])
def test_object_rows_keep_seconds_meter_and_drum_names(family):
    """Object-layout albums retain actual performance seconds and named kit strokes."""
    payload = normalize_track(
        family,
        {
            "events": [
                {
                    "part": "drums",
                    "kind": "hit",
                    "time": 1.5,
                    "duration": 0.1,
                    "midi": 38,
                    "velocity": 0.6,
                    "pan": 0.25,
                    "voice": "snare",
                },
                {
                    "part": "rain",
                    "kind": "noise",
                    "time": 0,
                    "duration": 21.8,
                    "midi": 0,
                    "velocity": 0.03,
                    "voice": "original-rain",
                },
            ],
            "bpm": 72,
            "meter": "5/4",
            "color": ["#112233", "#445566", "#778899"],
        },
    )
    score = Score.from_payload(payload)
    assert score.bpm == 72 and score.meter == (5, 4)
    snare = score.notes["drums"][0]
    assert snare["onset"] == 1.5
    assert score.kinds[int(snare["kind"])] == "snare"
    assert score.voices[int(snare["voice"])] == "snare"
    assert score.kinds[int(score.notes["rain"][0]["kind"])] == "noise"
    assert score.level("drums", 1.6, decay_s=0.2, kind="snare") > 0


def test_aquatic_arrays_root_tables_palette_and_motifs():
    html = (
        'const palette = [["#112233", "#445566", "#778899", "#aabbcc"], '
        '["#123456", "#234567", "#345678", "#456789"],];'
    )
    payload = normalize_track(
        "aquatic",
        {
            "number": 2,
            "bpm": 84,
            "kinds": ["pad", "note"],
            "voices": ["lower", "upper"],
            "events": {
                "piano": [[1, 2, 62, 0.4, 0.1, 1, 1]],
                "texture": [[0, 5, 50, 0.1, 0, 0, 0]],
            },
            "major_first_f_sharp": 144.48697,
            "sections": [{"name": "solo", "start": 0, "end": 10, "role": "intro", "meter": "7/8"}],
            "motifs": [{"name": "contour", "notes": [[1, 62], [3, 67]]}],
        },
        html,
    )
    score = Score.from_payload(payload)
    assert payload["palette"] == ["#123456", "#234567", "#345678", "#456789"]
    assert score.bpm == 84 and score.meter == (7, 8)
    assert score.markers["major_onset"] == 144.48697
    assert score.motifs[0]["name"] == "contour"
    assert score.kinds[int(score.notes["piano"]["kind"][0])] == "note"
    assert score.voices[int(score.notes["piano"]["voice"][0])] == "upper"
    assert score.section(1).mode == "intro"
    assert len(normalize_track("aquatic", {})["palette"]) == 4


def test_rooms_objects_wind_programs_and_javascript_radiance():
    payload = normalize_track(
        "rooms",
        {
            "number": 6,
            "bpm": 80,
            "meter": "4/4",
            "color": ["#111522", "#526d83", "#e2c48d"],
            "events": [
                {
                    "part": "wind",
                    "time": i,
                    "duration": 1.5,
                    "midi": 72,
                    "velocity": 0.4,
                    "pan": 0.2,
                    "kind": "note",
                    "voice": "late-flute",
                    "program": program,
                }
                for i, program in enumerate((73, 71))
            ],
        },
        "const radiance = track.number === 6 ? smooth(160, 180, time) "
        "* (1 - .84 * smooth(230, 280, time)) : 0;",
    )
    score = Score.from_payload(payload)
    assert score.markers == {"radiance_on": 160, "radiance_full": 180, "radiance_off": 230}
    assert [score.kinds[i] for i in score.notes["wind"]["kind"]] == ["flute", "clarinet"]
    fallback = normalize_track("rooms", {"number": 6})
    assert fallback["markers"] == {"radiance_on": 168, "radiance_full": 185, "radiance_off": 240}
    assert normalize_track("rooms", {"number": 1})["markers"] == {}


def test_coupon_metadata_without_invented_score():
    payload = normalize_track("coupon", {"bpm": 174, "palette": ["#ff826b", "#86dddd", "#eddfb1"]})
    assert payload["bpm"] == 174
    assert payload["palette"] == ["#ff826b", "#86dddd", "#eddfb1"]
    score = Score.from_payload(payload)
    assert not score.notes and not score.sections and not score.motifs
    assert score.level("bass", 10) == 0 and score.section(10) is None


def test_undertow_preserves_independent_hands_and_piano_memory():
    """The single pianist's hand voices stay queryable without adding band members."""
    rows = [
        dict(
            part="piano",
            kind="note",
            time=1.013,
            duration=1.2,
            midi=74,
            velocity=0.6,
            pan=0.12,
            voice="right",
        ),
        dict(
            part="piano",
            kind="note",
            time=0.993,
            duration=0.7,
            midi=50,
            velocity=0.4,
            pan=-0.13,
            voice="left",
        ),
        dict(
            part="memory",
            kind="noise",
            time=0.4,
            duration=4,
            midi=74,
            velocity=0.12,
            pan=0,
            voice="piano-memory",
        ),
    ]
    score = Score.from_payload(normalize_track("undertow", {"events": rows}))
    np.testing.assert_allclose(score.notes["piano"]["onset"], [0.993, 1.013])
    right = score.level("piano", 1.1, voice="right")
    left = score.level("piano", 1.1, voice="left")
    assert right > left > 0
    assert score.level("piano", 1, voice="right") == 0
    assert score.level("memory", 1, kind="noise", voice="piano-memory") > 0

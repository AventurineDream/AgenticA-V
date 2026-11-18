"""Cover deterministic real-pipeline previews, sequential safety, and TTY restoration."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from agentic_av.viz import preview
from agentic_av.viz.audio import SILENT
from agentic_av.viz.scene import Movement
from agentic_av.viz.score import Score


def _source(duration=4.0):
    movement = Movement("unknown", 0, 1, "Test", "ribbons", "Ribbons", duration, (), 120, None, 5)
    return preview._Source(movement, None, Score.from_payload({}))


def _args(*flags):
    return preview._parser().parse_args(["coupon", "1", "--size", "16x6", "--tier", "half", *flags])


def test_parser_supports_all_plan_flags():
    args = _args("--at", "1,2,3", "--sheet", "3", "--color", "none", "--motion", "reduced")
    assert args.at == [1, 2, 3]
    assert args.sheet == 3
    assert args.size == (16, 6)
    assert _args("--live", "--from", "2").start == 2
    assert _args("--bench").bench
    assert _args("--safety").safety


@pytest.mark.parametrize("value", ["0x1", "12", "3x-4", "axb"])
def test_invalid_size_is_rejected(value):
    with pytest.raises(SystemExit):
        _args("--size", value)


def test_fixed_warmup_is_deterministic():
    args = _args("--at", "3.25")
    a = preview._warm(_source(), args, 3.25)
    b = preview._warm(_source(), args, 3.25)
    np.testing.assert_array_equal(a.surface.rgb, b.surface.rgb)
    assert a._last_frame.t == 3.25


def test_contact_sheet_and_multiple_png_paths(tmp_path, capsys):
    args = _args("--sheet", "3", "--out", str(tmp_path / "sheet.png"))
    preview._snapshots(_source(), args)
    assert args.out.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    args = _args("--at", "1,2", "--out", str(tmp_path / "frame.png"))
    preview._snapshots(_source(), args)
    assert (tmp_path / "frame-01-1s.png").exists()
    assert (tmp_path / "frame-02-2s.png").exists()
    assert "sheet.png" in capsys.readouterr().out


def test_bench_reports_individual_pipeline_times(capsys):
    import json

    preview._bench(_source(), _args("--bench"))
    report = json.loads(capsys.readouterr().out)
    assert report["frames"] == 120
    for key in ("render_ms", "fit_ms", "encode_ms", "total_ms"):
        assert report[key] > 0


def test_safety_streams_entire_duration_with_real_signal_samples(monkeypatch, capsys):
    import agentic_av.viz.safety as safety

    times, samples = [], []

    class Features:
        def sample(self, t):
            samples.append(t)
            return SILENT

    class Meter:
        def push(self, t, image):
            assert image.dtype == np.uint8
            times.append(t)

        def report(self):
            return {"passed": True}

    monkeypatch.setattr(safety, "FlashMeter", Meter)
    source = replace(_source(0.15), features=Features())
    report = preview._safety(source, _args("--safety", "--color", "256"))
    assert report["passed"]
    assert times[0] == 0 and times[-1] == 0.15
    assert np.all(np.diff(times) > 0)
    assert samples == times
    assert "not WCAG certification" in capsys.readouterr().out


def test_safety_rejects_silent_fallback():
    with pytest.raises(ValueError, match="requires real audio"):
        preview._safety(_source(), _args("--safety"))


def test_live_restores_terminal_on_write_failure(monkeypatch):
    restored, handlers, writes = [], [], []

    class Output:
        def write(self, data):
            writes.append(data)
            if len(writes) == 2:
                raise OSError("broken output")

        def flush(self):
            pass

    stdin = SimpleNamespace(isatty=lambda: True, fileno=lambda: 5)
    stdout = SimpleNamespace(isatty=lambda: True, fileno=lambda: 6, buffer=Output())
    monkeypatch.setattr(preview.sys, "stdin", stdin)
    monkeypatch.setattr(preview.sys, "stdout", stdout)
    monkeypatch.setattr(preview.termios, "tcgetattr", lambda fd: ["original"])
    monkeypatch.setattr(preview.termios, "tcsetattr", lambda *args: restored.append(args))
    monkeypatch.setattr(preview.tty, "setcbreak", lambda fd: None)
    monkeypatch.setattr(preview.signal, "getsignal", lambda sig: "old")
    monkeypatch.setattr(preview.signal, "signal", lambda *args: handlers.append(args))
    monkeypatch.setattr(preview, "cell_aspect", lambda fd: 2.0)
    with pytest.raises(OSError, match="broken output"):
        preview._live(_source(), _args("--live"))
    assert restored[-1][-1] == ["original"]
    assert handlers[-1][-1] == "old"
    assert writes[-1].endswith(b"\x1b[?1049l")


def test_main_uses_loaded_album_without_substitution(monkeypatch, tmp_path):
    calls = []

    def load(album, movement):
        calls.append((album, movement))
        return _source()

    monkeypatch.setattr(preview, "_load", load)
    target = tmp_path / "frame.png"
    assert preview.main(["forest", "6", "--size", "12x4", "--out", str(target)]) == 0
    assert calls == [("forest", "6")]
    assert target.exists()


def test_load_uses_native_extract_score_palette_and_one_based_movement(monkeypatch):
    score = Score.from_payload({"bpm": 123, "meter": [7, 8]})
    tracks = tuple(
        SimpleNamespace(
            scene=f"scene-{index}",
            scene_label="Label",
            score={"duration": 30, "palette": ["#010203", "#aabbcc"]},
        )
        for index in range(6)
    )
    album = SimpleNamespace(family="forest", tracks=tracks)
    requested = []
    monkeypatch.setattr(preview, "extract_album", lambda asset: album)

    def signals(native, index):
        assert native is album
        requested.append(index)
        return None, score

    monkeypatch.setattr(preview, "movement_signals", signals)
    source = preview._load("forest", "6")
    assert requested == [5]
    assert source.movement.index == 5
    assert source.movement.scene == "scene-5"
    assert source.movement.duration_s == 30
    assert source.movement.palette == ("#010203", "#aabbcc")
    assert source.movement.bpm == 123
    assert source.movement.meter == (7, 8)
    assert preview._load("Nurse Log", "6").movement.seed == source.movement.seed


def test_still_cli_at_captures_requested_progress_not_warmup_start(monkeypatch):
    source = _source(60)
    args = _args("--motion", "still", "--at", "20")
    captures = []
    monkeypatch.setattr(preview, "_load", lambda *names: source)
    monkeypatch.setattr(preview, "write_png", lambda path, image: captures.append(image.copy()))
    assert (
        preview.main(
            [
                "coupon",
                "1",
                "--size",
                "16x6",
                "--tier",
                "half",
                "--motion",
                "still",
                "--at",
                "20",
            ]
        )
        == 0
    )
    requested = preview._stage(source, args)
    requested.frame(20, 0, motion="still")
    earlier = preview._stage(source, args)
    earlier.frame(17, 0, motion="still")
    np.testing.assert_array_equal(captures[0], preview._raster(requested))
    assert not np.array_equal(captures[0], preview._raster(earlier))

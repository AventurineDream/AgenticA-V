"""Synthetic PCM covers visualizer timing, envelopes, views, decoding, and cache I/O."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from agentic_av.viz.audio import (
    ANALYSIS_REVISION,
    FPS,
    SAMPLE_RATE,
    SILENT,
    AudioError,
    Segment,
    analyze,
    decode_pcm,
    load_features,
)


def _clicks(bpm=120, duration=16, delay_s=0.5):
    pcm = np.zeros((int(duration * SAMPLE_RATE), 2), dtype=np.float32)
    rng = np.random.default_rng(4)
    length = int(0.012 * SAMPLE_RATE)
    pulse = rng.uniform(-0.8, 0.8, length).astype(np.float32) * np.linspace(1, 0, length)
    for t in np.arange(delay_s, duration - 0.1, 60 / bpm):
        start = round(t * SAMPLE_RATE)
        pcm[start : start + length] = pulse[:, None]
    return pcm


@pytest.mark.parametrize("hint", [None, 118.0, 120.0])
def test_click_tempo_and_beat_alignment(hint):
    features = analyze(_clicks(), (Segment(0, 16, hint),))
    assert features.tempo_bpm == pytest.approx(120, abs=1)
    beats = features.beats(1, 15)
    assert len(beats) >= 25
    expected = np.arange(1, 15, 0.5)
    assert np.max(np.min(abs(beats[:, None] - expected), axis=1)) <= 0.03


def test_sine_band_absolute_loudness_and_stereo():
    times = np.arange(3 * SAMPLE_RATE) / SAMPLE_RATE
    signal = (0.1 * np.sin(2 * np.pi * 1000 * times)).astype(np.float32)
    features = analyze(np.column_stack((np.zeros_like(signal), signal)))
    levels = features.sample(2)
    assert levels.bands[3] > 0.9
    assert levels.bands[0] < 0.01
    assert levels.loud == pytest.approx((20 * np.log10(0.05) + 54) / 48, abs=0.01)
    assert levels.balance == pytest.approx(1)
    assert levels.width > 0


def test_integrators_are_monotonic_and_clamp():
    features = analyze(_clicks())
    levels = [features.sample(t) for t in np.arange(0, 16, 0.031)]
    for attribute in ("beat", "travel", "drive"):
        assert np.all(np.diff([getattr(level, attribute) for level in levels]) >= 0)
    assert features.sample(-10).travel == 0
    assert features.sample(30).travel == features.sample(16).travel
    assert features.sample(5.001).travel >= features.sample(5).travel


def test_shifted_views_share_arrays_and_reset_all_time_bases():
    features = analyze(_clicks(), (Segment(0, 8, 120), Segment(8, 16, 120)))
    shifted = features.shifted(8, 4)
    assert shifted._frames is features._frames
    assert shifted._beat_times is features._beat_times
    assert shifted.duration_s == 4
    original = features.sample(8)
    local = shifted.sample(0)
    assert local.beat == pytest.approx(original.beat - np.floor(original.beat))
    assert local.travel == local.drive == 0
    assert local.loud == original.loud
    assert shifted.sample(2).travel == pytest.approx(features.sample(10).travel - original.travel)
    np.testing.assert_allclose(shifted.beats(0, 4), features.beats(8, 12) - 8)
    for band in ("low", "mid", "high"):
        t, strength = shifted.onsets(band, 0, 4)
        source_t, source_strength = features.onsets(band, 8, 12)
        np.testing.assert_allclose(t, source_t - 8)
        np.testing.assert_array_equal(strength, source_strength)
    nested = shifted.shifted(1, 2)
    assert nested.sample(0).travel == 0
    assert nested.sample(1).travel == pytest.approx(
        features.sample(10).travel - features.sample(9).travel
    )
    with pytest.raises(ValueError):
        shifted.onsets("bass", 0, 1)


@pytest.mark.parametrize("energy", [1, 0.35, 0])
def test_calmed_semantics(energy):
    full = replace(
        SILENT,
        bands=np.full(7, 0.8, dtype=np.float32),
        bass=0.8,
        mid=0.7,
        treble=0.6,
        loud=0.9,
        slow_bass=0.2,
        slow_loud=0.3,
        slow_centroid=0.1,
        flux=0.5,
        centroid=0.6,
        kick=1,
        snare=0.8,
        hat=0.7,
        beat=12.5,
        travel=8,
        drive=7,
        balance=-0.4,
        width=0.8,
    )
    calm = full.calmed(energy)
    assert (calm.beat, calm.travel, calm.drive) == (12.5, 8, 7)
    if energy == 1:
        assert calm is full
    else:
        assert calm.bass == pytest.approx(energy * (0.2 + energy * 0.6))
        assert calm.loud == pytest.approx(energy * (0.3 + energy * 0.6))
        assert calm.kick == energy
        assert calm.flux == 0.5 * energy
        assert calm.slow_centroid == 0.1 * energy
        np.testing.assert_allclose(calm.bands, calm.bass)
        if energy == 0:
            for name in (
                "mid",
                "treble",
                "slow_bass",
                "slow_loud",
                "centroid",
                "snare",
                "hat",
                "balance",
                "width",
            ):
                assert getattr(calm, name) == 0


def test_empty_and_silent_analysis():
    features = analyze(np.empty((0, 2), dtype=np.float32))
    assert features.duration_s == 0
    assert not features.beats(0, 1).size
    assert features.sample(0).loud == 0
    silent = analyze(np.zeros((SAMPLE_RATE, 2), dtype=np.float32))
    assert np.count_nonzero(silent.sample(0.5).bands) == 0
    assert silent.sample(1).travel == silent.sample(1).drive == 0


def test_segment_tempos_and_monotonic_boundary():
    first, second = _clicks(120, 10), _clicks(150, 10)
    features = analyze(np.concatenate((first, second)), (Segment(0, 10, 120), Segment(10, 20, 150)))
    assert features.shifted(0, 10).tempo_bpm == pytest.approx(120, abs=1)
    assert features.shifted(10, 10).tempo_bpm == pytest.approx(150, abs=1)
    assert features.sample(10).beat >= features.sample(9.99).beat


def test_delayed_beats_keep_integer_phase_in_shifted_and_nested_views():
    """Rebasing between detected beats must not move the musical beat phase."""
    features = analyze(_clicks(delay_s=0.24), (Segment(0, 16, 120),))
    shifted = features.shifted(0.37, 12)
    nested = shifted.shifted(0.21, 10)
    for view in (features, shifted, nested):
        beats = view.beats(0, view.duration_s)
        assert len(beats) > 15
        positions = np.array([view.sample(float(t)).beat for t in beats])
        np.testing.assert_allclose(positions, np.round(positions), atol=1e-4)
        assert np.all(np.diff(positions) > 0)
    assert 0.01 < shifted.sample(0).beat < 0.99
    assert 0.01 < nested.sample(0).beat < 0.99
    assert shifted.sample(0).travel == shifted.sample(0).drive == 0
    assert nested.sample(0).travel == nested.sample(0).drive == 0


def test_segment_grids_preserve_phase_and_monotonic_integrators():
    pcm = np.concatenate(
        (
            _clicks(120, 8, delay_s=0.24),
            _clicks(150, 8, delay_s=0.14),
        )
    )
    features = analyze(pcm, (Segment(0, 8, 120), Segment(8, 16, 150)))
    for view in (features, features.shifted(8.17, 7)):
        positions = np.array([view.sample(float(t)).beat for t in view.beats(0, view.duration_s)])
        np.testing.assert_allclose(positions, np.round(positions), atol=1e-4)
    levels = [features.sample(float(t)) for t in np.arange(7.8, 8.3, 0.001)]
    for attribute in ("beat", "travel", "drive"):
        assert np.all(np.diff([getattr(level, attribute) for level in levels]) >= 0)


@pytest.mark.parametrize("pcm", [np.zeros(2), np.full((5, 2), np.nan)])
def test_bad_pcm_raises_audio_error(pcm):
    with pytest.raises(AudioError):
        analyze(pcm)


def test_cache_hit_skips_decode_and_changed_segments_invalidate(tmp_path, monkeypatch):
    audio = tmp_path / "music.mp3"
    audio.write_bytes(b"audio")
    decode = Mock(return_value=_clicks(duration=3))
    monkeypatch.setattr("agentic_av.viz.audio.decode_pcm", decode)
    first = load_features(audio, (Segment(0, 3, 120),))
    second = load_features(audio, (Segment(0, 3, 120),))
    assert decode.call_count == 1
    np.testing.assert_array_equal(first._frames, second._frames)
    assert not second._frames.flags.writeable
    assert (tmp_path / f"music-a{ANALYSIS_REVISION}.npz").exists()
    load_features(audio, (Segment(0, 3, 100),))
    assert decode.call_count == 2
    audio.write_bytes(b"different audio")
    load_features(audio, (Segment(0, 3, 100),))
    assert decode.call_count == 3


@pytest.mark.parametrize("corrupt", [b"interrupted archive", b"PK\x03\x04"])
def test_concurrent_cache_publication_and_corruption_recovery(tmp_path, monkeypatch, corrupt):
    audio = tmp_path / "mix.mp3"
    audio.write_bytes(b"audio")
    decode = Mock(return_value=_clicks(duration=2))
    monkeypatch.setattr("agentic_av.viz.audio.decode_pcm", decode)
    (tmp_path / f"mix-a{ANALYSIS_REVISION}.npz").write_bytes(corrupt)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(load_features, (audio, audio)))
    assert results[0].sample(1).loud == results[1].sample(1).loud
    decode.reset_mock()
    load_features(audio)
    decode.assert_not_called()
    assert not list(tmp_path.glob("*.tmp"))


def test_decoder_uses_no_shell_and_stereo_float_output(monkeypatch):
    run = Mock(
        return_value=subprocess.CompletedProcess(
            [], 0, np.zeros((10, 2), dtype="<f4").tobytes(), b""
        )
    )
    monkeypatch.setattr("agentic_av.viz.audio.subprocess.run", run)
    pcm = decode_pcm(Path("name with ; shell.mp3"))
    assert pcm.shape == (10, 2) and pcm.dtype == np.float32
    args, kwargs = run.call_args
    assert args[0][args[0].index("-i") + 1] == "name with ; shell.mp3"
    assert args[0][args[0].index("-ac") + 1] == "2"
    assert args[0][args[0].index("-ar") + 1] == str(SAMPLE_RATE)
    assert "shell" not in kwargs


@pytest.mark.parametrize(
    "error", [FileNotFoundError(), subprocess.CalledProcessError(1, "ffmpeg", stderr=b"bad file")]
)
def test_decoder_failures_are_nonfatal_analysis_errors(monkeypatch, error):
    monkeypatch.setattr("agentic_av.viz.audio.subprocess.run", Mock(side_effect=error))
    with pytest.raises(AudioError):
        decode_pcm(Path("missing.mp3"))


def test_sampling_interpolates_at_analysis_rate():
    features = analyze(_clicks(duration=2))
    t = 0.5
    a, b = features.sample(t), features.sample(t + 1 / FPS)
    middle = features.sample(t + 0.5 / FPS)
    assert middle.loud == pytest.approx((a.loud + b.loud) / 2)

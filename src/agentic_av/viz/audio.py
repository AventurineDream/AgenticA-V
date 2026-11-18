"""Extract seekable musical signals for the numpy visualizer (plan §4.2).

Analysis uses bounded Hann-STFT chunks and numpy only. Frame-time sampling is
pure; decoding and atomic, versioned sidecar publication happen before playback.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from zipfile import BadZipFile

import numpy as np

ANALYSIS_REVISION = "2"
SAMPLE_RATE = 22050
N_FFT = 1024
HOP = 441
FPS = 50.0
BANDS = ("sub", "bass", "lowmid", "mid", "highmid", "high", "air")
_EDGES = (20, 60, 250, 500, 2000, 4000, 8000, 11025)
# Seven bands followed by the scalar fields in Levels, in declaration order.
_BASS, _LOUD, _SLOW_BASS, _SLOW_LOUD, _SLOW_CENTROID = 7, 10, 11, 12, 13
_BEAT, _TRAVEL, _DRIVE = 19, 20, 21


class AudioError(RuntimeError):
    """Audio cannot be decoded, analyzed, or stored; scenes may run silently."""


@dataclass(frozen=True, slots=True)
class Segment:
    """A half-open span of an audio file, in seconds, with an optional BPM hint."""

    start_s: float
    end_s: float
    bpm: float | None = None


@dataclass(frozen=True, slots=True)
class Levels:
    """One interpolated instant; envelopes are 0..1, integrators never decrease.

    Bands follow BANDS. Beat counts the detected beat grid; its fraction is phase.
    Travel/drive integrate loudness/bass in seconds; balance is -1 left to +1 right,
    and width is 0..1.
    """

    bands: np.ndarray
    bass: float
    mid: float
    treble: float
    loud: float
    slow_bass: float
    slow_loud: float
    slow_centroid: float
    flux: float
    centroid: float
    kick: float
    snare: float
    hat: float
    beat: float
    travel: float
    drive: float
    balance: float
    width: float

    def calmed(self, energy: float) -> Levels:
        """Return motion-safe signals without changing any elapsed integrator.

        Args:
            energy: Reactive gain, clamped to 0..1; 1 returns this object.

        Returns:
            Fast envelopes blended toward slow forms and then attenuated;
            zero gain silences every reactive field, including stereo motion.
        """
        energy = min(1.0, max(0.0, energy))
        if energy == 1.0:
            return self
        if energy == 0.0:
            return Levels(SILENT.bands, *([0.0] * 12), self.beat, self.travel, self.drive, 0, 0)
        slow = self.slow_loud

        def blend(fast, baseline):
            return energy * (baseline + energy * (fast - baseline))

        return Levels(
            energy * (self.slow_bass + energy * (self.bands - self.slow_bass)),
            blend(self.bass, self.slow_bass),
            blend(self.mid, slow),
            blend(self.treble, slow),
            blend(self.loud, slow),
            energy * self.slow_bass,
            energy * slow,
            energy * self.slow_centroid,
            energy * self.flux,
            blend(self.centroid, self.slow_centroid),
            energy * self.kick,
            energy * self.snare,
            energy * self.hat,
            self.beat,
            self.travel,
            self.drive,
            energy * self.balance,
            energy * self.width,
        )


_ZERO_BANDS = np.zeros(7, dtype=np.float32)
_ZERO_BANDS.flags.writeable = False
SILENT = Levels(_ZERO_BANDS, *([0.0] * 17))


@dataclass(frozen=True)
class Features:
    """Read-only analyzed frames and zero-copy movement views, sampled at 50 Hz.

    Public callers obtain this object from analyze/load_features, not its private
    array layout. Views retain the original arrays and expose movement-local time.
    """

    duration_s: float
    tempo_bpm: float
    _frames: np.ndarray = field(repr=False, compare=False)
    _beat_times: np.ndarray = field(repr=False, compare=False)
    _onset_times: tuple[np.ndarray, ...] = field(repr=False, compare=False)
    _onset_strengths: tuple[np.ndarray, ...] = field(repr=False, compare=False)
    _segments: tuple[tuple[float, float, float], ...] = ()
    _offset_s: float = 0.0
    _origins: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        for array in (self._frames, self._beat_times, *self._onset_times, *self._onset_strengths):
            array.flags.writeable = False

    def _row(self, t: float) -> np.ndarray:
        at = min(max(0.0, t), self.duration_s) + self._offset_s
        position = min(at * FPS, len(self._frames) - 1)
        lo = int(position)
        hi = min(lo + 1, len(self._frames) - 1)
        return self._frames[lo] + (self._frames[hi] - self._frames[lo]) * (position - lo)

    def sample(self, t: float) -> Levels:
        """Interpolate a clamped movement-local time in seconds, without I/O.

        Returns:
            Envelopes and local integrators, including silence for empty audio.
        """
        row = self._row(t)
        row[_BEAT : _DRIVE + 1] -= self._origins
        return Levels(row[:7], *map(float, row[7:]))

    def beats(self, t0: float, t1: float) -> np.ndarray:
        """Return beat times in the half-open local interval [t0, t1), seconds."""
        return self._times(self._beat_times, t0, t1)[0]

    def _times(self, times: np.ndarray, t0: float, t1: float) -> tuple[np.ndarray, slice]:
        lo = max(0.0, t0) + self._offset_s
        hi = min(self.duration_s, t1) + self._offset_s
        a, b = np.searchsorted(times, (lo, max(lo, hi)))
        selected = slice(a, b)
        return times[selected] - self._offset_s, selected

    def onsets(self, band: str, t0: float, t1: float) -> tuple[np.ndarray, np.ndarray]:
        """Return local onset times (seconds) and strengths in [t0, t1).

        Args:
            band: One of low, mid, high (kick/snare/hat analysis bands).
            t0: Inclusive local start, seconds.
            t1: Exclusive local end, seconds.

        Raises:
            ValueError: The band name is unknown.
        """
        index = ("low", "mid", "high").index(band)
        times, selected = self._times(self._onset_times[index], t0, t1)
        return times, self._onset_strengths[index][selected]

    def shifted(self, offset_s: float, duration_s: float) -> Features:
        """Return a zero-copy subview, preserving detected fractional beat phase.

        Args:
            offset_s: Start within this view, seconds, clamped to its duration.
            duration_s: Requested nonnegative duration in seconds, clipped to fit.

        Returns:
            A local view with only whole elapsed beats subtracted. Travel and
            drive start at zero; beat can start between zero and one.
        """
        offset = min(max(0.0, offset_s), self.duration_s)
        duration = min(max(0.0, duration_s), self.duration_s - offset)
        absolute = self._offset_s + offset
        tempo = next(
            (bpm for start, end, bpm in self._segments if start <= absolute < end),
            self.tempo_bpm,
        )
        origin_row = self._row(offset)
        origins = (
            math.floor(float(origin_row[_BEAT])),
            float(origin_row[_TRAVEL]),
            float(origin_row[_DRIVE]),
        )
        return Features(
            duration,
            tempo,
            self._frames,
            self._beat_times,
            self._onset_times,
            self._onset_strengths,
            self._segments,
            absolute,
            origins,
        )


def decode_pcm(path: Path) -> np.ndarray:
    """Decode a file with ffmpeg into stereo float32 PCM at 22050 Hz.

    Args:
        path: Audio file; passed as one argument, never through a shell.

    Returns:
        Read-only (samples, 2) array backed by ffmpeg's stdout bytes.

    Raises:
        AudioError: ffmpeg is missing, exits unsuccessfully, or emits invalid PCM.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(path),
                "-ac",
                "2",
                "-ar",
                str(SAMPLE_RATE),
                "-f",
                "f32le",
                "-",
            ],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as error:
        raise AudioError("ffmpeg is not installed; visualizer analysis unavailable") from error
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", b"").decode("utf-8", errors="replace").strip()
        raise AudioError(f"audio decode failed: {detail or error}") from error
    if not result.stdout or len(result.stdout) % 8:
        raise AudioError("ffmpeg returned empty or incomplete stereo PCM")
    return np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2)


def _normalize(values: np.ndarray) -> np.ndarray:
    low, high = np.percentile(values, (10, 95), axis=0)
    # Constant tones should occupy their band, not disappear because p10 == p95.
    low = np.where(high - low < 1e-4, np.minimum(low, -80.0), low)
    return np.clip((values - low) / np.maximum(high - low, 1e-5), 0, 1).astype(np.float32)


def _smooth(values: np.ndarray, rise_s: float, fall_s: float) -> np.ndarray:
    result = np.empty_like(values)
    state = np.zeros(values.shape[1:] or (), dtype=np.float32)
    rise, fall = math.exp(-1 / (FPS * rise_s)), math.exp(-1 / (FPS * fall_s))
    for i, value in enumerate(values):
        coefficient = np.where(value > state, rise, fall)
        state = value + coefficient * (state - value)
        result[i] = state
    return result


def _peaks(envelope: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # A causal 25-frame baseline and 180 ms lockout prevent ringing retriggers.
    sums = np.concatenate(([0.0], np.cumsum(envelope, dtype=np.float64)))
    indices = np.arange(len(envelope))
    starts = np.maximum(0, indices - 25)
    baseline = (sums[indices] - sums[starts]) / np.maximum(1, indices - starts)
    previous = np.r_[0, envelope[:-1]]
    following = np.r_[envelope[1:], 0]
    candidates = np.flatnonzero(
        (envelope > 1.6 * baseline)
        & (envelope > 0.04)
        & (envelope >= previous)
        & (envelope > following)
    )
    kept = []
    for index in candidates:
        if not kept or index - kept[-1] >= round(0.18 * FPS):
            kept.append(index)
        elif envelope[index] > envelope[kept[-1]]:
            kept[-1] = index
    selected = np.asarray(kept, dtype=np.int64)
    return selected, envelope[selected]


def _track_beats(flux: np.ndarray, hint: float | None) -> tuple[float, np.ndarray]:
    """Estimate tempo, then maximize onset reward plus Ellis log-interval cost."""
    if not len(flux) or np.max(flux) < 1e-6:
        return float(hint or 0), np.empty(0, dtype=np.float32)
    centered = flux - np.mean(flux)
    size = 1 << (2 * len(flux) - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=size)
    correlation = np.fft.irfft(spectrum * spectrum.conj(), n=size)[: len(flux)]
    minimum, maximum = (hint * 0.85, hint * 1.15) if hint else (50.0, 200.0)
    lags = np.arange(max(2, int(60 * FPS / maximum)), int(60 * FPS / minimum) + 1)
    lags = lags[lags < len(correlation) - 1]
    if not len(lags):
        return float(hint or 120), np.empty(0, dtype=np.float32)
    prior_center = hint or 120.0
    prior_width = 0.10 if hint else 0.7
    prior = np.exp(-0.5 * (np.log((60 * FPS / lags) / prior_center) / prior_width) ** 2)
    objective = np.maximum(0, correlation[lags]) * prior
    lag = int(lags[np.argmax(objective)])
    # Sub-frame parabolic refinement avoids integer-lag tempo quantization at 50 Hz.
    left, center, right = correlation[lag - 1 : lag + 2]
    denominator = left - 2 * center + right
    delta = np.clip(0.5 * (left - right) / denominator, -0.5, 0.5) if denominator else 0
    period = lag + delta
    tempo = 60 * FPS / period
    local = flux / max(float(np.std(flux)), 1e-6)
    # Small ±1-frame smoothing tolerates the STFT's 20 ms timing quantization.
    local = np.convolve(local, (0.2, 0.6, 0.2), mode="same")[: len(flux)]
    offsets = np.arange(max(1, int(period * 0.5)), int(period * 2) + 1)
    penalty = -100.0 * np.log(offsets / period) ** 2
    cumulative = np.zeros(len(flux), dtype=np.float32)
    backlink = np.full(len(flux), -1, dtype=np.int32)
    for i in range(len(flux)):
        valid = offsets <= i
        previous = i - offsets[valid]
        if len(previous):
            candidates = cumulative[previous] + penalty[valid]
            best = int(np.argmax(candidates))
            if candidates[best] > 0:
                backlink[i] = previous[best]
                cumulative[i] = candidates[best]
        cumulative[i] += local[i]
    tail = max(0, len(flux) - int(2 * period))
    last = tail + int(np.argmax(cumulative[tail:]))
    path = []
    while last >= 0:
        path.append(last)
        last = int(backlink[last])
    return float(tempo), np.asarray(path[::-1], dtype=np.float32) / FPS


def analyze(pcm: np.ndarray, segments: Sequence[Segment] = ()) -> Features:
    """Analyze stereo PCM into musical envelopes, onsets, and seekable positions.

    Args:
        pcm: (samples, 2) finite PCM at SAMPLE_RATE; not modified.
        segments: Nonoverlapping file-local spans in seconds, each with its BPM hint.
            Omitted means one span with free tempo search from 50 to 200 BPM.

    Returns:
        Read-only 50 Hz features; empty PCM yields silent, zero-duration features.

    Raises:
        AudioError: PCM shape/values or segment boundaries are invalid.
    """
    pcm = np.asarray(pcm)
    if pcm.ndim != 2 or pcm.shape[1] != 2:
        raise AudioError("analysis expects stereo PCM with shape (samples, 2)")
    duration = len(pcm) / SAMPLE_RATE
    spans = tuple(segments) or (Segment(0, duration),)
    previous_end = 0.0
    for segment in spans:
        if (
            not math.isfinite(segment.start_s)
            or not math.isfinite(segment.end_s)
            or segment.start_s < previous_end
            or segment.end_s < segment.start_s
            or (segment.bpm is not None and (not math.isfinite(segment.bpm) or segment.bpm <= 0))
        ):
            raise AudioError("segments must be ordered, nonoverlapping spans with positive BPM")
        previous_end = segment.end_s
    count = max(1, math.ceil(duration * FPS) + 1)
    frames = np.zeros((count, 24), dtype=np.float32)
    power = np.zeros((count, 7), dtype=np.float32)
    drum_power = np.zeros((count, 3), dtype=np.float32)
    flux = np.zeros(count, dtype=np.float32)
    window = np.hanning(N_FFT).astype(np.float32)
    frequencies = np.fft.rfftfreq(N_FFT, 1 / SAMPLE_RATE)
    masks = [(frequencies >= a) & (frequencies < b) for a, b in pairwise(_EDGES)]
    drums = [
        (frequencies >= a) & (frequencies < b) for a, b in ((35, 130), (1000, 2500), (3000, 10000))
    ]
    prior = np.zeros(N_FFT // 2 + 1, dtype=np.float32)
    # Centered, 1024-frame chunks cap FFT scratch space at ~30 MB, independent
    # of album duration. Even a 12-minute file never holds a full spectrogram.
    for first in range(0, count, 1024):
        stop = min(count, first + 1024)
        start_sample = first * HOP - N_FFT // 2
        end_sample = (stop - 1) * HOP + N_FFT // 2
        stereo = np.zeros((end_sample - start_sample, 2), dtype=np.float32)
        a, b = max(0, start_sample), min(len(pcm), end_sample)
        if b > a:
            stereo[a - start_sample : b - start_sample] = pcm[a:b]
        if not np.isfinite(stereo).all():
            raise AudioError("PCM contains non-finite values")
        windows = np.lib.stride_tricks.sliding_window_view(stereo, N_FFT, axis=0)[::HOP]
        mono = windows.mean(axis=1)
        magnitude = np.abs(np.fft.rfft(mono * window, axis=1)).astype(np.float32)
        energy = magnitude * magnitude / (N_FFT * np.sum(window * window))
        for j, mask in enumerate(masks):
            power[first:stop, j] = energy[:, mask].sum(axis=1)
        for j, mask in enumerate(drums):
            drum_power[first:stop, j] = energy[:, mask].sum(axis=1)
        logmag = np.log1p(magnitude)
        difference = np.diff(logmag, axis=0, prepend=prior[None, :])
        flux[first:stop] = np.maximum(difference, 0).mean(axis=1)
        prior = logmag[-1].copy()
        total = magnitude.sum(axis=1)
        frames[first:stop, 15] = (
            (magnitude @ frequencies) / np.maximum(total, 1e-9) / (SAMPLE_RATE / 2)
        )
        channel_power = (windows * windows).mean(axis=2)
        rms = np.sqrt(channel_power.mean(axis=1))
        frames[first:stop, _LOUD] = np.clip((20 * np.log10(np.maximum(rms, 1e-9)) + 54) / 48, 0, 1)
        frames[first:stop, 22] = (channel_power[:, 1] - channel_power[:, 0]) / np.maximum(
            channel_power.sum(axis=1), 1e-9
        )
        side = ((windows[:, 0] - windows[:, 1]) ** 2).mean(axis=1)
        frames[first:stop, 23] = np.clip(
            np.sqrt(side / np.maximum(2 * channel_power.sum(axis=1), 1e-9)), 0, 1
        )
    logpower = 10 * np.log10(np.maximum(power, 1e-12))
    bands = _normalize(logpower)
    bands[power < 1e-10] = 0
    frames[:, :7] = _smooth(bands, 0.03, 0.25)
    frames[:, 7] = frames[:, :2].mean(axis=1)
    frames[:, 8] = frames[:, 2:5].mean(axis=1)
    frames[:, 9] = frames[:, 5:7].mean(axis=1)
    frames[:, _SLOW_BASS] = _smooth(frames[:, _BASS], 1.2, 1.2)
    frames[:, _SLOW_LOUD] = _smooth(frames[:, _LOUD], 1.2, 1.2)
    frames[:, _SLOW_CENTROID] = _smooth(frames[:, 15], 3.0, 3.0)
    flux_scale = max(float(np.percentile(flux, 95)), 1e-6)
    frames[:, 14] = np.clip(flux / flux_scale, 0, 1)
    onset_times, onset_strengths = [], []
    for j, decay in enumerate((0.16, 0.18, 0.10)):
        novelty = np.maximum(np.diff(np.log1p(drum_power[:, j] * 10000), prepend=0), 0)
        novelty = np.clip(novelty / max(float(np.percentile(novelty, 95)), 1e-6), 0, 1)
        indices, strengths = _peaks(novelty)
        onset_times.append((indices / FPS).astype(np.float32))
        onset_strengths.append(strengths.astype(np.float32))
        pulses = np.zeros(count, dtype=np.float32)
        pulses[indices] = strengths
        state = 0.0
        coefficient = math.exp(-1 / (FPS * decay))
        for i, pulse in enumerate(pulses):
            state = max(float(pulse), state * coefficient)
            frames[i, 16 + j] = state
    times = np.arange(count) / FPS
    all_beats, tempos = [], []
    beat_origin = 0.0
    for segment in spans:
        start = min(count, max(0, round(segment.start_s * FPS)))
        end = min(count, max(start, round(segment.end_s * FPS)))
        tempo, beats = _track_beats(flux[start:end], segment.bpm)
        beats += start / FPS
        all_beats.append(beats)
        tempos.append((segment.start_s, min(duration, segment.end_s), tempo))
        period_s = 60 / tempo if tempo > 0 else 1
        if len(beats):
            positions = np.interp(times[start:end], beats, np.arange(len(beats)))
            before = times[start:end] < beats[0]
            after = times[start:end] > beats[-1]
            positions[before] = (times[start:end][before] - beats[0]) / period_s
            positions[after] = len(beats) - 1 + (times[start:end][after] - beats[-1]) / period_s
            # Each segment has its own detected grid. An integer translation
            # preserves phase at actual beats while preventing backward steps
            # when the next movement starts between beats on the previous grid.
            segment_origin = math.ceil(beat_origin - positions[0])
            frames[start:end, _BEAT] = segment_origin + positions
            beat_origin = float(frames[end - 1, _BEAT]) + 1 / (FPS * period_s)
        else:
            frames[start:end, _BEAT] = beat_origin
        frames[end:, _BEAT] = beat_origin
    # Left sums make the integrators exactly zero at the start, and monotonic
    # irrespective of seeks or downward changes in instantaneous loudness.
    frames[1:, _TRAVEL] = np.cumsum(frames[:-1, _LOUD], dtype=np.float64) / FPS
    frames[1:, _DRIVE] = np.cumsum(frames[:-1, _BASS], dtype=np.float64) / FPS
    beat_times = np.concatenate(all_beats).astype(np.float32)
    return Features(
        duration,
        tempos[0][2],
        frames,
        beat_times,
        tuple(onset_times),
        tuple(onset_strengths),
        tuple(tempos),
    )


def load_features(audio: Path, segments: Sequence[Segment] = ()) -> Features:
    """Load or atomically publish analyzed features beside an audio file.

    Args:
        audio: Cached audio file; its size and mtime invalidate stale analysis.
        segments: File-local movement spans and BPM hints; included in cache identity.

    Returns:
        Features without decoding on a valid cache hit. Concurrent writers use
        unique temporary files and atomic replacement, never partial archives.

    Raises:
        AudioError: Audio decoding, analysis, or cache I/O fails.
    """
    audio = Path(audio)
    cache = audio.with_name(f"{audio.stem}-a{ANALYSIS_REVISION}.npz")
    try:
        stat = audio.stat()
        identity = json.dumps(
            [
                ANALYSIS_REVISION,
                stat.st_size,
                stat.st_mtime_ns,
                [(s.start_s, s.end_s, s.bpm) for s in segments],
            ]
        )
        fingerprint = hashlib.sha256(identity.encode()).hexdigest()
        try:
            with np.load(cache, allow_pickle=False) as stored:
                if str(stored["fingerprint"]) == fingerprint:
                    return Features(
                        float(stored["duration"]),
                        float(stored["tempo"]),
                        stored["frames"],
                        stored["beats"],
                        tuple(stored[f"onset{i}"] for i in range(3)),
                        tuple(stored[f"strength{i}"] for i in range(3)),
                        tuple(map(tuple, stored["segments"].tolist())),
                    )
        except (OSError, ValueError, KeyError, EOFError, BadZipFile):
            pass
        features = analyze(decode_pcm(audio), segments)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=audio.parent, prefix=f".{cache.name}.", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                arrays = {
                    "fingerprint": fingerprint,
                    "duration": features.duration_s,
                    "tempo": features.tempo_bpm,
                    "frames": features._frames,
                    "beats": features._beat_times,
                    "segments": np.asarray(features._segments),
                }
                arrays.update({f"onset{i}": a for i, a in enumerate(features._onset_times)})
                arrays.update({f"strength{i}": a for i, a in enumerate(features._onset_strengths)})
                np.savez_compressed(stream, **arrays)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, cache)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return features
    except OSError as error:
        raise AudioError(f"audio analysis cache unavailable: {error}") from error

"""Native terminal playback of a bundled album movement.

`library.py` calls `play_native` when Enter selects a movement. Extraction
publishes cached MP3s and normalized score sidecars without modifying bundled
archives. mpv's media position remains authoritative; ffplay is a wall-clock
fallback. The numpy Stage paints terminal mosaics from audio features and score.

The playback loop owns picture time, input, and synchronized frame writes.
Analysis failures keep audio playable with an explicit quiet-visuals note.
Prefetch workers are daemon threads and never delay terminal cleanup.
The packaged archive is never modified.

The stage shares its rows with a catalog cover when one is available. The
still panel sits at the left edge and is repainted after a layout or scene
change. It is omitted silently when too narrow or short; a cover that fails
verification is omitted and noted in the transport.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import gzip
import hashlib
import json
import os
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from agentic_av.catalog import (
    Album,
    CatalogEntry,
    bundled_assets,
    format_clock,
    movement_duration_s,
)
from agentic_av.library import (
    AlbumError,
    _asset_stem,
    _atomic_write,
    album_cache_dir,
    read_bundled_album,
)
from agentic_av.paint import Cell, _text_row, render_ansi
from agentic_av.palette import Palette
from agentic_av.session import _REDUCED_FIELD_SCALE
from agentic_av.tty import (
    KeyDecoder,
    _on_sigterm,
    _size,
    _terminal_frame,
)
from agentic_av.viz.audio import AudioError, Features, Segment, load_features
from agentic_av.viz.caps import budget_tier, cell_aspect, detect_tier
from agentic_av.viz.cover import ArtworkError, load_cover, render_cover
from agentic_av.viz.encode import SYNC_BEGIN, SYNC_END
from agentic_av.viz.glyphs import TIER_ORDER, TIERS
from agentic_av.viz.scene import Movement
from agentic_av.viz.score import Score, normalize_track
from agentic_av.viz.stage import Stage

# Bump when sidecar fields change; warm plays never reparse the archive.
EXTRACT_REVISION = "3"

_VISUAL_LEAD_S = 0.025
_SEEK_STEP_S = 10.0
# Seconds a fresh movement's clock gets to settle after a seek before the
# elapsed-time auto-advance may fire. A stale first reading (the previous
# movement's position) must not end the new movement at once.
_SETTLE_S = 1.0
_ANALYSIS_LOCK = threading.Lock()
# Cover panel: at most 40% of the width, two blank columns before the stage, and omitted
# rather than shrunk below these sizes, so the stage always keeps its minimum share.
_COVER_SHARE = 0.4
_COVER_GAP = 2
_MIN_STAGE_COLS = 30
_MIN_COVER_ROWS = 6
# Album asset -> (visual family, `window.<NAME>` holding album JSON).
# Verified against each bundled archive; the names differ per player.
_ALBUM_DATA: dict[str, tuple[str, str]] = {
    # Coupon predates the `window.<NAME>` JSON; its movements are a
    # `const tracks=[...]` literal read by `_coupon_tracks`.
    "coupon-seance-saturn.html.gz": ("coupon", ""),
    "drowning-collective-are-we-fish.html.gz": ("aquatic", "BAND02_VISUAL_EVENTS"),
    "nurse-log-ground-moves-anyway.html.gz": ("forest", "NURSE_LOG_ALBUM"),
    "nurse-log-the-forest-has-a-pocket.html.gz": ("pocket", "NL2_ALBUM"),
    "quiet-machinery-atlas-unlit-rooms.html.gz": ("rooms", "QUIET_MACHINERY"),
    "drowning-collective-the-shape-that-stays.html.gz": ("undertow", "DC2_ALBUM"),
}


class NativeError(RuntimeError):
    """Native playback cannot start or recover; the caller shows the note."""


@dataclass(frozen=True, slots=True)
class TrackData:
    """Hold one movement's immutable cache metadata.

    Attributes:
        audio: Cached MP3 path, shared for a whole-album mix.
        offset_s: Movement start in media seconds.
        scene: Scene identifier within its visual family.
        scene_label: Listener-facing scene label.
        score: JSON-safe normalized composition payload.
    """

    audio: Path
    offset_s: float = 0.0
    scene: str = ""
    scene_label: str = ""
    score: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NativeAlbum:
    """Hold extracted tracks and single-flight analysis/query caches.

    Attributes:
        tracks: Movements in archive order.
        family: Scene registry family.
    """

    tracks: tuple[TrackData, ...]
    family: str
    _features: dict[Path, Features | None] = field(default_factory=dict, compare=False, repr=False)
    _signals: dict[int, tuple[Features | None, Score]] = field(
        default_factory=dict, compare=False, repr=False
    )
    _analysis_lock: Any = field(default_factory=lambda: _ANALYSIS_LOCK, compare=False, repr=False)


def _decode_base64(payload: str) -> bytes:
    """Decode one base64 payload, ignoring whitespace; raise `NativeError`."""
    try:
        return base64.b64decode(re.sub(r"\s+", "", payload), validate=True)
    except (binascii.Error, ValueError) as error:
        raise NativeError("album audio is not valid base64") from error


def _data_uri_payload(value: object) -> str | None:
    """Return the base64 body of an ``data:audio/...;base64,`` URI, else None."""
    if isinstance(value, str) and value.startswith("data:audio"):
        header, _, encoded = value.partition(",")
        if header.endswith(";base64") and encoded:
            return encoded
    return None


def _asset_manifest(html: str) -> dict[str, Any]:
    """Return Drowning's `band02-assets` JSON (path -> data URI), or {}."""
    match = re.search(r'<script[^>]*id="band02-assets"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise NativeError("album asset manifest is not JSON") from error
    return data if isinstance(data, dict) else {}


def _album_audio(html: str) -> str:
    """Return the base64 body of Coupon's single whole-album `<audio>` mix."""
    match = re.search(r"data:audio/mpeg;base64,([A-Za-z0-9+/=\s]+)", html)
    if not match:
        raise NativeError("album HTML has no embedded audio")
    return match.group(1)


def _track_audio(html: str, tracks: list[Any], family: str) -> list[tuple[str, float]]:
    """Return ``(base64 payload, offset_s)`` per movement.

    Coupon stores one album mix, so every movement shares it and starts at
    its `start`. Every other album stores one MP3 per movement. Both Nurse Log albums,
    Quiet Machinery and Drowning Collective A-02 inline a data URI in each track's
    `audio`. Drowning Collective A-01 alone uses relative `audio` paths keyed into
    its `band02-assets` manifest.
    """
    if family == "coupon":
        payload = _album_audio(html)
        return [
            (payload, float(item.get("start") or 0.0) if isinstance(item, dict) else 0.0)
            for item in tracks
        ]
    manifest: dict[str, Any] | None = None
    result: list[tuple[str, float]] = []
    for number, item in enumerate(tracks, start=1):
        ref = item.get("audio") if isinstance(item, dict) else None
        payload = _data_uri_payload(ref)
        if payload is None and isinstance(ref, str):
            if manifest is None:
                manifest = _asset_manifest(html)
            payload = _data_uri_payload(manifest.get(ref))
        if payload is None:
            raise NativeError(f"movement {number} has no embedded audio")
        result.append((payload, 0.0))
    return result


def _album_json(html: str, variable: str) -> dict[str, Any] | None:
    """Return the `window.<variable> = {...}` object, or None if absent."""
    match = re.search(rf"window\.{re.escape(variable)}\s*=\s*(\{{.*?\}})\s*;", html, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _coupon_tracks(html: str) -> list[dict[str, Any]] | None:
    """Return Coupon Seance's `const tracks=[...]` array as dicts, or None.

    This album's player predates the `window.<NAME>` JSON the other albums
    use; its movements live in a JS array literal with unquoted keys and
    single-quoted string values.
    We parse it with a tolerant regex per object rather than a JS engine.
    """
    match = re.search(r"const\s+tracks\s*=\s*\[(.*?)\]\s*;", html, re.DOTALL)
    if not match:
        return None
    body = match.group(1)
    objects = re.findall(r"\{([^{}]*)\}", body)
    tracks: list[dict[str, Any]] = []
    for obj in objects:
        fields: dict[str, Any] = {}
        for key, value in re.findall(
            r"(\w+)\s*:\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|[\d.]+|true|false|null)", obj
        ):
            if value.startswith(("'", '"')):
                fields[key] = value[1:-1]
            elif value in {"true", "false"}:
                fields[key] = value == "true"
            elif value == "null":
                fields[key] = None
            else:
                try:
                    fields[key] = float(value)
                except ValueError:
                    fields[key] = value
        palette = re.search(r"palette\s*:\s*\[([^\]]*)\]", obj)
        if palette:
            fields["palette"] = re.findall(r"#[0-9a-fA-F]{6}\b", palette[1])
        if "title" in fields:
            tracks.append(fields)
    return tracks or None


def _fallback_scenes(asset: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return stable movement identifiers for archives without scene metadata."""
    family = _ALBUM_DATA.get(asset, ("", ""))[0]
    if family == "coupon":
        return (
            ("arrival", "friction", "commerce", "pursuit", "memory", "gravity", "return"),
            ("Arrival", "Friction", "Commerce", "Pursuit", "Memory", "Gravity", "Return"),
        )
    if family == "aquatic":
        return ("kindness", "bass", "current", "downbeat", "air", "major"), ()
    return (), ()


def _track_data(
    track: dict[str, Any],
    index: int,
    audio: Path,
    offset_s: float,
    fallback_scenes: tuple[str, ...],
    fallback_labels: tuple[str, ...],
    family: str,
    html: str,
) -> TrackData:
    """Build `TrackData` for one track, tolerating missing visuals fields."""
    scene = str(track.get("scene") or "")
    label = str(track.get("scene_label") or track.get("scene") or "")
    if not scene and index < len(fallback_scenes):
        scene = fallback_scenes[index]
    if not label and index < len(fallback_labels):
        label = fallback_labels[index]
    return TrackData(
        audio=audio,
        offset_s=offset_s,
        scene=scene,
        scene_label=label,
        score=normalize_track(family, track, html),
    )


def _load_sidecar(path: Path, cache_dir: Path) -> NativeAlbum | None:
    """Return the album recorded in a score sidecar, or None if unusable.

    Any missing or empty MP3, or a malformed file, falls back to a full
    extraction rather than playing a half-populated cache.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tracks: list[TrackData] = []
        for item in data["tracks"]:
            audio = cache_dir / str(item["audio"])
            if audio.name != item["audio"] or audio.stat().st_size == 0:
                return None
            tracks.append(
                TrackData(
                    audio=audio,
                    offset_s=float(item["offset_s"]),
                    scene=str(item["scene"]),
                    scene_label=str(item["scene_label"]),
                    score=dict(item["score"]),
                )
            )
        family = str(data["family"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if family not in {item[0] for item in _ALBUM_DATA.values()} or not tracks:
        return None
    return NativeAlbum(tracks=tuple(tracks), family=family)


def _sidecar_bytes(album: NativeAlbum) -> bytes:
    """Serialize `album` for `_load_sidecar`; audio is stored by file name."""
    tracks = [
        {
            "audio": track.audio.name,
            "offset_s": track.offset_s,
            "scene": track.scene,
            "scene_label": track.scene_label,
            "score": dict(track.score),
        }
        for track in album.tracks
    ]
    return json.dumps({"family": album.family, "tracks": tracks}).encode("utf-8")


def extract_album(
    asset: str,
    cache_home: Path | None = None,
    source: bytes | None = None,
) -> NativeAlbum:
    """Decode one bundled album's audio and visuals data into the cache.

    The first call decodes the MP3s and writes a JSON sidecar with each
    movement's scene, offset, and normalized score. Later calls hash the
    archive bytes to find the sidecar, then skip decompression and parsing.
    Movements that share one payload (Coupon) share one file. `source` lets
    tests pass a tiny gzip instead of the bundled archives.

    Args:
        asset: Album asset basename from the public catalog.
        cache_home: XDG cache home override.
        source: Compressed HTML bytes; defaults to the packaged asset.

    Returns:
        `NativeAlbum` with cached audio and data for each movement.

    Raises:
        AlbumError: `asset` is not a bundled album or cannot be read.
        NativeError: The HTML lacks audio, data, or a usable structure.
        OSError: The cache cannot be published.
    """
    if asset not in bundled_assets():
        raise AlbumError(f"album asset {asset!r} is not in the public catalog")
    family, variable = _ALBUM_DATA.get(asset, ("", ""))
    if family not in {item[0] for item in _ALBUM_DATA.values()}:
        raise NativeError(f"no native scenes are defined for {asset}")
    data = read_bundled_album(asset) if source is None else source
    stem = _asset_stem(asset)
    digest = hashlib.sha256(data).hexdigest()[:16]
    cache_dir = album_cache_dir(cache_home)
    sidecar = cache_dir / f"{stem}-{digest}-r{EXTRACT_REVISION}.json"
    cached = _load_sidecar(sidecar, cache_dir)
    if cached is not None:
        return cached

    try:
        html = gzip.decompress(data).decode("utf-8")
    except (gzip.BadGzipFile, UnicodeDecodeError) as error:
        raise NativeError(f"{asset} is not gzip UTF-8 HTML") from error
    fallback_scenes, fallback_labels = _fallback_scenes(asset)

    album_data = _album_json(html, variable) if variable else None
    tracks = album_data.get("tracks") if album_data else None
    if tracks is None and family == "coupon":
        tracks = _coupon_tracks(html)
    if not isinstance(tracks, list) or not tracks:
        raise NativeError(f"{asset} has no track data for native playback")

    if family == "aquatic" and album_data:
        tracks = [
            {
                **item,
                **{name: album_data[name] for name in ("kinds", "voices") if name in album_data},
            }
            for item in tracks
        ]
    if family == "coupon":
        duration = re.search(r'const\s+ANALYSIS\s*=\s*\{[^}]*?"duration"\s*:\s*([\d.]+)', html)
        total = float(duration[1]) if duration else 0.0
        for index, item in enumerate(tracks):
            end = float(tracks[index + 1]["start"]) if index + 1 < len(tracks) else total
            item["duration"] = max(0.0, end - float(item.get("start", 0)))

    paths: dict[str, Path] = {}
    built: list[TrackData] = []
    for index, (payload, offset_s) in enumerate(_track_audio(html, tracks, family)):
        path = paths.get(payload)
        if path is None:
            # Coupon's movements all map to one file; others get one each.
            suffix = "" if family == "coupon" else f"-t{index + 1:02d}"
            path = cache_dir / f"{stem}-{digest}{suffix}-r{EXTRACT_REVISION}.mp3"
            if not path.exists() or path.stat().st_size == 0:
                _atomic_write(path, _decode_base64(payload))
            paths[payload] = path
        item = tracks[index]
        built.append(
            _track_data(item, index, path, offset_s, fallback_scenes, fallback_labels, family, html)
            if isinstance(item, dict)
            else TrackData(audio=path, offset_s=offset_s)
        )
    album = NativeAlbum(tracks=tuple(built), family=family)
    # Written last, after every MP3 is published, so a present sidecar
    # always points at complete audio.
    _atomic_write(sidecar, _sidecar_bytes(album))
    return album


def movement_signals(album: NativeAlbum, index: int) -> tuple[Features | None, Score]:
    """Return cached movement-local audio signals and a normalized score.

    Args:
        album: Extracted native album; owns the in-memory analysis/query cache.
        index: Zero-based movement number.

    Returns:
        A zero-copy movement Features view, or None if analysis raises AudioError,
        and its Score. Shared mixes are analyzed once with each movement's BPM.

    Raises:
        IndexError: The movement number is outside the album.
    """
    # A single lock covers cache lookup, decode, publication, and view creation.
    # A prefetch and an immediate n press must never analyze the same mix twice.
    with album._analysis_lock:
        if index in album._signals:
            return album._signals[index]
        track = album.tracks[index]
        score = Score.from_payload(track.score)
        if track.audio not in album._features:
            related = [item for item in album.tracks if item.audio == track.audio]
            segments = []
            for number, item in enumerate(related):
                duration = float(item.score.get("duration") or 0)
                end = (
                    related[number + 1].offset_s
                    if number + 1 < len(related)
                    else item.offset_s + duration
                )
                if end <= item.offset_s:
                    end = 1e12
                segments.append(Segment(item.offset_s, end, item.score.get("bpm")))
            try:
                album._features[track.audio] = load_features(track.audio, segments)
            except AudioError:
                album._features[track.audio] = None
        features = album._features[track.audio]
        if features is not None:
            duration = float(track.score.get("duration") or features.duration_s - track.offset_s)
            features = features.shifted(track.offset_s, duration)
        result = features, score
        album._signals[index] = result
        return result


@dataclass(slots=True)
class _AnalysisRequest:
    """Carry a foreground analysis result without blocking the terminal loop."""

    index: int
    done: threading.Event = field(default_factory=threading.Event)
    result: tuple[Features | None, Score] | None = None
    error: Exception | None = None


def _start_analysis_request(album: NativeAlbum, index: int) -> _AnalysisRequest:
    """Run one foreground signal lookup on a daemon thread.

    Args:
        album: Extracted album whose shared analysis lock may be held by prefetch.
        index: Zero-based movement being prepared.

    Returns:
        Request populated with signals or an exception once ``done`` is set.
    """
    request = _AnalysisRequest(index)

    def load() -> None:
        try:
            request.result = movement_signals(album, index)
        except Exception as error:
            request.error = error
        finally:
            request.done.set()

    threading.Thread(target=load, name="aav-current-analysis", daemon=True).start()
    return request


def _mpv_available() -> bool:
    return shutil.which("mpv") is not None


def _ffplay_available() -> bool:
    return shutil.which("ffplay") is not None


class Mpv:
    """Control audio through mpv JSON IPC while retaining its authoritative clock."""

    def __init__(self, media: Path, offset: float = 0.0) -> None:
        """Start mpv on `media` at `offset` seconds; raises `NativeError`."""
        self.path = Path(tempfile.gettempdir()) / f"aav-mpv-{os.getpid()}-{time.time_ns()}.sock"
        args = [
            "mpv",
            "--no-config",
            "--no-terminal",
            "--no-video",
            "--force-window=no",
            f"--input-ipc-server={self.path}",
        ]
        if offset > 0:
            args.append(f"--start={offset:.3f}")
        args.extend(["--", str(media)])
        try:
            self.proc = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as error:
            raise NativeError("mpv was not found") from error
        try:
            # mpv binds its IPC socket ~80 ms after exec; 2 s covers a cold
            # start without stalling the library when mpv dies first.
            deadline = time.monotonic() + 2.0
            while (
                not self.path.exists() and self.proc.poll() is None and time.monotonic() < deadline
            ):
                time.sleep(0.025)
            if not self.path.exists():
                raise NativeError("mpv IPC socket did not appear")
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            # 25 ms recv timeout, as in the original player's Mpv client.
            self.sock.settimeout(0.025)
            self.sock.connect(str(self.path))
        except OSError as error:
            self.close()
            raise NativeError(f"mpv IPC connect failed: {error}") from error
        except BaseException:
            # Includes SIGTERM (`_PlayerTerminatedError`) mid-startup: the
            # caller never receives this object, so it must not leave mpv
            # playing with no UI to stop it.
            self.close()
            raise
        self.buffer = b""
        self.request_id = 0

    def command(self, command: list[Any]) -> Any:
        """Send one mpv command and return its `data`, or None on timeout."""
        self.request_id += 1
        request_id = self.request_id
        payload = json.dumps({"command": command, "request_id": request_id}).encode() + b"\n"
        try:
            self.sock.sendall(payload)
        except (AttributeError, OSError):
            return None
        # Give up after 120 ms (about two frames) so a stalled mpv cannot
        # freeze the UI; a late reply is skipped by its request_id.
        deadline = time.monotonic() + 0.12
        while time.monotonic() < deadline:
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                self.buffer += chunk
            except TimeoutError:
                continue
            except OSError:
                break
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if response.get("request_id") == request_id:
                    return response.get("data")
        return None

    def get(self, name: str) -> Any:
        """Return one mpv property."""
        return self.command(["get_property", name])

    def seek(self, seconds: float) -> None:
        """Seek to `seconds` from the media start, absolute."""
        self.command(["seek", max(0.0, seconds), "absolute+exact"])

    def set_pause(self, paused: bool) -> None:
        """Pause or resume playback."""
        self.command(["set_property", "pause", paused])

    def close(self) -> None:
        """Terminate mpv and remove its socket; safe to call twice."""
        try:
            if hasattr(self, "sock"):
                self.sock.close()
        except OSError:
            pass
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                # Children exit on SIGTERM within tens of ms; kill after
                # 0.5 s so leaving playback never hangs.
                self.proc.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
            self.proc.wait()
        with contextlib.suppress(OSError):
            self.path.unlink(missing_ok=True)


class Ffplay:
    """ffplay audio-only fallback; wall clock from the requested start.

    ffplay cannot report position without video, so `position` counts
    seconds since launch minus pauses. With `-nodisp` and no stdin it has
    no pause key, so pause stops the process with SIGSTOP and resumes it
    with SIGCONT. Seek is unsupported. `close` terminates the child.
    """

    def __init__(self, media: Path, offset: float = 0.0) -> None:
        """Start ffplay on `media` at `offset` seconds; raises `NativeError`."""
        args = [
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-ss",
            f"{offset:.3f}",
            "-i",
            str(media),
        ]
        try:
            self.proc = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as error:
            raise NativeError("ffplay was not found") from error
        self._start = time.monotonic()
        self._paused_at: float | None = None
        self._paused_total = 0.0

    def position(self) -> float:
        """Seconds played since launch, minus pauses; `_position` adds the start offset."""
        now = time.monotonic()
        if self._paused_at is not None:
            return self._paused_at - self._start - self._paused_total
        return now - self._start - self._paused_total

    def seek(self, seconds: float) -> None:
        """Ffplay cannot seek mid-stream; always raises `NativeError`."""
        raise NativeError("ffplay cannot seek; choose another movement")

    def set_pause(self, paused: bool) -> None:
        """Stop or continue the ffplay child; track pause time for the clock."""
        if paused and self._paused_at is None:
            with contextlib.suppress(OSError):
                self.proc.send_signal(signal.SIGSTOP)
            self._paused_at = time.monotonic()
        elif not paused and self._paused_at is not None:
            with contextlib.suppress(OSError):
                self.proc.send_signal(signal.SIGCONT)
            self._paused_total += time.monotonic() - self._paused_at
            self._paused_at = None

    def close(self) -> None:
        """Terminate ffplay; safe to call twice."""
        try:
            if self.proc.poll() is None:
                # A stopped child queues SIGTERM until continued.
                self.proc.send_signal(signal.SIGCONT)
                self.proc.terminate()
                self.proc.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
            self.proc.wait()


def _player_for(media: Path, offset: float) -> Mpv | Ffplay:
    """Return an mpv controller when available, else ffplay, else raise."""
    if _mpv_available():
        return Mpv(media, offset)
    if _ffplay_available():
        return Ffplay(media, offset)
    raise NativeError("no audio player found; install mpv or ffplay")


def _position(player: Any, offset_s: float) -> float:
    """Current media position in seconds from the start of the audio file.

    mpv's `time-pos` is authoritative, and test fakes answer
    `get("time-pos")` the same way. ffplay's `position()` counts from the
    requested start, so `offset_s` is added back.
    """
    get = getattr(player, "get", None)
    if callable(get):
        raw = get("time-pos")
        if isinstance(raw, (int, float)):
            return float(raw)
    pos_fn = getattr(player, "position", None)
    if callable(pos_fn):
        return offset_s + pos_fn()
    return offset_s


_KEY_HINTS = ("space pause  ←/→ seek  n/p movement  m motion  g glyphs  q back", "q back")


def _status_line(
    width: int, state: str, clock: str, title: str, scene: str, motion: str, note: str
) -> str:
    """Fit the status text so state, clock, and a way out stay visible.

    Bundled titles make the full line ~110 columns, so at 80 the middle
    (title and scene) is truncated first. A note replaces the key hint and
    gives way to plain `q back` before it can push the clock off-screen.
    """
    left = f" {state}  {clock}"
    middle = f"  {title} · {scene}"
    if motion != "full":
        middle += f" · motion {motion}"
    rights = (f"{note}  q back", "q back") if note else _KEY_HINTS
    right = rights[-1]
    for candidate in rights:
        if len(left) + len(candidate) + 4 <= width:
            right = candidate
            break
    room = width - len(left) - len(right) - 2
    if room <= 0:
        line = f"{left}  {right}"
        if len(line) > width:
            # Too narrow for both: the way out wins over the clock.
            line = f" {right}"
        return line
    if len(middle) > room:
        middle = middle[: max(0, room - 1)] + "…"
    gap = " " * (width - len(left) - len(middle) - len(right) - 1)
    return f"{left}{middle}{gap}{right} "


@dataclass(frozen=True, slots=True)
class _Panel:
    """Terminal placement with a one-based top row and zero-based left column.

    Attributes:
        top: One-based terminal row of the panel's top edge.
        left: Zero-based column offset of the panel's left edge.
        cols: Panel width in character cells.
        rows: Panel height in character cells.
    """

    top: int
    left: int
    cols: int
    rows: int


@dataclass(frozen=True, slots=True)
class _Layout:
    """Column split of the canvas rows between the stage and an optional cover.

    Attributes:
        stage_left: Zero-based column offset of the stage's first cell.
        stage_cols: Stage width in character cells.
        cover: Panel for the album cover, or None when there is nothing to show.
    """

    stage_left: int
    stage_cols: int
    cover: _Panel | None


def _layout(width: int, canvas_rows: int, aspect: float, ratio: float | None) -> _Layout:
    """Place the cover left of the stage, or give the stage the whole canvas.

    The panel keeps the image's own proportions. A panel `cols` wide and `rows` tall
    spans `cols` by `rows * aspect` cell-widths of physical area, so its width over
    height equals `cols / (rows * aspect)`. The panel is vertically centered in the
    canvas rows. If it would fall below `_MIN_COVER_ROWS`, or the stage below
    `_MIN_STAGE_COLS`, no panel is drawn and the stage keeps the full width.

    Args:
        width: Terminal width in character cells, positive.
        canvas_rows: Rows shared by the stage and the panel, positive.
        aspect: Cell height divided by cell width, positive.
        ratio: Cover width divided by height, positive; None when there is no cover.

    Returns:
        The split for this terminal size.
    """
    whole = _Layout(stage_left=0, stage_cols=width, cover=None)
    if ratio is None or canvas_rows < _MIN_COVER_ROWS:
        return whole
    max_cols = min(int(width * _COVER_SHARE), width - _COVER_GAP - _MIN_STAGE_COLS)
    rows = min(canvas_rows, int(max_cols / (aspect * ratio)))
    if rows < _MIN_COVER_ROWS:
        return whole
    cols = min(max_cols, int(rows * aspect * ratio))
    return _Layout(
        stage_left=cols + _COVER_GAP,
        stage_cols=width - cols - _COVER_GAP,
        cover=_Panel(top=1 + (canvas_rows - rows) // 2, left=0, cols=cols, rows=rows),
    )


def _cover_tier(tier: str) -> str:
    """Return the mosaic tier that draws the cover.

    ASCII stays ASCII for consoles. Every other tier draws the cover with half blocks,
    the most widely rendered glyphs, so the still panel does not depend on finer glyphs.

    Args:
        tier: The stage's budgeted tier key.

    Returns:
        ``"ascii"`` or ``"half"``.
    """
    return "ascii" if tier == "ascii" else "half"


def _cover_pixels(album: Album) -> tuple[np.ndarray | None, str]:
    """Load the album's bundled cover, reporting a failed verification as a note.

    Args:
        album: Album whose catalog record may name a cover.

    Returns:
        Pixels and no note when the cover loads; ``(None, "")`` when the album has no
        cover; or ``(None, note)`` when a recorded cover fails verification.
    """
    if album.cover is None:
        return None, ""
    try:
        return load_cover(album.cover.asset, album.cover.sha256), ""
    except ArtworkError:
        return None, "cover art unavailable"


def _canvas_prefix(
    layout: _Layout, pixels: np.ndarray | None, canvas_rows: int, tier: str, color_mode: str
) -> bytes:
    """Return the bytes that repaint the cover panel after a layout or scene change.

    The canvas rows are erased first, because a previous layout may have left stage
    pixels in the panel and gap columns. Color modes reset SGR before erasing so an
    erased cell takes the default background, not the last stage cell's color. The stage
    rewrites its own columns in the same frame, since the caller invalidated its row state.

    Args:
        layout: Current column split.
        pixels: Decoded cover, or None.
        canvas_rows: Rows shared by the stage and the panel, positive.
        tier: The stage's budgeted tier; the cover uses `_cover_tier` of it.
        color_mode: ``truecolor``, ``256``, or ``none``.

    Returns:
        Cursor-addressed bytes inside the caller's synchronized frame. Empty when the
        layout has no cover.
    """
    panel = layout.cover
    if panel is None or pixels is None:
        return b""
    reset = b"" if color_mode == "none" else b"\x1b[0m"
    erase = reset + b"".join(b"\x1b[%d;1H\x1b[2K" % row for row in range(1, canvas_rows + 1))
    art = render_cover(
        pixels,
        cols=panel.cols,
        rows=panel.rows,
        tier=_cover_tier(tier),
        color_mode=color_mode,
        top=panel.top,
        left=panel.left,
    )
    return erase + art


def _joined_notes(*notes: str) -> str:
    """Join the non-empty transport notes with the status line's separator."""
    return " · ".join(note for note in notes if note)


def _movement(
    entry: CatalogEntry, family: str, data: TrackData, index: int, count: int
) -> Movement:
    """Build the immutable scene identity without process-randomized hashes."""
    payload = data.score
    meter = payload.get("meter")
    seed = int.from_bytes(
        hashlib.sha256(f"{entry.album.asset}:{index}".encode()).digest()[:8], "big"
    )
    return Movement(
        family=family,
        index=index,
        count=count,
        title=entry.track.title,
        scene=data.scene,
        label=data.scene_label or data.scene,
        duration_s=movement_duration_s(entry.album, entry.track),
        palette=tuple(payload.get("palette") or ()),
        bpm=payload.get("bpm"),
        meter=tuple(meter) if meter else None,
        seed=seed,
    )


def _write_output(target: Any, payload: bytes) -> None:
    """Write once to a binary terminal, or decode UTF-8 for a text-only sink."""
    binary = getattr(target, "buffer", None)
    stream = binary if binary is not None else target
    value = payload if binary is not None else payload.decode("utf-8")
    written = stream.write(value)
    if written is not None and written != len(value):
        raise OSError("short terminal frame write")
    stream.flush()


def _transport_bytes(
    entry: CatalogEntry,
    movement: Movement,
    score: Score,
    elapsed: float,
    width: int,
    height: int,
    palette: Palette,
    color_mode: str,
    *,
    playing: bool,
    motion: str,
    tier: str,
    note: str,
) -> bytes:
    """Paint absolute-addressed transport rows, including section progress ticks."""
    duration = movement.duration_s
    section = score.section(elapsed)
    label = section.name if section is not None else movement.label or movement.family
    clock = f"{format_clock(elapsed)} / {format_clock(duration)}"
    line = _status_line(
        width,
        "PLAYING" if playing else "PAUSED",
        clock,
        entry.track.title,
        f"{label} · {tier}",
        motion,
        note,
    )
    rows = []
    if height >= 10:
        progress = min(1.0, max(0.0, elapsed / duration)) if duration > 0 else 0.0
        filled = int(progress * width)
        accent = movement.palette[-1] if movement.palette else palette.accent
        ticks = {
            min(width - 1, int(item.start_s / duration * width))
            for item in score.sections
            if duration > 0
        }
        rows.append(
            [
                Cell(
                    "│" if col in ticks else "─",
                    accent if col < filled else palette.muted,
                    palette.background,
                )
                for col in range(width)
            ]
        )
    rows.append(_text_row(line, width, palette.foreground, palette.background))
    top = height - len(rows) + 1
    return f"\x1b[{top};1H".encode() + _terminal_frame(render_ansi(rows, color_mode)).encode()


# Picture speed per motion mode: reduced matches the visual player's 0.22x,
# still holds the picture as the original player's motion-off did.
_MOTION_RATES = {"full": 1.0, "reduced": _REDUCED_FIELD_SCALE, "still": 0.0}


def play_native(
    entry: CatalogEntry,
    album_entries: Sequence[CatalogEntry],
    palette: Palette,
    color_mode: str,
    *,
    motion: str = "full",
    glyphs: str = "auto",
    input_stream: Any = None,
    output_stream: Any = None,
    cache_home: Path | None = None,
    source: bytes | None = None,
    player_factory: Callable[[Path, float], Any] | None = None,
) -> str:
    """Play `entry`'s album natively in the terminal until q or Escape.

    Shows a loading line, extracts the album (decoded once into the cache;
    see `extract_album`), then runs the scene loop. Space pauses, arrows
    seek 10 s, n/p change movement, m toggles still motion, and g cycles glyph
    tiers. q/Escape return ``"quit"``. The caller's raw mode stays on: unlike the
    browser launch, mpv/ffplay get no stdin, so nothing needs the terminal
    restored and the child cannot eat keys.

    An album with a catalog cover shows it in a panel left of the stage. The panel
    is omitted silently when the terminal is too narrow or short; a cover that fails
    verification is omitted and noted in the transport.

    Args:
        entry: Selected movement.
        album_entries: Catalog entries; only those of `entry`'s album are
            used, in track order, so n/p stays inside the album.
        palette: Active palette for status chrome.
        color_mode: `render_ansi` mode: ``truecolor``, ``256``, or ``none``.
        motion: ``full``, ``reduced`` (0.22x picture), or ``still`` (held
            picture, as the original player's motion-off). Audio and the
            clock are unaffected. Seeks and movement changes move the held
            picture to the new time.
        glyphs: ``auto`` detects the terminal; otherwise a named mosaic tier.
        input_stream: TTY input; defaults to sys.stdin.
        output_stream: TTY output; defaults to sys.stdout.
        cache_home: XDG cache home override.
        source: Optional compressed HTML override for tests.
        player_factory: `(media_path, offset_s) -> player`; tests inject a
            fake. Defaults to mpv then ffplay.

    Returns:
        ``"quit"`` when the listener leaves playback.

    Raises:
        ValueError: Motion or glyph tier is unknown.
        NativeError: Extraction or player startup failed.
        AlbumError: The asset is not bundled.
        OSError: The cache cannot be written.
        _PlayerTerminatedError: SIGTERM arrived; the audio child is already
            stopped, and the caller restores the terminal and exits.
    """
    if motion not in _MOTION_RATES:
        raise ValueError(f"unknown motion mode {motion!r}")
    if glyphs != "auto" and glyphs not in TIERS:
        raise ValueError(f"unknown glyph tier {glyphs!r}")
    moving = motion if motion != "still" else "full"
    source_stream = input_stream or sys.stdin
    target = output_stream or sys.stdout
    fd = source_stream.fileno()
    width, height = _size(fd)
    loading = _text_row(
        f" Listening… {entry.album.title}", width, palette.foreground, palette.background
    )
    _write_output(
        target, ("\x1b[H" + _terminal_frame(render_ansi([loading], color_mode)) + "\x1b[J").encode()
    )
    album = extract_album(entry.album.asset, cache_home, source)
    entries = sorted(
        (e for e in album_entries if e.album.asset == entry.album.asset),
        key=lambda e: e.track.number,
    ) or [entry]
    entries = entries[: len(album.tracks)]
    index = next((i for i, e in enumerate(entries) if e.track.number == entry.track.number), 0)
    requested_tier = detect_tier(os.environ) if glyphs == "auto" else glyphs
    canvas_rows = max(1, height - (2 if height >= 10 else 1))
    aspect = cell_aspect(fd)
    cover_pixels, cover_note = _cover_pixels(entry.album)
    ratio = None if cover_pixels is None else cover_pixels.shape[1] / cover_pixels.shape[0]
    layout = _layout(width, canvas_rows, aspect, ratio)
    tier = budget_tier(requested_tier, layout.stage_cols, canvas_rows)
    stage = Stage(
        layout.stage_cols,
        canvas_rows,
        tier=tier,
        color_mode=color_mode,
        cell_aspect=aspect,
        left=layout.stage_left,
    )
    anchor_scene = anchor_clock = 0.0
    scene_s = 0.0
    captured_clock: tuple[float, float] | None = None
    factory = player_factory or _player_for
    player: Any = None
    decoder = KeyDecoder()
    playing = True
    note = ""
    dirty = True
    repaint = False
    pending_open = True
    opened_at = 0.0
    prefetch: threading.Thread | None = None
    analysis_request: _AnalysisRequest | None = None
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        while True:
            started = time.monotonic()
            data = album.tracks[index]
            if pending_open:
                signal_data = album._signals.get(index)
                if (
                    signal_data is None
                    and analysis_request is not None
                    and analysis_request.done.is_set()
                ):
                    request, analysis_request = analysis_request, None
                    if request.index == index:
                        if request.error is not None:
                            raise request.error
                        signal_data = request.result
                if signal_data is None:
                    if analysis_request is None:
                        analysis_request = _start_analysis_request(album, index)
                    if analysis_request.index != index or not analysis_request.done.is_set():
                        loading = _terminal_frame(
                            render_ansi(
                                [
                                    _text_row(
                                        f" Listening… {entries[index].track.title}",
                                        width,
                                        palette.foreground,
                                        palette.background,
                                    )
                                ],
                                color_mode,
                            )
                        )
                        _write_output(
                            target, SYNC_BEGIN + ("\x1b[1;1H" + loading).encode() + SYNC_END
                        )
                        timeout = 0.05
                        remaining = decoder.hold_remaining()
                        if remaining is not None:
                            timeout = min(timeout, remaining)
                        readable, _, _ = select.select([fd], [], [], timeout)
                        keys = decoder.feed(os.read(fd, 64)) if readable else decoder.flush()
                        step = 0
                        for key in keys:
                            if key in ("q", "Q", "esc", "quit"):
                                return "quit"
                            if key in ("n", "j", "down"):
                                step += 1
                            elif key in ("p", "k", "up"):
                                step -= 1
                        if step:
                            index = (index + step) % len(entries)
                            # The in-flight analysis is for the old movement.
                            # Drop it so the next iteration starts a fresh
                            # request for the new index instead of waiting
                            # out the stale one; a late n/p during loading
                            # must not make the player feel stuck and invite
                            # a second press that overshoots by one more.
                            analysis_request = None
                        continue
                    request, analysis_request = analysis_request, None
                    if request.error is not None:
                        raise request.error
                    signal_data = request.result
                if signal_data is None:
                    raise NativeError("movement analysis completed without a result")
                features, score = signal_data
                movement = _movement(entries[index], album.family, data, index, len(entries))
                stage.open(movement, features, score)
                stage.repaint()
                note = _joined_notes(
                    "" if features is not None else "audio analysis unavailable · quiet visuals",
                    cover_note,
                )
                player = factory(data.audio, data.offset_s)
                pending_open = False
                # A fresh player's clock can still report the previous
                # movement's position until its seek settles. Do not let
                # that stale reading end the new movement (which would skip
                # forward and can wrap to track 1). Give the seek a short
                # window to settle; process exit still ends the movement
                # promptly, so this only delays the elapsed-time fallback.
                # `started` is this iteration's clock read, so recording it
                # costs no extra tick.
                opened_at = started
                dirty = repaint = True
                captured_clock = None
            # No executor shutdown/join: analysis must never hold q or SIGTERM hostage.
            next_index = (index + 1) % len(entries)
            if (prefetch is None or not prefetch.is_alive()) and next_index not in album._signals:
                prefetch = threading.Thread(
                    target=movement_signals,
                    args=(album, next_index),
                    name="aav-analysis",
                    daemon=True,
                )
                prefetch.start()
            duration = movement.duration_s
            size = _size(fd)
            if size != (width, height):
                width, height = size
                canvas_rows = max(1, height - (2 if height >= 10 else 1))
                layout = _layout(width, canvas_rows, aspect, ratio)
                stage.resize(layout.stage_cols, canvas_rows, left=layout.stage_left)
                dirty = repaint = True
            desired_tier = budget_tier(requested_tier, layout.stage_cols, canvas_rows)
            if desired_tier != tier:
                tier = desired_tier
                stage.set_tier(tier)
                dirty = repaint = True
            elapsed = max(0.0, _position(player, data.offset_s) - data.offset_s)
            if playing:
                scene_s = max(0.0, anchor_scene + (elapsed - anchor_clock) * _MOTION_RATES[motion])
            held = not playing or motion == "still"
            if dirty or not held:
                if held and captured_clock is not None:
                    frame_t, frame_tau = captured_clock
                else:
                    lead = _VISUAL_LEAD_S if not held else 0.0
                    frame_t = min(duration, elapsed + lead)
                    frame_tau = scene_s + lead * _MOTION_RATES[motion]
                canvas = stage.frame(frame_t, frame_tau, motion=motion)
                captured_clock = frame_t, frame_tau
                dirty = False
            if height == 1:
                canvas = b""
            prefix = b""
            if repaint:
                prefix = _canvas_prefix(layout, cover_pixels, canvas_rows, tier, color_mode)
                repaint = False
            transport = _transport_bytes(
                entries[index],
                movement,
                score,
                elapsed,
                width,
                height,
                palette,
                color_mode,
                playing=playing,
                motion=motion,
                tier=tier,
                note=note,
            )
            _write_output(target, SYNC_BEGIN + prefix + canvas + transport + SYNC_END)
            period = 0.2 if held else 1.0 / 30.0
            # Each deadline begins with this frame; slow draws drop frames, never catch up.
            timeout = max(0.0, period - (time.monotonic() - started))
            remaining = decoder.hold_remaining()
            if remaining is not None:
                timeout = min(timeout, remaining)
            readable, _, _ = select.select([fd], [], [], timeout)
            keys = decoder.feed(os.read(fd, 64)) if readable else decoder.flush()
            step = 0
            for key in keys:
                if key in ("q", "Q", "esc", "quit"):
                    return "quit"
                if key == " ":
                    playing = not playing
                    player.set_pause(not playing)
                    anchor_clock, anchor_scene = elapsed, scene_s
                elif key in ("m", "M"):
                    motion = moving if motion == "still" else "still"
                    anchor_clock = elapsed
                    anchor_scene = elapsed if motion == "full" else scene_s
                elif key in ("g", "G"):
                    requested_tier = TIER_ORDER[(TIER_ORDER.index(tier) + 1) % len(TIER_ORDER)]
                    dirty = True
                elif key in ("left", "right"):
                    delta = _SEEK_STEP_S if key == "right" else -_SEEK_STEP_S
                    rel = min(duration, max(0.0, elapsed + delta))
                    try:
                        player.seek(data.offset_s + rel)
                    except NativeError as error:
                        note = str(error)
                    else:
                        elapsed = rel
                        anchor_scene = anchor_clock = scene_s = rel
                        stage.seek()
                        dirty = True
                        captured_clock = None
                elif key in ("n", "j", "down"):
                    step += 1
                elif key in ("p", "k", "up"):
                    step -= 1
            if step == 0:
                proc = getattr(player, "proc", None)
                returncode = proc.poll() if proc is not None else None
                if returncode is not None:
                    if returncode != 0:
                        raise NativeError(
                            f"audio player exited with status {returncode}; playback stopped"
                        )
                    step = 1
                elif started - opened_at >= _SETTLE_S and elapsed >= duration:
                    step = 1
            if step:
                index = (index + step) % len(entries)
                player.close()
                player = None
                pending_open = True
                anchor_scene = anchor_clock = 0.0
                playing = True
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            if player is not None:
                player.close()
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)

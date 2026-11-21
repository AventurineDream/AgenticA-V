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
framed, captioned panel sits at the left and is repainted after a layout or
scene change. It is omitted silently when too narrow or short; a cover that
fails verification is omitted and noted in the transport. `nowplaying.py`
composes that panel, the loading splash, the movement title card, and the
transport; this module decides when each is drawn.
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

from agentic_av import nowplaying
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
from agentic_av.palette import Palette
from agentic_av.session import _REDUCED_FIELD_SCALE
from agentic_av.tty import (
    KeyDecoder,
    _on_sigterm,
    _size,
)
from agentic_av.viz.audio import AudioError, Features, Segment, load_features
from agentic_av.viz.caps import budget_tier, cell_aspect, detect_tier
from agentic_av.viz.cover import ArtworkError, cover_accent, load_cover, prepare_cover
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
# Album asset -> (visual family, `window.<NAME>` holding album JSON).
# Verified against each bundled archive; the names differ per player.
_ALBUM_DATA: dict[str, tuple[str, str]] = {
    # Coupon predates the `window.<NAME>` JSON; its movements are a
    # `const tracks=[...]` literal read by `_coupon_tracks`.
    "coupon-seance-saturn.html.gz": ("coupon", ""),
    "coupon-seance-buy-one-haunt-one-free.html.gz": ("haunt", "CS2_ALBUM"),
    "drowning-collective-are-we-fish.html.gz": ("aquatic", "BAND02_VISUAL_EVENTS"),
    "nurse-log-ground-moves-anyway.html.gz": ("forest", "NURSE_LOG_ALBUM"),
    "nurse-log-the-forest-has-a-pocket.html.gz": ("pocket", "NL2_ALBUM"),
    "quiet-machinery-atlas-unlit-rooms.html.gz": ("rooms", "QUIET_MACHINERY"),
    "drowning-collective-the-shape-that-stays.html.gz": ("undertow", "DC2_ALBUM"),
    "quiet-machinery-instruments-for-measuring-dusk.html.gz": ("dusk", "QM2_ALBUM"),
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
    accent: str,
) -> bytes:
    """Paint absolute-addressed transport rows, including section progress ticks."""
    duration = movement.duration_s
    section = score.section(elapsed)
    label = section.name if section is not None else movement.label or movement.family
    parts = nowplaying.status_parts(
        width,
        playing=playing,
        clock=f"{format_clock(elapsed)} / {format_clock(duration)}",
        position=f"{movement.index + 1}/{movement.count}" if movement.count > 1 else "",
        title=entry.track.title,
        scene=f"{label} · {tier}",
        motion=motion,
        note=note,
    )
    ticks = {
        min(width - 1, int(item.start_s / duration * width))
        for item in score.sections
        if duration > 0 and item.start_s > 0
    }
    return nowplaying.transport(
        width,
        height,
        progress=elapsed / duration if duration > 0 else 0.0,
        ticks=ticks,
        parts=parts,
        palette=palette,
        accent=accent,
        color_mode=color_mode,
    )


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

    A splash appears during extraction, then audio drives the album-specific
    scene. Space or k pauses, j/l seek by ten seconds, and left/right switch
    movements; n/p and up/down remain movement aliases. m toggles motion, g
    cycles glyph tiers, and f toggles a chrome-free full-screen stage. Full-screen
    state persists across movements and terminal resizes.
    The caller's raw mode stays on: mpv and ffplay get no stdin, so the child
    cannot consume keys and terminal cleanup remains with the library. The
    cover panel is omitted when too narrow or short, and a cover that fails
    verification is noted in the transport.
    Side effects: Starts audio playback, writes terminal frames, and publishes extracted
        media/analysis cache files.

    Args:
        entry: Selected album movement.
        album_entries: Catalog rows from which this album's movement order is taken.
        palette: Active theme roles for transport and cover caption.
        color_mode: ``truecolor``, ``256``, or ``none`` terminal output mode.
        motion: ``full``, ``reduced``, or ``still`` picture motion.
        glyphs: ``auto`` or an explicit mosaic tier.
        input_stream: TTY input, defaulting to standard input.
        output_stream: TTY output, defaulting to standard output.
        cache_home: Optional cache root for materialized playback data.
        source: Optional gzip archive bytes for deterministic tests.
        player_factory: Optional ``(path, offset_s)`` audio-player factory.

    Returns:
        ``quit`` when the listener returns to the library.

    Raises:
        ValueError: Motion or glyph tier is unknown.
        NativeError: Extraction or player startup failed.
        AlbumError: The asset is not bundled.
        OSError: The cache cannot be written.
        _PlayerTerminatedError: SIGTERM arrived; the caller restores the terminal.
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
    aspect = cell_aspect(fd)
    requested_tier = detect_tier(os.environ) if glyphs == "auto" else glyphs
    cover_pixels, cover_note = _cover_pixels(entry.album)
    cover: np.ndarray | None = None
    ratio: float | None = None
    cover_rgb: tuple[int, int, int] | None = None
    if cover_pixels is not None:
        # Prepared once: every later repaint fits the cover in a few milliseconds.
        cover = prepare_cover(cover_pixels)
        ratio = cover_pixels.shape[1] / cover_pixels.shape[0]
        cover_rgb = cover_accent(cover_pixels)
    # Without a cover the accent follows each movement's palette once it opens.
    accent = nowplaying.album_accent(cover_rgb, (), palette)
    splash_bytes = nowplaying.splash(
        title=entry.album.title,
        artist=entry.album.artist,
        cover=cover,
        ratio=ratio,
        width=width,
        height=height,
        aspect=aspect,
        tier=requested_tier,
        palette=palette,
        accent=accent,
        color_mode=color_mode,
        status=f" Listening… {entry.track.title}",
    )
    _write_output(target, SYNC_BEGIN + splash_bytes + SYNC_END)
    album = extract_album(entry.album.asset, cache_home, source)
    entries = sorted(
        (e for e in album_entries if e.album.asset == entry.album.asset),
        key=lambda e: e.track.number,
    ) or [entry]
    entries = entries[: len(album.tracks)]
    index = next((i for i, e in enumerate(entries) if e.track.number == entry.track.number), 0)
    full_screen = False
    canvas_rows = max(1, height - (2 if height >= nowplaying.RAIL_MIN_ROWS else 1))
    layout = nowplaying.layout(width, canvas_rows, aspect, ratio)
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
    card_drawn = False
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
                        loading = nowplaying.status_row(
                            height,
                            width,
                            f" Listening… {entries[index].track.title}",
                            palette,
                            color_mode,
                        )
                        if card_drawn and stage.cells is not None:
                            # The previous movement's card would otherwise sit beside
                            # the new title for the whole wait: restore its picture.
                            stage.repaint()
                            loading = stage.encoder.encode(stage.cells, left=stage.left) + loading
                            card_drawn = False
                        _write_output(target, SYNC_BEGIN + loading + SYNC_END)
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
                            if key in ("n", "right", "down"):
                                step += 1
                            elif key in ("p", "left", "up"):
                                step -= 1
                            elif key in (" ", "k", "K"):
                                playing = not playing
                            elif key in ("f", "F"):
                                full_screen = not full_screen
                                canvas_rows = (
                                    height
                                    if full_screen
                                    else max(
                                        1, height - (2 if height >= nowplaying.RAIL_MIN_ROWS else 1)
                                    )
                                )
                                layout = (
                                    nowplaying.Layout(0, width, None)
                                    if full_screen
                                    else nowplaying.layout(width, canvas_rows, aspect, ratio)
                                )
                                stage.resize(layout.stage_cols, canvas_rows, left=layout.stage_left)
                                # Match the playback loop so the new layout paints right away.
                                dirty = repaint = True
                        if step:
                            index = (index + step) % len(entries)
                            # The in-flight analysis is for the old movement.
                            # Drop it so the next iteration starts a fresh
                            # request for the new index instead of waiting
                            # out the stale one; a late movement key during
                            # loading must not make the player feel stuck and invite
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
                accent = nowplaying.album_accent(cover_rgb, movement.palette, palette)
                note = _joined_notes(
                    "" if features is not None else "audio analysis unavailable · quiet visuals",
                    cover_note,
                )
                player = factory(data.audio, data.offset_s)
                if not playing:
                    player.set_pause(True)
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
                canvas_rows = (
                    height
                    if full_screen
                    else max(1, height - (2 if height >= nowplaying.RAIL_MIN_ROWS else 1))
                )
                layout = (
                    nowplaying.Layout(0, width, None)
                    if full_screen
                    else nowplaying.layout(width, canvas_rows, aspect, ratio)
                )
                stage.resize(layout.stage_cols, canvas_rows, left=layout.stage_left)
                dirty = repaint = True
            desired_tier = budget_tier(requested_tier, layout.stage_cols, canvas_rows)
            if desired_tier != tier:
                tier = desired_tier
                stage.set_tier(tier)
                dirty = repaint = True
            elapsed = max(0.0, _position(player, data.offset_s) - data.offset_s)
            card_live = started - opened_at < nowplaying.TITLE_CARD_S
            if card_drawn and not card_live:
                # The card covered cells the stage's encoder believes are on screen.
                stage.repaint()
                dirty = True
                card_drawn = False
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
            card = b""
            if height == 1 and not full_screen:
                canvas = b""
            elif card_live:
                card = nowplaying.title_card(
                    stage.cells,
                    layout,
                    canvas_rows,
                    number=index + 1,
                    count=len(entries),
                    title=entries[index].track.title,
                    age_s=started - opened_at,
                    fade=motion == "full" and color_mode == "truecolor",
                    palette=palette,
                    accent=accent,
                    color_mode=color_mode,
                )
                card_drawn = card_drawn or bool(card)
            prefix = b""
            if repaint:
                prefix = nowplaying.canvas_prefix(
                    layout,
                    cover,
                    canvas_rows,
                    tier,
                    color_mode,
                    title=entry.album.title,
                    artist=entry.album.artist,
                    palette=palette,
                    accent=accent,
                )
                repaint = False
            transport = (
                b""
                if full_screen
                else _transport_bytes(
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
                    accent=accent,
                )
            )
            _write_output(target, SYNC_BEGIN + prefix + canvas + card + transport + SYNC_END)
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
                if key in (" ", "k", "K"):
                    playing = not playing
                    player.set_pause(not playing)
                    anchor_clock, anchor_scene = elapsed, scene_s
                elif key in ("f", "F"):
                    full_screen = not full_screen
                    canvas_rows = (
                        height
                        if full_screen
                        else max(1, height - (2 if height >= nowplaying.RAIL_MIN_ROWS else 1))
                    )
                    layout = (
                        nowplaying.Layout(0, width, None)
                        if full_screen
                        else nowplaying.layout(width, canvas_rows, aspect, ratio)
                    )
                    stage.resize(layout.stage_cols, canvas_rows, left=layout.stage_left)
                    dirty = repaint = True
                elif key in ("m", "M"):
                    motion = moving if motion == "still" else "still"
                    anchor_clock = elapsed
                    anchor_scene = elapsed if motion == "full" else scene_s
                elif key in ("g", "G"):
                    requested_tier = TIER_ORDER[(TIER_ORDER.index(tier) + 1) % len(TIER_ORDER)]
                    dirty = True
                elif key in ("j", "J", "l", "L"):
                    delta = _SEEK_STEP_S if key in ("l", "L") else -_SEEK_STEP_S
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
                elif key in ("right", "n", "down"):
                    step += 1
                elif key in ("left", "p", "up"):
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
                scene_s = 0.0
                playing = True
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            if player is not None:
                player.close()
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)

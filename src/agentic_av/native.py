"""Native terminal playback of a bundled album movement.

`library.py` calls `play_native` when Enter selects a track. Each bundled
`.html.gz` holds base64 MP3 audio (one album mix for Coupon Seance, one
file per movement for the other three) and per-track scenes and scored
note events. This module decodes both once into the versioned XDG cache,
beside the browser materialization, and plays the audio through `mpv`
JSON IPC. mpv is the clock: its `time-pos` drives the glyph scene in
`scenes.py`, so the visuals follow the same audio the listener hears.
Without mpv, `ffplay` plays the audio and the scene follows wall time from
the requested start.

Keys inside playback: space pause/resume, left/right seek 10 s, n/p next or
previous movement, m toggles still motion, q or Escape return to the
library. The terminal stays in raw mode; mpv gets no stdin so it cannot
eat keys. Every exit path, including SIGTERM, terminates the audio child.
The packaged archive is never modified.
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
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_av.catalog import (
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
from agentic_av.scenes import (
    AQUATIC_SCENES,
    COUPON_SCENE_LABELS,
    COUPON_SCENES,
    FAMILIES,
    Canvas,
    EventIndex,
    draw_scene,
    normalize_events,
    scene_colors,
)
from agentic_av.session import _REDUCED_FIELD_SCALE
from agentic_av.tty import (
    KeyDecoder,
    _on_sigterm,
    _size,
    _terminal_frame,
)

# Bump when the decoded cache layout changes. The filename already hashes
# the gzip source bytes, so this only separates old cache generations.
EXTRACT_REVISION = "1"

_MPVPOLL_S = 1.0 / 15.0
_SEEK_STEP_S = 10.0

# Album asset -> (visual family, `window.<NAME>` holding album JSON).
# Verified against each bundled archive; the names differ per player.
_ALBUM_DATA: dict[str, tuple[str, str]] = {
    # Coupon predates the `window.<NAME>` JSON; its movements are a
    # `const tracks=[...]` literal read by `_coupon_tracks`.
    "coupon-seance-saturn.html.gz": ("coupon", ""),
    "drowning-collective-are-we-fish.html.gz": ("aquatic", "BAND02_VISUAL_EVENTS"),
    "nurse-log-ground-moves-anyway.html.gz": ("forest", "NURSE_LOG_ALBUM"),
    "quiet-machinery-atlas-unlit-rooms.html.gz": ("rooms", "QUIET_MACHINERY"),
}


class NativeError(RuntimeError):
    """Native playback cannot start or recover; the caller shows the note."""


@dataclass(frozen=True, slots=True)
class TrackData:
    """One movement's cached audio and decoded visuals payload.

    Attributes:
        audio: Cached MP3 that holds this movement.
        offset_s: Seconds into `audio` where the movement starts. Zero for
            per-movement files; the movement start for Coupon's single mix.
        scene: Scene name for `scenes.draw_scene`; empty uses the family default.
        scene_label: Listener-facing scene name for the status line.
        events: Normalized ``[part, onset_s, gate_s, velocity]`` rows, with
            onsets relative to the movement start.
    """

    audio: Path
    offset_s: float = 0.0
    scene: str = ""
    scene_label: str = ""
    events: tuple[list[object], ...] = ()


@dataclass(frozen=True, slots=True)
class NativeAlbum:
    """Decoded album: per-movement audio and visuals data.

    Attributes:
        tracks: Per-movement data, ordered by catalog track number.
        family: Visual family for `scenes.draw_scene`.
    """

    tracks: tuple[TrackData, ...]
    family: str


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
    its `start`. The other three store one MP3 per movement: Nurse Log and
    Quiet Machinery inline a data URI in each track's `audio`; Drowning's
    `audio` is a relative path keyed into its `band02-assets` manifest.
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

    This album's player predates the `window.<NAME>` JSON the other three
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
        if "title" in fields:
            tracks.append(fields)
    return tracks or None


def _fallback_scenes(asset: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (scenes, labels) for albums whose HTML lacks a scene field."""
    family = _ALBUM_DATA.get(asset, ("", ""))[0]
    if family == "coupon":
        return COUPON_SCENES, COUPON_SCENE_LABELS
    if family == "aquatic":
        return AQUATIC_SCENES, ()
    return (), ()


def _track_data(
    track: dict[str, Any],
    index: int,
    audio: Path,
    offset_s: float,
    fallback_scenes: tuple[str, ...],
    fallback_labels: tuple[str, ...],
) -> TrackData:
    """Build `TrackData` for one track, tolerating missing visuals fields."""
    scene = str(track.get("scene") or "")
    label = str(track.get("scene_label") or track.get("scene") or "")
    if not scene and index < len(fallback_scenes):
        scene = fallback_scenes[index]
    if not label and index < len(fallback_labels):
        label = fallback_labels[index]
    rows = normalize_events(track.get("events"))
    return TrackData(
        audio=audio, offset_s=offset_s, scene=scene, scene_label=label, events=tuple(rows)
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
                    events=tuple(item["events"]),
                )
            )
        family = str(data["family"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if family not in FAMILIES or not tracks:
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
            "events": list(track.events),
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
    movement's scene, offset, and normalized events. Later calls read only
    that sidecar: the archives are 70-112 MB of HTML, and re-parsing them
    froze the library for up to ~2 s per Enter. Cache names hash the gzip
    source bytes, so a changed archive misses the cache. Movements that
    share one payload (Coupon) share one file. `source` lets tests pass a
    tiny gzip instead of the bundled archives.

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
    if family not in FAMILIES:
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
            _track_data(item, index, path, offset_s, fallback_scenes, fallback_labels)
            if isinstance(item, dict)
            else TrackData(audio=path, offset_s=offset_s)
        )
    album = NativeAlbum(tracks=tuple(built), family=family)
    # Written last, after every MP3 is published, so a present sidecar
    # always points at complete audio.
    _atomic_write(sidecar, _sidecar_bytes(album))
    return album


def _mpv_available() -> bool:
    return shutil.which("mpv") is not None


def _ffplay_available() -> bool:
    return shutil.which("ffplay") is not None


class Mpv:
    """Minimal mpv JSON-IPC client; mpv remains the audio clock.

    Same contract as the original player's `Mpv`: a unix socket under the
    temp dir, `time-pos` polling, `seek`, `set_property pause`, and a
    `close` that terminates the child and removes the socket.
    """

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


def _scene_rows(
    width: int,
    height: int,
    family: str,
    scene: str,
    position_s: float,
    events: EventIndex,
) -> list[list[Cell]]:
    """Render one scene frame as `Cell` rows for `render_ansi`.

    The scene canvas covers the full frame; the caller draws the status
    strip over the last row. Colors come from the original xterm-256
    palette, emitted through the shared renderer's color modes.
    """
    canvas = Canvas(width, height)
    draw_scene(canvas, family, scene, position_s, events)
    colors = scene_colors(family, scene)
    bg = colors.background
    rows: list[list[Cell]] = []
    for y in range(height):
        row: list[Cell] = []
        for x in range(width):
            char = canvas.chars[y][x]
            ink = canvas.inks[y][x]
            # Blank cells still need a valid fg: render_ansi emits a color
            # escape for every cell whose fg differs from the last, and an
            # empty string is not a parseable hex. Use the scene background
            # so the cell is invisible either way.
            fg = colors.ink(ink) if char != " " else bg
            row.append(Cell(char, fg, bg))
        rows.append(row)
    return rows


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


_KEY_HINTS = ("space pause  ←/→ seek  n/p movement  m motion  q back", "q back")


def _status_line(
    width: int, state: str, clock: str, title: str, scene: str, motion: str, note: str
) -> str:
    """Fit the status text so state, clock, and a way out stay visible.

    Bundled titles make the full line ~110 columns, so at 80 the middle
    (title and scene) is truncated first. A note replaces the key hint
    instead of pushing the clock off-screen.
    """
    left = f" {state}  {clock}"
    middle = f"  {title} · {scene}"
    if motion != "full":
        middle += f" · motion {motion}"
    rights = (f"{note}  q back",) if note else _KEY_HINTS
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


def _playback_frame(
    family: str,
    entry: CatalogEntry,
    data: TrackData,
    events: EventIndex,
    position_s: float,
    scene_s: float,
    width: int,
    height: int,
    palette: Palette,
    color_mode: str,
    *,
    playing: bool,
    motion: str,
    note: str,
) -> str:
    """Compose and serialize one playback frame.

    `position_s` is the movement clock the listener hears; `scene_s` is
    the picture's time, which motion modes slow or hold. Both are seconds
    from the movement start. The scene fills `height - 1` rows; the last
    row carries state, clock, and the key hint in the active palette.
    """
    scene_h = max(1, height - 1)
    rows = _scene_rows(width, scene_h, family, data.scene, scene_s, events)
    if height > 1:
        clock = (
            f"{format_clock(position_s)} / "
            f"{format_clock(movement_duration_s(entry.album, entry.track))}"
        )
        line = _status_line(
            width,
            "PLAYING" if playing else "PAUSED",
            clock,
            entry.track.title,
            data.scene_label or data.scene or family,
            motion,
            note,
        )
        rows.append(_text_row(line, width, palette.foreground, palette.background))
    else:
        rows = rows[:1]
    return _terminal_frame(render_ansi(rows, color_mode))


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
    input_stream: Any = None,
    output_stream: Any = None,
    cache_home: Path | None = None,
    source: bytes | None = None,
    player_factory: Callable[[Path, float], Any] | None = None,
) -> str:
    """Play `entry`'s album natively in the terminal until q or Escape.

    Shows a loading line, extracts the album (decoded once into the cache;
    see `extract_album`), then runs the scene loop. Space pauses, arrows
    seek 10 s, n/p change movement, m toggles still motion, q/Escape return
    ``"quit"``. The caller's raw mode stays on throughout: unlike the
    browser launch, mpv/ffplay get no stdin, so nothing needs the terminal
    restored and the child cannot eat keys.

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
        input_stream: TTY input; defaults to sys.stdin.
        output_stream: TTY output; defaults to sys.stdout.
        cache_home: XDG cache home override.
        source: Optional compressed HTML override for tests.
        player_factory: `(media_path, offset_s) -> player`; tests inject a
            fake. Defaults to mpv then ffplay.

    Returns:
        ``"quit"`` when the listener leaves playback.

    Raises:
        ValueError: `motion` is not a known mode.
        NativeError: Extraction or player startup failed.
        AlbumError: The asset is not bundled.
        OSError: The cache cannot be written.
        _PlayerTerminatedError: SIGTERM arrived; the audio child is already
            stopped, and the caller restores the terminal and exits.
    """
    if motion not in _MOTION_RATES:
        raise ValueError(f"unknown motion mode {motion!r}")
    # `m` toggles between still and the requested moving mode.
    moving = motion if motion != "still" else "full"
    source_stream = input_stream or sys.stdin
    target = output_stream or sys.stdout
    width, height = _size(source_stream.fileno())
    loading = _text_row(
        f" Loading {entry.album.title}…", width, palette.foreground, palette.background
    )
    target.write("\x1b[H" + _terminal_frame(render_ansi([loading], color_mode)) + "\x1b[J")
    target.flush()

    album = extract_album(entry.album.asset, cache_home, source)
    entries = sorted(
        (e for e in album_entries if e.album.asset == entry.album.asset),
        key=lambda e: e.track.number,
    ) or [entry]
    # The catalog and archive agree today; trimming keeps `album.tracks[i]`
    # in range if either ever lists an extra movement.
    entries = entries[: len(album.tracks)]
    index = next(
        (i for i, e in enumerate(entries) if e.track.number == entry.track.number),
        0,
    )
    # Built lazily per movement: an album holds up to ~4k events per track,
    # too many to re-sort every frame.
    event_indexes: dict[int, EventIndex] = {}
    # The picture's time is anchor_scene + (elapsed - anchor_clock) * rate,
    # re-anchored on every mode change, seek, and movement change.
    anchor_scene = anchor_clock = 0.0

    factory = player_factory or _player_for
    player: Any = None
    decoder = KeyDecoder()
    playing = True
    note = ""
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        player = factory(album.tracks[index].audio, album.tracks[index].offset_s)
        while True:
            data = album.tracks[index]
            events = event_indexes.get(index)
            if events is None:
                events = event_indexes[index] = EventIndex.build(list(data.events))
            duration = movement_duration_s(entries[index].album, entries[index].track)
            width, height = _size(source_stream.fileno())
            elapsed = max(0.0, _position(player, data.offset_s) - data.offset_s)
            scene_s = max(0.0, anchor_scene + (elapsed - anchor_clock) * _MOTION_RATES[motion])
            frame = _playback_frame(
                album.family,
                entries[index],
                data,
                events,
                elapsed,
                scene_s,
                width,
                height,
                palette,
                color_mode,
                playing=playing,
                motion=motion,
                note=note,
            )
            target.write("\x1b[H" + frame + "\x1b[J")
            target.flush()
            # ~15 fps: smooth glyph motion with one mpv time-pos round trip
            # per frame, and longer than the KeyDecoder's Escape hold so an
            # idle poll flushes a lone Esc.
            readable, _, _ = select.select([source_stream.fileno()], [], [], _MPVPOLL_S)
            keys = (
                decoder.feed(os.read(source_stream.fileno(), 64)) if readable else decoder.flush()
            )
            step = 0
            for key in keys:
                if key in ("q", "Q", "esc", "quit"):
                    return "quit"
                if key == " ":
                    playing = not playing
                    player.set_pause(not playing)
                    note = ""
                elif key in ("m", "M"):
                    anchor_scene, anchor_clock = scene_s, elapsed
                    motion = moving if motion == "still" else "still"
                    note = ""
                elif key in ("left", "right"):
                    delta = _SEEK_STEP_S if key == "right" else -_SEEK_STEP_S
                    rel = min(duration, max(0.0, elapsed + delta))
                    try:
                        player.seek(data.offset_s + rel)
                    except NativeError as error:
                        note = str(error)
                    else:
                        # Carried forward so two presses in one read seek
                        # 20 s, not the same target twice.
                        elapsed = rel
                        anchor_scene = anchor_clock = scene_s = rel
                elif key in ("n", "j", "down"):
                    step += 1
                elif key in ("p", "k", "up"):
                    step -= 1
            # End of movement: mpv exits on its own (per-movement files), or
            # the position passes the movement's end (Coupon's shared mix).
            # Skipped when a key already chose a movement, so auto-advance
            # cannot turn `p` or `nn` into one step forward.
            if step == 0:
                proc = getattr(player, "proc", None)
                if (proc is not None and proc.poll() is not None) or elapsed >= duration:
                    step = 1
            if step:
                index = (index + step) % len(entries)
                player.close()
                player = None
                player = factory(album.tracks[index].audio, album.tracks[index].offset_s)
                anchor_scene = anchor_clock = 0.0
                playing = True
                note = ""
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            if player is not None:
                player.close()
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)

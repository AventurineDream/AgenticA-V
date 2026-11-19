"""Preview real bundled movements through the same Stage pipeline as playback.

Run ``python -m agentic_av.viz.preview coupon 1 --sheet 6 --out sheet.png``.
Extraction/analysis use native caches; PNGs, benchmarks, and sequential safety scans never
retain a movie in memory. Live mode restores TTY attributes and handlers on every exit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import select
import shutil
import signal
import sys
import termios
import time
import tty
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from agentic_av.catalog import ALBUMS, movement_duration_s
from agentic_av.native import NativeError, extract_album, movement_signals

from .audio import Features
from .caps import budget_tier, cell_aspect, detect_tier
from .encode import SYNC_BEGIN, SYNC_END, displayed_cells
from .glyphs import TIERS
from .png import rasterize, write_png
from .scene import Movement
from .score import Score
from .stage import Stage

_FPS = 30.0
_RATES = {"full": 1.0, "reduced": 0.22, "still": 0.0}
# Positional: each name matches the ALBUMS entry at the same index. Append only.
_FAMILIES = ("coupon", "aquatic", "forest", "rooms", "pocket", "undertow", "haunt", "dusk")


@dataclass(frozen=True)
class _Source:
    movement: Movement
    features: Features | None
    score: Score


def _load(album_name: str, movement_name: str) -> _Source:
    key = album_name.casefold()
    albums = [
        (i, album)
        for i, album in enumerate(ALBUMS)
        if key
        in (
            str(i + 1),
            _FAMILIES[i],
            album.title.casefold(),
            album.artist.casefold(),
            album.asset.removesuffix(".html.gz"),
        )
    ]
    if not albums:
        raise ValueError("unknown album; use a family, catalog number, or exact album title")
    if len(albums) > 1:
        raise ValueError("ambiguous album; use a family, catalog number, or exact album title")
    _, album = albums[0]
    native = extract_album(album.asset)
    candidates = [
        i
        for i, track in enumerate(album.tracks)
        if movement_name.casefold()
        in (str(i + 1), track.title.casefold(), native.tracks[i].scene.casefold())
    ]
    if len(candidates) != 1:
        raise ValueError(f"movement must be 1..{len(album.tracks)} or an exact title/scene")
    index = candidates[0]
    track, data = album.tracks[index], native.tracks[index]
    features, score = movement_signals(native, index)
    if features is None:
        print("warning: audio analysis unavailable; rendering silent signals", file=sys.stderr)
    duration = float(data.score.get("duration") or movement_duration_s(album, track))
    palette = tuple(data.score.get("palette") or ())
    seed = int.from_bytes(hashlib.sha256(f"{album.asset}:{index}".encode()).digest()[:8], "big")
    movement = Movement(
        native.family,
        index,
        len(album.tracks),
        track.title,
        data.scene,
        data.scene_label,
        duration,
        palette,
        score.bpm,
        score.meter,
        seed,
    )
    return _Source(movement, features, score)


def _size(value: str) -> tuple[int, int]:
    try:
        cols, rows = (int(item) for item in value.lower().split("x"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("size must be COLSxROWS") from error
    if cols < 1 or rows < 1:
        raise argparse.ArgumentTypeError("size dimensions must be positive")
    return cols, rows


def _times(value: str) -> list[float]:
    try:
        values = [float(item) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("at must be comma-separated seconds") from error
    if not values or any(not math.isfinite(item) or item < 0 for item in values):
        raise argparse.ArgumentTypeError("at times must be finite and nonnegative")
    return values


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("album", help="family, album title, artist, or 1-based catalog number")
    parser.add_argument("movement", help="1-based movement number, title, or scene key")
    parser.add_argument("--at", type=_times, default=[0.0], help="comma-separated seconds")
    parser.add_argument(
        "--sheet", type=int, metavar="N", help="N evenly spaced pictures in one PNG"
    )
    parser.add_argument("--size", type=_size, default=(190, 45))
    parser.add_argument("--tier", choices=("auto", *TIERS), default="auto")
    parser.add_argument("--color", choices=("truecolor", "256", "none"), default="truecolor")
    parser.add_argument("--motion", choices=tuple(_RATES), default="full")
    parser.add_argument("--out", type=Path, default=Path("preview.png"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--live", action="store_true", help="wall-clock TTY preview without audio")
    modes.add_argument("--bench", action="store_true", help="time 120 sequential frames")
    modes.add_argument("--safety", action="store_true", help="scan the entire movement at 30 fps")
    parser.add_argument("--from", dest="start", type=float, default=0.0, metavar="S")
    return parser


def _stage(source: _Source, args: argparse.Namespace) -> Stage:
    import os

    cols, rows = args.size
    tier = detect_tier(os.environ) if args.tier == "auto" else args.tier
    tier = budget_tier(tier, cols, rows)
    aspect = cell_aspect(sys.stdout.fileno()) if sys.stdout.isatty() else 2.0
    stage = Stage(cols, rows, tier=tier, color_mode=args.color, cell_aspect=aspect)
    stage.open(source.movement, source.features, source.score)
    return stage


def _warm(source: _Source, args: argparse.Namespace, at: float) -> Stage:
    stage = _stage(source, args)
    # Still captures its first instant permanently: warming would freeze at at-3s.
    if args.motion == "still":
        stage.frame(at, 0.0, motion="still")
        return stage
    start = max(0.0, at - 3.0)
    steps = math.floor((at - start) * _FPS)
    rate = _RATES[args.motion]
    for step in range(steps + 1):
        t = start + step / _FPS
        stage.frame(t, t * rate, motion=args.motion)
    # Fractional requested instants must not get rounded down to the warm-up grid.
    stage.frame(at, at * rate, motion=args.motion)
    return stage


def _raster(stage: Stage, *, safety: bool = False) -> np.ndarray:
    if stage.cells is None:
        raise RuntimeError("preview requested before the first frame")
    spec = TIERS[stage.cells.tier]
    # Mosaic native samples preserve every fitted region without upscaling meter state.
    # Font/dot coverage needs the full 8x16 mask; 2x4 would overstate braille dot area.
    cell_px = (
        (spec.sub_w, spec.sub_h)
        if safety and stage.cells.tier not in ("ascii", "braille")
        else (8, 16)
    )
    return rasterize(displayed_cells(stage.cells, stage.color_mode), cell_px=cell_px)


def _snapshots(source: _Source, args: argparse.Namespace) -> None:
    times = (
        np.linspace(0.0, source.movement.duration_s, args.sheet).tolist() if args.sheet else args.at
    )
    images = []
    for index, at in enumerate(times):
        stage = _warm(source, args, min(at, source.movement.duration_s))
        image = _raster(stage)
        if args.sheet:
            images.append(image)
        else:
            path = (
                args.out
                if len(times) == 1
                else args.out.with_name(f"{args.out.stem}-{index + 1:02d}-{at:g}s{args.out.suffix}")
            )
            write_png(path, image)
            print(path)
    if args.sheet:
        columns = math.ceil(math.sqrt(len(images)))
        rows = math.ceil(len(images) / columns)
        h, w = images[0].shape[:2]
        sheet = np.zeros((rows * h, columns * w, 3), dtype=np.uint8)
        for index, image in enumerate(images):
            y, x = divmod(index, columns)
            sheet[y * h : (y + 1) * h, x * w : (x + 1) * w] = image
        write_png(args.out, sheet)
        print(args.out)


def _bench(source: _Source, args: argparse.Namespace) -> None:
    at = min(args.at[0], source.movement.duration_s)
    stage = _warm(source, args, at)
    timings = np.empty((120, 3), dtype=np.float64)
    byte_count = 0
    start = time.perf_counter()
    for index in range(len(timings)):
        t = min(source.movement.duration_s, at + (index + 1) / _FPS)
        tau = (at + (index + 1) / _FPS) * _RATES[args.motion]
        byte_count += len(stage.frame(t, tau, motion=args.motion))
        timings[index] = stage.timings
    elapsed = time.perf_counter() - start
    print(
        json.dumps(
            {
                "frames": len(timings),
                "tier": stage.tier,
                "size": args.size,
                "render_ms": float(timings[:, 0].mean() * 1000),
                "render_p95_ms": float(np.percentile(timings[:, 0], 95) * 1000),
                "fit_ms": float(timings[:, 1].mean() * 1000),
                "encode_ms": float(timings[:, 2].mean() * 1000),
                "total_ms": elapsed / len(timings) * 1000,
                "bytes_per_frame": byte_count / len(timings),
            },
            indent=2,
        )
    )


def _safety(source: _Source, args: argparse.Namespace) -> dict:
    from .safety import FlashMeter

    if source.features is None:
        raise ValueError("--safety requires real audio analysis; silent fallback is not a scan")
    stage = _stage(source, args)
    meter = FlashMeter()
    duration = source.movement.duration_s
    for index in range(math.ceil(duration * _FPS) + 1):
        t = min(index / _FPS, duration)
        stage.frame(t, t * _RATES[args.motion], motion=args.motion)
        meter.push(t, _raster(stage, safety=True))
    report = meter.report()
    report.update(
        {
            "duration_s": duration,
            "fps": _FPS,
            "motion": args.motion,
            "tier": stage.tier,
            "color": args.color,
            "limits": "Heuristic flash/area and 100ms mean-luminance limits; "
            "not WCAG certification. "
            "Mosaics use exact native subpixel coverage; font/dots use 8x16 masks. "
            "Area is screen-relative, not measured viewing geometry. "
            "No-color assumes white on black; actual terminal defaults may differ.",
        }
    )
    print(json.dumps(report, indent=2))
    return report


def _interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def _live(source: _Source, args: argparse.Namespace) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("--live requires a TTY on stdin and stdout")
    stage = _warm(source, args, args.start)
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    old_handler = signal.getsignal(signal.SIGTERM)
    output = sys.stdout.buffer
    started = time.monotonic()
    try:
        signal.signal(signal.SIGTERM, _interrupt)
        tty.setcbreak(fd)
        output.write(b"\x1b[?1049h\x1b[?25l")
        stage.encoder.invalidate()
        while True:
            elapsed = time.monotonic() - started
            t = min(source.movement.duration_s, args.start + elapsed)
            size = shutil.get_terminal_size()
            dims = min(args.size[0], size.columns), min(args.size[1], size.lines)
            if dims != (stage.surface.cols, stage.surface.rows):
                stage.resize(*dims)
            data = stage.frame(t, t * _RATES[args.motion], motion=args.motion)
            output.write(SYNC_BEGIN + data + SYNC_END)
            output.flush()
            if t >= source.movement.duration_s:
                break
            ready = select.select(
                [sys.stdin], [], [], max(0.0, 1 / _FPS - (time.monotonic() - started - elapsed))
            )[0]
            if ready and sys.stdin.read(1) in ("q", "\x1b"):
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        signal.signal(signal.SIGTERM, old_handler)
        output.write(SYNC_END + b"\x1b[0m\x1b[?25h\x1b[?1049l")
        output.flush()


def main(argv: list[str] | None = None) -> int:
    """Run real-scene PNG, live, benchmark, or heuristic safety previews.

    Args:
        argv: CLI arguments excluding the executable; None reads sys.argv.

    Returns:
        Zero on success, one for a failed safety scan, 130 for interruption.

    Raises:
        SystemExit: argparse rejects invalid flags or an unavailable album.
    """
    parser = _parser()
    args = parser.parse_args(argv)
    if args.sheet is not None and args.sheet < 1:
        parser.error("--sheet must be positive")
    if not math.isfinite(args.start) or args.start < 0:
        parser.error("--from must be finite and nonnegative")
    try:
        source = _load(args.album, args.movement)
        args.start = min(args.start, source.movement.duration_s)
        if args.live:
            _live(source, args)
        elif args.bench:
            _bench(source, args)
        elif args.safety:
            return 0 if _safety(source, args)["passed"] else 1
        else:
            _snapshots(source, args)
    except (ValueError, NativeError, OSError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

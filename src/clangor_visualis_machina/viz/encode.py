"""Serialize fitted cells using vectorized byte records and mask compaction.

Stage owns synchronized output; this module emits only CUP, SGR, and UTF-8.
Reusable buffers avoid per-cell Python formatting; row snapshots are copied because
callers may mutate their Cells arrays before the next encode.
"""

from __future__ import annotations

import numpy as np

from clangor_visualis_machina.colorutil import xterm256_hue_match
from clangor_visualis_machina.viz.glyphs import TIERS, Cells

SYNC_BEGIN = b"\x1b[?2026h"
SYNC_END = b"\x1b[?2026l"
_DIGITS = np.asarray([list(f"{v:03d}".encode()) for v in range(256)], dtype=np.uint8)
_CUBE = np.array([0, 95, 135, 175, 215, 255], dtype=np.int32)
_NEAREST = np.abs(np.arange(256)[:, None] - _CUBE).argmin(axis=1).astype(np.uint8)
_DITHER = (
    np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) - 7.5
)
# Only indices 16..255 are emitted: ANSI 0..15 are terminal-theme dependent.
# Keep the RGB reconstruction beside quantization so preview never has a second
# palette or Bayer implementation that can disagree with the terminal encoder.
_XTERM_RGB = np.concatenate(
    (
        np.stack(np.meshgrid(_CUBE, _CUBE, _CUBE, indexing="ij"), axis=-1).reshape(-1, 3),
        np.repeat((8 + np.arange(24) * 10)[:, None], 3, axis=1),
    )
).astype(np.uint8)


def _quantize(rgb: np.ndarray, *, dither: bool = True) -> np.ndarray:
    """Match colorutil's `to_xterm256` rule, with optional spatial dither.

    Dither moves the nearest cube/gray choice only. The hue match uses the
    undithered color, so a flat muted field gets one cube color instead of
    dithered specks, and ``dither=False`` equals `to_xterm256` exactly.
    """
    raw = rgb.astype(np.int32)
    values = raw
    if dither:
        rows, cols = rgb.shape[:2]
        y, x = np.ogrid[:rows, :cols]
        values = np.rint(raw + _DITHER[y % 4, x % 4, None]).clip(0, 255).astype(np.int32)
    cube = _NEAREST[values]
    cube_rgb = _CUBE[cube]
    cube_dist = ((values - cube_rgb) ** 2).sum(axis=-1)
    slot = np.clip((values.sum(axis=-1) - 24 + 14) // 30, 0, 23)
    gray_dist = ((values - (8 + slot[..., None] * 10)) ** 2).sum(axis=-1)
    index = 16 + 36 * cube[..., 0].astype(np.int32) + 6 * cube[..., 1] + cube[..., 2]
    use_gray = gray_dist < cube_dist
    nearest = np.where(use_gray, 232 + slot, index)
    neutral = use_gray | ((cube[..., 0] == cube[..., 1]) & (cube[..., 1] == cube[..., 2]))
    hue = xterm256_hue_match(raw)
    return np.where(neutral & (hue > 0), hue, nearest).astype(np.uint8)[..., None]


def displayed_cells(cells: Cells, color_mode: str) -> Cells:
    """Return the cell colors a PNG preview should use for the selected mode.

    Args:
        cells: Fitted canvas; input arrays are never modified. Glyph storage is
            shared with the result and must not be mutated through this view.
        color_mode: "truecolor", "256", or "none", matching FrameEncoder.

    Returns:
        The input itself for truecolor; otherwise a new Cells wrapper with
        encoder-identical dithered xterm RGB, or mono white foreground on black.
        Mono input remains mono in every mode. White/black is a worst-case
        contrast preview assumption: no-color emits no SGR, and the terminal's
        actual default foreground/background colors are unknown.

    Raises:
        ValueError: Unknown color mode.
    """
    if color_mode not in ("truecolor", "256", "none"):
        raise ValueError(f"unknown color mode: {color_mode!r}")
    if color_mode == "truecolor":
        return cells
    if color_mode == "none" or cells.mono:
        return Cells(
            cells.tier,
            True,
            cells.glyph,
            np.full_like(cells.fg, 255),
            np.zeros_like(cells.bg),
        )
    return Cells(
        cells.tier,
        False,
        cells.glyph,
        _XTERM_RGB[_quantize(cells.fg)[..., 0] - 16],
        _XTERM_RGB[_quantize(cells.bg)[..., 0] - 16],
    )


class FrameEncoder:
    """Keep row-diff state and reusable serialization storage for one canvas.

    Args:
        color_mode: "truecolor", "256", or "none"; no-color never emits SGR.

    Raises:
        ValueError: Unknown color mode.
    """

    def __init__(self, color_mode: str):
        if color_mode not in ("truecolor", "256", "none"):
            raise ValueError(f"unknown color mode: {color_mode!r}")
        self.color_mode = color_mode
        self._previous: tuple | None = None
        self._key: tuple | None = None
        self._records = np.empty((0, 0, 42), dtype=np.uint8)
        self._mask = np.empty((0, 0, 42), dtype=bool)
        self._glyph_bytes: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def invalidate(self) -> None:
        """Forget the last frame so the next call repaints every row."""
        self._previous = None

    def encode(self, cells: Cells, *, top: int = 1, left: int = 0) -> bytes:
        """Return changed rows as terminal bytes, without a sync wrapper or clear.

        Args:
            cells: Fitted canvas; arrays are read without mutation.
            top: One-based terminal row for the canvas top edge.
            left: Zero-based column offset of the canvas left edge. Rows start at
                column ``left + 1``, so a cover panel can sit beside the stage.

        Returns:
            Empty bytes when nothing visible changed. Colored rows end in SGR reset.

        Raises:
            ValueError: top is not a positive terminal row, or left is negative.
        """
        if top < 1 or left < 0:
            raise ValueError("top must be a positive terminal row and left nonnegative")
        rows, cols = cells.glyph.shape
        mode = "none" if cells.mono else self.color_mode
        key = (cells.tier, mode, rows, cols, top, left)
        if key != self._key:
            self.invalidate()
            self._key = key
        if rows == 0 or cols == 0:
            return b""
        if self._records.shape[:2] != (rows, cols):
            self._records = np.empty((rows, cols, 42), dtype=np.uint8)
            self._mask = np.empty_like(self._records, dtype=bool)
        if cells.tier not in self._glyph_bytes:
            table = TIERS[cells.tier].glyphs
            data = np.zeros((len(table), 4), dtype=np.uint8)
            lengths = np.empty(len(table), dtype=np.uint8)
            for index, glyph in enumerate(table):
                raw = glyph.encode("utf-8")
                data[index, : len(raw)] = np.frombuffer(raw, dtype=np.uint8)
                lengths[index] = len(raw)
            self._glyph_bytes[cells.tier] = data, lengths
        glyph_data, lengths = self._glyph_bytes[cells.tier]
        spaces = cells.glyph == 0
        if mode == "256":
            fg, bg = _quantize(cells.fg), _quantize(cells.bg)
        elif mode == "truecolor":
            fg, bg = cells.fg, cells.bg
        else:
            fg = bg = np.zeros((rows, cols, 1), dtype=np.uint8)
        # Spaces do not use foreground. Carry the last non-space color across
        # their run, so the next glyph cannot inherit a suppressed SGR value.
        last = np.maximum.accumulate(np.where(~spaces, np.arange(cols), 0), axis=1)
        effective_fg = np.take_along_axis(fg, last[..., None], axis=1)
        effective_fg[np.cumsum(~spaces, axis=1) == 0] = 0
        if self._previous is None:
            changed = np.ones(rows, dtype=bool)
        else:
            old_glyph, old_fg, old_bg = self._previous
            changed = (
                (cells.glyph != old_glyph).any(axis=1)
                | (effective_fg != old_fg).any(axis=(1, 2))
                | (bg != old_bg).any(axis=(1, 2))
            )
        if not changed.any():
            return b""
        self._previous = (cells.glyph.copy(), effective_fg.copy(), bg.copy())
        record, mask = self._records, self._mask
        mask.fill(False)
        if mode != "none":
            size = 19 if mode == "truecolor" else 11
            template = b"\x1b[38;2;000;000;000m" if mode == "truecolor" else b"\x1b[38;5;000m"
            record[..., :size] = np.frombuffer(template, dtype=np.uint8)
            record[..., size : 2 * size] = np.frombuffer(
                template.replace(b"38;", b"48;"), dtype=np.uint8
            )
            for start, colors, foreground in ((0, effective_fg, True), (size, bg, False)):
                emit = np.ones((rows, cols), dtype=bool)
                emit[:, 1:] = (colors[:, 1:] != colors[:, :-1]).any(axis=-1)
                if foreground:
                    first = np.cumsum(~spaces, axis=1) == 1
                    emit |= first & ~spaces
                    emit &= ~spaces
                mask[..., start : start + size] = emit[..., None]
                for channel in range(colors.shape[-1]):
                    at = start + 7 + channel * 4
                    values = colors[..., channel]
                    record[..., at : at + 3] = _DIGITS[values]
                    mask[..., at] &= values >= 100
                    mask[..., at + 1] &= values >= 10
            offset = size * 2
        else:
            offset = 0
        record[..., offset : offset + 4] = glyph_data[cells.glyph]
        mask[..., offset : offset + 4] = np.arange(4) < lengths[cells.glyph][..., None]
        parts = []
        for row in np.flatnonzero(changed):
            parts.append(b"\x1b[%d;%dH" % (row + top, left + 1))
            parts.append(record[row][mask[row]].tobytes())
            if mode != "none":
                parts.append(b"\x1b[0m")
        return b"".join(parts)

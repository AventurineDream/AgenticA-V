"""Measure conservative flash-risk regressions in rasterized terminal output.

Preview and scene tests supply displayed sRGB pixels, never pre-fit scene colors. This
is not WCAG certification: terminal size, viewing distance, font coverage, display
response, and actual angular geometry are unknown. Samples cannot reveal inter-frame
flashes. No fine-pattern exemption is assumed; opposing subregions never cancel.

The reference is WCAG 2.2 SC 2.3.1's understanding document:
https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html
The area surrogate scans every placement of a rectangle one third of the raster's
width and height, approximating the reference screen's 10-degree field. More than
three flash events each covering a quarter of the same rectangle in a sliding
second are flagged, even when their pixels differ. Repeated per-pixel evidence is
also retained. This screen-relative surrogate is not a measured visual angle.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any

import numpy as np

# Exact sRGB decoding is essential: gamma-encoded differences are not luminance.
_SRGB = np.arange(256, dtype=np.float32) / 255.0
_LINEAR = np.where(_SRGB <= 0.04045, _SRGB / 12.92, ((_SRGB + 0.055) / 1.055) ** 2.4)
_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ],
    dtype=np.float32,
)
# Dimensionless excursion units: one unit is a qualifying luminance/red change.
_HYSTERESIS = 0.02
_TIME_EPSILON = 1e-9  # Seconds; avoid treating roundoff at a sliding boundary as overlap.
_AREA_THRESHOLD = 0.25
_MEAN_THRESHOLD = 0.04


class _Transitions:
    """Retain per-pixel extrema and consume disjoint opposing transition pairs.

    A segment emits at most once, when its excursion qualifies, rather than once
    per frame. Reversals must move back 2% of a threshold along the excursion's
    direction; smaller quantization jitter cannot turn a smooth fade into flashes.
    Red uses a vector of chromaticity and red excess, so equal-luminance color
    changes and intensity changes along the same red hue both retain evidence.
    """

    def __init__(
        self, values: np.ndarray, flags: np.ndarray, shape: tuple[int, int], *, red: bool
    ) -> None:
        self.red = red
        self.origin = values.copy()
        self.extreme = values.copy()
        self.origin_flags = flags.copy()
        self.extreme_flags = flags.copy()
        self.emitted = np.zeros(values.shape[0], dtype=bool)
        self.pending = np.zeros(values.shape[0], dtype=bool)
        self.pending_vector = np.zeros_like(values)
        self.count = np.zeros(values.shape[0], dtype=np.int32)
        self.events: deque[tuple[float, np.ndarray]] = deque()
        self.shape = shape
        h, w = shape
        region_h, region_w = (h + 2) // 3, (w + 2) // 3
        self.region_area = region_h * region_w
        self.region_count = np.zeros((h - region_h + 1, w - region_w + 1), dtype=np.int32)
        self.region_events: deque[tuple[float, np.ndarray]] = deque()
        self.latest_region_areas: np.ndarray | None = None

    def push(self, t_s: float, values: np.ndarray, flags: np.ndarray) -> None:
        """Advance turning points and sliding counts without regional averaging."""
        direction = self.extreme - self.origin
        step = values - self.extreme
        projection = np.einsum("ij,ij->i", step, direction)
        length = np.sqrt(np.einsum("ij,ij->i", direction, direction))
        reverse = projection < -_HYSTERESIS * length
        self.origin[reverse] = self.extreme[reverse]
        self.origin_flags[reverse] = self.extreme_flags[reverse]
        self.emitted[reverse] = False
        advance = reverse | (projection >= 0)
        self.extreme[advance] = values[advance]
        self.extreme_flags[advance] = flags[advance]
        excursion = self.extreme - self.origin

        if self.red:
            saturated = self.origin_flags[:, 0] | self.extreme_flags[:, 0]
            chroma_valid = self.origin_flags[:, 1] & self.extreme_flags[:, 1]
            # Current WCAG working definition: delta u'v' > 0.2 involving red.
            chroma = np.sum(excursion[:, :2] ** 2, axis=1) > 1.0
            # Also retain the older red-excess test (>20 on a 320 scale).
            # It conservatively catches red/black intensity strobes, for which
            # black has no defined UCS chromaticity.
            excess = np.abs(excursion[:, 2]) > 1.0
            qualifies = saturated & ((chroma & chroma_valid) | excess)
        else:
            qualifies = (np.abs(excursion[:, 0]) >= 1.0) & (
                np.minimum(self.origin[:, 0], self.extreme[:, 0]) < 8.0
            )

        transition = qualifies & ~self.emitted
        opposing = np.einsum("ij,ij->i", self.pending_vector, excursion) < 0
        paired = transition & self.pending & opposing
        # Disjoint pairs prevent double-counting A->B->A->B as two flashes.
        self.pending[transition] = ~paired[transition]
        self.pending_vector[transition] = excursion[transition]
        self.emitted[transition] = True
        indices = np.flatnonzero(paired)
        self.latest_region_areas = None
        if indices.size:
            self.count[indices] += 1
            self.events.append((t_s, indices))
            # Count area-qualifying concurrent events in every fixed regional
            # placement. Requiring the *same pixels* to flash four times would
            # miss flashes moving between disjoint patches in the visual field.
            self.latest_region_areas = _regional_areas(paired.reshape(self.shape))
            regions = np.flatnonzero(self.latest_region_areas >= _AREA_THRESHOLD * self.region_area)
            if regions.size:
                self.region_count.flat[regions] += 1
                self.region_events.append((t_s, regions))
        # A flash is timestamped at its second qualifying transition. Half-open
        # (t-1,t] windows count exactly 3 Hz as three, including at 30 fps.
        while self.events and self.events[0][0] <= t_s - 1.0 + _TIME_EPSILON:
            _, expired = self.events.popleft()
            self.count[expired] -= 1
        while self.region_events and self.region_events[0][0] <= t_s - 1.0 + _TIME_EPSILON:
            _, expired = self.region_events.popleft()
            self.region_count.flat[expired] -= 1


def _red_features(linear: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return normalized UCS/red-excess evidence and endpoint validity flags."""
    xyz = linear @ _XYZ.T
    denominator = xyz[:, 0] + 15 * xyz[:, 1] + 3 * xyz[:, 2]
    nonblack = denominator > 0
    safe = np.where(nonblack, denominator, 1.0)
    values = np.empty_like(linear)
    values[:, 0] = 4 * xyz[:, 0] / safe / 0.2
    values[:, 1] = 9 * xyz[:, 1] / safe / 0.2
    values[:, 2] = np.maximum(linear[:, 0] - linear[:, 1] - linear[:, 2], 0) / 0.0625
    total = linear.sum(axis=1)
    saturated = (linear[:, 0] >= 0.8 * total) & (total > 0)
    return values, np.column_stack((saturated, nonblack))


def _regional_areas(mask: np.ndarray) -> np.ndarray:
    """Sum concurrent pixel evidence in every complete screen-relative region."""
    h, w = mask.shape
    region_h, region_w = (h + 2) // 3, (w + 2) // 3
    integral = np.zeros((h + 1, w + 1), dtype=np.int64)
    integral[1:, 1:] = mask.cumsum(axis=0).cumsum(axis=1)
    areas = (
        integral[region_h:, region_w:]
        - integral[:-region_h, region_w:]
        - integral[region_h:, :-region_w]
        + integral[:-region_h, :-region_w]
    )
    return areas


def _regional_fraction(mask: np.ndarray) -> float:
    """Find maximal affected area without omitting edges or averaging colors."""
    h, w = mask.shape
    region_area = ((h + 2) // 3) * ((w + 2) // 3)
    return float(_regional_areas(mask).max()) / region_area


class FlashMeter:
    """Collect a conservative, screen-relative flash-risk regression report.

    Call ``push`` on every displayed frame at increasing timestamps in seconds,
    preferably at 30 fps or faster; create a new meter after a seek or resize.
    Pixels are tracked individually using hysteretic turning points. A flash is
    two non-overlapping, qualifying opposing excursions, timestamped when the
    second excursion qualifies. Counts use sliding half-open ``(t-1, t]`` windows.
    Smooth multiframe excursions count once, not once per sampled step.

    General transitions require linear luminance change >=0.10 with darker state
    <0.80. Red transitions require a saturated endpoint (linear R/(R+G+B)>=0.8)
    and either UCS distance >0.2 or legacy red-excess change >20/320. UCS is used
    only when both endpoints are nonblack. Red trajectory reversals use the dot
    product in normalized UCS/red-excess coordinates: this is an intentionally
    conservative engineering heuristic, not a normative color-trajectory analyzer.

    Risk is flagged by >3 concurrent flash events, each covering >=25% of the
    same ceil(h/3)-by-ceil(w/3) regional placement within a second. The flashing
    pixels may differ between events. As an additional conservative guard, >=25%
    of a region with individually >3 flashes also fails, even when completion
    times differ. The scene-design guard flags whole-raster mean linear luminance
    change >0.04 between supplied samples at most 100 ms apart, even without
    repeated flashes. Small canvases use the same fractions without dropping pixels.

    No I/O occurs. State is cumulative and memory retains only current per-pixel
    evidence, a second of flash events, and 100 ms of mean-luminance extrema.
    """

    def __init__(self) -> None:
        self._shape: tuple[int, int] | None = None
        self._last_t: float | None = None
        self._general: _Transitions | None = None
        self._red: _Transitions | None = None
        self._min_means: deque[tuple[float, float]] = deque()
        self._max_means: deque[tuple[float, float]] = deque()
        self._worst_count = 0
        self._max_fraction = 0.0
        self._max_mean_delta = 0.0
        self._violations: dict[str, dict[str, Any]] = {}

    def push(self, t_s: float, rgb8: np.ndarray) -> None:
        """Consume one displayed raster without mutating or retaining its array.

        Args:
            t_s: Finite, strictly increasing observation time in seconds.
            rgb8: Nonempty, stable (height, width, 3) sRGB uint8 displayed pixels.
                Non-contiguous arrays are accepted. Input ownership stays with caller.

        Raises:
            TypeError: Pixels are not a numpy uint8 array.
            ValueError: Shape is invalid/changed, or time is nonfinite/nonincreasing.
        """
        if not isinstance(rgb8, np.ndarray) or rgb8.dtype != np.uint8:
            raise TypeError("rgb8 must be a numpy uint8 array")
        if rgb8.ndim != 3 or rgb8.shape[2] != 3 or min(rgb8.shape[:2]) < 1:
            raise ValueError("rgb8 must have nonempty shape (height, width, 3)")
        shape = rgb8.shape[:2]
        if self._shape is not None and self._shape != shape:
            raise ValueError("raster shape must stay stable; create a new FlashMeter")
        if not math.isfinite(t_s) or (self._last_t is not None and t_s <= self._last_t):
            raise ValueError("timestamps must be finite and strictly increasing")

        linear = _LINEAR[rgb8].reshape(-1, 3)
        luminance = linear @ _LUMA
        mean = float(luminance.mean())
        self._push_mean(t_s, mean)
        red, red_flags = _red_features(linear)
        general = (luminance / 0.1)[:, None]
        general_flags = np.empty((linear.shape[0], 0), dtype=bool)
        if self._general is None:
            self._general = _Transitions(general, general_flags, shape, red=False)
            self._red = _Transitions(red, red_flags, shape, red=True)
            self._shape = shape
        else:
            self._general.push(t_s, general, general_flags)
            assert self._red is not None
            self._red.push(t_s, red, red_flags)
            self._measure_regions(t_s, shape)
        self._last_t = t_s

    def _push_mean(self, t_s: float, mean: float) -> None:
        for queue in (self._min_means, self._max_means):
            while queue and queue[0][0] < t_s - 0.1 - _TIME_EPSILON:
                queue.popleft()
        candidates = [queue[0] for queue in (self._min_means, self._max_means) if queue]
        if candidates:
            old_t, old_mean = max(candidates, key=lambda item: abs(mean - item[1]))
            delta = abs(mean - old_mean)
            if delta > self._max_mean_delta:
                self._max_mean_delta = delta
                if delta > _MEAN_THRESHOLD:
                    self._violations["mean_delta"] = {
                        "kind": "mean_delta",
                        "start_s": old_t,
                        "end_s": t_s,
                        "delta": delta,
                        "detail": "mean linear luminance changed >0.04 within 100 ms",
                    }
        while self._min_means and self._min_means[-1][1] >= mean:
            self._min_means.pop()
        while self._max_means and self._max_means[-1][1] <= mean:
            self._max_means.pop()
        self._min_means.append((t_s, mean))
        self._max_means.append((t_s, mean))

    def _measure_regions(self, t_s: float, shape: tuple[int, int]) -> None:
        assert self._general is not None and self._red is not None
        for kind, tracker in (("luminance", self._general), ("red", self._red)):
            pixel_count = int(tracker.count.max())
            region_count = int(tracker.region_count.max())
            self._worst_count = max(self._worst_count, pixel_count, region_count)
            if pixel_count == 0:
                continue
            affected = _regional_fraction((tracker.count > 0).reshape(shape))
            self._max_fraction = max(self._max_fraction, affected)
            fraction = (
                _regional_fraction((tracker.count > 3).reshape(shape)) if pixel_count > 3 else 0.0
            )
            count = pixel_count
            detail = ">3 per-pixel flash pairs in >=25% of a screen-relative region"
            if region_count > 3 and tracker.latest_region_areas is not None:
                concurrent_fraction = (
                    float(tracker.latest_region_areas[tracker.region_count > 3].max())
                    / tracker.region_area
                )
                if concurrent_fraction >= _AREA_THRESHOLD and (
                    concurrent_fraction,
                    region_count,
                ) > (fraction, count):
                    fraction, count = concurrent_fraction, region_count
                    detail = ">3 concurrent >=25%-area flash events in the same region"
            if fraction < _AREA_THRESHOLD:
                continue
            previous = self._violations.get(kind)
            if previous is None or (fraction, count) > (
                previous["affected_fraction"],
                previous["flash_count"],
            ):
                self._violations[kind] = {
                    "kind": kind,
                    "start_s": t_s - 1.0,
                    "end_s": t_s,
                    "flash_count": count,
                    "affected_fraction": fraction,
                    "detail": detail,
                }

    def report(self) -> dict[str, Any]:
        """Return independent cumulative diagnostics, not a safety certification.

        Returns:
            Dict containing ``passed`` (no heuristic guard triggered),
            ``worst_flash_count`` (largest sliding-second per-pixel count or count
            of concurrent >=25%-area flash events within one regional placement),
            ``max_affected_fraction`` (largest regional fraction with any completed
            flashes in a sliding second), ``max_mean_delta_100ms`` (largest sampled
            linear-mean change at separation <=100 ms), and ``violations`` (at most
            one strongest time/detail record for each of luminance, red, mean guard).
            An empty meter passes with zero measurements; it proves nothing about
            unobserved output. Mutating the report cannot change meter state.
        """
        return {
            "passed": not self._violations,
            "worst_flash_count": self._worst_count,
            "max_affected_fraction": self._max_fraction,
            "max_mean_delta_100ms": self._max_mean_delta,
            "violations": [dict(item) for item in self._violations.values()],
        }

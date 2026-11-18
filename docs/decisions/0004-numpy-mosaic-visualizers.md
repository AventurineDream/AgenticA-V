# 0004 — Paint audio-reactive scenes with numpy terminal mosaics

## Status

Accepted. Supersedes decision 0003's faithful glyph-port requirement only. Its
native audio, media-clock, input, cache, browser, and cleanup contracts remain.
Aven authorized replacing the old art rather than preserving its glyphs.

## Context

The restored terminal scenes established playback but left large cells and weak
musical detail. The bundled albums contain both real audio and, for three albums,
composition data. Character-cell art remains the project's identity; pixel
protocols would add terminal-specific transports without solving portability.

## Decision

Use numpy as the single new runtime dependency. Scenes paint linear-light RGB
surfaces using vectorized splats, fields, geometry, and decaying feedback. Shared
OKLab palette interpolation and tone mapping precede shape-based two-color
mosaic fitting. Soft-cell treatment preserves smooth gradients. The terminal
encoder batches color runs, skips unchanged rows, and emits bytes. Native adds
transport and one synchronized-output wrapper in one write per frame.

Support octants, sextants, quadrants, half-blocks, braille, and shape-matched
ASCII. Default conservatively: verified kitty octants, Linux/dumb ASCII,
otherwise half-blocks. Explicit CLI choice wins over environment detection;
`AAV_GLYPHS` controls auto, and `g` cycles at runtime. A sub-pixel budget lowers
sampling resolution in large terminals. No-color uses ordered monochrome
patterns, not a second art implementation. Font support is not universally
knowable, so the listener always has a manual fallback.

Audio analysis decodes once through ffmpeg and caches seven-band envelopes,
onsets, tracked beat position, and monotonic loudness/bass travel integrators.
Scores normalize instrument notes, sections, palettes, and markers. Audio time
queries music; independently anchored picture time drives geometry. mpv remains
the playback clock. Reduced motion slows picture time and calms reactivity;
still and pause retain exact pixels. The current movement is analyzed before
audio starts; a daemon worker prefetches the next without delaying exit. Shared
analysis is serialized to avoid duplicate foreground/background work. Expected
analysis failure is an explicit quiet-visuals mode, never a fake live signal or
a reason to lose the score/audio.

The 25 new movements form four album-specific worlds, documented in the
[scene guide](../visuals.md). Their palettes belong to the album, while UI theme
roles color transport. Scenes are seeded and remain composed without signals.

## Performance and measurement

Target 30 fps while playing and five transport updates per second while held.
Deadlines start fresh each frame: expensive work drops frames instead of queuing
catch-up. The prototype demonstrated feasibility, not a guarantee for every scene
or machine. Preview benchmarks separate rendering, fitting, and encoding costs;
integration review must report actual measurements and inspect rendered frames.

Audio should move geometry rather than flash illumination. The displayed-cell
regional meter checks luminance reversals, saturated-red reversals, and a
whole-canvas guard with explicit spatial/viewing assumptions. It is a conservative
regression heuristic, **not WCAG certification, a clinical assessment, or a
guarantee of flash safety**. Synthetic adversarial fixtures and real-audio
previews complement manual review. Reduced/still controls remain available.

## Consequences

- numpy is required at runtime; ffmpeg is required for analysis cache misses.
  mpv is preferred for playback and accurate seeking; ffplay remains a fallback.
- Terminal capabilities and font coverage differ. Lower tiers trade detail for
  portability and budget; ASCII is an intentional alternate look.
- Revision 3 extraction sidecars retain normalized scores and remove obsolete
  simplified event rows. Existing caches rebuild rather than needing a shim.
- `scenes.py` and its old rendering path are removed. Tests assert visible
  transport, input, holds, color behavior, and cleanup rather than pinning art.
- Browser albums and bundled archives are unchanged, as are the abstract demo
  player and its independent preview/gallery commands.

# Terminal player architecture

`aav play` with no show or scene opens the album library. `aav demo`, and `aav play` with `--show` or `--scene`, render abstract terminal programs. `preview`, `themes`, and `gallery` stay on that visual path.

Four completed public albums are bundled as self-contained HTML players. All rights remain reserved. Enter plays native audio with a new audio-reactive mosaic scene; `o` opens cached HTML at the movement start instead. Browser autoplay still requires a Play click.

## Album library

`catalog.py` is the typed public catalog. Album artist and band are the same credit because the sources have no distinct per-track musician credits. Entries sort by album artist, band, album title, then track number and title. Only the four completed A-01 albums belong in the catalog.

`library.py` paints a fixed-grid selector with the active palette. `NO_COLOR`, `TERM=dumb`, and `--no-color` use the no-color renderer; selection stays visible as a `>` mark. j/k and arrows move the selection. Enter hands the terminal to `native.play_native` and stays in raw mode, because the audio child gets no stdin. `o` restores canonical terminal mode before the browser launch, then returns to the library.

## Native album playback

`native.py` publishes decoded MP3s and revisioned JSON score sidecars atomically.
The archive hash invalidates changed assets; extraction revision 3 removes the
legacy simplified event field while preserving full normalized composition data.
Warm plays skip HTML decompression and parsing. Coupon's movements share one mix
and media offsets; the other albums use one file per movement. Bundled archives
are read-only.

mpv JSON IPC supplies authoritative `time-pos`. ffplay is an audio-only fallback:
wall time approximates position, seeking is unavailable, and SIGSTOP/SIGCONT
implement pause. Children receive no stdin and close on every playback exit,
including SIGTERM during startup. The library owns terminal restoration.

Before starting current audio, `movement_signals` loads cached audio analysis and
the normalized score. One lock serializes analysis and cache publication across
foreground opens and daemon next-movement prefetch. Prefetch is never joined on
exit. Only expected `AudioError` becomes quiet visuals; other failures propagate.
The loading line says “Listening…” and failed analysis remains visible in the
transport. ffmpeg is needed for first analysis, not for the synthetic CI fixtures.

The native pipeline is:

```text
mpv media position → movement-relative audio t / picture tau
cached Features + Score → Stage → album Scene → linear RGB Surface
→ tone map → glyph fit → Cells → incremental FrameEncoder bytes
→ synchronized canvas + progress + status write
```

`viz/audio.py` uses Hann STFT analysis, seven envelopes, onsets, tracked beats,
and monotonic loudness/bass integrators. Shared mixes are analyzed once with
per-movement tempo hints; movement views shift time without copying arrays.
`viz/score.py` normalizes source layouts into note arrays, sections, markers,
and motifs. A score remains usable when audio analysis fails.

`viz/stage.py` owns scene lifecycle, size-dependent surfaces, seeks, motion gain,
and full-motion crossfades. Its latest `.surface` and fitted `.cells` are exposed
for previews and regression measurement. Seeds are stable per movement. Native
picture time is anchored independently: full runs at 1×, reduced at 0.22× with
0.35 reactive gain, and still holds the exact image. Pausing also holds pixels,
even if progress/signals change. Seek and movement changes update the picture;
leaving still for full rejoins audio time. A named 25 ms visual lead compensates
render latency while transport keeps the actual media clock.

Playing targets 30 fps, held transport 5 fps. Each frame has a fresh deadline,
so slow rendering drops frames without a catch-up queue. Stage emits absolute
cursor writes and skips unchanged rows. Native adds progress/status and one
`CSI ? 2026 h/l` synchronized wrapper in a single write, never a per-frame clear.
Binary TTY buffers receive UTF-8 bytes; text-only output streams receive an
explicit UTF-8 decode. Short writes fail visibly.

Glyph selection is explicit `--glyphs`, otherwise `AAV_GLYPHS` then conservative
terminal detection: kitty octants, Linux/dumb ASCII, otherwise half-blocks.
`g` cycles all tiers. A ~110k sub-pixel budget steps large mosaics down through
sextants/quadrants/halves. Color modes are truecolor, xterm-256, and monochrome
ordered dithering without SGR; terminal control sequences are still required.
The theme colors transport, not album art. Status preserves state, clock, and
`q back`; current sections appear when available. At ten rows or more a
movement-accent hairline and section ticks sit above status.

`viz/safety.py` measures conservative regional luminance/red reversals and a
whole-canvas guard on displayed cells. Region size and viewing geometry are
assumptions; this is a regression heuristic, **not WCAG certification or a
guarantee of flash safety**. Preview measurements and synthetic adversarial
fixtures complement, rather than replace, rendered-art review.

Browser materialization remains separate: cached HTML receives a numeric-start
script that seeks after metadata without calling `play()`. `aav tracks` prints
the catalog without a TTY. See [visuals](visuals.md) and [ADR 0004](decisions/0004-numpy-mosaic-visualizers.md).

## Data flow

`cli.py` parses commands. Bare `play` and `tracks` use the catalog. The visual commands load a TOML show. `omarchy.py` reads the resolved Omarchy palette read-only — applied `colors.toml` when present, otherwise the slug's user or stock `colors.toml` — plus `theme.name` and `theme.generation`. `palette.py` maps that palette into immutable semantic roles shared by built-in themes and the library frame. `field.py` samples abstract visuals, `paint.py` composes exact-size character-cell frames, and `tty.py` owns raw terminal mode and input for the visual player. The preview command and live TTY call the same composer. The library uses the same cell grid and the same key decoder, and it leaves raw mode before opening a browser.

## Theme contract

All UI regions consume the same role set: background, stage, panel, foreground, muted, accent, accent2, success, warning, error, meter, progress, selection, and border. Built-ins are distinct visual treatments. The `omarchy` theme reads `$XDG_STATE_HOME/omarchy/current/theme/colors.toml` (or `~/.local/state/omarchy/current/theme/colors.toml`) first. Omarchy itself merges stock colors and user overlays when a theme is applied; if that applied file is absent, the player reads `$XDG_CONFIG_HOME/omarchy/themes/<slug>/colors.toml` (and `~/.config/omarchy/themes/<slug>/colors.toml`) then `$OMARCHY_PATH/themes/<slug>/colors.toml` (default `/usr/share/omarchy`). It never writes theme files. Live sync checks theme name, generation, and the resolved palette file's content and metadata on a two-second cadence, so editing a fallback source is observed.

Abstract color stages sample two field rows per cell as half-blocks. Their gallery uses each theme's roles. Native stages instead sample tier-specific mosaics and album palettes. `NO_COLOR`, `TERM=dumb`, and `--no-color` emit no color SGR; interactive cursor positioning remains. Truecolor requires `COLORTERM` support; `TERM` containing `256color` enables xterm quantization, otherwise output is monochrome. Frames stay bounded to terminal cells.

## Transport and motion

The abstract demo transport is a monotonic visual clock, not an audio player. Pause, seeks, rate changes, show looping, reduced picture time, and held program selection live in `session.py` and `transport.py`. Native albums instead follow mpv time and the independent picture anchor described above. Both paths preserve seek direction and let transport update while pictures are held.

## Files

- `catalog.py`: typed public albums, sort order, and the plain `tracks` listing.
- `library.py`: library frame, Enter/`o` dispatch, versioned cache materialization, and browser deep link.
- `native.py`: album audio and score extraction with a JSON score cache, the mpv/ffplay players, and the playback loop.
- `viz/`: numpy surfaces, drawing/effects, audio and score queries, mosaic fitting, encoding, Stage, album scenes, previews, and regional risk measurement.
- `albums/*.html.gz`: authorized public album players. Read-only package data.
- `palette.py` and `omarchy.py`: role definitions and read-only theme resolution.
- `field.py`: deterministic abstract luminance/hue samples.
- `paint.py`: fixed-grid composition, half-block stage, theme-atlas cards, and ANSI serialization.
- `tty.py`: alternate-screen terminal runner and key handling. Incomplete escape sequences are buffered across reads; a lone Escape waits out a short silence. SIGTERM leaves through the same cleanup as a normal exit, then the previous handler is restored.
- `show.py` and `transport.py`: minimal TOML show and clock.

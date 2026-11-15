# Terminal player architecture

`aav play` with no show or scene opens the album library. `aav demo`, and `aav play` with `--show` or `--scene`, render abstract terminal programs. `preview`, `themes`, and `gallery` stay on that visual path.

Four completed public albums are bundled as self-contained HTML players. All rights remain reserved. The terminal does not decode audio. It selects a movement and opens the cached HTML in the default browser at that movement's start. The page keeps its own controls. Browser autoplay is blocked, so the listener clicks Play. That page is the full synchronized A/V experience.

## Album library

`catalog.py` is the typed public catalog. Album artist and band are the same credit because the sources have no distinct per-track musician credits. Entries sort by album artist, band, album title, then track number and title. Only the four completed A-01 albums belong in the catalog.

`library.py` paints a fixed-grid selector with the active palette. `NO_COLOR`, `TERM=dumb`, and `--no-color` use the no-color renderer; selection stays visible as a `>` mark. j/k and arrows move the selection. Enter restores canonical terminal mode before the browser launch, then returns to the library.

Bundled assets are `.html.gz` package data and are never rewritten. Materialization decompresses into `$XDG_CACHE_HOME/agentic-av/<version>/track-start-<revision>/` (or `~/.cache/agentic-av/...`), injects a small script immediately before `</body>`, and publishes the file with an atomic rename. The script reads a numeric `start` query parameter, sets `#audio` `currentTime` after metadata loads, and updates `#seek` when that element exists. It does not call `play()`.

`aav tracks` prints the same sorted catalog without a TTY.

## Data flow

`cli.py` parses commands. Bare `play` and `tracks` use the catalog. The visual commands load a TOML show. `omarchy.py` reads the resolved Omarchy palette read-only — applied `colors.toml` when present, otherwise the slug's user or stock `colors.toml` — plus `theme.name` and `theme.generation`. `palette.py` maps that palette into immutable semantic roles shared by built-in themes and the library frame. `field.py` samples abstract visuals, `paint.py` composes exact-size character-cell frames, and `tty.py` owns raw terminal mode and input for the visual player. The preview command and live TTY call the same composer. The library uses the same cell grid and the same key decoder, and it leaves raw mode before opening a browser.

## Theme contract

All UI regions consume the same role set: background, stage, panel, foreground, muted, accent, accent2, success, warning, error, meter, progress, selection, and border. Built-ins are distinct visual treatments. The `omarchy` theme reads `$XDG_STATE_HOME/omarchy/current/theme/colors.toml` (or `~/.local/state/omarchy/current/theme/colors.toml`) first. Omarchy itself merges stock colors and user overlays when a theme is applied; if that applied file is absent, the player reads `$XDG_CONFIG_HOME/omarchy/themes/<slug>/colors.toml` (and `~/.config/omarchy/themes/<slug>/colors.toml`) then `$OMARCHY_PATH/themes/<slug>/colors.toml` (default `/usr/share/omarchy`). It never writes theme files. Live sync checks theme name, generation, and the resolved palette file's content and metadata on a two-second cadence, so editing a fallback source is observed.

Color stages sample two field rows per terminal cell and paint them as a half-block, so the picture is continuous instead of a stripe on a flat background. The in-player gallery paints each theme's own roles on a miniature of the current scene. `NO_COLOR`, `TERM=dumb`, and `--no-color` dither density glyphs and emit no ANSI sequences. Truecolor is used when `COLORTERM` advertises it. `TERM` values containing `256color` quantize to the xterm cube (`0, 95, 135, 175, 215, 255`) and gray ramp (`8` through `238`); `xterm` and `linux` without that capability use the no-color renderer. Output rows are fixed to the current terminal width and height, and a standard-height frame reserves a row for the key legend.

## Transport and motion

The transport is a monotonic visual clock in seconds. Pause, seek, and rate changes preserve the anchor; the show loops at its declared duration. `full` tracks playhead movement. `reduced` keeps the current picture and then advances field time at 0.22×, so selecting it does not rewind the frame; shimmer is omitted. `still` freezes field time and the selected visual program while transport remains seekable. A seek, a chapter skip, or leaving still updates that program; crossing a chapter does not. Arrow seeks and chapter skips apply their signed delta, including across a wrap, so a short show does not reverse them; the half-show adjustment is only for unseeked loop wraps. The visual player does not decode or play audio and does not claim score-synchronized behavior. Synchronized album playback is the bundled HTML in the browser, not this clock.

## Files

- `catalog.py`: typed public albums, sort order, and the plain `tracks` listing.
- `library.py`: library frame, versioned cache materialization, and browser deep link.
- `albums/*.html.gz`: authorized public album players. Read-only package data.
- `palette.py` and `omarchy.py`: role definitions and read-only theme resolution.
- `field.py`: deterministic abstract luminance/hue samples.
- `paint.py`: fixed-grid composition, half-block stage, theme-atlas cards, and ANSI serialization.
- `tty.py`: alternate-screen terminal runner and key handling. Incomplete escape sequences are buffered across reads; a lone Escape waits out a short silence. SIGTERM leaves through the same cleanup as a normal exit, then the previous handler is restored.
- `show.py` and `transport.py`: minimal TOML show and clock.

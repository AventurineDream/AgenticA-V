# Terminal player architecture

The player is a reusable visual instrument, not the catalog installer/open command from the A/V catalog roadmap. It renders abstract terminal-friendly programs for development and preview. Project-specific band identities, album names, audio, artwork, and production assets are deliberately absent from the repository.

## Data flow

`cli.py` parses commands and loads a TOML show. `omarchy.py` reads the applied `colors.toml` and `theme.generation` state read-only. `palette.py` maps that palette into immutable semantic roles shared by built-in themes, `field.py` samples abstract visuals, `paint.py` composes exact-size character-cell frames, and `tty.py` owns raw terminal mode and input. The preview command and live TTY call the same composer.

## Theme contract

All UI regions consume the same role set: background, stage, panel, foreground, muted, accent, accent2, success, warning, error, meter, progress, selection, and border. Built-ins are distinct visual treatments. The `omarchy` theme reads `$XDG_STATE_HOME/omarchy/current/theme/colors.toml` (or `~/.local/state/omarchy/current/theme/colors.toml`) first. Omarchy itself merges stock colors and user overlays when a theme is applied; the player falls back to the slug-specific user or stock `colors.toml` if the applied file is absent. It never writes theme files. Live sync checks the state generation and file metadata on a two-second cadence.

Color stages sample two field rows per terminal cell and paint them as a half-block, so the picture is continuous instead of a stripe on a flat background. The in-player gallery paints each theme's own roles on a miniature of the current scene. `NO_COLOR`, `TERM=dumb`, and `--no-color` dither density glyphs and emit no ANSI sequences. Truecolor is used when `COLORTERM` advertises it. `TERM` values containing `256color` quantize the palette; `xterm` and `linux` without that capability use the no-color renderer. Output rows are fixed to the current terminal width and height, and a standard-height frame reserves a row for the key legend.

## Transport and motion

The transport is a monotonic visual clock in seconds. Pause, seek, and rate changes preserve the anchor; the show loops at its declared duration. `full` tracks playhead movement. `reduced` keeps the current picture and then advances field time at 0.22×, so selecting it does not rewind the frame; shimmer is omitted. `still` freezes field time while transport remains seekable. Arrow seeks and chapter skips apply their signed delta, including across a wrap, so a short show does not reverse them; the half-show adjustment is only for unseeked loop wraps. This initial player does not decode or play audio and does not claim score-synchronized behavior. Audio and score mappings remain separate implementation decisions.

## Files

- `palette.py` and `omarchy.py`: role definitions and read-only theme resolution.
- `field.py`: deterministic abstract luminance/hue samples.
- `paint.py`: fixed-grid composition, half-block stage, theme-atlas cards, and ANSI serialization.
- `tty.py`: alternate-screen terminal runner and key handling.
- `show.py` and `transport.py`: minimal TOML show and clock.

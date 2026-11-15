# Terminally Agentic A/V

A terminal album library and visual player, with multiple palettes and live Omarchy theme sync.

## Status

Active — album library plus the abstract visual player. Four completed public albums are bundled. All rights remain reserved.

## Quick start

```bash
uv sync --group dev
uv run aav tracks
uv run aav play
uv run aav demo
```

`play` with no `--show` or `--scene` needs an interactive TTY. It lists the bundled albums. Enter opens the selected movement in the default browser at that movement's start. Click Play there: browser autoplay is blocked. The browser page is the full synchronized album; the terminal does not play the audio.

`aav demo` is the abstract visual player. `aav play --show /path/to/show.toml` and `aav play --scene garden` stay on that visual player too.

## Commands

| Task | Command |
|---|---|
| Build/install editable | `uv sync --group dev` |
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check` |
| Format | `uv run ruff format .` |
| Full gate | `uv run ruff format --check && uv run ruff check && uv run pytest` |

### Library controls

- `j` / `k` or `↑` / `↓`: select a track. The list wraps.
- `Enter`: open that movement in the default browser. Click Play on the page.
- `?`: help. `Esc`: close help. `q`: leave the library.

`aav tracks` prints the same catalog without a TTY, sorted by album artist, band, album title, then track number and title. Band is the album-artist credit. There are no separate per-track musician credits.

### Visual player controls

- `Space`: play/pause; `←` / `→`: seek five seconds.
- `j` / `k`: previous/next visual program.
- `t`: cycle palette; `Shift-T`: open the visual theme gallery; `1`–`9`: select a built-in palette.
- `o`: read and apply the current Omarchy palette now.
- `m`: cycle full, reduced, and still motion. Reduced continues from the current picture at a slower rate. Still holds that picture and its program until a seek, chapter skip, or another motion mode. `[` / `]`: change playback rate.
- `?`: help; `Esc`: return to the stage without applying a gallery browse; `q`: quit.

### Theme and preview examples

```bash
uv run aav themes
uv run aav preview --theme phosphor --scene aperture --at 8 --width 96 --height 28
uv run aav preview --theme newsprint --no-color
uv run aav gallery --theme tungsten --width 80 --height 24
uv run aav play --theme phosphor
```

Nine built-ins are included: tungsten, phosphor, broadcast, newsprint, signal, glacier, carbon, marigold, and void. `omarchy`, `sync`, and `system` load the active Omarchy theme. If Omarchy is unavailable, playback falls back to tungsten. `AAV_THEME` sets the default; `--theme` overrides it. `NO_COLOR`, `TERM=dumb`, a `TERM` that does not advertise `256color` or truecolor, and `--no-color` avoid ANSI output. The library uses the same palette and no-color rules.

Color frames sample the field twice per cell. `aav gallery` prints one stage frame for each built-in theme.

A show TOML file requires `title`, positive `duration` in seconds, and a non-empty list of `programs` (`garden`, `aperture`, `scan`, `tide`). Optional `detail` and integer `tempo` fields are shown in the player.

## Layout

- `src/agentic_av/` — CLI, album catalog, palettes, abstract field programs, renderer, and TTY loop.
- `src/agentic_av/albums/` — authorized public album HTML archives.
- `tests/` — isolated color, Omarchy, layout, clock, CLI, library, and input tests.
- `docs/` — architecture and decisions.
- `docs/plans/` — project roadmap.

## Documentation

See [docs/README.md](docs/README.md) for the documentation map. Project tracking: `10_Projects/Active/Terminally Agentic AV.md` in the project's vault.

## License

All rights reserved. No open-source license has been selected. See [LICENSE](LICENSE). The bundled albums are included under that same reservation; bundling them is not a license grant.

## Public scope

The four completed A-01 albums are authorized for public bundling: Coupon Seance, *Saturn Has a Dollar Store*; Drowning Collective, *Are We Fish?*; Nurse Log, *The Ground Moves Anyway*; Quiet Machinery, *The Atlas of Unlit Rooms*. All rights remain reserved. In-progress, archive, and other private material stay out of this repository. The visual demo uses original abstract terminal fields only.

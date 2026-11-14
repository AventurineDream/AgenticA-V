# Terminally Agentic A/V

A terminal player for polished abstract visual programs, with multiple palettes and live Omarchy theme sync.

## Status

Active — first CLI player implementation. Project-specific albums, identities, recordings, and visuals remain outside this repository.

## Quick start

```bash
uv sync --group dev
uv run aav themes
uv run aav preview --theme omarchy --width 80 --height 24
uv run aav play
```

`play` needs an interactive TTY. The default visual demo is abstract and contains no album media. To run a custom TOML show, use `uv run aav play --show /path/to/show.toml`.

## Commands

| Task | Command |
|---|---|
| Build/install editable | `uv sync --group dev` |
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check` |
| Format | `uv run ruff format .` |
| Full gate | `uv run ruff format --check && uv run ruff check && uv run pytest` |

### Player controls

- `Space`: play/pause; `←` / `→`: seek five seconds.
- `j` / `k`: previous/next visual program.
- `t`: cycle palette; `Shift-T`: open the visual theme gallery; `1`–`9`: select a built-in palette.
- `o`: read and apply the current Omarchy palette now.
- `m`: cycle full, reduced, and still motion. Reduced continues from the current picture at a slower rate. `[` / `]`: change playback rate.
- `?`: help; `Esc`: return to the stage; `q`: quit.

### Theme and preview examples

```bash
uv run aav themes
uv run aav preview --theme phosphor --scene aperture --at 8 --width 96 --height 28
uv run aav preview --theme newsprint --no-color
uv run aav gallery --theme tungsten --width 80 --height 24
```

Nine built-ins are included: tungsten, phosphor, broadcast, newsprint, signal, glacier, carbon, marigold, and void. `omarchy`, `sync`, and `system` load the active Omarchy theme. If Omarchy is unavailable, playback falls back to tungsten. `AAV_THEME` sets the default; `--theme` overrides it. `NO_COLOR`, `TERM=dumb`, a `TERM` that does not advertise `256color` or truecolor, and `--no-color` avoid ANSI output.

Color frames sample the field twice per cell. `aav gallery` prints one stage frame for each built-in theme.

A show TOML file requires `title`, positive `duration` in seconds, and a non-empty list of `programs` (`garden`, `aperture`, `scan`, `tide`). Optional `detail` and integer `tempo` fields are shown in the player.

## Layout

- `src/agentic_av/` — CLI, palettes, abstract field programs, renderer, and TTY loop.
- `tests/` — isolated color, Omarchy, layout, clock, CLI, and input tests.
- `docs/` — architecture and decisions.
- `docs/plans/` — project roadmap.

## Documentation

See [docs/README.md](docs/README.md) for the documentation map. Project tracking: `10_Projects/Active/Terminally Agentic AV.md` in the project's vault.

## License

All rights reserved. No open-source license has been selected. See [LICENSE](LICENSE).

## Public scope

This repository is for reusable creative process and tooling. Individual band identities, albums, recordings, artwork, and production materials are not included. The visual demo uses original abstract terminal fields only.

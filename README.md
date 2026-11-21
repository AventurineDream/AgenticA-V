# Terminally Agentic A/V

A terminal album library and visual player, with multiple palettes and live Omarchy theme sync.

## Status

Active — album library plus the abstract visual player. Eight albums are bundled: the four completed A-01 albums and four A-02 albums recorded in ADR 0002. Code is MIT-licensed; bundled albums are CC0 (see License).

## Quick start

```bash
uv sync --group dev
uv run aav tracks
uv run aav play
uv run aav demo
```

`play` with no `--show` or `--scene` needs an interactive TTY. Enter plays a movement with a new numpy-painted, audio-reactive mosaic scene. Playback needs `mpv` (preferred; its media position is the clock) or `ffplay`. `ffmpeg` enables cached audio analysis; without it, audio still plays and the transport explicitly reports quiet visuals. `o` opens the synchronized web page instead; click Play there, since browser autoplay is blocked.

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
- `s`: toggle sorting by band or album; the highlighted movement stays selected.
- At 72 columns by 16 rows or larger, the highlighted song's album cover and description appear beside the list.
- `Enter`: play that movement in the terminal.
- `o`: open the album's web page in the default browser at that movement. Click Play on the page.
- `?`: help. `Esc`: close help. `q`: leave the library.

### Album playback controls

- `Space`: pause or resume. `←` / `→`: seek 10 seconds.
- `n` / `p` (or `j` / `k`): next or previous movement. Playback continues into the next movement on its own.
- `m`: hold the picture (still) or let it move again. `aav play --motion reduced` slows the picture to 0.22×, and `--motion still` starts held. Audio is unaffected.
- `f`: toggle full-screen visuals; the stage fills the terminal and hides the transport.
- `q` / `Esc`: back to the library.
- `g`: cycle octant, sextant, quadrant, half-block, braille, and ASCII mosaics.

`aav tracks` prints the same catalog without a TTY, sorted by album artist, band, album title, then track number and title. Band is the album-artist credit. There are no separate per-track musician credits.

`aav play --glyphs half` selects a tier; `--glyphs auto` (the default) honors
`AAV_GLYPHS`, otherwise selects octants for kitty, ASCII for Linux consoles/dumb
terminals, and half-blocks elsewhere. Font support varies: cycle with `g` if a
glyph is missing. Large canvases step down sampling resolution to bound work.
Playing targets 30 fps; paused or still pictures are held at 5 transport updates
per second. Slow frames are dropped rather than queued. Reduced motion uses
0.22× picture time and gentler reactivity. `--no-color` preserves geometry with
ordered monochrome dithering; cursor positioning remains necessary in the TTY.

See the [scene guide](docs/visuals.md) for all 37 movements and preview commands.
The regional flash meter is a conservative regression heuristic, not a
certification of flash safety; use reduced/still motion as needed.

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

Nine built-ins are included: tungsten, phosphor, broadcast, newsprint, signal, glacier, carbon, marigold, and void. `omarchy`, `sync`, and `system` load the active Omarchy theme read-only. If unavailable, playback falls back to tungsten. `AAV_THEME` sets the default; `--theme` overrides it. `NO_COLOR`, `TERM=dumb`, a terminal without advertised color, and `--no-color` disable color escapes. Interactive output still uses cursor/control sequences. Native scenes use album palettes; the active theme colors their transport text, and an accent from the album's cover or palette colors its rail and labels.

### App icon

The piano-camera icon set lives under `assets/icons/piano-camera-icons-final/`: the default orange-on-teal set plus eight color variants, each with a 1024 PNG, SVG masters, a full AppIcon.iconset, and a macOS .icns, plus a menu-bar template icon.

```bash
uv run aav icons            # list the nine variants
uv run aav icons pick red-orange   # save the choice and install it
uv run aav icons install    # install the saved variant (or the default)
uv run aav icons show       # saved variant and install state
```

On Linux, `install` writes `~/.local/share/applications/agentic-av.desktop` (which launches `aav play` in a terminal) and the chosen variant's iconset PNGs into `~/.local/share/icons/hicolor/` (plus the menu-bar template as `agentic-av-menubar` at 18/36/54), then refreshes the desktop and icon caches when their tools exist. Only files this app owns are written; no desktop or Omarchy configuration is edited. The choice is saved in `~/.config/agentic-av/icons.toml`.

macOS has no app bundle in this repository, so `install` there reports the chosen variant's .icns path instead of installing; the picker still saves the choice. The menu-bar template has no color variants and no consumer in this repository yet, so it is not installed.

Color frames sample the field twice per cell. `aav gallery` prints one stage frame for each built-in theme.

A show TOML file requires `title`, positive `duration` in seconds, and a non-empty list of `programs` (`garden`, `aperture`, `scan`, `tide`). Optional `detail` and integer `tempo` fields are shown in the player.

## Layout

- `src/agentic_av/` — CLI, album catalog, palettes, abstract field programs, renderer, and TTY loop.
- `src/agentic_av/albums/` — authorized public album HTML archives.
- `src/agentic_av/artwork/` — the bundled A-02 cover JPEGs, hash-checked on load.
- `tests/` — isolated color, Omarchy, layout, clock, CLI, library, and input tests.
- `docs/` — architecture and decisions.
- `docs/plans/` — project roadmap.

## Documentation

See [docs/README.md](docs/README.md) for the documentation map. Project tracking: `10_Projects/Active/Terminally Agentic AV.md` in the project's vault.

## License

Code in this repository is licensed under the MIT License — see [LICENSE](LICENSE). The bundled albums (audio and album artwork) are dedicated to the public domain under CC0 — see [LICENSE-CC0](LICENSE-CC0). Material not bundled in this repository (source archives, stems, candidate artwork) is not covered by either.

## Public scope

The four completed A-01 albums are authorized for public bundling: Coupon Seance, *Saturn Has a Dollar Store*; Drowning Collective, *Are We Fish?*; Nurse Log, *The Ground Moves Anyway*; Quiet Machinery, *The Atlas of Unlit Rooms*. Nurse Log, *The Forest Has a Pocket* (A-02) is also bundled under Aven's single-album approval dated 2026-11-18. That approval supersedes the source archive's `public_release: false` flag for that album only; it does not cover the source ZIP, stems, candidate artwork, or other A-02 material. A-02's selected cover is bundled under the cover amendment in ADR 0002. Drowning Collective, *The Shape That Stays* (A-02, made by openai-codex/gpt-6.1-sol), Coupon Seance, *Buy One, Haunt One Free* (A-02, made by anthropic/claude-opus-5-5), and Quiet Machinery, *Instruments for Measuring Dusk* (A-02, made by anthropic/claude-opus-5-5), with their agent-proposed covers, are bundled under Aven's 2026-11-18 run instruction, recorded in ADR 0002; their source packages, stems and other cover candidates are not bundled. The four A-01 covers Aven selected on 2026-11-18 are bundled under their own ADR 0002 amendment; their unselected candidates are not. The bundled albums and bundled cover art are dedicated to the public domain under CC0 (see License). In-progress, archive, and other private material stay out of this repository. The visual demo uses original abstract terminal fields only.

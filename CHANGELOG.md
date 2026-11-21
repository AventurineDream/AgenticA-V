# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- Bundle Fog's Omarchy themeable piano-camera icon under `assets/icons/omarchy-themeable/`: one icon that recolours itself to the active Omarchy theme (built-in or custom) via `piano-camera-theme-icon` and a theme-set hook that redraws it on every theme switch, with contrast checks and prebaked output for all 23 built-in themes. Install per user with `./install.sh` (or `--name <IconName>` to match the app's `.desktop` file).
- Add `aav icons follow`: the installed app icon follows the live Omarchy theme. An explicit theme-to-variant table wins (blackwater -> mono-dark today; Fog's theme-matched icon files plug in as new variant directories + mapping entries when they land). Themes with no dedicated file fall back to the closest plate/body colors among the theme's light/dark family (dark themes never land on a light plate). Follow is off by default so existing manual picks are untouched; a manual `pick` turns it back off. The icon re-syncs at `aav play` startup and when the live theme changes while the visual player runs. `aav icons show` and `list` report the follow state and the followed variant.
- Bundle *The Shape That Stays* (Drowning Collective A-02): six original instrumentals, 27:12, made by `openai-codex/gpt-6.1-sol`. Add the `undertow` native scene family, independent piano-hand score queries, six inline MP3s and an agent-proposed baseline JPEG cover. Aven's 2026-11-18 instruction authorizes making, bundling and PR; merge is publication approval and cover confirmation/swap, not listening-review approval.
- Add `aav icons`: list the nine piano-camera icon variants, pick one to save and install, install the saved choice, and show the install state. On Linux, install writes `agentic-av.desktop` and the chosen variant's iconset PNGs into the hicolor theme under `~/.local/share`; the choice is saved in `~/.config/agentic-av/icons.toml`. The default variant installs when no choice is saved. The menu-bar template is installed alongside as `agentic-av-menubar` at 18/36/54. macOS reports the chosen variant's .icns path instead of installing, since this repository has no app bundle.
- Add the final piano-camera app icon set (v2.2) under `assets/icons/piano-camera-icons-final/`: default orange-on-teal plus eight color variants, full AppIcon.iconsets, .icns files, and a macOS menu bar template icon.
- Add an album library. Bare `aav play` selects from six public albums, with native audio through mpv (or ffplay), movement navigation, seeking, and browser opening. Warm plays reuse cached extraction and scores.
- `o` in the library opens the movement on the album's synchronized web page in the default browser. Click Play there; autoplay is blocked.
- Add `aav tracks`, a sorted noninteractive catalog. Album artist and band are the same credit.
- Bundle the four completed A-01 album players as gzip HTML, plus *The Forest Has a Pocket* (Nurse Log, A-02) under Aven's single-album approval dated 2026-11-18. Bundled media follows the CC0 license amendment below.
- Add *The Forest Has a Pocket* visuals: six numpy scenes (root, rain, spiral, canopy, spores, river) in a `pocket` family, separate from the A-01 forest painter.
- Bundle Coupon Seance A-02, *Buy One, Haunt One Free* (six instrumentals, 26:43, made by anthropic/claude-opus-5-5), with its agent-proposed cover, under Aven's 2026-11-18 run instruction. Its visuals are six numpy scenes (perihelion, haunt-free, aisle, coin-return, layaway, change) in a `haunt` family, separate from the A-01 coupon painter. With two Coupon Seance albums, `preview` now needs the family or album title rather than the artist name, as Nurse Log already did.
- Bundle Quiet Machinery A-02, *Instruments for Measuring Dusk* (six instrumentals, 26:36, made by anthropic/claude-opus-5-5), with its agent-proposed cover, under Aven's 2026-11-18 run instruction. Its visuals are six numpy scenes (survey, sheets, bell, faults, warm-room, transmission) in a `dusk` family, separate from the A-01 rooms painter. With two Quiet Machinery albums, `preview` now needs the family or album title rather than the artist name, as Nurse Log already did.
- Add an abstract terminal A/V player, nine named palettes, live Omarchy theme sync, and preview/gallery commands.
- Add full, reduced, and still motion modes with a terminal-color fallback.
- Show each album's bundled cover as a still panel beside the native player's stage. Each cover's SHA-256 is checked before Pillow decodes it. The panel is omitted below six canvas rows or when it would leave a stage narrower than 30 columns. For square art with 2:1 terminal cells, it appears from 44 columns; taller cells can require more. Failed verification is noted in the transport.
- Bundle the four A-01 covers Aven selected on 2026-11-18 (Saturn 4, Fish 1, Ground 3, Atlas 4) as hash-pinned `CoverArt` records, byte-identical to their Drive selection receipts (ADR 0002 amendment). Every bundled album now shows a cover.
- Add library sort modes for band and album, keeping the same highlighted movement when the order changes. On wide terminals, show the highlighted album's verified cover and description beside the track list.

### Changed

- Polish the native player's presentation (#20). Covers are framed after a two-column margin and captioned with album title and artist, and are now resampled in linear light with Lanczos for crisper detail (from 46 columns for square art). A splash shows the cover and letter-spaced title while the album loads. Each movement opens with a four-second title card on a scrim, faded in truecolor full motion, and scene crossfades are eased. One album accent, from the cover's dominant hue or the movement palette, is lifted to 3:1 contrast and colors the caption, state label, title card, and rail. The rail gains a half-cell playhead and rising section ticks. The status row adds play/pause glyphs and movement position, and keeps state, clock, and `q back` from 30 columns.
- License the repository: code under the MIT License (LICENSE); the bundled albums and bundled cover art dedicated to the public domain under CC0 (LICENSE-CC0). Material not bundled in this repository stays out and is not covered.
- Replace the legacy glyph port with 37 numpy-painted audio-reactive mosaic scenes. Cached seven-band audio analysis and normalized scores drive distinct album worlds; missing analysis explicitly falls back to quiet visuals without blocking audio.
- Add automatic terminal glyph selection, `--glyphs`, `AAV_GLYPHS`, and runtime `g` cycling. Large canvases step down their sub-pixel tier.
- Native playback targets 30 fps (5 transport updates/s when paused or still), batches one synchronized write per frame, and skips unchanged canvas rows. Add section names, progress, and section ticks to transport.
- Add scene previews, benchmarks, and a conservative regional flash-risk regression meter. This is not flash-safety certification.
- Replace extraction sidecar revision 2 with revision 3, retaining full normalized scores and removing obsolete simplified event rows.

- Refine the four A-02 native visualizer families for denser detail and smoother motion without changing their album identities.
- Add `f` full-screen mode to native album playback; the stage fills the terminal without transport chrome, survives resizes and movement changes, and returns to the normal page with `f`.
- The abstract visual player is `aav demo`. `aav play --show` and `aav play --scene` keep the previous visual behavior. `preview`, `themes`, and `gallery` are unchanged.

- Color stages sample both halves of each cell, and the four scenes use distinct motifs instead of similar bands.
- The in-player theme gallery shows labeled cards with role chips and miniature field art. `aav gallery` prints one stage frame per built-in theme.
- A standard-height frame keeps the key legend instead of clipping it.

### Fixed

- Scale the piano-camera icon tile up inside its canvas: the whole tile (plate + camera together, camera proportions unchanged) is drawn 1.2x larger, so the icon reads the same size as other app icons instead of ~20% smaller. SVGs, re-rendered PNGs, and the Omarchy kit templates plus prebaked/demo renders are updated; .icns files still carry the previous art (no macOS tooling on Linux).
- Replace the piano-camera icon set with Fog's corrected set: the top highlight fade and the glow behind it are drawn in the rounded plate shape itself instead of relying on clip-paths, so viewers that ignore clipping no longer show faint square corners at the top of the icon. The artwork is otherwise unchanged. This supersedes the sheen fade-in in the entry below.
- Install the variant's `AppIcon.svg` as the scalable hicolor icon. Docks prefer the scalable SVG when present, and install never wrote it, so a stale SVG could keep showing after a pick. Stale copies of the app's icon at sizes install never writes (22/24/48, left by old hand-installs) are removed for the same reason.
- Fix the piano-camera icon sheen: the top-light gradient started at full brightness exactly on the tile's top edge, which read as faint sharp corners at small sizes. The sheen now fades in below the edge in all nine variants; the SVGs and their re-rendered PNG iconsets are updated. The .icns files and preview sheets still carry the previous art (no macOS bundle tooling on Linux).
- Still motion keeps the selected visual program when transport crosses a chapter. A seek, chapter skip, or leaving still updates it.
- Canceling the theme gallery with Escape no longer changes the next theme cycle.
- SIGTERM restores canonical mode, echo, the cursor, and the primary screen.
- Reduced and still motion changes no longer rewind or skip the picture. Reduced motion continues from the current frame at 0.22×.
- Theme cycling and the gallery follow the active built-in. A live Omarchy palette is not treated as the last built-in, and Enter does not apply one until a built-in is chosen.
- Quit and Ctrl-C leave help and the theme gallery. Esc still returns to the stage.
- Pausing or resuming in still mode no longer replaces the held picture with the playhead. Seeks and chapter skips still update it.
- Seeks and chapter skips keep their direction on short shows and one-program reels. Unseeked loop wraps still advance forward.
- 256-color output is used only when `TERM` advertises `256color`.
- Show titles and details cannot inject terminal control characters into preview or raw-mode output.
- Wide and combining characters in a show title or detail stay on the fixed grid. CJK, emoji, and regional indicators become one cell; combining marks and zero-width Hangul jamo are removed.
- Arrow keys split across terminal reads resolve to navigation instead of Escape plus a letter. A lone Escape still closes overlays after a short silence.
- 256-color quantization uses the xterm cube levels (0, 95, 135, 175, 215, 255) and gray ramp (8 through 238). Black and white stay indexes 16 and 231 when those are nearer.
- 256-color output keeps the hue of dark, muted colors. Nearest-color matching sent them to the gray ramp because the cube has no dark muted entries, so Coupon Seance's violet sky rendered gray with stray blue and red specks. When the nearest entry is neutral but the color has visible OKLab chroma, the nearest cube entry of the same hue family (within 12° and 0.16 lightness) is used instead, and the hue choice ignores the dither so a flat field stays one color. The rule is shared with the chrome, so six built-in palette roles also take their hue in 256 colors: the broadcast, phosphor, and void borders and broadcast selection (blue or green, was gray) and the newsprint and marigold greens. Grays, near-black tints, and truecolor output are unchanged.
- Live Omarchy sync notices edits to the resolved palette, including a user or stock fallback, not only the applied state file.
- Restore the project roadmap at `docs/plans/PROJECT-ROADMAP.md`.

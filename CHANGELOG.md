# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- Add an abstract terminal A/V player, nine named palettes, live Omarchy theme sync, and preview/gallery commands.
- Add full, reduced, and still motion modes with a terminal-color fallback.

### Changed

- Color stages sample both halves of each cell, and the four scenes use distinct motifs instead of similar bands.
- The in-player theme gallery shows labeled cards with role chips and miniature field art. `aav gallery` prints one stage frame per built-in theme.
- A standard-height frame keeps the key legend instead of clipping it.

### Fixed

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
- Live Omarchy sync notices edits to the resolved palette, including a user or stock fallback, not only the applied state file.
- Restore the project roadmap at `docs/plans/PROJECT-ROADMAP.md`.

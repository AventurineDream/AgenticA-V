# Terminally Agentic A/V — Agent Guide

<!-- Owner: Aven. Maintained by: Malachite. Last verified: 2026-11-14. -->

## Purpose and sources of truth

This repository contains the terminal album library and reusable visual player tooling. Project direction and scope are in `docs/plans/PROJECT-ROADMAP.md`; implementation contracts are in `docs/architecture.md`. The project's vault note is `10_Projects/Active/Terminally Agentic AV.md`.

## Setup

```bash
uv sync --group dev
```

## Commands

| Task | Command |
|---|---|
| Format | `uv run ruff format .` |
| Lint | `uv run ruff check .` |
| Typecheck | Not configured |
| Test (fast) | `uv run pytest` |
| Test (full / slow) | `uv run pytest` |
| Full gate (run before handoff) | `uv run ruff format --check && uv run ruff check && uv run pytest` |

## Definition of done

1. The full gate passes and its command/result are in the handoff.
2. New or changed behavior has a user-visible test.
3. Comments meet Aven Code Standard §5.4 for every touched source file.
4. `CHANGELOG.md` Unreleased is updated for user-visible changes.
5. Keep diffs focused on a feature branch; do not push or merge without direction.

## Conventions

- Public scope is eight albums: the four completed A-01 albums, Nurse Log A-02 under Aven's single-album approval, and Drowning Collective A-02, Coupon Seance A-02, and Quiet Machinery A-02 under her 2026-11-18 make/bundle/PR run instruction (ADR 0002). Merge is her publication approval. The four A-01 covers and Nurse Log A-02's cover are creator-selected; the Drowning Collective, Coupon Seance, and Quiet Machinery A-02 covers are agent-proposed and approved at merge. All are hash-pinned. Bundled albums and covers are CC0; code is MIT (LICENSE and LICENSE-CC0). Do not add other albums, in-progress work, archives, stems, source ZIPs, candidate artwork, or private material.
- Album artist and band are the same credit. The sources have no distinct per-track musician credits; do not invent any.
- Bundled `.html.gz` archives are read-only.
- `aav play` with no `--show` or `--scene` is the album library. `aav demo`, and `aav play --show` or `--scene`, are the abstract visual player. `preview`, `themes`, and `gallery` stay on that visual path.
- `colors.toml` is read-only. Omarchy theme changes are discovered from its applied state; the player never edits desktop configuration.
- Time values are seconds, terminal dimensions are character cells, and palettes are immutable role sets.
- Motion modes are `full`, `reduced`, and `still`; always preserve the no-color renderer.
- Enter in the library plays natively: `native.py` extracts cached audio and normalized scores, loads audio features, and drives `viz/stage.py`. New numpy scenes in `viz/albums/` replace the legacy faithful glyph port (ADR 0004). mpv's `time-pos` is the clock; ffplay is the fallback. Preserve input, seek, exact held pictures, cleanup, no-color output, and quiet-analysis failure notes.
- Native album playback keys: `j` / `l` seek 10 seconds, `k` or `Space` pauses/resumes, `←` / `→` change movement, and `f` toggles full screen. In the library, `s` sorts by band or album.
- Native images are linear RGB numpy surfaces, fitted to width-one mosaic cells and encoded as bytes. Keep one synchronized output write per frame; never clear the canvas per frame. Tier detection and sub-pixel budgeting belong in `viz/caps.py`.
- Audio moves geometry, not beat-synchronized light. `FlashMeter` is a conservative regional regression heuristic with viewing assumptions, not WCAG certification. Preserve reduced/still controls and test visible behavior rather than pinning art glyphs.
- For parallel work, format/lint/test only owned files; the integration owner runs the full gate after all slices land. Scene changes require deterministic, silent, motion, timing, and rendered-image review.

## Boundaries

Do not add private band content or choose a code/media license on Aven's behalf. Do not edit Omarchy configuration from this repository. Do not overwrite the bundled album archives. Avoid compatibility aliases that hide a changed CLI contract.

## Repository map

- `src/agentic_av/` — CLI, album catalog, palettes, field programs, TTY runtime, and renderer.
- `src/agentic_av/albums/` — authorized public album HTML archives. Do not overwrite them.
- `src/agentic_av/artwork/` — the bundled album cover JPEGs (A-01 and A-02), hash-checked on load. Do not overwrite them.
- `src/agentic_av/viz/albums/undertow.py` — six Drowning Collective A-02 scenes; object score rows preserve Iris's separate `right`/`left` voices.
- `tests/` — isolated palette, layout, CLI, transport, library, and input tests.
- `docs/` — architecture and decision records.
- `docs/plans/` — project roadmap.

## Handoff

Summarize changed files and behavior, commands run with results, and anything unverified.

# Terminally Agentic A/V — Agent Guide

<!-- Owner: Aven. Maintained by: Malachite. Last verified: 2026-11-13. -->

## Purpose and sources of truth

This repository contains reusable terminal-friendly visual player tooling. Project direction and scope are in `docs/plans/PROJECT-ROADMAP.md`; implementation contracts are in `docs/architecture.md`. The project's vault note is `10_Projects/Active/Terminally Agentic AV.md`.

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

- The terminal player contains abstract reusable visual programs only. Band identities, album titles, audio, artwork, and production media stay outside this repository.
- `colors.toml` is read-only. Omarchy theme changes are discovered from its applied state; the player never edits desktop configuration.
- Time values are seconds, terminal dimensions are character cells, and palettes are immutable role sets.
- Motion modes are `full`, `reduced`, and `still`; always preserve the no-color renderer.

## Boundaries

Do not add private band content or choose a code/media license on Aven's behalf. Do not edit Omarchy configuration from this repository. Avoid compatibility aliases that hide a changed CLI contract.

## Repository map

- `src/agentic_av/` — CLI, palettes, field programs, TTY runtime, and renderer.
- `tests/` — isolated palette, layout, CLI, transport, and input tests.
- `docs/` — architecture and decision records.
- `docs/plans/` — project roadmap.

## Handoff

Summarize changed files and behavior, commands run with results, and anything unverified.

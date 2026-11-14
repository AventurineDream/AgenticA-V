# 0001 — Build a stdlib terminal player around shared frames

## Context

The project roadmap calls for terminal-friendly visual interpretations and a CLI player, but no runtime or audio engine has been selected. The current request prioritizes a polished look, multiple themes, and Omarchy theme sync. A full UI framework would add dependency and version surface before the rendering contract is known.

## Decision

Use a small Python CLI with a pure fixed-grid painter and a standard-library raw-TTY runner. Both `preview` and interactive playback use the same composed frame. Keep transport as a monotonic visual clock and keep demo imagery abstract. Read the active Omarchy `colors.toml` without changing it. Offer named palettes for users without Omarchy and support full, reduced, still, and no-color output.

## Consequences

The result is easy to test and does not add runtime dependencies. The custom TTY runner must always restore terminal attributes and preserve cell dimensions. Audio decoding, MIDI, score synchronization, catalog installation, and project-specific media are not part of this decision; they remain future, independently validated choices.

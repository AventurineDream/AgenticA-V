# 0006 — Follow the live Omarchy theme for the app icon

## Context

`aav icons` (0005) picks are fully manual: `pick <variant>` saves one of the
nine piano-camera variants and installs it. Moths asked for the icon to
match the user's theme both ways: the Omarchy theme specifically (the
player already follows the live Omarchy palette for its own visuals) and
light/dark. The mono-dark / mono-light pair already covers a light/dark
split, and Fog is making dedicated theme-matched icon files for named
themes; those files are not in this repository yet and must not be invented
here. A saved manual pick must keep winning over any automatic choice, so
nobody's explicit choice gets overridden. The boundary from 0005 stands:
the player never edits desktop or Omarchy configuration.

A second gap surfaced while installing the sheen fix: `install` wrote the
seven iconset PNGs but never the variant's `AppIcon.svg` as the scalable
hicolor icon, and never wrote 22/24/48. Docks prefer the scalable SVG when
present, so a stale SVG (or a stale 48 px file left by a hand-install) kept
showing after a pick. The install contract needs to cover the scalable icon.

## Decision

Add a `follow_theme` preference to `$XDG_CONFIG_HOME/agentic-av/icons.toml`
(default false; existing files gain the key on their next save). `aav icons
follow` turns follow on and installs the live theme's variant; `aav icons
pick <variant>` turns follow off and installs the manual choice; `aav icons
show` and `list` report the follow state and the followed variant.

Resolution order for a live theme:

1. An explicit theme-slug -> variant table (`_THEME_VARIANT_OVERRIDES` in
   `icons.py`). Today it holds one entry, blackwater -> mono-dark.
   Fog's theme-matched icon files plug in here as new variant directories
   + mapping entries when they land; wiring them in is a data change, not
   a code change. A TODO in the table marks lavender-rain as the next
   expected entry.
2. Fallback color derivation for themes with no dedicated file: among the
   variants whose plate luminance matches the theme's light/dark family
   (dark theme -> dark plate, light theme -> light plate), the closest
   plate to the theme background plus the closest body to the theme
   accent, by squared RGB distance. The plate/body colors are a static
   table read from the shipped `AppIcon.svg` files (mid stop of the
   `plate` gradient, first stop of the `bg1` body gradient), pinned to
   the SVGs by `test_variant_plate_colors_match_svgs`, so a Fog recolor
   fails loudly instead of silently drifting the derivation. The family
   split is unambiguous in the shipped set: every dark plate is below
   0.1 luminance, both light plates (blue-violet, mono-light) are above
   0.6. With the current set, lavender-rain falls back to mono-dark.

Follow syncs in two places, and only when the resolved variant differs
from the installed one (a poll must not rewrite files):

- At `aav play` startup, in both the album-library path and the visual
  player path. Best-effort and silent: no Omarchy theme or an install
  error never breaks play; the next launch retries.
- On Omarchy generation-token change in the visual player's live-sync
  loop (`tty.py`, every 2 s when follow is on), using the already-loaded
  theme. The stage palette is never touched by this check, so the icon
  follows the theme even while the stage uses a built-in palette. The
  preference is re-read each poll, so a `pick` in another terminal (which
  turns follow off) takes effect mid-session.

`install` now also writes the variant's `AppIcon.svg` to
`hicolor/scalable/apps/agentic-av.svg` and removes stale copies of this
app's icon at the sizes it never writes (22/24/48). Both are files this
app owns; no desktop, Omarchy, or system configuration is touched, and
`aav icons install` keeps its 0005 meaning (install the saved choice).

## Consequences

With follow on, the dock icon tracks the Omarchy theme across theme
switches without manual picks, and a manual pick always wins until follow
is turned back on. With follow off (the default), nothing changes: picks,
installs, and saved choices behave exactly as in 0005, except the
preference file now carries a `follow_theme` key and installs write the
scalable SVG. The override table is the single place where a named theme's
intended match lives; the color derivation is only a fallback, and its
choices (mono-dark for both live dark themes today) are Aven's to correct
when Fog's dedicated files arrive. Open for Aven: whether lavender-rain
should get a dedicated file (its lavender accent currently loses to
mono-dark's neutral plate/body distances), and whether `aav icons install`
should stay saved-variant-only while follow is on.

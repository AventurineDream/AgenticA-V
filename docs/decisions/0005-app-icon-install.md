# 0005 — Install the piano-camera icon set with an `aav icons` picker

## Context

PR #11 bundled the final piano-camera icon set (default plus eight color
variants, full AppIcon.iconsets, .icns files, and a macOS menu-bar template)
and deliberately left the wiring out of scope: default icon choice/install and
an icon picker. The app is a terminal CLI installed editable with `uv sync`;
there is no .desktop file, no macOS app bundle, and no GUI settings surface.
The icon README's macOS notes (apply a saved preference with
`applicationIconImage` on launch, or set a custom Finder icon on the bundle)
assume an app that does not exist here. The player never edits desktop or
Omarchy configuration; the icon install must respect that boundary.

## Decision

Add `aav icons` with four subcommands: `list` (nine variants with
descriptions), `pick <variant>` (save the choice and install it), `install`
(install the saved choice, or the default when none is saved), and `show`
(saved variant and install state). The choice is saved in
`$XDG_CONFIG_HOME/agentic-av/icons.toml` as a single `variant` key.

On Linux, `install` writes only files this app owns: an
`agentic-av.desktop` launcher (`Exec` is the `aav` entry point for the
running installation, `Terminal=true`, `Icon=agentic-av`) under
`$XDG_DATA_HOME/applications/`, and the chosen variant's iconset PNGs into
the freedesktop hicolor theme under `$XDG_DATA_HOME/icons/hicolor/` at
16/32/64/128/256/512/1024, and the menu-bar template as `agentic-av-menubar`
at 18/36/54. Desktop and icon caches are refreshed
best-effort when their tools exist; a missing tool never fails the install.
The installed variant is identified by content (SHA-256 of the installed
1024 PNG), not by a stored name, so `show` reports honestly after a
hand-edited install.

macOS has no app bundle in this repository, so `install` there reports the
chosen variant's .icns path and the icon README instead of pretending to
install; `pick` still saves the choice. The menu-bar template (18/36/54
PNGs) has no color variants; it is installed alongside the variant as
`agentic-av-menubar` in the hicolor theme, identically for every variant, so
a future menu-bar consumer can find it by name.

The icon assets stay at `assets/icons/piano-camera-icons-final/` and are
resolved from the repository root at runtime; the project is installed
editable, per its own README. If the project ever ships a wheel, the icons
need to move under `src/` or be added as data files.

## Consequences

Launchers and docks on Linux show the piano-camera icon for `aav play`, and
the user can switch among the nine variants from the CLI. The install never
touches Omarchy or system configuration, and it never overwrites another
app's files. A macOS app bundle and a menu-bar consumer remain future,
independently validated choices; the .icns files are already in the repository
for the bundle, and the menu-bar template is installed for the consumer.

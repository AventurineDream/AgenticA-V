# Piano-camera icon — Omarchy themeable (v2.2)

One icon that re-colours itself to **whatever Omarchy theme is active**, built-in or custom.
The art is the approved v2.2 creature; only colours change.

## Install (per user, no sudo)

    unzip piano-camera-omarchy-themeable.zip && cd omarchy-themeable
    ./install.sh                      # icon name "piano-camera"
    ./install.sh --name <IconName>    # if the app's .desktop file says Icon=<IconName>

This puts:

| what | where |
|---|---|
| the recolour script | `~/.local/bin/piano-camera-theme-icon` |
| the colour-slot templates | `~/.local/share/piano-camera-icon/templates/` |
| the theme-change hook | `~/.config/omarchy/hooks/theme-set.d/piano-camera-icon` |
| the icon (scalable SVG + 16/32/48/64/128/256/512 PNG) | `~/.local/share/icons/hicolor/<size>/apps/piano-camera.{svg,png}` |

After that, every `omarchy theme set …` (menu, keybind or CLI) redraws the icon in the new theme's colours. The hook runs in the background, so switching doesn't slow down.
The app's `.desktop` file just needs `Icon=piano-camera` (no path). To remove it, run `./install.sh --uninstall`.
To redraw it by hand, run `piano-camera-theme-icon`. For a palette file that isn't installed, run `piano-camera-theme-icon --colors my.colors.toml --out /tmp/x --no-install`.

## How it works

* **Templates.** `templates/piano-camera{,-32,-16}.svg.tmpl` are the v2.2 SVGs, with each colour replaced by a named slot (`{{ plate_top }}`, `{{ plate_mid }}`, `{{ plate_bottom }}`, `{{ glow }}`, `{{ floor_shadow }}`, `{{ body }}`, `{{ body_hi }}`, `{{ body_shade }}`, `{{ ball_hi }}`, `{{ ring }}`, `{{ keys }}`, `{{ key_black }}`, `{{ ink }}`, `{{ glass }}`, `{{ edge }}`, `{{ edge_opacity }}`).
  * The 16 and 32 px templates are the thicker-line small-size drawings.
  * The SVGs use no clip-paths, so they render the same in every viewer.
  * Filled with `--classic`, they are pixel-identical to the default orange icon.
* **Palette lookup**, first hit wins:
  1. `omarchy-theme-color --all`: Omarchy's own resolver, with its aliases and fallbacks;
  2. `~/.local/state/omarchy/current/theme/colors.toml`: current Omarchy;
  3. `~/.config/omarchy/current/theme/colors.toml` or `alacritty.toml`: older Omarchy, and themes that only ship alacritty colours;
  4. the classic orange-on-teal icon.
* **Colour rules**:
  * The plate is built from the theme `background`, with `lighter_background` and `darker_background` where present (otherwise mixed).
  * The body is the theme `accent`.
  * Values can be written as `#rgb`, `#rrggbb`, `#rrggbbaa`, `0xRRGGBB` or `rgb()`.
  * Light or dark comes from `mode` (or `theme_type`), else from the background's luminance.
* **Contrast check**:
  * The body must reach at least 3:1 against the plate. If the accent doesn't, the script tries blue, yellow, orange, magenta, cyan, green, red and then foreground, in that order.
  * The body is then nudged lighter or darker until it reaches at least 3:1 against the dark outline ink and at least 1.6:1 against the plate.
  * What it chose and the ratios are written to `~/.local/share/icons/hicolor/.piano-camera-palette.json`.
* **Output**:
  * PNGs are made with rsvg-convert (librsvg; normally already installed on Omarchy as a GTK dependency). The fallbacks are ImageMagick, Inkscape and Python cairosvg; with none of them it installs the SVG only.
  * Files are swapped in atomically.
  * The script then runs `gtk-update-icon-cache -f -t` on the user hicolor folder.

## What's in this folder

* `demo/`: the script run against 4 real built-in palettes (tokyo-night, catppuccin-latte, gruvbox, rose-pine) and 2 made-up ones.
  * `my-custom-swamp` has no `mode`, an 8-digit background, and an accent too dark to read. The contrast check swaps in magenta.
  * `legacy-alacritty` is an alacritty.toml-only theme with no accent, so it falls back to blue.
  * `demo/contact-sheet-demo.png` shows them all.
* `prebaked/<theme>/hicolor/`: optional ready-made output for all 23 built-in themes, with the sheet at `prebaked/contact-sheet-prebaked.png`.
  * To use one without the script, copy its `hicolor` folder over `~/.local/share/icons/hicolor`.
  * The script is better, because it also follows custom themes and theme switches.

## Omarchy theme mechanism (researched from basecamp/omarchy @ b20d787, 19 Nov 2026)

* **The active theme** is copied or staged to `~/.local/state/omarchy/current/theme/`, and its name is in `…/current/theme.name`.
  * Older releases used `~/.config/omarchy/current/theme`; migration 1781043107 moved it.
  * Sources: https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/bin/omarchy-theme-set and https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/migrations/1781043107.sh
* **Every theme has a `colors.toml`** with these keys:
  * mode, accent, selection, muted;
  * background, dark_background, darker_background, lighter_background;
  * foreground, dark_foreground, light_foreground, bright_foreground;
  * red, yellow, orange, green, cyan, blue, magenta, brown, and their bright_* forms.
  * Themes that ship only alacritty.toml are converted by `omarchy-theme-colors-from-alacritty`.
  * Sources: https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/themes/tokyo-night/colors.toml and https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/bin/omarchy-theme-color
* **Hooks.** At the end of a switch, `omarchy-theme-set` calls `omarchy-hook theme-set <name>`.
  * That runs `~/.config/omarchy/hooks/theme-set` and every file in `~/.config/omarchy/hooks/theme-set.d/` with bash, passing the theme name.
  * Source: https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/bin/omarchy-hook
* **App icons in Omarchy.**
  * Omarchy no longer uses Yaru colour icon themes (`icons.theme`); every theme now gets Adwaita. Source: https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/migrations/1794397144.sh
  * Instead it has its own *icon sets* (papercraft (default), arcade, original), made of `<Icon=name>.svg.tpl` templates drawn in the theme's colours.
  * After each switch, `omarchy-theme-set-icons` renders them into `~/.local/state/omarchy/current/icons` and symlinks them into `~/.local/share/icons/hicolor/scalable/apps/`.
  * Template tokens are `{{ key }}`, `{{ key_strip }}`, `{{ key_rgb }}` and `{{ mix key1 key2 30% }}`, plus derived icon roles such as `icon_main` and `icon_paper`.
  * Sources: https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/bin/omarchy-theme-set-icons, https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/bin/omarchy-theme-set-templates and https://github.com/basecamp/omarchy/blob/b20d7876f5ec6a45d18b9e4383dc4b6d9e8492ab/bin/omarchy-theme-icon-palette
* **Why a hook rather than a set template.** A `.svg.tpl` only applies to the one icon set that is active, and it can only mix palette keys. It can't fall back for missing keys or check contrast. The hook works under any set, any theme, and older Omarchy too.

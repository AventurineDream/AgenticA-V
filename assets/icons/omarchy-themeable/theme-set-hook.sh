#!/bin/bash
# Omarchy theme-set hook: recolour the piano-camera icon to the theme just applied.
# Installed as ~/.config/omarchy/hooks/theme-set.d/piano-camera-icon
# (omarchy-hook runs every file in that folder with the theme name as $1).
# Runs in the background so it never slows a theme switch.
( "$HOME/.local/bin/piano-camera-theme-icon" "$@" >/dev/null 2>&1 & ) || true

#!/bin/bash
# Install the themeable piano-camera icon for Omarchy (per user, no sudo).
#   ./install.sh                 install script + templates + theme-set hook, then draw for the current theme
#   ./install.sh --name myapp    use another icon name (must match Icon= in the app's .desktop file)
#   ./install.sh --uninstall     remove everything this installed
set -euo pipefail
cd "$(dirname "$0")"
NAME=piano-camera
[[ ${1:-} == --name ]] && NAME=$2
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
HOOKDIR="$HOME/.config/omarchy/hooks/theme-set.d"
if [[ ${1:-} == --uninstall ]]; then
  rm -f "$HOME/.local/bin/piano-camera-theme-icon" "$HOOKDIR/piano-camera-icon"
  rm -rf "$DATA/piano-camera-icon"
  find "$DATA/icons/hicolor" -name "$NAME.png" -o -name "$NAME.svg" -o -name ".$NAME-palette.json" 2>/dev/null | xargs -r rm -f
  command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t -q "$DATA/icons/hicolor" || true
  echo "removed"; exit 0
fi
install -Dm755 piano-camera-theme-icon "$HOME/.local/bin/piano-camera-theme-icon"
mkdir -p "$DATA/piano-camera-icon/templates"
cp templates/*.svg.tmpl "$DATA/piano-camera-icon/templates/"
mkdir -p "$HOOKDIR"
if [[ $NAME == piano-camera ]]; then
  install -m755 theme-set-hook.sh "$HOOKDIR/piano-camera-icon"
else
  sed "s|piano-camera-theme-icon\" \"\$@\"|piano-camera-theme-icon\" --name $NAME \"\$@\"|" theme-set-hook.sh >"$HOOKDIR/piano-camera-icon"
  chmod 755 "$HOOKDIR/piano-camera-icon"
fi
"$HOME/.local/bin/piano-camera-theme-icon" --name "$NAME"
echo "Installed. The icon now follows every Omarchy theme switch (hook: $HOOKDIR/piano-camera-icon)."

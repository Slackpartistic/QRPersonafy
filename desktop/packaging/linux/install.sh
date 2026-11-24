#!/bin/sh
# Adds QRestoa to your app menu, from the unpacked tarball. No admin rights needed.
# Run it again after unpacking a newer version; ./install.sh --remove takes it out again.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
TARGET="$DATA/qrestoa-app"
# Before 1.2 the app was called QRPersonafy. Take that copy out of the menu, so there's only one.
rm -rf "$DATA/qrpersonafy-app" "$DATA/applications/qrpersonafy.desktop" "$DATA/icons/hicolor/256x256/apps/qrpersonafy.png"

if [ "$1" = "--remove" ]; then
  rm -rf "$TARGET" "$DATA/applications/qrestoa.desktop" "$DATA/icons/hicolor/256x256/apps/qrestoa.png"
  echo "QRestoa removed. Your saved backups in $DATA/QRestoa were kept."
  exit 0
fi

rm -rf "$TARGET"
mkdir -p "$TARGET" "$DATA/applications" "$DATA/icons/hicolor/256x256/apps"
cp -r "$HERE/QRestoa" "$HERE/_internal" "$TARGET/"
cp "$HERE/qrestoa.png" "$DATA/icons/hicolor/256x256/apps/qrestoa.png"
sed "s|^Exec=.*|Exec=\"$TARGET/QRestoa\"|" "$HERE/qrestoa.desktop" > "$DATA/applications/qrestoa.desktop"
update-desktop-database "$DATA/applications" 2>/dev/null || true
echo "QRestoa installed. Open it from your app menu (you may need to sign out and in once)."

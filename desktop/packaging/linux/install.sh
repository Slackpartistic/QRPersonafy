#!/bin/sh
# Adds QRPersonafy to your app menu, from the unpacked tarball. No admin rights needed.
# Run it again after unpacking a newer version; ./install.sh --remove takes it out again.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
TARGET="$DATA/qrpersonafy-app"

if [ "$1" = "--remove" ]; then
  rm -rf "$TARGET" "$DATA/applications/qrpersonafy.desktop" "$DATA/icons/hicolor/256x256/apps/qrpersonafy.png"
  echo "QRPersonafy removed. Your saved backups in $DATA/QRPersonafy were kept."
  exit 0
fi

rm -rf "$TARGET"
mkdir -p "$TARGET" "$DATA/applications" "$DATA/icons/hicolor/256x256/apps"
cp -r "$HERE/QRPersonafy" "$HERE/_internal" "$TARGET/"
cp "$HERE/qrpersonafy.png" "$DATA/icons/hicolor/256x256/apps/qrpersonafy.png"
sed "s|^Exec=.*|Exec=\"$TARGET/QRPersonafy\"|" "$HERE/qrpersonafy.desktop" > "$DATA/applications/qrpersonafy.desktop"
update-desktop-database "$DATA/applications" 2>/dev/null || true
echo "QRPersonafy installed. Open it from your app menu (you may need to sign out and in once)."

#!/bin/sh
# Builds the Linux app from desktop/: dist/QRPersonafy-<version>-x86_64.AppImage and
# dist/QRPersonafy-<version>-linux-x86_64.tar.gz. Needs: pip install ".[build,linux-app]" pillow,
# plus xvfb for the smoke test, desktop-file-utils (appimagetool checks the .desktop file)
# and curl to fetch appimagetool.
set -e
cd "$(dirname "$0")/../.."
version=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
arch=$(uname -m)

# The app folder: QRPersonafy plus _internal, with its own Python and Qt.
pyinstaller --onedir --windowed --noconfirm --name QRPersonafy \
  --add-data "src/qrpersonafy/gui/web:qrpersonafy/gui/web" \
  --collect-submodules qrpersonafy \
  --hidden-import webview.platforms.qt \
  --exclude-module gi \
  src/qrpersonafy/gui/__main__.py
python packaging/linux/trim.py dist/QRPersonafy
# Open the window once, offscreen, to check the folder has everything it needs.
if command -v xvfb-run >/dev/null; then
  timeout 180 xvfb-run -a dist/QRPersonafy/QRPersonafy --smoke-test
fi
python -c "from PIL import Image; Image.open('installer/qrpersonafy.ico').save('dist/qrpersonafy.png', sizes=[(256, 256)])"

# The tarball, for people who'd rather not use an AppImage.
rm -rf "build/tarball" && mkdir -p "build/tarball/QRPersonafy-$version"
cp -r dist/QRPersonafy/. "build/tarball/QRPersonafy-$version/"
cp dist/qrpersonafy.png packaging/linux/qrpersonafy.desktop packaging/linux/install.sh "build/tarball/QRPersonafy-$version/"
chmod +x "build/tarball/QRPersonafy-$version/install.sh"
tar -C build/tarball -czf "dist/QRPersonafy-$version-linux-$arch.tar.gz" "QRPersonafy-$version"

# The AppImage: one file that runs on any distribution, no install needed.
appdir=build/AppDir
rm -rf "$appdir" && mkdir -p "$appdir/usr/lib/qrpersonafy"
cp -r dist/QRPersonafy/. "$appdir/usr/lib/qrpersonafy/"
cp packaging/linux/AppRun "$appdir/AppRun" && chmod +x "$appdir/AppRun"
cp packaging/linux/qrpersonafy.desktop dist/qrpersonafy.png "$appdir/"
if [ ! -x build/appimagetool ]; then
  curl -fsSL -o build/appimagetool \
    "https://github.com/AppImage/appimagetool/releases/download/1.9.0/appimagetool-$arch.AppImage"
  chmod +x build/appimagetool
fi
# The tool is itself an AppImage; extracting it avoids needing FUSE on the build machine.
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=$arch build/appimagetool --no-appstream "$appdir" "dist/QRPersonafy-$version-$arch.AppImage"
ls -l dist

#!/bin/sh
# Builds the Linux app from desktop/: dist/QRestoa-<version>-x86_64.AppImage and
# dist/QRestoa-<version>-linux-x86_64.tar.gz. Needs: pip install ".[build,linux-app]" pillow,
# plus xvfb for the smoke test, desktop-file-utils (appimagetool checks the .desktop file)
# and curl to fetch appimagetool.
set -e
cd "$(dirname "$0")/../.."
version=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
arch=$(uname -m)

# The app folder: QRestoa plus _internal, with its own Python and Qt.
pyinstaller --onedir --windowed --noconfirm --name QRestoa \
  --add-data "src/qrpersonafy/gui/web:qrpersonafy/gui/web" \
  --collect-submodules qrpersonafy \
  --hidden-import webview.platforms.qt \
  --exclude-module gi \
  src/qrpersonafy/gui/__main__.py
python packaging/linux/trim.py dist/QRestoa
# Open the window once, offscreen, to check the folder has everything it needs.
if command -v xvfb-run >/dev/null; then
  timeout 180 xvfb-run -a dist/QRestoa/QRestoa --smoke-test
fi
python -c "from PIL import Image; Image.open('installer/qrestoa.ico').save('dist/qrestoa.png', sizes=[(256, 256)])"

# The tarball, for people who'd rather not use an AppImage.
rm -rf "build/tarball" && mkdir -p "build/tarball/QRestoa-$version"
cp -r dist/QRestoa/. "build/tarball/QRestoa-$version/"
cp dist/qrestoa.png packaging/linux/qrestoa.desktop packaging/linux/install.sh "build/tarball/QRestoa-$version/"
chmod +x "build/tarball/QRestoa-$version/install.sh"
tar -C build/tarball -czf "dist/QRestoa-$version-linux-$arch.tar.gz" "QRestoa-$version"

# The AppImage: one file that runs on any distribution, no install needed.
appdir=build/AppDir
rm -rf "$appdir" && mkdir -p "$appdir/usr/lib/qrestoa"
cp -r dist/QRestoa/. "$appdir/usr/lib/qrestoa/"
cp packaging/linux/AppRun "$appdir/AppRun" && chmod +x "$appdir/AppRun"
cp packaging/linux/qrestoa.desktop dist/qrestoa.png "$appdir/"
if [ ! -x build/appimagetool ]; then
  curl -fsSL -o build/appimagetool \
    "https://github.com/AppImage/appimagetool/releases/download/1.9.0/appimagetool-$arch.AppImage"
  chmod +x build/appimagetool
fi
# The tool is itself an AppImage; extracting it avoids needing FUSE on the build machine.
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=$arch build/appimagetool --no-appstream "$appdir" "dist/QRestoa-$version-$arch.AppImage"
ls -l dist

"""Removes parts of Qt the app never uses from the PyInstaller folder, about halving its size.

The window is a QtWebEngine view and nothing else. The build runs the app afterwards
(--smoke-test) to check nothing it needs was removed.
"""

import shutil
import sys
from pathlib import Path

UNUSED = (
    "libQt6Quick3D*", "libQt6QuickControls2*", "libQt6QuickDialogs2*", "libQt6QuickTest*",
    "libQt6QuickTimeline*", "libQt6QuickParticles*", "libQt6QuickVectorImage*", "libQt6QuickEffects*",
    "libQt6QuickShapes*", "libQt6QuickLayouts*", "libQt6Multimedia*", "libQt6SpatialAudio*",
    "libQt6Sensors*", "libQt6SerialPort*", "libQt6TextToSpeech*", "libQt6RemoteObjects*",
    "libQt6Test*", "libQt6StateMachine*", "libQt6ShaderTools*", "libQt6WebEngineQuick*",
    "libQt6WebChannelQuick*", "libQt6PositioningQuick*", "libQt6WebSockets*", "libQt6Pdf*",
    "libQt6Bluetooth*", "libQt6Nfc*", "libQt6Charts*", "libQt6DataVisualization*", "libQt6Graphs*",
    "libQt6Designer*", "libQt6Help*", "libQt6Lottie*", "libQt6VirtualKeyboard*", "libQt63D*",
    "libQt6Scxml*", "libQt6Location*",
)

root = Path(sys.argv[1]) / "_internal"
qt = root / "PyQt6" / "Qt6"
removed = 0


def drop(path: Path) -> None:
    global removed
    removed += sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else path.stat().st_size
    shutil.rmtree(path) if path.is_dir() else path.unlink()


for pattern in UNUSED:
    for path in (qt / "lib").glob(pattern):
        drop(path)
# QML modules, and translations: the app is in English, so WebEngine only needs its English strings.
locales = [p for p in (qt / "translations" / "qtwebengine_locales").glob("*.pak") if p.name != "en-US.pak"]
for path in [qt / "qml", *(qt / "translations").glob("*.qm"), *locales]:
    if path.exists():
        drop(path)
# Qt's GTK theme plugin drags in a copy of GTK, which must come from the system to work.
for path in [qt / "plugins" / "platformthemes" / "libqgtk3.so", *root.glob("libgtk-3.so*"), *root.glob("libgdk-3.so*")]:
    if path.exists():
        drop(path)
print(f"trimmed {removed / 1024 / 1024:.0f} MB")

"""Opens the desktop app's window."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

WEB = Path(__file__).parent / "web"


def unblock_dlls(folder: Path) -> int:
    """Remove the "downloaded from the internet" mark from the app's own DLLs.

    Windows' zip extractor marks every file it unpacks from a downloaded zip, and .NET refuses
    to load marked assemblies, which stops pywebview's Windows backend from starting. The mark
    is an NTFS stream named Zone.Identifier next to each file.
    """
    removed = 0
    for dll in folder.rglob("*.dll"):
        try:
            os.remove(f"{dll}:Zone.Identifier")
            removed += 1
        except OSError:
            pass
    return removed


def prepare_linux() -> str | None:
    """Pick the window toolkit on Linux, returning pywebview's name for it.

    The AppImage carries its own Qt, so it works the same on every distribution. Run from source,
    pywebview uses GTK if the system has it and Qt otherwise.
    """
    if not getattr(sys, "frozen", False):
        return None
    os.environ.setdefault("QT_API", "pyqt6")
    # Chromium's sandbox needs user namespaces, which Ubuntu 24.04 and others restrict for
    # apps outside the distribution. The window only ever shows this app's own pages.
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    return "qt"


def make_context_factory():
    if sys.platform == "win32":
        from ..registry import WindowsRegistry
        from ..settings import Context
        from ..system import WindowsSystem

        return lambda: Context(WindowsRegistry(), WindowsSystem())
    from ..linux import linux_context

    return linux_context


def main() -> int:
    if sys.platform != "win32" and not sys.platform.startswith("linux"):
        print("The QRPersonafy app runs on Windows and Linux.", file=sys.stderr)
        return 1
    gui = None
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        unblock_dlls(Path(sys._MEIPASS))
    if sys.platform.startswith("linux"):
        gui = prepare_linux()
    try:
        import webview
    except ImportError:
        print('The app needs pywebview. Install it with: python -m pip install "pywebview[qt]"', file=sys.stderr)
        return 1

    from .api import Api

    # Used by the build to check the packaged app can open its window: it opens, loads the page
    # and closes again.
    smoke_test = "--smoke-test" in sys.argv

    windows: list = []

    def emit(event: dict) -> None:
        if windows:
            windows[0].evaluate_js(f"window.onAppEvent({json.dumps(event)})")

    def choose_file(save: bool, filename: str) -> str | None:
        kind = webview.FileDialog.SAVE if save else webview.FileDialog.OPEN
        result = windows[0].create_file_dialog(kind, save_filename=filename, file_types=("QRPersonafy profile (*.json)",))
        if not result:
            return None
        return result if isinstance(result, str) else result[0]

    api = Api(make_context_factory(), emit)
    api._choose_file = choose_file
    window = webview.create_window(
        "QRPersonafy",
        url=str(WEB / "index.html"),
        js_api=api,
        width=980,
        height=720,
        min_size=(720, 560),
        background_color="#F4F6FB",
    )
    windows.append(window)
    window.events.closed += api.cancel
    result = {"ok": not smoke_test}

    def check_page() -> None:
        result["ok"] = window.evaluate_js("typeof window.onAppEvent") == "function"
        print("smoke test:", "page loaded" if result["ok"] else "page did not load", flush=True)
        # Qt WebEngine sometimes hangs while closing a window this quickly, and the check is
        # done, so leave without waiting for it.
        os._exit(0 if result["ok"] else 1)

    if smoke_test:
        window.events.loaded += check_page
    webview.start(gui=gui)
    return 0 if result["ok"] else 1

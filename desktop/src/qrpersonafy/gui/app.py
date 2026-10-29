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


def main() -> int:
    if sys.platform != "win32":
        print("The QRPersonafy app only runs on Windows.", file=sys.stderr)
        return 1
    if getattr(sys, "frozen", False):
        unblock_dlls(Path(sys._MEIPASS))
    import webview

    from ..registry import WindowsRegistry
    from ..settings import Context
    from ..system import WindowsSystem
    from .api import Api

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

    api = Api(lambda: Context(WindowsRegistry(), WindowsSystem()), emit)
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
    webview.start()
    return 0

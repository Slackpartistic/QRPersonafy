"""Opens the desktop app's window."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WEB = Path(__file__).parent / "web"


def main() -> int:
    if sys.platform != "win32":
        print("The QRPersonafy app only runs on Windows.", file=sys.stderr)
        return 1
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

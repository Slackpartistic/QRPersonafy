"""Windows system calls that make settings take effect, with a recording fake for tests."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Protocol

# SystemParametersInfo actions.
SPI_SETMOUSE = 0x0004
SPI_SETKEYBOARDSPEED = 0x000B
SPI_SETDESKWALLPAPER = 0x0014
SPI_SETKEYBOARDDELAY = 0x0017
SPI_SETDOUBLECLICKTIME = 0x0020
SPI_SETMOUSEBUTTONSWAP = 0x0021
SPI_SETCURSORS = 0x0057
SPI_SETWHEELSCROLLLINES = 0x0069
SPI_SETMOUSESPEED = 0x0071

SPIF_UPDATEINIFILE_SENDCHANGE = 0x01 | 0x02


class System(Protocol):
    appdata: Path
    localappdata: Path

    def spi(self, action: int, ui_param: int = 0, pv_param: int | str | list[int] | None = None) -> None:
        """Call SystemParametersInfoW, persisting the change and notifying other apps."""

    def broadcast_setting_change(self, area: str) -> None:
        """Send WM_SETTINGCHANGE so running apps pick up a change in `area`."""

    def stop_process(self, image_name: str) -> None: ...

    def restart_explorer(self) -> None: ...

    def run_powershell(self, script: str) -> str: ...

    def windows_build(self) -> str: ...


class WindowsSystem:
    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.SystemParametersInfoW.argtypes = [
            wintypes.UINT,
            wintypes.UINT,
            ctypes.c_void_p,
            wintypes.UINT,
        ]
        self._user32.SystemParametersInfoW.restype = wintypes.BOOL
        self.appdata = Path(os.environ["APPDATA"])
        self.localappdata = Path(os.environ["LOCALAPPDATA"])

    def spi(self, action, ui_param=0, pv_param=None):
        ctypes = self._ctypes
        if isinstance(pv_param, str):
            buffer = ctypes.create_unicode_buffer(pv_param)
            pv = ctypes.cast(buffer, ctypes.c_void_p)
        elif isinstance(pv_param, list):
            buffer = (ctypes.c_int * len(pv_param))(*pv_param)
            pv = ctypes.cast(buffer, ctypes.c_void_p)
        elif pv_param is None:
            pv = None
        else:
            pv = ctypes.c_void_p(pv_param)
        if not self._user32.SystemParametersInfoW(action, ui_param, pv, SPIF_UPDATEINIFILE_SENDCHANGE):
            error = ctypes.get_last_error()
            # Some actions, such as SPI_SETCURSORS, return FALSE without an error code even though
            # the change was made. Only a real error code means it failed.
            if error:
                raise OSError(error, f"SystemParametersInfo(0x{action:04X}) failed")

    def broadcast_setting_change(self, area):
        ctypes = self._ctypes
        result = ctypes.c_size_t()
        HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
        self._user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, area, SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
        )

    def stop_process(self, image_name):
        subprocess.run(["taskkill", "/f", "/im", image_name], capture_output=True)

    def restart_explorer(self):
        self.stop_process("explorer.exe")
        subprocess.Popen(["explorer.exe"])

    def run_powershell(self, script):
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout

    def windows_build(self):
        return platform.version()


class FakeSystem:
    """Records calls instead of making them."""

    def __init__(self, root: Path) -> None:
        self.appdata = root / "AppData" / "Roaming"
        self.localappdata = root / "AppData" / "Local"
        self.calls: list[tuple] = []
        self.powershell_output = ""

    def spi(self, action, ui_param=0, pv_param=None):
        self.calls.append(("spi", action, ui_param, pv_param))

    def broadcast_setting_change(self, area):
        self.calls.append(("broadcast", area))

    def stop_process(self, image_name):
        self.calls.append(("stop_process", image_name))

    def restart_explorer(self):
        self.calls.append(("restart_explorer",))

    def run_powershell(self, script):
        self.calls.append(("powershell", script))
        return self.powershell_output

    def windows_build(self):
        return "10.0.26100"

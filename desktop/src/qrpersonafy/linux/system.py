"""Where things live on a Linux desktop, and the tools used to change it."""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping
from pathlib import Path

from .runner import Runner, SubprocessRunner


class LinuxSystem:
    def __init__(self, runner: Runner | None = None, home: Path | None = None, env: Mapping[str, str] | None = None) -> None:
        self.runner = runner or SubprocessRunner()
        self.env = dict(os.environ if env is None else env)
        self.home = Path(home or self.env.get("HOME") or Path.home())
        self.data_home = Path(self.env.get("XDG_DATA_HOME") or self.home / ".local" / "share")
        self.config_home = Path(self.env.get("XDG_CONFIG_HOME") or self.home / ".config")
        # Backups go to ~/.local/share/QRPersonafy/backups, the same place as on Windows' LOCALAPPDATA.
        self.appdata = self.data_home
        self.localappdata = self.data_home

    def data_dirs(self) -> list[Path]:
        """XDG data folders, the user's own first."""
        dirs = [self.data_home]
        dirs += [Path(d) for d in (self.env.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
        return dirs

    def wayland(self) -> bool:
        return self.env.get("XDG_SESSION_TYPE") == "wayland" or "WAYLAND_DISPLAY" in self.env

    def restart_explorer(self) -> None:
        """Windows only; Linux desktops pick changes up as they are made."""

    def windows_build(self) -> str:
        return ""

    def distribution(self) -> str:
        for path in (Path("/etc/os-release"), Path("/usr/lib/os-release")):
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
            except OSError:
                continue
        return f"Linux {platform.release()}"

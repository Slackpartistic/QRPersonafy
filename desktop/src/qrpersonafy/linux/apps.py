"""Finding installed apps, so pinned apps from another PC can be pinned here.

Apps are found through their .desktop files. A pin saved on Linux carries its desktop file
name; a pin from Windows only has a shortcut name like "Google Chrome", so it is matched by
the app's name, with a few Windows apps standing in for the Linux app that does the same job.
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path

from .system import LinuxSystem

# Windows apps (and the generic names KDE uses) and the kind of Linux app that replaces them.
STAND_INS = {
    "file explorer": "FileManager",
    "file manager": "FileManager",
    "this pc": "FileManager",
    "terminal": "TerminalEmulator",
    "windows terminal": "TerminalEmulator",
    "command prompt": "TerminalEmulator",
    "windows powershell": "TerminalEmulator",
    "powershell": "TerminalEmulator",
    "microsoft store": "PackageManager",
    "settings": "Settings",
    "control panel": "Settings",
    "notepad": "TextEditor",
    "web browser": "WebBrowser",
}


@dataclass(frozen=True)
class App:
    id: str
    name: str
    categories: tuple[str, ...]


def app_folders(system: LinuxSystem) -> list[Path]:
    folders = [d / "applications" for d in system.data_dirs()]
    folders += [
        system.data_home / "flatpak" / "exports" / "share" / "applications",
        Path("/var/lib/flatpak/exports/share/applications"),
        Path("/var/lib/snapd/desktop/applications"),
    ]
    return folders


def installed_apps(system: LinuxSystem) -> dict[str, App]:
    """Visible apps by desktop file name. Earlier folders win, as they do for the desktop."""
    apps: dict[str, App] = {}
    hidden: set[str] = set()
    for folder in app_folders(system):
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.desktop")):
            app_id = "-".join(path.relative_to(folder).parts)
            if app_id in apps or app_id in hidden:
                continue
            entry = _read_entry(path)
            if entry is None:
                continue
            if entry.get("NoDisplay", "").lower() == "true" or entry.get("Hidden", "").lower() == "true" or not entry.get("Name"):
                hidden.add(app_id)
                continue
            categories = tuple(c for c in entry.get("Categories", "").split(";") if c)
            apps[app_id] = App(app_id, entry["Name"], categories)
    return apps


def _read_entry(path: Path) -> dict[str, str] | None:
    parser = configparser.RawConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    try:
        parser.read_string(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error):
        return None
    if not parser.has_section("Desktop Entry"):
        return None
    entry = dict(parser.items("Desktop Entry"))
    return entry if entry.get("Type", "Application") == "Application" else None


def _words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def find_app(pin: dict, apps: dict[str, App]) -> str | None:
    """The desktop file name of the installed app that best matches a pin."""
    if pin.get("id") in apps:
        return pin["id"]
    name = _words(pin.get("name", ""))
    if not name:
        return None
    by_name = [app for app in apps.values() if _words(app.name) == name]
    if not by_name:
        by_name = [app for app in apps.values() if _words(app.name).startswith(name + " ")]
    if not by_name:
        compact = name.replace(" ", "")
        by_name = [app for app in apps.values() if compact and compact in re.sub(r"[^a-z0-9]", "", app.id.lower()[: -len(".desktop")])]
    if not by_name and name in STAND_INS:
        category = STAND_INS[name]
        by_name = [app for app in apps.values() if category in app.categories]
        if category == "Settings":
            by_name = [app for app in by_name if "settings" in _words(app.name) or "DesktopSettings" in app.categories] or by_name
    if not by_name:
        return None
    # Prefer the shortest id: "firefox.desktop" over "firefox-developer-edition.desktop".
    return min(by_name, key=lambda app: (len(app.id), app.id)).id


def match_pins(pins: list[dict], apps: dict[str, App]) -> tuple[list[str], list[str]]:
    """Desktop file names for the pins that have an app here, and names of those that don't."""
    found, missing = [], []
    for pin in pins:
        app_id = find_app(pin, apps)
        if app_id is None:
            missing.append(pin.get("name") or pin.get("id", "?"))
        elif app_id not in found:
            found.append(app_id)
    return found, missing


def pins_for(ids: list[str], apps: dict[str, App]) -> list[dict]:
    """Portable pins for desktop file names, with names so other systems can match them."""
    pins = []
    for app_id in ids:
        app = apps.get(app_id)
        pin = {"id": app_id}
        if app is not None:
            pin["name"] = app.name
        pins.append(pin)
    return pins

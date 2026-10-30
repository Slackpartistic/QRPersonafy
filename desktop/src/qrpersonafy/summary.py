"""A friendly description of a profile, for the desktop app's screens."""

from __future__ import annotations

import base64

from . import portable
from .settings import ALL
from .settings.accent import DWM
from .settings.keyboard import parse_languages
from .settings.mouse import CURSORS, MOUSE
from .settings.taskbar import ADVANCED
from .settings.theme import PERSONALIZE
from .settings.wallpaper import image_extension

# Larger wallpapers are summarised without a preview, to keep the window responsive.
MAX_PREVIEW_BYTES = 12 * 1024 * 1024
_MIME = {".jpg": "image/jpeg", ".png": "image/png", ".bmp": "image/bmp"}


def _value(section: dict, key: str, name: str):
    for entry in section.get("registry", []):
        if isinstance(entry, dict) and entry.get("key", "").lower() == key.lower() and entry.get("name", "").lower() == name.lower():
            return entry.get("data")
    return None


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def accent_hex(value) -> str | None:
    """Windows stores the accent color as 0xAABBGGRR."""
    number = _int(value)
    if number is None:
        return None
    red, green, blue = number & 0xFF, (number >> 8) & 0xFF, (number >> 16) & 0xFF
    return f"#{red:02X}{green:02X}{blue:02X}"


def _wallpaper(section: dict) -> dict:
    image = section.get("files", {}).get("image")
    if not isinstance(image, dict) or not isinstance(image.get("data"), str):
        return {"details": "Fit settings only"}
    size = len(image["data"]) * 3 // 4
    item = {"details": f"Image, {size / 1024 / 1024:.1f} MB"}
    if size <= MAX_PREVIEW_BYTES:
        try:
            head = base64.b64decode(image["data"][:16])
            item["image"] = f"data:{_MIME[image_extension(head)]};base64,{image['data']}"
        except ValueError:
            pass
    return item


def _theme(section: dict) -> dict:
    apps, system = _value(section, PERSONALIZE, "AppsUseLightTheme"), _value(section, PERSONALIZE, "SystemUsesLightTheme")
    mode = lambda v: "light" if v == 1 else "dark"
    if apps is None and system is None:
        return {"details": "Default"}
    if apps == system:
        return {"details": f"{mode(apps).capitalize()} mode", "dark": apps == 0}
    return {"details": f"Apps {mode(apps)}, Windows {mode(system)}", "dark": system == 0}


def _accent(section: dict) -> dict:
    color = accent_hex(_value(section, DWM, "AccentColor"))
    places = []
    if _value(section, PERSONALIZE, "ColorPrevalence") == 1:
        places.append("Start and taskbar")
    if _value(section, DWM, "ColorPrevalence") == 1:
        places.append("title bars")
    details = color or "Default"
    if places:
        details += ", shown on " + " and ".join(places)
    return {"details": details, "color": color}


def _taskbar(section: dict) -> dict:
    pins = sorted(name[4:-4] for name in section.get("files", {}) if name.startswith("pin:") and name.lower().endswith(".lnk"))
    alignment = "Left" if _value(section, ADVANCED, "TaskbarAl") == 0 else "Centered"
    details = f"{alignment}, {len(pins)} pinned app{'s' if len(pins) != 1 else ''}"
    return {"details": details, "list": pins}


def _start(section: dict) -> dict:
    has_layout = any(name.endswith(".bin") for name in section.get("files", {}))
    return {"details": "Pinned apps and layout" if has_layout else "Layout options only"}


def _mouse(section: dict) -> dict:
    parts = []
    speed = _int(_value(section, MOUSE, "MouseSensitivity"))
    if speed is not None:
        parts.append(f"pointer speed {speed}/20")
    if _value(section, MOUSE, "SwapMouseButtons") in ("1", 1):
        parts.append("buttons swapped")
    scheme = _value(section, CURSORS, "")
    if isinstance(scheme, str) and scheme:
        parts.append(f"{scheme} cursors")
    text = ", ".join(parts)
    return {"details": text[:1].upper() + text[1:] if text else "Default"}


def _keyboard(section: dict) -> dict:
    try:
        languages = [language["tag"] for language in parse_languages(section.get("languages", []))]
    except ValueError:
        languages = []
    return {"details": ", ".join(languages) or "Repeat speed only", "list": languages}


def _from_portable(name: str, section: dict) -> dict:
    """Describe a section saved on Linux."""
    values = portable.of(name, section)
    if name == "wallpaper":
        return _wallpaper(section)
    if name == "theme":
        if "apps_dark" not in values:
            return {"details": "Default"}
        return {"details": "Dark mode" if values["apps_dark"] else "Light mode", "dark": values["apps_dark"]}
    if name == "accent":
        return {"details": values.get("color", "Default"), "color": values.get("color")}
    if name == "taskbar":
        pins = [p.get("name") or p.get("id", "")[: -len(".desktop")] for p in values.get("pinned", [])]
        where = values.get("position", "").capitalize()
        details = f"{where + ', ' if where else ''}{len(pins)} pinned app{'s' if len(pins) != 1 else ''}"
        return {"details": details, "list": pins}
    if name == "mouse":
        parts = []
        if "speed" in values:
            parts.append(f"pointer speed {round(values['speed'] * 10 + 10)}/20")
        if values.get("left_handed"):
            parts.append("buttons swapped")
        if values.get("cursor_theme"):
            parts.append(f"{values['cursor_theme']} cursors")
        text = ", ".join(parts)
        return {"details": text[:1].upper() + text[1:] if text else "Default"}
    if name == "keyboard":
        layouts = [portable.layout_label(item) for item in values.get("layouts", [])]
        return {"details": ", ".join(layouts) or "Repeat speed only", "list": layouts}
    return {"details": "Saved"}


_DESCRIBE = {
    "wallpaper": _wallpaper,
    "theme": _theme,
    "accent": _accent,
    "taskbar": _taskbar,
    "start": _start,
    "mouse": _mouse,
    "keyboard": _keyboard,
}


def summarize(profile: dict) -> dict:
    sections = profile.get("settings", {})
    items = []
    for setting in ALL:
        section = sections.get(setting.name)
        if not isinstance(section, dict):
            continue
        try:
            if "portable" in section and not section.get("registry"):
                item = _from_portable(setting.name, section)
            else:
                item = _DESCRIBE[setting.name](section)
        except (TypeError, ValueError, AttributeError):
            item = {"details": "Saved"}
        items.append({"name": setting.name, "label": setting.label, **item})
    return {
        "created": profile.get("created"),
        "windows_build": profile.get("windows_build"),
        "system": profile.get("system") if isinstance(profile.get("system"), str) else None,
        "items": items,
    }

"""Settings in a form any desktop can use, so a profile saved on one system applies on another.

Windows profiles keep their registry values, and a Linux desktop reads them through
`from_windows`. Linux profiles store the portable form directly, under "portable" in each
section, and Windows turns it back into registry values with `to_windows`.

Portable values, all optional:

    wallpaper  fit: fill | fit | stretch | tile | center | span    (the image is in "files")
    theme      apps_dark, system_dark: bool
    accent     color: "#RRGGBB"
    taskbar    position: bottom | top | left | right, autohide: bool,
               pinned: [{"name": "Firefox", "id": "firefox.desktop"}]
    mouse      speed: -1.0 .. 1.0, acceleration, left_handed: bool, double_click_ms: int,
               cursor_theme: str, cursor_size: int
    keyboard   repeat_delay_ms, repeat_interval_ms: int, layouts: [{"layout": "us", "variant": ""}]

Like the rest of a profile this is untrusted input, so `clean` checks every value.
"""

from __future__ import annotations

import base64
import re

from .registry import REG_DWORD, REG_SZ, TYPE_NAMES

FITS = ("fill", "fit", "stretch", "tile", "center", "span")
POSITIONS = ("bottom", "top", "left", "right")

PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
DWM = r"Software\Microsoft\Windows\DWM"
ACCENT = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"
DESKTOP = r"Control Panel\Desktop"
MOUSE = r"Control Panel\Mouse"
KEYBOARD = r"Control Panel\Keyboard"
STUCK_RECTS = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3"

# App names are only compared, never run, so any printable text will do.
_NAME = re.compile(r"^[^\x00-\x1f\x7f]{1,100}$")
_THEME = re.compile(r"^[A-Za-z0-9 ._+\-]{1,100}$")
_DESKTOP_ID = re.compile(r"^[A-Za-z0-9._\-]{1,200}\.desktop$")
_XKB = re.compile(r"^[a-z][a-z0-9_\-]{0,30}$")
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Windows keyboard layouts (KLID) and the matching XKB layout and variant, with the language
# Windows lists them under. Layouts not listed here are reported instead of guessed.
LAYOUTS: tuple[tuple[str, str, str, str], ...] = (
    ("00000409", "us", "", "en-US"),
    ("00020409", "us", "intl", "en-US"),
    ("00010409", "us", "dvorak", "en-US"),
    ("00000809", "gb", "", "en-GB"),
    ("00001809", "ie", "", "en-IE"),
    ("00001009", "ca", "", "fr-CA"),
    ("00000407", "de", "", "de-DE"),
    ("00000807", "ch", "", "de-CH"),
    ("0000100C", "ch", "fr", "fr-CH"),
    ("00000C07", "at", "", "de-AT"),
    ("0000040C", "fr", "", "fr-FR"),
    ("0000080C", "be", "", "fr-BE"),
    ("00000813", "be", "", "nl-BE"),
    ("00000413", "nl", "", "nl-NL"),
    ("0000040A", "es", "", "es-ES"),
    ("0000080A", "latam", "", "es-MX"),
    ("00000410", "it", "", "it-IT"),
    ("00000816", "pt", "", "pt-PT"),
    ("00000416", "br", "", "pt-BR"),
    ("00000406", "dk", "", "da-DK"),
    ("0000041D", "se", "", "sv-SE"),
    ("00000414", "no", "", "nb-NO"),
    ("0000040B", "fi", "", "fi-FI"),
    ("0000040F", "is", "", "is-IS"),
    ("00000415", "pl", "", "pl-PL"),
    ("00000405", "cz", "", "cs-CZ"),
    ("0000041B", "sk", "", "sk-SK"),
    ("0000040E", "hu", "", "hu-HU"),
    ("00010418", "ro", "", "ro-RO"),
    ("00000424", "si", "", "sl-SI"),
    ("0000041A", "hr", "", "hr-HR"),
    ("00000425", "ee", "", "et-EE"),
    ("00000426", "lv", "", "lv-LV"),
    ("00010427", "lt", "", "lt-LT"),
    ("00000408", "gr", "", "el-GR"),
    ("0000041F", "tr", "", "tr-TR"),
    ("00000419", "ru", "", "ru-RU"),
    ("00000422", "ua", "", "uk-UA"),
    ("00000423", "by", "", "be-BY"),
    ("00000402", "bg", "", "bg-BG"),
    ("00000C1A", "rs", "", "sr-Cyrl-RS"),
    ("0000040D", "il", "", "he-IL"),
    ("00000401", "ara", "", "ar-SA"),
    ("00000429", "ir", "", "fa-IR"),
    ("00000439", "in", "deva", "hi-IN"),
    ("0000041E", "th", "", "th-TH"),
    ("0000042A", "vn", "", "vi-VN"),
    ("00000411", "jp", "", "ja-JP"),
    ("00000412", "kr", "", "ko-KR"),
)
_BY_KLID = {klid: (layout, variant) for klid, layout, variant, _ in LAYOUTS}
_BY_XKB = {}
for _klid, _layout, _variant, _tag in LAYOUTS:
    _BY_XKB.setdefault((_layout, _variant), (_klid, _tag))


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _registry(section: dict) -> dict[tuple[str, str], object]:
    values = {}
    entries = section.get("registry", [])
    if not isinstance(entries, list):
        return values
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("key"), str) and isinstance(entry.get("name"), str):
            values[(entry["key"].lower(), entry["name"].lower())] = entry.get("data")
    return values


# Windows to portable


def from_windows(name: str, section: dict) -> dict:
    """The portable form of a section saved on Windows."""
    reg = _registry(section)
    get = lambda key, value: reg.get((key.lower(), value.lower()))
    out: dict = {}
    if name == "wallpaper":
        style, tile = _int(get(DESKTOP, "WallpaperStyle")), _int(get(DESKTOP, "TileWallpaper"))
        fit = {10: "fill", 6: "fit", 2: "stretch", 22: "span"}.get(style)
        if style == 0:
            fit = "tile" if tile == 1 else "center"
        if fit:
            out["fit"] = fit
    elif name == "theme":
        apps, system = _int(get(PERSONALIZE, "AppsUseLightTheme")), _int(get(PERSONALIZE, "SystemUsesLightTheme"))
        if apps is not None:
            out["apps_dark"] = apps == 0
        if system is not None:
            out["system_dark"] = system == 0
    elif name == "accent":
        abgr = _int(get(DWM, "AccentColor"))
        if abgr is not None:
            red, green, blue = abgr & 0xFF, (abgr >> 8) & 0xFF, (abgr >> 16) & 0xFF
            out["color"] = f"#{red:02X}{green:02X}{blue:02X}"
    elif name == "taskbar":
        rects = get(STUCK_RECTS, "Settings")
        if isinstance(rects, str):
            try:
                data = base64.b64decode(rects, validate=True)
            except ValueError:
                data = b""
            if len(data) > 12:
                out["autohide"] = bool(data[8] & 0x01)
                out["position"] = {0: "left", 1: "top", 2: "right", 3: "bottom"}.get(data[12], "bottom")
        files = section.get("files", {})
        if isinstance(files, dict):
            names = sorted(k[4:-4] for k in files if isinstance(k, str) and k.startswith("pin:") and k.lower().endswith(".lnk"))
            out["pinned"] = [{"name": n} for n in names]
    elif name == "mouse":
        speed = _int(get(MOUSE, "MouseSensitivity"))
        if speed is not None:
            out["speed"] = round((min(max(speed, 1), 20) - 10) / 10, 2)
        accel = _int(get(MOUSE, "MouseSpeed"))
        if accel is not None:
            out["acceleration"] = accel != 0
        swap = _int(get(MOUSE, "SwapMouseButtons"))
        if swap is not None:
            out["left_handed"] = swap == 1
        double_click = _int(get(MOUSE, "DoubleClickSpeed"))
        if double_click is not None:
            out["double_click_ms"] = double_click
    elif name == "keyboard":
        delay, rate = _int(get(KEYBOARD, "KeyboardDelay")), _int(get(KEYBOARD, "KeyboardSpeed"))
        if delay is not None:
            out["repeat_delay_ms"] = (min(max(delay, 0), 3) + 1) * 250
        if rate is not None:
            # 0 is about 2.5 repeats a second and 31 about 30.
            per_second = 2.5 + min(max(rate, 0), 31) * 27.5 / 31
            out["repeat_interval_ms"] = round(1000 / per_second)
        layouts = []
        for language in section.get("languages", []) if isinstance(section.get("languages"), list) else []:
            tips = language.get("tips", []) if isinstance(language, dict) else []
            for tip in tips if isinstance(tips, list) else []:
                klid = tip.split(":", 1)[-1].upper() if isinstance(tip, str) else ""
                if klid in _BY_KLID:
                    layout, variant = _BY_KLID[klid]
                    if {"layout": layout, "variant": variant} not in layouts:
                        layouts.append({"layout": layout, "variant": variant})
                else:
                    layouts.append({"unknown": tip, "language": language.get("tag")})
        if layouts:
            out["layouts"] = layouts
    return out


def of(name: str, section: dict) -> dict:
    """Portable values of a section, whichever system saved it. Always checked with `clean`."""
    if not isinstance(section, dict):
        return {}
    portable = section.get("portable")
    if isinstance(portable, dict):
        return clean(name, portable)
    return clean(name, from_windows(name, section))


def clean(name: str, values: dict) -> dict:
    """Keep only well-formed portable values."""
    out: dict = {}

    def boolean(key):
        if isinstance(values.get(key), bool):
            out[key] = values[key]

    def number(key, low, high, kind=int):
        value = values.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high:
            out[key] = kind(value)

    if name == "wallpaper":
        if values.get("fit") in FITS:
            out["fit"] = values["fit"]
    elif name == "theme":
        boolean("apps_dark")
        boolean("system_dark")
    elif name == "accent":
        if isinstance(values.get("color"), str) and _COLOR.match(values["color"]):
            out["color"] = values["color"].upper()
    elif name == "taskbar":
        if values.get("position") in POSITIONS:
            out["position"] = values["position"]
        boolean("autohide")
        pins = []
        for pin in values.get("pinned", []) if isinstance(values.get("pinned"), list) else []:
            if not isinstance(pin, dict):
                continue
            item = {}
            if isinstance(pin.get("name"), str) and _NAME.match(pin["name"]):
                item["name"] = pin["name"]
            if isinstance(pin.get("id"), str) and _DESKTOP_ID.match(pin["id"]):
                item["id"] = pin["id"]
            if item:
                pins.append(item)
        if "pinned" in values:
            out["pinned"] = pins
    elif name == "mouse":
        number("speed", -1, 1, float)
        boolean("acceleration")
        boolean("left_handed")
        number("double_click_ms", 100, 5000)
        if isinstance(values.get("cursor_theme"), str) and _THEME.match(values["cursor_theme"]):
            out["cursor_theme"] = values["cursor_theme"]
        number("cursor_size", 8, 256)
    elif name == "keyboard":
        number("repeat_delay_ms", 100, 5000)
        number("repeat_interval_ms", 5, 1000)
        layouts = []
        for item in values.get("layouts", []) if isinstance(values.get("layouts"), list) else []:
            if not isinstance(item, dict):
                continue
            if "unknown" in item:
                tip, language = item.get("unknown"), item.get("language")
                if isinstance(tip, str) and len(tip) < 100:
                    layouts.append({"unknown": tip, "language": language if isinstance(language, str) else ""})
                continue
            layout, variant = item.get("layout"), item.get("variant") or ""
            if isinstance(layout, str) and _XKB.match(layout) and isinstance(variant, str) and (not variant or _XKB.match(variant)):
                layouts.append({"layout": layout, "variant": variant})
        if layouts:
            out["layouts"] = layouts
    return out


# Portable to Windows


def _entry(key: str, name: str, type_code: int, data) -> dict:
    return {"key": key, "name": name, "type": TYPE_NAMES[type_code], "data": data}


def to_windows(name: str, section: dict) -> tuple[dict, list[str]]:
    """A Windows section built from a section saved on another system, and what couldn't be kept."""
    values = of(name, section)
    entries: list[dict] = []
    notes: list[str] = []
    out: dict = {"registry": entries}
    if name == "wallpaper":
        if isinstance(section.get("files"), dict) and "image" in section["files"]:
            out["files"] = {"image": section["files"]["image"]}
        style, tile = {
            "fill": ("10", "0"), "fit": ("6", "0"), "stretch": ("2", "0"),
            "tile": ("0", "1"), "center": ("0", "0"), "span": ("22", "0"),
        }.get(values.get("fit"), (None, None))
        if style is not None:
            entries += [_entry(DESKTOP, "WallpaperStyle", REG_SZ, style), _entry(DESKTOP, "TileWallpaper", REG_SZ, tile)]
    elif name == "theme":
        for key, value in (("apps_dark", "AppsUseLightTheme"), ("system_dark", "SystemUsesLightTheme")):
            if key in values:
                entries.append(_entry(PERSONALIZE, value, REG_DWORD, 0 if values[key] else 1))
        if "system_dark" not in values and "apps_dark" in values:
            entries.append(_entry(PERSONALIZE, "SystemUsesLightTheme", REG_DWORD, 0 if values["apps_dark"] else 1))
    elif name == "accent":
        if "color" in values:
            red, green, blue = (int(values["color"][i : i + 2], 16) for i in (1, 3, 5))
            abgr = 0xFF000000 | blue << 16 | green << 8 | red
            argb = 0xC4000000 | red << 16 | green << 8 | blue
            entries += [
                _entry(DWM, "AccentColor", REG_DWORD, abgr),
                _entry(DWM, "ColorizationColor", REG_DWORD, argb),
                _entry(DWM, "ColorizationAfterglow", REG_DWORD, argb),
                _entry(ACCENT, "AccentColorMenu", REG_DWORD, abgr),
                _entry(ACCENT, "StartColorMenu", REG_DWORD, abgr),
                _entry(DESKTOP, "AutoColorization", REG_SZ, "0"),
            ]
    elif name == "taskbar":
        if values.get("pinned"):
            notes.append("Taskbar: apps pinned on Linux can't be pinned on Windows automatically; pin them by hand.")
        if values.get("position") not in (None, "bottom"):
            notes.append("Taskbar: Windows 11 keeps the taskbar at the bottom of the screen.")
    elif name == "mouse":
        if "speed" in values:
            entries.append(_entry(MOUSE, "MouseSensitivity", REG_SZ, str(round(values["speed"] * 10 + 10))))
        if "acceleration" in values:
            on = values["acceleration"]
            entries += [
                _entry(MOUSE, "MouseSpeed", REG_SZ, "1" if on else "0"),
                _entry(MOUSE, "MouseThreshold1", REG_SZ, "6" if on else "0"),
                _entry(MOUSE, "MouseThreshold2", REG_SZ, "10" if on else "0"),
            ]
        if "left_handed" in values:
            entries.append(_entry(MOUSE, "SwapMouseButtons", REG_SZ, "1" if values["left_handed"] else "0"))
        if "double_click_ms" in values:
            entries.append(_entry(MOUSE, "DoubleClickSpeed", REG_SZ, str(values["double_click_ms"])))
    elif name == "keyboard":
        if "repeat_delay_ms" in values:
            delay = min(max(round(values["repeat_delay_ms"] / 250) - 1, 0), 3)
            entries.append(_entry(KEYBOARD, "KeyboardDelay", REG_SZ, str(delay)))
        if "repeat_interval_ms" in values:
            per_second = 1000 / values["repeat_interval_ms"]
            rate = min(max(round((per_second - 2.5) * 31 / 27.5), 0), 31)
            entries.append(_entry(KEYBOARD, "KeyboardSpeed", REG_SZ, str(rate)))
        languages: list[dict] = []
        for item in values.get("layouts", []):
            match = _BY_XKB.get((item.get("layout"), item.get("variant", ""))) or _BY_XKB.get((item.get("layout"), ""))
            if match is None:
                notes.append(f"Keyboard: no Windows match for the {layout_label(item)} layout, skipped.")
                continue
            klid, tag = match
            tip = f"{klid[-4:]}:{klid}"
            existing = next((lang for lang in languages if lang["tag"] == tag), None)
            if existing is None:
                languages.append({"tag": tag, "tips": [tip]})
            elif tip not in existing["tips"]:
                existing["tips"].append(tip)
        if languages:
            out["languages"] = languages
    return out, notes


def layout_label(item: dict) -> str:
    if "unknown" in item:
        language = item.get("language") or "unknown"
        # Input methods such as Japanese IMEs are long ids that mean nothing to people.
        return f"{language} input method" if "{" in item["unknown"] else f"{language} ({item['unknown']})"
    return item["layout"] + (f" ({item['variant']})" if item.get("variant") else "")

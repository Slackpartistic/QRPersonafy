"""The base for each Linux desktop QRPersonafy supports, and helpers they share.

A desktop saves and applies settings in the portable form (see `qrpersonafy.portable`), so a
profile saved on Windows, GNOME or KDE applies on any of them. Each setting is a pair of
methods, `export_<name>(ctx, files)` returning portable values and
`apply_<name>(ctx, values, section)`. A desktop without them for a setting skips it and
says why.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from .. import portable
from ..settings.base import Context, pack_file, unpack_file
from ..settings.wallpaper import image_extension
from . import gvariant
from .system import LinuxSystem

# Shown when a desktop has nothing to restore a setting into.
NO_START = (
    "Start menu: Linux desktops have no Start menu pins to restore. "
    "Pinned taskbar apps come over to the dock or panel instead."
)


class Desktop:
    id = ""
    name = ""
    # Names XDG_CURRENT_DESKTOP uses for this desktop, in lower case.
    session_names: tuple[str, ...] = ()
    # Shown when a setting isn't supported here, by setting name.
    missing: dict[str, str] = {}

    def __init__(self, system: LinuxSystem) -> None:
        self.system = system
        self.runner = system.runner

    @classmethod
    def matches(cls, names: list[str]) -> bool:
        return any(name in cls.session_names for name in names)

    def describe(self) -> str:
        return self.name

    def supports(self, name: str) -> bool:
        return hasattr(self, f"apply_{name}")

    def export(self, ctx: Context, name: str) -> dict | None:
        export = getattr(self, f"export_{name}", None)
        if export is None:
            return None
        files: dict = {}
        try:
            values = export(ctx, files)
        except OSError as error:
            ctx.warn(f"{label(name)}: could not read it from {self.name}: {error}")
            return None
        section: dict = {"portable": portable.clean(name, values or {})}
        if files:
            section["files"] = files
        return section

    def apply(self, ctx: Context, name: str, section: dict) -> bool:
        apply = getattr(self, f"apply_{name}", None)
        if apply is None:
            ctx.warn(self.missing.get(name) or (NO_START if name == "start" else f"{label(name)}: not supported on {self.name} yet."))
            return False
        values = portable.of(name, section)
        try:
            apply(ctx, values, section)
        except OSError as error:
            ctx.warn(f"{label(name)}: {error}")
        return True

    # Shared by several desktops

    def save_wallpaper(self, section: dict) -> Path | None:
        """Write a profile's wallpaper image to ~/.local/share/backgrounds and return its path."""
        files = section.get("files")
        entry = files.get("image") if isinstance(files, dict) else None
        if entry is None:
            return None
        name, data = unpack_file(entry)
        extension = Path(name).suffix.lower()
        if extension not in (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".jxl", ".svg"):
            extension = image_extension(data)
        # A new name for each image: desktops cache wallpapers by path.
        digest = hashlib.sha256(data).hexdigest()[:12]
        folder = self.system.data_home / "backgrounds" / "qrpersonafy"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"wallpaper-{digest}{extension}"
        target.write_bytes(data)
        return target

    def theme_exists(self, name: str) -> bool:
        if name in ("Adwaita", "Adwaita-dark", "HighContrast"):
            return True  # built into GTK
        folders = [self.system.home / ".themes"] + [d / "themes" for d in self.system.data_dirs()]
        return any((folder / name).is_dir() for folder in folders)

    def cursor_theme_exists(self, name: str) -> bool:
        folders = [self.system.home / ".icons"] + [d / "icons" for d in self.system.data_dirs()]
        return any((folder / name / "cursors").is_dir() for folder in folders)


def label(name: str) -> str:
    from ..settings import BY_NAME

    return BY_NAME[name].label if name in BY_NAME else name


def read_image(ctx: Context, files: dict, path: Path | None, desktop: str) -> None:
    """Add the wallpaper at `path` to an export."""
    if path is None or not path.is_file():
        ctx.warn(f"Wallpaper: no wallpaper image found on {desktop}, saving fit settings only")
        return
    if path.suffix.lower() == ".xml":
        # GNOME slideshows: use the first picture in the list.
        match = re.search(r"<file>\s*([^<]+?)\s*</file>", path.read_text(encoding="utf-8", errors="replace"))
        if match is None or not Path(match.group(1)).is_file():
            ctx.warn("Wallpaper: the slideshow's pictures weren't found, saving fit settings only")
            return
        path = Path(match.group(1))
    data = path.read_bytes()
    if path.suffix.lower() in (".jxl", ".svg", ".webp"):
        ctx.warn(f"Wallpaper: {path.name} is a {path.suffix[1:].upper()} image, which Windows may not be able to show")
    files["image"] = pack_file("wallpaper" + (path.suffix.lower() or image_extension(data)), data)


def path_from_uri(uri: object) -> Path | None:
    if not isinstance(uri, str) or not uri:
        return None
    if uri.startswith("file://"):
        return Path(unquote(urlparse(uri).path))
    if uri.startswith("/"):
        return Path(uri)
    return None


# Colors


def rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def nearest(color: str, palette: dict[str, str]) -> str:
    """The palette entry closest to `color`, judged roughly as people see it."""
    r1, g1, b1 = rgb(color)

    def distance(item):
        r2, g2, b2 = rgb(item[1])
        mean = (r1 + r2) / 2
        return (2 + mean / 256) * (r1 - r2) ** 2 + 4 * (g1 - g2) ** 2 + (2 + (255 - mean) / 256) * (b1 - b2) ** 2

    return min(palette.items(), key=distance)[0]


def is_dark_color(color: str) -> bool:
    r, g, b = rgb(color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 128


# GNOME 47 and later.
GNOME_ACCENTS = {
    "blue": "#3584E4",
    "teal": "#2190A4",
    "green": "#3A944A",
    "yellow": "#C88800",
    "orange": "#ED5B00",
    "red": "#E62D42",
    "pink": "#D56199",
    "purple": "#9141AC",
    "slate": "#6F8396",
}

# Ubuntu's Yaru theme comes in one variant per accent color ("" is the default orange).
YARU_ACCENTS = {
    "": "#E95420",
    "bark": "#787859",
    "sage": "#657B69",
    "olive": "#4B8501",
    "viridian": "#03875B",
    "prussiangreen": "#308280",
    "blue": "#0073E5",
    "purple": "#7764D8",
    "magenta": "#B34CB3",
    "red": "#DA3450",
}

# Linux Mint's Mint-Y theme, likewise ("" is the default green).
MINT_ACCENTS = {
    "": "#35A854",
    "Aqua": "#1F9EDE",
    "Blue": "#0C75DE",
    "Grey": "#70737A",
    "Orange": "#FF7139",
    "Pink": "#E54980",
    "Purple": "#8C5DD9",
    "Red": "#E82127",
    "Sand": "#C5A07C",
    "Teal": "#199CA8",
}


def yaru_parts(theme: str) -> tuple[str, bool] | None:
    """("blue", True) for "Yaru-blue-dark"; None if it isn't a Yaru theme."""
    match = re.fullmatch(r"Yaru(?:-([a-z]+?))?(-dark)?", theme)
    if match is None or (match.group(1) or "") not in YARU_ACCENTS:
        return None
    return match.group(1) or "", bool(match.group(2))


def yaru_name(accent: str, dark: bool) -> str:
    return "Yaru" + (f"-{accent}" if accent else "") + ("-dark" if dark else "")


def mint_parts(theme: str) -> tuple[str, str, bool] | None:
    """("Mint-Y", "Aqua", True) for "Mint-Y-Dark-Aqua"; None if it isn't a Mint theme."""
    match = re.fullmatch(r"(Mint-[YL])(-Dark|-Darker)?(?:-([A-Za-z]+))?", theme)
    if match is None or (match.group(3) or "") not in MINT_ACCENTS:
        return None
    return match.group(1), match.group(3) or "", bool(match.group(2))


def mint_name(family: str, accent: str, dark: bool) -> str:
    return family + ("-Dark" if dark else "") + (f"-{accent}" if accent else "")


def toggle_dark(desktop: Desktop, theme: str, dark: bool) -> str | None:
    """The light or dark sibling of a GTK theme, if one is installed."""
    if (parts := yaru_parts(theme)) is not None:
        return yaru_name(parts[0], dark)
    if (parts := mint_parts(theme)) is not None:
        return mint_name(parts[0], parts[1], dark)
    if dark:
        candidates = [theme + "-dark", theme + "-Dark", theme.replace("light", "dark"), theme.replace("Light", "Dark")]
    else:
        candidates = [re.sub(r"-[Dd]ark(er)?$", "", theme), theme.replace("dark", "light"), theme.replace("Dark", "Light")]
    for candidate in candidates:
        if candidate != theme and desktop.theme_exists(candidate):
            return candidate
    return None


def theme_is_dark(theme: object) -> bool:
    return isinstance(theme, str) and bool(re.search(r"[-_ ]?[Dd]ark(er)?\b|[Dd]ark$", theme))


# gsettings


class GSettings:
    """gsettings with missing schemas and keys treated as "not here" rather than errors.

    Settings move between schemas from one desktop version to the next, so every read and write
    checks the key exists first.
    """

    def __init__(self, runner) -> None:
        self.runner = runner
        self._keys: dict[str, set[str]] = {}

    def available(self) -> bool:
        return self.runner.has("gsettings")

    def has(self, schema: str, key: str | None = None) -> bool:
        if schema not in self._keys:
            try:
                self._keys[schema] = set(self.runner.run(["gsettings", "list-keys", schema]).split())
            except OSError:
                self._keys[schema] = set()
        return bool(self._keys[schema]) if key is None else key in self._keys[schema]

    def get(self, schema: str, key: str, default=None):
        if not self.has(schema, key):
            return default
        try:
            return gvariant.parse(self.runner.run(["gsettings", "get", schema, key]))
        except (OSError, ValueError):
            return default

    def set(self, schema: str, key: str, value) -> bool:
        if not self.has(schema, key):
            return False
        self.runner.run(["gsettings", "set", schema, key, gvariant.format(value)])
        return True


GNOME_INTERFACE = "org.gnome.desktop.interface"


def set_color_scheme(gsettings: GSettings, dark: bool) -> None:
    """Tell libadwaita and portal-aware apps about dark mode, on any desktop that has the key."""
    gsettings.set(GNOME_INTERFACE, "color-scheme", "prefer-dark" if dark else "default")


# Keyboard layouts as GNOME-family desktops write them.


def xkb_layouts(values: dict) -> tuple[list[tuple[str, str]], list[str]]:
    """(layout, variant) pairs from portable values, and labels of those that can't be used."""
    layouts, unknown = [], []
    for item in values.get("layouts", []):
        if "unknown" in item:
            unknown.append(portable.layout_label(item))
        else:
            layouts.append((item["layout"], item.get("variant", "")))
    return layouts, unknown


def warn_unknown_layouts(ctx: Context, unknown: list[str]) -> None:
    if unknown:
        ctx.warn(f"Keyboard: no Linux match for {', '.join(unknown)}; add those layouts in your keyboard settings.")

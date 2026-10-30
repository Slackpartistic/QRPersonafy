"""GNOME, the default desktop of Ubuntu, Fedora Workstation, Debian and many others.

Everything goes through gsettings. Ubuntu's dock is the Dash to Dock extension, so its
position and auto-hide are restored when that extension is installed.
"""

from __future__ import annotations

from ..settings.base import Context
from . import apps as app_lookup
from .desktop import (
    GNOME_ACCENTS,
    GNOME_INTERFACE,
    YARU_ACCENTS,
    Desktop,
    GSettings,
    nearest,
    path_from_uri,
    read_image,
    theme_is_dark,
    toggle_dark,
    warn_unknown_layouts,
    xkb_layouts,
    yaru_name,
    yaru_parts,
)

BACKGROUND = "org.gnome.desktop.background"
SHELL = "org.gnome.shell"
DOCK = "org.gnome.shell.extensions.dash-to-dock"
MOUSE = "org.gnome.desktop.peripherals.mouse"
KEYBOARD = "org.gnome.desktop.peripherals.keyboard"
INPUT_SOURCES = "org.gnome.desktop.input-sources"

# GNOME's picture-options and the portable fit names.
FIT_OPTIONS = {
    "zoom": "fill",
    "scaled": "fit",
    "stretched": "stretch",
    "wallpaper": "tile",
    "centered": "center",
    "spanned": "span",
}


class Gnome(Desktop):
    id = "gnome"
    name = "GNOME"
    # Ubuntu reports "ubuntu:GNOME", Pop!_OS "pop:GNOME", Budgie "Budgie:GNOME".
    session_names = ("gnome", "gnome-classic", "gnome-flashback", "ubuntu", "unity", "pop", "budgie", "pantheon", "zorin")

    def __init__(self, system) -> None:
        super().__init__(system)
        self.gs = GSettings(self.runner)

    def describe(self) -> str:
        version = ""
        try:
            version = self.runner.run(["gnome-shell", "--version"]).split()[-1]
        except (OSError, IndexError):
            pass
        return f"GNOME {version}".strip()

    def dark_now(self) -> bool:
        return self.gs.get(GNOME_INTERFACE, "color-scheme") == "prefer-dark" or theme_is_dark(self.gs.get(GNOME_INTERFACE, "gtk-theme"))

    # Wallpaper

    def export_wallpaper(self, ctx: Context, files: dict) -> dict:
        uri = None
        if self.dark_now():
            uri = self.gs.get(BACKGROUND, "picture-uri-dark")
        uri = uri or self.gs.get(BACKGROUND, "picture-uri")
        read_image(ctx, files, path_from_uri(uri), self.name)
        fit = FIT_OPTIONS.get(self.gs.get(BACKGROUND, "picture-options"))
        return {"fit": fit} if fit else {}

    def apply_wallpaper(self, ctx: Context, values: dict, section: dict) -> None:
        image = self.save_wallpaper(section)
        if image is not None:
            self.gs.set(BACKGROUND, "picture-uri", image.as_uri())
            self.gs.set(BACKGROUND, "picture-uri-dark", image.as_uri())
        if "fit" in values:
            option = next(o for o, f in FIT_OPTIONS.items() if f == values["fit"])
            self.gs.set(BACKGROUND, "picture-options", option)

    # Light/dark mode

    def export_theme(self, ctx: Context, files: dict) -> dict:
        dark = self.dark_now()
        return {"apps_dark": dark, "system_dark": dark}

    def apply_theme(self, ctx: Context, values: dict, section: dict) -> None:
        # GNOME has one switch. Windows' "apps" setting is the one people see most.
        dark = values.get("apps_dark", values.get("system_dark"))
        if dark is None:
            return
        self.gs.set(GNOME_INTERFACE, "color-scheme", "prefer-dark" if dark else "default")
        # Older GTK 3 apps follow the theme's name rather than the color scheme.
        theme = self.gs.get(GNOME_INTERFACE, "gtk-theme")
        if isinstance(theme, str) and (sibling := toggle_dark(self, theme, dark)) is not None:
            self.gs.set(GNOME_INTERFACE, "gtk-theme", sibling)

    # Accent color

    def export_accent(self, ctx: Context, files: dict) -> dict:
        accent = self.gs.get(GNOME_INTERFACE, "accent-color")
        if accent in GNOME_ACCENTS:
            return {"color": GNOME_ACCENTS[accent]}
        theme = self.gs.get(GNOME_INTERFACE, "gtk-theme")
        if isinstance(theme, str) and (parts := yaru_parts(theme)) is not None:
            return {"color": YARU_ACCENTS[parts[0]]}
        return {}

    def apply_accent(self, ctx: Context, values: dict, section: dict) -> None:
        if "color" not in values:
            return
        done = self.gs.set(GNOME_INTERFACE, "accent-color", nearest(values["color"], GNOME_ACCENTS))
        # Ubuntu before 24.10 picks the accent through Yaru's theme variants.
        theme = self.gs.get(GNOME_INTERFACE, "gtk-theme")
        if isinstance(theme, str) and (parts := yaru_parts(theme)) is not None:
            variant = nearest(values["color"], YARU_ACCENTS)
            self.gs.set(GNOME_INTERFACE, "gtk-theme", yaru_name(variant, parts[1]))
            icons = self.gs.get(GNOME_INTERFACE, "icon-theme")
            if isinstance(icons, str) and yaru_parts(icons) is not None:
                self.gs.set(GNOME_INTERFACE, "icon-theme", yaru_name(variant, False))
            done = True
        if not done:
            ctx.warn("Accent color: this GNOME has no accent color setting (it arrived in GNOME 47).")

    # Taskbar: the dash's favorites, and Ubuntu's dock

    def export_taskbar(self, ctx: Context, files: dict) -> dict:
        favorites = self.gs.get(SHELL, "favorite-apps", [])
        values: dict = {"pinned": app_lookup.pins_for([f for f in favorites if isinstance(f, str)], app_lookup.installed_apps(self.system))}
        position = self.gs.get(DOCK, "dock-position")
        if isinstance(position, str):
            values["position"] = position.lower()
            values["autohide"] = self.gs.get(DOCK, "dock-fixed") is False
        return values

    def apply_taskbar(self, ctx: Context, values: dict, section: dict) -> None:
        if values.get("pinned"):
            found, missing = app_lookup.match_pins(values["pinned"], app_lookup.installed_apps(self.system))
            if found and not self.gs.set(SHELL, "favorite-apps", found):
                ctx.warn("Taskbar: GNOME Shell's settings weren't found, so apps weren't pinned.")
            if missing:
                ctx.warn(f"Taskbar: these apps aren't installed here, so they weren't pinned: {', '.join(missing)}")
        if not self.gs.has(DOCK):
            if values.get("position") not in (None, "bottom") or values.get("autohide"):
                ctx.warn("Taskbar: this GNOME has no dock to move; pinned apps are in the Activities overview.")
            return
        if "position" in values:
            self.gs.set(DOCK, "dock-position", values["position"].upper())
        if "autohide" in values:
            self.gs.set(DOCK, "dock-fixed", not values["autohide"])
            self.gs.set(DOCK, "autohide", values["autohide"])

    # Mouse

    def export_mouse(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        speed = self.gs.get(MOUSE, "speed")
        if isinstance(speed, (int, float)):
            values["speed"] = float(speed)
        profile = self.gs.get(MOUSE, "accel-profile")
        if isinstance(profile, str):
            values["acceleration"] = profile != "flat"
        for key, name in (("left-handed", "left_handed"), ("double-click", "double_click_ms")):
            value = self.gs.get(MOUSE, key)
            if value is not None:
                values[name] = value
        for key, name in (("cursor-theme", "cursor_theme"), ("cursor-size", "cursor_size")):
            value = self.gs.get(GNOME_INTERFACE, key)
            if value is not None:
                values[name] = value
        return values

    def apply_mouse(self, ctx: Context, values: dict, section: dict) -> None:
        if "speed" in values:
            self.gs.set(MOUSE, "speed", values["speed"])
        if "acceleration" in values:
            self.gs.set(MOUSE, "accel-profile", "default" if values["acceleration"] else "flat")
        if "left_handed" in values:
            self.gs.set(MOUSE, "left-handed", values["left_handed"])
        if "double_click_ms" in values:
            self.gs.set(MOUSE, "double-click", values["double_click_ms"])
        if "cursor_theme" in values and self.cursor_theme_exists(values["cursor_theme"]):
            self.gs.set(GNOME_INTERFACE, "cursor-theme", values["cursor_theme"])
        if "cursor_size" in values:
            self.gs.set(GNOME_INTERFACE, "cursor-size", values["cursor_size"])

    # Keyboard

    def export_keyboard(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        for key, name in (("delay", "repeat_delay_ms"), ("repeat-interval", "repeat_interval_ms")):
            value = self.gs.get(KEYBOARD, key)
            if isinstance(value, int):
                values[name] = value
        layouts = []
        for source in self.gs.get(INPUT_SOURCES, "sources", []) or []:
            if isinstance(source, tuple) and len(source) == 2 and source[0] == "xkb" and isinstance(source[1], str):
                layout, _, variant = source[1].partition("+")
                layouts.append({"layout": layout, "variant": variant})
        if layouts:
            values["layouts"] = layouts
        return values

    def apply_keyboard(self, ctx: Context, values: dict, section: dict) -> None:
        if "repeat_delay_ms" in values:
            self.gs.set(KEYBOARD, "delay", values["repeat_delay_ms"])
        if "repeat_interval_ms" in values:
            self.gs.set(KEYBOARD, "repeat-interval", values["repeat_interval_ms"])
        layouts, unknown = xkb_layouts(values)
        if layouts:
            current = self.gs.get(INPUT_SOURCES, "sources", []) or []
            # Keep input methods such as Japanese or Chinese, which only have meaning here.
            others = [s for s in current if isinstance(s, tuple) and len(s) == 2 and s[0] != "xkb"]
            sources = [("xkb", layout + (f"+{variant}" if variant else "")) for layout, variant in layouts]
            self.gs.set(INPUT_SOURCES, "sources", sources + others)
        warn_unknown_layouts(ctx, unknown)

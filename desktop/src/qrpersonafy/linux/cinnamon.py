"""Cinnamon, Linux Mint's desktop, and MATE. Both keep their settings in gsettings, like GNOME."""

from __future__ import annotations

import json

from ..settings.base import Context
from . import apps as app_lookup
from .desktop import (
    MINT_ACCENTS,
    Desktop,
    GSettings,
    mint_name,
    mint_parts,
    nearest,
    path_from_uri,
    read_image,
    set_color_scheme,
    theme_is_dark,
    toggle_dark,
    warn_unknown_layouts,
    xkb_layouts,
)
from .gnome import FIT_OPTIONS

PORTAL = "org.x.apps.portal"
GNOMEKBD = "org.gnome.libgnomekbd.keyboard"


def tab_layouts(layouts: list[tuple[str, str]]) -> list[str]:
    """libgnomekbd's form: "us", or "de<TAB>nodeadkeys"."""
    return [layout + (f"\t{variant}" if variant else "") for layout, variant in layouts]


def from_tab_layouts(value) -> list[dict]:
    layouts = []
    for item in value or []:
        if isinstance(item, str) and item:
            layout, _, variant = item.partition("\t")
            layouts.append({"layout": layout, "variant": variant})
    return layouts


class GtkDesktop(Desktop):
    """What Cinnamon and MATE share. Subclasses name their schemas."""

    interface = ""
    background = ""
    mouse = ""
    keyboard = ""
    kbd_layouts = (GNOMEKBD, "layouts")
    # Other schemas holding the theme name, kept in step with the GTK theme.
    theme_keys: tuple[tuple[str, str], ...] = ()

    def __init__(self, system) -> None:
        super().__init__(system)
        self.gs = GSettings(self.runner)

    def gtk_theme(self) -> str | None:
        theme = self.gs.get(self.interface, "gtk-theme")
        return theme if isinstance(theme, str) else None

    def set_gtk_theme(self, theme: str) -> None:
        self.gs.set(self.interface, "gtk-theme", theme)
        for schema, key in self.theme_keys:
            self.gs.set(schema, key, theme)

    # Wallpaper

    def wallpaper_path(self):
        return path_from_uri(self.gs.get(self.background, "picture-uri"))

    def set_wallpaper_path(self, image) -> None:
        self.gs.set(self.background, "picture-uri", image.as_uri())

    def export_wallpaper(self, ctx: Context, files: dict) -> dict:
        read_image(ctx, files, self.wallpaper_path(), self.name)
        fit = FIT_OPTIONS.get(self.gs.get(self.background, "picture-options"))
        return {"fit": fit} if fit else {}

    def apply_wallpaper(self, ctx: Context, values: dict, section: dict) -> None:
        image = self.save_wallpaper(section)
        if image is not None:
            self.set_wallpaper_path(image)
        if "fit" in values:
            self.gs.set(self.background, "picture-options", next(o for o, f in FIT_OPTIONS.items() if f == values["fit"]))

    # Light/dark mode

    def export_theme(self, ctx: Context, files: dict) -> dict:
        scheme = self.gs.get(PORTAL, "color-scheme")
        dark = scheme == "prefer-dark" if isinstance(scheme, str) and scheme != "default" else theme_is_dark(self.gtk_theme())
        return {"apps_dark": dark, "system_dark": dark}

    def apply_theme(self, ctx: Context, values: dict, section: dict) -> None:
        dark = values.get("apps_dark", values.get("system_dark"))
        if dark is None:
            return
        self.gs.set(PORTAL, "color-scheme", "prefer-dark" if dark else "prefer-light")
        set_color_scheme(self.gs, dark)
        theme = self.gtk_theme()
        if theme and (sibling := toggle_dark(self, theme, dark)) is not None:
            self.set_gtk_theme(sibling)
        elif theme and theme_is_dark(theme) != dark:
            ctx.warn(f"Light/dark mode: the {theme} theme has no {'dark' if dark else 'light'} version installed.")

    # Accent color, through Mint-Y's color variants

    def export_accent(self, ctx: Context, files: dict) -> dict:
        theme = self.gtk_theme()
        parts = mint_parts(theme) if theme else None
        return {"color": MINT_ACCENTS[parts[1]]} if parts else {}

    def apply_accent(self, ctx: Context, values: dict, section: dict) -> None:
        if "color" not in values:
            return
        theme = self.gtk_theme()
        parts = mint_parts(theme) if theme else None
        if parts is None:
            ctx.warn(f"Accent color: {self.name} sets it through the theme, and {theme or 'this theme'} has no color choices.")
            return
        family, _, dark = parts
        self.set_gtk_theme(mint_name(family, nearest(values["color"], MINT_ACCENTS), dark))

    # Mouse and keyboard

    def export_mouse(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        speed = self.read_speed()
        if speed is not None:
            values["speed"] = speed
        for key, name in (("left-handed", "left_handed"), ("double-click", "double_click_ms")):
            if (value := self.gs.get(self.mouse, key)) is not None:
                values[name] = value
        for key, name in (("cursor-theme", "cursor_theme"), ("cursor-size", "cursor_size")):
            if (value := self.gs.get(self.cursor_schema(), key)) is not None:
                values[name] = value
        return values

    def apply_mouse(self, ctx: Context, values: dict, section: dict) -> None:
        if "speed" in values:
            self.write_speed(values["speed"])
        if "acceleration" in values:
            self.gs.set(self.mouse, "accel-profile", "default" if values["acceleration"] else "flat")
        if "left_handed" in values:
            self.gs.set(self.mouse, "left-handed", values["left_handed"])
        if "double_click_ms" in values:
            self.gs.set(self.mouse, "double-click", values["double_click_ms"])
        if "cursor_theme" in values and self.cursor_theme_exists(values["cursor_theme"]):
            self.gs.set(self.cursor_schema(), "cursor-theme", values["cursor_theme"])
        if "cursor_size" in values:
            self.gs.set(self.cursor_schema(), "cursor-size", values["cursor_size"])

    def cursor_schema(self) -> str:
        return self.interface

    def read_speed(self) -> float | None:
        speed = self.gs.get(self.mouse, "speed")
        return float(speed) if isinstance(speed, (int, float)) else None

    def write_speed(self, speed: float) -> None:
        self.gs.set(self.mouse, "speed", speed)

    def export_keyboard(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        if isinstance(delay := self.gs.get(self.keyboard, "delay"), int):
            values["repeat_delay_ms"] = delay
        if (interval := self.read_interval()) is not None:
            values["repeat_interval_ms"] = interval
        layouts = from_tab_layouts(self.gs.get(*self.kbd_layouts))
        if layouts:
            values["layouts"] = layouts
        return values

    def apply_keyboard(self, ctx: Context, values: dict, section: dict) -> None:
        if "repeat_delay_ms" in values:
            self.gs.set(self.keyboard, "delay", values["repeat_delay_ms"])
        if "repeat_interval_ms" in values:
            self.write_interval(values["repeat_interval_ms"])
        layouts, unknown = xkb_layouts(values)
        if layouts:
            self.gs.set(*self.kbd_layouts, tab_layouts(layouts))
        warn_unknown_layouts(ctx, unknown)

    def read_interval(self) -> int | None:
        interval = self.gs.get(self.keyboard, "repeat-interval")
        return interval if isinstance(interval, int) else None

    def write_interval(self, interval: int) -> None:
        self.gs.set(self.keyboard, "repeat-interval", interval)


class Cinnamon(GtkDesktop):
    id = "cinnamon"
    name = "Cinnamon"
    session_names = ("x-cinnamon", "cinnamon")
    interface = "org.cinnamon.desktop.interface"
    background = "org.cinnamon.desktop.background"
    mouse = "org.cinnamon.desktop.peripherals.mouse"
    keyboard = "org.cinnamon.desktop.peripherals.keyboard"
    theme_keys = (("org.cinnamon.theme", "name"), ("org.cinnamon.desktop.wm.preferences", "theme"))

    def apply_accent(self, ctx: Context, values: dict, section: dict) -> None:
        super().apply_accent(ctx, values, section)
        # Mint's icons come in the same colors.
        icons = self.gs.get(self.interface, "icon-theme")
        theme = self.gtk_theme()
        parts = mint_parts(theme) if theme else None
        if parts and isinstance(icons, str) and icons.startswith(parts[0]):
            self.gs.set(self.interface, "icon-theme", parts[0] + (f"-{parts[1]}" if parts[1] else ""))

    # The panel: "1:0:bottom" says panel 1 is on monitor 0 at the bottom.

    def export_taskbar(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        panels = self.gs.get("org.cinnamon", "panels-enabled", [])
        if panels and isinstance(panels[0], str) and panels[0].count(":") == 2:
            values["position"] = panels[0].split(":")[2]
        hide = self.gs.get("org.cinnamon", "panels-autohide", [])
        if hide and isinstance(hide[0], str) and ":" in hide[0]:
            values["autohide"] = hide[0].split(":", 1)[1] != "false"
        pinned = []
        for path in self.window_list_configs():
            try:
                pinned = json.loads(path.read_text(encoding="utf-8"))["pinned-apps"]["value"]
                break
            except (OSError, ValueError, KeyError, TypeError):
                continue
        values["pinned"] = app_lookup.pins_for([p for p in pinned if isinstance(p, str)], app_lookup.installed_apps(self.system))
        return values

    def apply_taskbar(self, ctx: Context, values: dict, section: dict) -> None:
        panels = self.gs.get("org.cinnamon", "panels-enabled", [])
        if "position" in values and panels and isinstance(panels[0], str) and panels[0].count(":") == 2:
            panel, monitor, _ = panels[0].split(":")
            self.gs.set("org.cinnamon", "panels-enabled", [f"{panel}:{monitor}:{values['position']}"] + panels[1:])
        hide = self.gs.get("org.cinnamon", "panels-autohide", [])
        if "autohide" in values and hide and isinstance(hide[0], str) and ":" in hide[0]:
            panel = hide[0].split(":", 1)[0]
            self.gs.set("org.cinnamon", "panels-autohide", [f"{panel}:{'true' if values['autohide'] else 'false'}"] + hide[1:])
        if values.get("pinned"):
            found, missing = app_lookup.match_pins(values["pinned"], app_lookup.installed_apps(self.system))
            configs = self.window_list_configs()
            if found and not configs:
                ctx.warn("Taskbar: the panel's window list wasn't found, so apps weren't pinned.")
            for path in configs if found else []:
                try:
                    config = json.loads(path.read_text(encoding="utf-8"))
                    config["pinned-apps"]["value"] = found
                    path.write_text(json.dumps(config, indent=4), encoding="utf-8")
                except (OSError, ValueError, KeyError, TypeError) as error:
                    ctx.warn(f"Taskbar: could not pin apps in {path.name}: {error}")
            if missing:
                ctx.warn(f"Taskbar: these apps aren't installed here, so they weren't pinned: {', '.join(missing)}")

    def window_list_configs(self):
        folder = self.system.config_home / "cinnamon" / "spices" / "grouped-window-list@cinnamon.org"
        return sorted(folder.glob("*.json")) if folder.is_dir() else []


class Mate(GtkDesktop):
    id = "mate"
    name = "MATE"
    session_names = ("mate",)
    interface = "org.mate.interface"
    background = "org.mate.background"
    mouse = "org.mate.peripherals-mouse"
    keyboard = "org.mate.peripherals-keyboard"
    kbd_layouts = ("org.mate.peripherals-keyboard-xkb.kbd", "layouts")
    theme_keys = (("org.mate.Marco.general", "theme"),)
    missing = {"taskbar": "Taskbar: restoring MATE's panel isn't supported yet; the rest still applies."}

    def wallpaper_path(self):
        return path_from_uri(self.gs.get(self.background, "picture-filename"))

    def set_wallpaper_path(self, image) -> None:
        self.gs.set(self.background, "picture-filename", str(image))

    def cursor_schema(self) -> str:
        return self.mouse

    # MATE's speed is "motion-acceleration", 1 to 10, or -1 for the default.

    def read_speed(self) -> float | None:
        value = self.gs.get(self.mouse, "motion-acceleration")
        if not isinstance(value, (int, float)):
            return None
        return 0.0 if value < 1 else round((min(value, 10) - 1) / 4.5 - 1, 2)

    def write_speed(self, speed: float) -> None:
        self.gs.set(self.mouse, "motion-acceleration", round(1 + (speed + 1) * 4.5, 1))

    # And its key repeat is a rate in keys per second.

    def read_interval(self) -> int | None:
        rate = self.gs.get(self.keyboard, "rate")
        return round(1000 / rate) if isinstance(rate, int) and rate > 0 else None

    def write_interval(self, interval: int) -> None:
        self.gs.set(self.keyboard, "rate", max(1, round(1000 / interval)))

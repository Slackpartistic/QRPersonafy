"""Cinnamon, Linux Mint's desktop, and MATE. Both keep their settings in gsettings, like GNOME."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..settings.base import Context
from . import apps as app_lookup
from .desktop import (
    Desktop,
    GSettings,
    mint_parts,
    path_from_uri,
    read_image,
    recolor_theme,
    set_color_scheme,
    theme_accent,
    theme_is_dark,
    toggle_dark,
    warn_unknown_layouts,
    xkb_layouts,
)
from .gnome import FIT_OPTIONS

PORTAL = "org.x.apps.portal"
MATE_PANEL = "org.mate.panel"
# Applets that list open windows, which make a MATE panel the taskbar.
TASK_LISTS = ("WindowListApplet", "DockApplet", "TasklistApplet")
# Panel and object ids become parts of a settings path.
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
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

    # Accent color, through the color variants of Mint-Y and Yaru

    def export_accent(self, ctx: Context, files: dict) -> dict:
        color = theme_accent(self.gtk_theme())
        return {"color": color} if color else {}

    def apply_accent(self, ctx: Context, values: dict, section: dict) -> None:
        if "color" not in values:
            return
        theme = self.gtk_theme()
        recolored = recolor_theme(theme, values["color"])
        if recolored is None:
            ctx.warn(f"Accent color: {self.name} sets it through the theme, and {theme or 'this theme'} has no color choices.")
            return
        self.set_gtk_theme(recolored)

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

    # The panel. Each panel ("toplevel") and each thing on one ("object") has its own settings
    # under a path, e.g. org.mate.panel.object:/org/mate/panel/objects/firefox/.

    def toplevel(self, toplevel_id: str) -> str:
        return f"{MATE_PANEL}.toplevel:/org/mate/panel/toplevels/{toplevel_id}/"

    def object(self, object_id: str) -> str:
        return f"{MATE_PANEL}.object:/org/mate/panel/objects/{object_id}/"

    def panel_objects(self) -> list[dict]:
        objects = []
        for object_id in self.gs.get(MATE_PANEL, "object-id-list", []) or []:
            if not isinstance(object_id, str) or not SAFE_ID.match(object_id):
                continue
            schema = self.object(object_id)
            objects.append({
                "id": object_id,
                "type": self.gs.get(schema, "object-type", ""),
                "toplevel": self.gs.get(schema, "toplevel-id", ""),
                "position": self.gs.get(schema, "position", 0),
                "end": self.gs.get(schema, "relative-to-edge", "start") == "end",
                "iid": self.gs.get(schema, "applet-iid", "") or "",
                "location": self.gs.get(schema, "launcher-location", "") or "",
            })
        return objects

    def main_toplevel(self, objects: list[dict]) -> str | None:
        """The panel acting as the taskbar: the one with the window list, else the bottom one."""
        toplevels = [t for t in self.gs.get(MATE_PANEL, "toplevel-id-list", []) or [] if isinstance(t, str) and SAFE_ID.match(t)]
        for item in objects:
            if any(name in item["iid"] for name in TASK_LISTS) and item["toplevel"] in toplevels:
                return item["toplevel"]
        for toplevel_id in toplevels:
            if self.gs.get(self.toplevel(toplevel_id), "orientation") == "bottom":
                return toplevel_id
        return toplevels[0] if toplevels else None

    def launcher_file(self, location: str):
        if not location:
            return None
        path = Path(location)
        # Launchers made from the panel's menu are copies kept in MATE's own folder.
        return path if path.is_absolute() else self.system.config_home / "mate" / "panel2.d" / "default" / "launchers" / location

    def launchers(self, objects: list[dict]) -> list[dict]:
        toplevels = self.gs.get(MATE_PANEL, "toplevel-id-list", []) or []
        found = [o for o in objects if o["type"] == "launcher" and o["location"]]
        return sorted(found, key=lambda o: (toplevels.index(o["toplevel"]) if o["toplevel"] in toplevels else 99, o["end"], o["position"]))

    def export_taskbar(self, ctx: Context, files: dict) -> dict:
        objects = self.panel_objects()
        values: dict = {}
        main = self.main_toplevel(objects)
        if main is not None:
            orientation = self.gs.get(self.toplevel(main), "orientation")
            if orientation in ("top", "bottom", "left", "right"):
                values["position"] = orientation
            hide = self.gs.get(self.toplevel(main), "auto-hide")
            if isinstance(hide, bool):
                values["autohide"] = hide
        paths = [p for o in self.launchers(objects) if (p := self.launcher_file(o["location"])) is not None]
        values["pinned"] = app_lookup.pins_from_launchers(paths, app_lookup.installed_apps(self.system))
        return values

    def apply_taskbar(self, ctx: Context, values: dict, section: dict) -> None:
        if not self.gs.has(MATE_PANEL, "object-id-list"):
            ctx.warn("Taskbar: MATE's panel settings weren't found, so the panel wasn't changed.")
            return
        objects = self.panel_objects()
        main = self.main_toplevel(objects)
        if main is not None:
            if "position" in values:
                self.gs.set(self.toplevel(main), "orientation", values["position"])
            if "autohide" in values:
                self.gs.set(self.toplevel(main), "auto-hide", values["autohide"])
        if values.get("pinned"):
            self.add_launchers(ctx, values["pinned"], objects, main)

    def add_launchers(self, ctx: Context, pins: list[dict], objects: list[dict], main: str | None) -> None:
        """Add a launcher for each pinned app the panel doesn't have one for yet.

        Launchers already on the panel stay. New ones go after the last launcher, or before the
        window list on a panel that has none.
        """
        apps = app_lookup.installed_apps(self.system)
        found, missing = app_lookup.match_pins(pins, apps)
        files = [p for o in self.launchers(objects) if (p := self.launcher_file(o["location"])) is not None]
        pinned = app_lookup.pins_from_launchers(files, apps)
        have = {f.name for f in files} | {pin.get("id") for pin in pinned}
        have_names = {pin.get("name") for pin in pinned}
        new = [a for a in found if a not in have and apps[a].name not in have_names]
        if new:
            start = [o for o in self.launchers(objects) if not o["end"]]
            if start:
                toplevel, position = start[-1]["toplevel"], start[-1]["position"] + 1
            elif main is not None:
                toplevel = main
                window_list = next((o for o in objects if o["toplevel"] == main and any(n in o["iid"] for n in TASK_LISTS)), None)
                before = [o["position"] for o in objects if o["toplevel"] == main and not o["end"]
                          and (window_list is None or o["position"] < window_list["position"])]
                position = max(before) + 1 if before else 0
            else:
                ctx.warn("Taskbar: MATE has no panel to pin apps to.")
                return
            ids = [o for o in self.gs.get(MATE_PANEL, "object-id-list", []) or [] if isinstance(o, str)]
            for i, app_id in enumerate(new):
                path = app_lookup.app_file(app_id, self.system)
                if path is None:
                    continue
                object_id = next(f"qrestoa-launcher-{n}" for n in range(len(ids) + len(new) + 1) if f"qrestoa-launcher-{n}" not in ids)
                schema = self.object(object_id)
                # Everything about the launcher first, so the panel sees it whole when it's listed.
                self.gs.set(schema, "object-type", "launcher")
                self.gs.set(schema, "toplevel-id", toplevel)
                self.gs.set(schema, "position", position + i)
                self.gs.set(schema, "relative-to-edge", "start")
                self.gs.set(schema, "launcher-location", str(path))
                ids.append(object_id)
                self.gs.set(MATE_PANEL, "object-id-list", ids)
        if missing:
            ctx.warn(f"Taskbar: these apps aren't installed here, so they weren't pinned: {', '.join(missing)}")

    # And its key repeat is a rate in keys per second.

    def read_interval(self) -> int | None:
        rate = self.gs.get(self.keyboard, "rate")
        return round(1000 / rate) if isinstance(rate, int) and rate > 0 else None

    def write_interval(self, interval: int) -> None:
        self.gs.set(self.keyboard, "rate", max(1, round(1000 / interval)))

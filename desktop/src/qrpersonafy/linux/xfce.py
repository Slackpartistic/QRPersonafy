"""Xfce, through xfconf-query. Xubuntu, Linux Mint Xfce and Manjaro Xfce use it."""

from __future__ import annotations

import re
from pathlib import Path

from ..settings.base import Context
from . import apps as app_lookup
from .desktop import (
    Desktop,
    GSettings,
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

# xfce4-desktop's image-style and the portable fit names.
IMAGE_STYLES = {5: "fill", 4: "fit", 3: "stretch", 2: "tile", 1: "center", 6: "span"}

# Where a panel snaps to, the "p" in its position "p=6;x=0;y=0" (xfce4-panel's SnapPosition).
# Horizontal panels are at the top or bottom, vertical ones at the left or right.
SNAP_SIDES = {
    "horizontal": {2: "top", 6: "top", 9: "top", 11: "top", 4: "bottom", 8: "bottom", 10: "bottom", 12: "bottom"},
    "vertical": {5: "left", 6: "left", 7: "left", 8: "left", 1: "right", 2: "right", 3: "right", 4: "right"},
}
# Where QRestoa puts a panel: centred on that side (a full-width panel fills it either way).
SNAP_TO = {"top": 9, "bottom": 10, "left": 7, "right": 3}
# Plug-ins that list open windows, which make a panel the taskbar, and app menus, which
# new launchers go after.
TASK_LISTS = ("tasklist", "docklike")
MENUS = ("whiskermenu", "applicationsmenu", "menu")
PANEL = "xfce4-panel"


class Xfce(Desktop):
    id = "xfce"
    name = "Xfce"
    session_names = ("xfce",)

    def __init__(self, system) -> None:
        super().__init__(system)
        self.gs = GSettings(self.runner)

    def get(self, channel: str, prop: str):
        try:
            return self.runner.run(["xfconf-query", "-c", channel, "-p", prop]).strip()
        except OSError:
            return None

    def get_list(self, channel: str, prop: str) -> list[str]:
        """An array property's items. xfconf-query prints "Value is an array with 2 items:" first."""
        text = self.get(channel, prop)
        if not text:
            return []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines[1:] if lines[0].startswith("Value is an array") else lines

    def set(self, channel: str, prop: str, kind: str, value) -> None:
        if kind == "bool":
            value = "true" if value else "false"
        self.runner.run(["xfconf-query", "-c", channel, "-p", prop, "-n", "-t", kind, "-s", str(value)])

    def set_list(self, channel: str, prop: str, kind: str, values: list) -> None:
        args = ["xfconf-query", "-c", channel, "-p", prop, "-n", "-a"]
        for value in values:
            args += ["-t", kind, "-s", str(value)]
        self.runner.run(args)

    def props(self, channel: str) -> list[str]:
        try:
            return self.runner.run(["xfconf-query", "-c", channel, "-l"]).split()
        except OSError:
            return []

    # Wallpaper: each monitor and workspace has its own, so all of them are set.

    def export_wallpaper(self, ctx: Context, files: dict) -> dict:
        images = [p for p in self.props("xfce4-desktop") if p.endswith("/last-image")]
        path = self.get("xfce4-desktop", images[0]) if images else None
        read_image(ctx, files, Path(path) if path else None, self.name)
        style = self.get("xfce4-desktop", images[0].replace("/last-image", "/image-style")) if images else None
        fit = IMAGE_STYLES.get(int(style)) if style and style.isdigit() else None
        return {"fit": fit} if fit else {}

    def apply_wallpaper(self, ctx: Context, values: dict, section: dict) -> None:
        images = [p for p in self.props("xfce4-desktop") if p.endswith("/last-image")]
        if not images:
            ctx.warn("Wallpaper: Xfce's desktop has no wallpaper slots yet; open Desktop Settings once and try again.")
            return
        image = self.save_wallpaper(section)
        style = next((s for s, f in IMAGE_STYLES.items() if f == values.get("fit")), None)
        for prop in images:
            if image is not None:
                self.set("xfce4-desktop", prop, "string", image)
            if style is not None:
                self.set("xfce4-desktop", prop.replace("/last-image", "/image-style"), "int", style)

    # Light/dark mode

    def export_theme(self, ctx: Context, files: dict) -> dict:
        dark = theme_is_dark(self.get("xsettings", "/Net/ThemeName"))
        return {"apps_dark": dark, "system_dark": dark}

    def apply_theme(self, ctx: Context, values: dict, section: dict) -> None:
        dark = values.get("apps_dark", values.get("system_dark"))
        if dark is None:
            return
        set_color_scheme(self.gs, dark)
        theme = self.get("xsettings", "/Net/ThemeName")
        if not theme:
            return
        sibling = toggle_dark(self, theme, dark)
        if sibling is None:
            if theme_is_dark(theme) != dark:
                ctx.warn(f"Light/dark mode: the {theme} theme has no {'dark' if dark else 'light'} version installed.")
            return
        self.set("xsettings", "/Net/ThemeName", "string", sibling)
        window_theme = self.get("xfwm4", "/general/theme")
        if window_theme and (window_sibling := toggle_dark(self, window_theme, dark)) is not None:
            self.set("xfwm4", "/general/theme", "string", window_sibling)

    # Accent color: Xfce takes it from the theme, so themes with color versions (Mint-Y, Yaru)
    # are switched to the closest color.

    def export_accent(self, ctx: Context, files: dict) -> dict:
        color = theme_accent(self.get("xsettings", "/Net/ThemeName"))
        return {"color": color} if color else {}

    def apply_accent(self, ctx: Context, values: dict, section: dict) -> None:
        if "color" not in values:
            return
        theme = self.get("xsettings", "/Net/ThemeName")
        recolored = recolor_theme(theme, values["color"])
        if recolored is None:
            ctx.warn(
                f"Accent color: Xfce takes it from the theme, and {theme or 'this theme'} has no color choices. "
                "Themes that come in colors, like Mint-Y or Yaru, can be changed."
            )
            return
        if recolored == theme:
            return
        if not self.theme_exists(recolored):
            ctx.warn(f"Accent color: the {recolored} theme isn't installed, so the color wasn't changed.")
            return
        self.set("xsettings", "/Net/ThemeName", "string", recolored)
        window_theme = self.get("xfwm4", "/general/theme")
        window_recolored = recolor_theme(window_theme, values["color"])
        if window_recolored and window_recolored != window_theme and self.window_theme_exists(window_recolored):
            self.set("xfwm4", "/general/theme", "string", window_recolored)
        icons = self.get("xsettings", "/Net/IconThemeName")
        icons_recolored = recolor_theme(icons, values["color"], icons=True)
        if icons_recolored and icons_recolored != icons and self.icon_theme_exists(icons_recolored):
            self.set("xsettings", "/Net/IconThemeName", "string", icons_recolored)

    def window_theme_exists(self, name: str) -> bool:
        folders = [self.system.home / ".themes", self.system.data_home / "themes"] + [d / "themes" for d in self.system.data_dirs()]
        return any((folder / name / "xfwm4").is_dir() for folder in folders)

    # Taskbar: the panel with the window list (Xubuntu has one panel at the top, Mint and
    # upstream Xfce one at the bottom), and launchers for pinned apps.

    def panel_ids(self) -> list[int]:
        return [int(i) for i in self.get_list(PANEL, "/panels") if i.isdigit()]

    def plugin_ids(self, panel: int) -> list[int]:
        return [int(i) for i in self.get_list(PANEL, f"/panels/panel-{panel}/plugin-ids") if i.isdigit()]

    def plugin_kind(self, plugin: int) -> str:
        return self.get(PANEL, f"/plugins/plugin-{plugin}") or ""

    def main_panel(self) -> int | None:
        panels = self.panel_ids()
        for panel in panels:
            if any(self.plugin_kind(p) in TASK_LISTS for p in self.plugin_ids(panel)):
                return panel
        return panels[0] if panels else None

    def side(self, panel: int) -> str | None:
        match = re.search(r"p=(\d+)", self.get(PANEL, f"/panels/panel-{panel}/position") or "")
        mode = self.get(PANEL, f"/panels/panel-{panel}/mode")
        layout = "vertical" if mode in ("1", "2") else "horizontal"
        return SNAP_SIDES[layout].get(int(match.group(1))) if match else None

    def launchers(self) -> list[tuple[int, int, Path]]:
        """(panel, plugin, .desktop file) for each launcher, in panel order."""
        found = []
        for panel in self.panel_ids():
            for plugin in self.plugin_ids(panel):
                if self.plugin_kind(plugin) != "launcher":
                    continue
                items = self.get_list(PANEL, f"/plugins/plugin-{plugin}/items")
                if items:
                    found.append((panel, plugin, self.launcher_file(plugin, items[0])))
        return found

    def launcher_file(self, plugin: int, item: str) -> Path:
        """A launcher item: a file in the launcher's own folder, a full path, or an installed app."""
        if item.startswith(("file://", "/")):
            return path_from_uri(item) or Path(item)
        own = self.system.config_home / "xfce4" / "panel" / f"launcher-{plugin}" / item
        if own.is_file():
            return own
        return app_lookup.app_file(item, self.system) or Path(item)

    def export_taskbar(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        panel = self.main_panel()
        if panel is not None:
            if side := self.side(panel):
                values["position"] = side
            hide = self.get(PANEL, f"/panels/panel-{panel}/autohide-behavior")
            if hide is not None and hide.isdigit():
                values["autohide"] = hide != "0"
        apps = app_lookup.installed_apps(self.system)
        values["pinned"] = app_lookup.pins_from_launchers([path for _, _, path in self.launchers()], apps)
        return values

    def apply_taskbar(self, ctx: Context, values: dict, section: dict) -> None:
        panel = self.main_panel()
        if panel is None:
            ctx.warn("Taskbar: Xfce's panel settings weren't found; is the panel running?")
            return
        if "position" in values and self.side(panel) != values["position"]:
            vertical = values["position"] in ("left", "right")
            mode = self.get(PANEL, f"/panels/panel-{panel}/mode")
            if vertical and mode not in ("1", "2"):
                self.set(PANEL, f"/panels/panel-{panel}/mode", "uint", 1)
            elif not vertical and mode in ("1", "2"):
                self.set(PANEL, f"/panels/panel-{panel}/mode", "uint", 0)
            self.set(PANEL, f"/panels/panel-{panel}/position", "string", f"p={SNAP_TO[values['position']]};x=0;y=0")
        if "autohide" in values:
            # 0 is never, 1 is "intelligently" (when a window is in the way), 2 is always.
            self.set(PANEL, f"/panels/panel-{panel}/autohide-behavior", "uint", 2 if values["autohide"] else 0)
        if values.get("pinned"):
            self.add_launchers(ctx, values["pinned"], panel)

    def add_launchers(self, ctx: Context, pins: list[dict], main: int) -> None:
        """Add a launcher for each pinned app the panel doesn't have one for yet.

        Launchers already there stay. New ones go after the last launcher, or after the app menu
        on the taskbar panel when there are none, and the panel restarts to show them.
        """
        apps = app_lookup.installed_apps(self.system)
        found, missing = app_lookup.match_pins(pins, apps)
        launchers = self.launchers()
        pinned = app_lookup.pins_from_launchers([path for _, _, path in launchers], apps)
        have = {path.name for _, _, path in launchers} | {pin.get("id") for pin in pinned}
        have_names = {pin.get("name") for pin in pinned}
        new = [a for a in found if a not in have and apps[a].name not in have_names]
        if new:
            if launchers:
                panel, after = launchers[-1][0], launchers[-1][1]
            else:
                panel, after = main, None
            plugins = self.plugin_ids(panel)
            if after is not None:
                index = plugins.index(after) + 1
            else:
                index = 1 if plugins and self.plugin_kind(plugins[0]) in MENUS else 0
            used = {int(m.group(1)) for prop in self.props(PANEL) if (m := re.match(r"/plugins/plugin-(\d+)$", prop))}
            next_id = max(used | set(plugins) | {0}) + 1
            added = []
            for app_id in new:
                self.set(PANEL, f"/plugins/plugin-{next_id}", "string", "launcher")
                # A file name alone is looked up in the app folders, like Xfce's own defaults.
                self.set_list(PANEL, f"/plugins/plugin-{next_id}/items", "string", [app_id])
                added.append(next_id)
                next_id += 1
            self.set_list(PANEL, f"/panels/panel-{panel}/plugin-ids", "int", plugins[:index] + added + plugins[index:])
            # "--restart" starts a new panel and waits when none is running, so check first.
            try:
                self.runner.run(["pgrep", "-x", "xfce4-panel"])
                self.runner.run(["xfce4-panel", "--restart"])
            except OSError:
                ctx.warn("Taskbar: pinned apps show on the panel the next time you sign in.")
        if missing:
            ctx.warn(f"Taskbar: these apps aren't installed here, so they weren't pinned: {', '.join(missing)}")

    # Mouse: speed and handedness are set on each pointer xfconf knows about.

    def pointer_devices(self) -> list[str]:
        return sorted({p.split("/")[1] for p in self.props("pointers") if p.count("/") >= 2})

    def export_mouse(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        for device in self.pointer_devices():
            speed = self.get("pointers", f"/{device}/Properties/libinput_Accel_Speed")
            right = self.get("pointers", f"/{device}/RightHanded")
            try:
                if speed is not None:
                    values["speed"] = float(speed)
            except ValueError:
                pass
            if right in ("true", "false"):
                values["left_handed"] = right == "false"
            if values:
                break
        double_click = self.get("xsettings", "/Net/DoubleClickTime")
        if double_click and double_click.isdigit():
            values["double_click_ms"] = int(double_click)
        if theme := self.get("xsettings", "/Gtk/CursorThemeName"):
            values["cursor_theme"] = theme
        size = self.get("xsettings", "/Gtk/CursorThemeSize")
        if size and size.isdigit():
            values["cursor_size"] = int(size)
        return values

    def apply_mouse(self, ctx: Context, values: dict, section: dict) -> None:
        devices = self.pointer_devices()
        if ("speed" in values or "left_handed" in values) and not devices:
            ctx.warn("Mouse: Xfce hasn't seen a mouse yet, so speed and buttons weren't set.")
        for device in devices:
            if "speed" in values:
                self.set("pointers", f"/{device}/Properties/libinput_Accel_Speed", "double", values["speed"])
            if "left_handed" in values:
                self.set("pointers", f"/{device}/RightHanded", "bool", not values["left_handed"])
        if "double_click_ms" in values:
            self.set("xsettings", "/Net/DoubleClickTime", "int", values["double_click_ms"])
        if "cursor_theme" in values and self.cursor_theme_exists(values["cursor_theme"]):
            self.set("xsettings", "/Gtk/CursorThemeName", "string", values["cursor_theme"])
        if "cursor_size" in values:
            self.set("xsettings", "/Gtk/CursorThemeSize", "int", values["cursor_size"])

    # Keyboard

    def export_keyboard(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        delay, rate = self.get("keyboards", "/Default/KeyRepeat/Delay"), self.get("keyboards", "/Default/KeyRepeat/Rate")
        if delay and delay.isdigit():
            values["repeat_delay_ms"] = int(delay)
        if rate and rate.isdigit() and int(rate) > 0:
            values["repeat_interval_ms"] = round(1000 / int(rate))
        layouts = self.get("keyboard-layout", "/Default/XkbLayout")
        if layouts and self.get("keyboard-layout", "/Default/XkbDisable") == "false":
            variants = (self.get("keyboard-layout", "/Default/XkbVariant") or "").split(",")
            values["layouts"] = [
                {"layout": layout, "variant": variants[i] if i < len(variants) else ""}
                for i, layout in enumerate(layouts.split(","))
                if layout
            ]
        return values

    def apply_keyboard(self, ctx: Context, values: dict, section: dict) -> None:
        if "repeat_delay_ms" in values:
            self.set("keyboards", "/Default/KeyRepeat/Delay", "int", values["repeat_delay_ms"])
        if "repeat_interval_ms" in values:
            self.set("keyboards", "/Default/KeyRepeat/Rate", "int", max(1, round(1000 / values["repeat_interval_ms"])))
        layouts, unknown = xkb_layouts(values)
        if layouts:
            # Xfce only uses its own layout list when told not to follow the system's.
            self.set("keyboard-layout", "/Default/XkbDisable", "bool", False)
            self.set("keyboard-layout", "/Default/XkbLayout", "string", ",".join(layout for layout, _ in layouts))
            self.set("keyboard-layout", "/Default/XkbVariant", "string", ",".join(variant for _, variant in layouts))
        warn_unknown_layouts(ctx, unknown)

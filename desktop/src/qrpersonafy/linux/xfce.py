"""Xfce, through xfconf-query. Xubuntu, Linux Mint Xfce and Manjaro Xfce use it."""

from __future__ import annotations

from pathlib import Path

from ..settings.base import Context
from .desktop import Desktop, GSettings, read_image, set_color_scheme, theme_is_dark, toggle_dark, warn_unknown_layouts, xkb_layouts

# xfce4-desktop's image-style and the portable fit names.
IMAGE_STYLES = {5: "fill", 4: "fit", 3: "stretch", 2: "tile", 1: "center", 6: "span"}


class Xfce(Desktop):
    id = "xfce"
    name = "Xfce"
    session_names = ("xfce",)
    missing = {
        "accent": "Accent color: Xfce has no accent color setting; it comes from the theme.",
        "taskbar": "Taskbar: restoring Xfce's panel isn't supported yet; the rest still applies.",
    }

    def __init__(self, system) -> None:
        super().__init__(system)
        self.gs = GSettings(self.runner)

    def get(self, channel: str, prop: str):
        try:
            return self.runner.run(["xfconf-query", "-c", channel, "-p", prop]).strip()
        except OSError:
            return None

    def set(self, channel: str, prop: str, kind: str, value) -> None:
        if kind == "bool":
            value = "true" if value else "false"
        self.runner.run(["xfconf-query", "-c", channel, "-p", prop, "-n", "-t", kind, "-s", str(value)])

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

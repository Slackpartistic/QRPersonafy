"""KDE Plasma 5 and 6: Kubuntu, Fedora KDE, KDE neon, openSUSE, Manjaro KDE, Steam Deck desktop mode.

Settings live in KDE's config files under ~/.config. They are read directly and written with
kwriteconfig, which tells running apps about the change. The wallpaper and panel are changed
through Plasma's own scripting, and the mouse through KWin, so they take effect right away.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..settings.base import Context
from . import apps as app_lookup
from . import gvariant
from .desktop import Desktop, is_dark_color, path_from_uri, read_image, warn_unknown_layouts, xkb_layouts

# Plasma's image FillMode and the portable fit names. Plasma has no "span".
FILL_MODES = {2: "fill", 1: "fit", 0: "stretch", 3: "tile", 6: "center"}


def read_kconfig(path: Path) -> dict[tuple[str, ...], dict[str, str]]:
    """Groups of a KDE config file. "[Containments][1][General]" becomes ("Containments", "1", "General")."""
    groups: dict[tuple[str, ...], dict[str, str]] = {}
    current: tuple[str, ...] = ()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return groups
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            current = tuple(re.findall(r"\[([^\]]*)\]", line))
            groups.setdefault(current, {})
        elif "=" in line:
            key, value = line.split("=", 1)
            # "Key[$e]" marks values with shell expansion; the plain value is still usable.
            groups.setdefault(current, {})[re.sub(r"\[\$\w+\]$", "", key.strip())] = value.strip()
    return groups


def _rgb(value: str | None) -> str | None:
    """KDE colors are "r,g,b"."""
    if not value:
        return None
    parts = value.split(",")
    try:
        red, green, blue = (int(p) for p in parts[:3])
    except ValueError:
        return None
    return f"#{red:02X}{green:02X}{blue:02X}"


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def package_image(folder: Path) -> Path | None:
    """The largest picture in a wallpaper package such as /usr/share/wallpapers/Next."""
    images = [p for p in (folder / "contents" / "images").glob("*") if p.is_file()]

    def pixels(path: Path) -> int:
        match = re.match(r"(\d+)x(\d+)", path.stem)
        return int(match.group(1)) * int(match.group(2)) if match else 0

    return max(images, key=pixels) if images else None


class Kde(Desktop):
    id = "kde"
    name = "KDE Plasma"
    session_names = ("kde", "plasma")

    def __init__(self, system) -> None:
        super().__init__(system)
        self.version = 6 if self.runner.has("kwriteconfig6") else 5

    def describe(self) -> str:
        return f"KDE Plasma {self.version}"

    def config(self, name: str) -> dict[tuple[str, ...], dict[str, str]]:
        return read_kconfig(self.system.config_home / name)

    def write(self, file: str, groups: tuple[str, ...], key: str, value) -> None:
        if isinstance(value, bool):
            value = "true" if value else "false"
        args = [f"kwriteconfig{self.version}", "--file", file]
        for group in groups:
            args += ["--group", group]
        self.runner.run(args + ["--key", key, "--notify", str(value)])

    # D-Bus, through whichever tool this system has.

    def call(self, service: str, path: str, method: str, *args) -> str:
        """Call a method with string, bool or float arguments and return its text reply."""
        if self.runner.has("gdbus"):
            reply = self.runner.run(
                ["gdbus", "call", "--session", "--dest", service, "--object-path", path, "--method", method]
                + [gvariant.format(a) if not isinstance(a, Variant) else f"<{gvariant.format(a.value)}>" for a in args]
            )
            value = gvariant.parse(reply)
            return str(value[0]) if isinstance(value, tuple) and value else ""
        typed = []
        for a in args:
            inner = a.value if isinstance(a, Variant) else a
            kind = "boolean" if isinstance(inner, bool) else "double" if isinstance(inner, float) else "string"
            text = ("true" if inner else "false") if isinstance(inner, bool) else str(inner)
            typed.append(f"variant:{kind}:{text}" if isinstance(a, Variant) else f"{kind}:{text}")
        reply = self.runner.run(["dbus-send", "--session", "--print-reply", f"--dest={service}", path, method] + typed)
        match = re.search(r'string "(.*)"\s*$', reply, re.S)
        if match:
            return match.group(1)
        match = re.search(r"variant\s+\w+\s+(\S+)\s*$", reply)
        return match.group(1) if match else ""

    def script(self, code: str) -> str:
        """Run a Plasma desktop script and return what it printed."""
        return self.call("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", code)

    # Wallpaper

    def export_wallpaper(self, ctx: Context, files: dict) -> dict:
        groups = self.config("plasma-org.kde.plasma.desktop-appletsrc")
        image, fill = None, None
        for group, values in groups.items():
            if len(group) == 5 and group[0] == "Containments" and group[2:] == ("Wallpaper", "org.kde.image", "General"):
                if "Image" in values:
                    image, fill = values["Image"], values.get("FillMode")
                    break
        path = path_from_uri(image) if image else None
        if path is None and image:
            path = Path(image)
        if path is not None and path.is_dir():
            path = package_image(path)
        if image is None:
            # Plasma's default wallpaper is a package it doesn't write to the config.
            path = package_image(Path("/usr/share/wallpapers/Next"))
        read_image(ctx, files, path, self.name)
        fit = FILL_MODES.get(int(fill)) if fill and fill.isdigit() else "fill"
        return {"fit": fit} if fit else {}

    def apply_wallpaper(self, ctx: Context, values: dict, section: dict) -> None:
        image = self.save_wallpaper(section)
        mode = next((m for m, f in FILL_MODES.items() if f == values.get("fit")), 2 if values.get("fit") == "span" else None)
        settings = {"image": image.as_uri() if image else None, "fill": mode}
        code = (
            f"var want = {json.dumps(settings)};"
            "desktops().forEach(function (d) {"
            " d.wallpaperPlugin = 'org.kde.image';"
            " d.currentConfigGroup = ['Wallpaper', 'org.kde.image', 'General'];"
            " if (want.image) d.writeConfig('Image', want.image);"
            " if (want.fill !== null) d.writeConfig('FillMode', want.fill);"
            "});"
        )
        try:
            self.script(code)
        except OSError:
            if image is None:
                raise
            self.runner.run(["plasma-apply-wallpaperimage", str(image)])

    # Light/dark mode, by switching between Breeze's light and dark color schemes

    def export_theme(self, ctx: Context, files: dict) -> dict:
        window = _rgb(self.config("kdeglobals").get(("Colors:Window",), {}).get("BackgroundNormal"))
        dark = is_dark_color(window) if window else False
        return {"apps_dark": dark, "system_dark": dark}

    def apply_theme(self, ctx: Context, values: dict, section: dict) -> None:
        dark = values.get("apps_dark", values.get("system_dark"))
        if dark is None:
            return
        window = _rgb(self.config("kdeglobals").get(("Colors:Window",), {}).get("BackgroundNormal"))
        if window and is_dark_color(window) == dark:
            return
        schemes = re.findall(r"^\s*\*\s+(\S+)", self.runner.run(["plasma-apply-colorscheme", "--list-schemes"]), re.M)
        wanted = ["BreezeDark"] if dark else ["BreezeLight", "Breeze"]
        scheme = next((s for s in wanted if s in schemes), None)
        if scheme is None:
            ctx.warn(f"Light/dark mode: no {'dark' if dark else 'light'} Breeze color scheme is installed.")
            return
        self.runner.run(["plasma-apply-colorscheme", scheme])

    # Accent color

    def export_accent(self, ctx: Context, files: dict) -> dict:
        globals_ = self.config("kdeglobals")
        color = _rgb(globals_.get(("General",), {}).get("AccentColor")) or _rgb(
            globals_.get(("Colors:Selection",), {}).get("BackgroundNormal")
        )
        return {"color": color} if color else {}

    def apply_accent(self, ctx: Context, values: dict, section: dict) -> None:
        if "color" in values:
            self.runner.run(["plasma-apply-colorscheme", "--accent-color", values["color"]])

    # Taskbar: the panel holding the task manager, and its pinned launchers

    def export_taskbar(self, ctx: Context, files: dict) -> dict:
        code = (
            "var out = [];"
            "panels().forEach(function (p) {"
            " var launchers = null;"
            " p.widgets().forEach(function (w) {"
            "  if (w.type.indexOf('taskmanager') !== -1) {"
            "   w.currentConfigGroup = ['General'];"
            "   launchers = String(w.readConfig('launchers', ''));"
            "  }"
            " });"
            " out.push({location: p.location, hiding: p.hiding, launchers: launchers});"
            "});"
            "print(JSON.stringify(out));"
        )
        panels = json.loads(self.script(code) or "[]")
        panel = next((p for p in panels if p.get("launchers") is not None), panels[0] if panels else None)
        if panel is None:
            return {}
        values: dict = {"position": panel.get("location"), "autohide": panel.get("hiding") not in ("none", None)}
        ids = []
        for launcher in (panel.get("launchers") or "").split(","):
            launcher = launcher.strip()
            if launcher.startswith("applications:"):
                ids.append(launcher[len("applications:"):])
            elif launcher.startswith("file://") and launcher.endswith(".desktop"):
                ids.append(Path(launcher).name)
        pins = app_lookup.pins_for(ids, app_lookup.installed_apps(self.system))
        # KDE's defaults name the kind of app rather than the app.
        launchers = panel.get("launchers") or ""
        for preferred, name in (("preferred://filemanager", "File Manager"), ("preferred://browser", "Web Browser")):
            if preferred in launchers:
                pins.insert(0 if "file" in preferred else len(pins), {"name": name})
        values["pinned"] = pins
        return values

    def apply_taskbar(self, ctx: Context, values: dict, section: dict) -> None:
        want: dict = {}
        if "position" in values:
            want["location"] = values["position"]
        if "autohide" in values:
            want["hiding"] = "autohide" if values["autohide"] else "none"
        if values.get("pinned"):
            found, missing = app_lookup.match_pins(values["pinned"], app_lookup.installed_apps(self.system))
            if found:
                want["launchers"] = [f"applications:{app_id}" for app_id in found]
            if missing:
                ctx.warn(f"Taskbar: these apps aren't installed here, so they weren't pinned: {', '.join(missing)}")
        if not want:
            return
        code = (
            f"var want = {json.dumps(want)};"
            "var done = false;"
            "panels().forEach(function (p) {"
            " if (done) return;"
            " p.widgets().forEach(function (w) {"
            "  if (w.type.indexOf('taskmanager') === -1) return;"
            "  done = true;"
            "  if (want.launchers) { w.currentConfigGroup = ['General']; w.writeConfig('launchers', want.launchers); }"
            "  if (want.location) p.location = want.location;"
            "  if (want.hiding) p.hiding = want.hiding;"
            " });"
            "});"
            "print(done ? 'ok' : 'no task manager');"
        )
        if self.script(code).strip() != "ok":
            ctx.warn("Taskbar: no panel with a task manager was found, so it wasn't changed.")

    # Mouse

    def pointer_groups(self) -> list[tuple[str, ...]]:
        """kcminputrc's per-device groups, which Plasma on Wayland uses."""
        return [g for g in self.config("kcminputrc") if len(g) == 4 and g[0] == "Libinput"]

    def export_mouse(self, ctx: Context, files: dict) -> dict:
        input_rc = self.config("kcminputrc")
        mouse = input_rc.get(("Mouse",), {})
        devices = [input_rc[g] for g in self.pointer_groups()]
        values: dict = {}
        speed = next((_float(d.get("PointerAcceleration")) for d in devices if "PointerAcceleration" in d), None)
        if speed is None:
            speed = _float(mouse.get("XLbInptPointerAcceleration"))
        if speed is not None:
            values["speed"] = speed
        profile = next((d["PointerAccelerationProfile"] for d in devices if "PointerAccelerationProfile" in d), None)
        if profile is not None:
            values["acceleration"] = profile != "1"
        elif "XLbInptAccelProfileFlat" in mouse:
            values["acceleration"] = mouse["XLbInptAccelProfileFlat"] != "true"
        left = next((d["LeftHanded"] for d in devices if "LeftHanded" in d), mouse.get("XLbInptLeftHanded"))
        if left is not None:
            values["left_handed"] = left == "true"
        double_click = self.config("kdeglobals").get(("KDE",), {}).get("DoubleClickInterval")
        if double_click and double_click.isdigit():
            values["double_click_ms"] = int(double_click)
        if theme := mouse.get("cursorTheme"):
            values["cursor_theme"] = theme
        if (size := mouse.get("cursorSize")) and size.isdigit():
            values["cursor_size"] = int(size)
        return values

    def apply_mouse(self, ctx: Context, values: dict, section: dict) -> None:
        keys = {}
        if "speed" in values:
            keys["PointerAcceleration"] = round(values["speed"], 3)
        if "acceleration" in values:
            keys["PointerAccelerationProfile"] = 2 if values["acceleration"] else 1
        if "left_handed" in values:
            keys["LeftHanded"] = values["left_handed"]
        # Plasma on X11 reads these.
        x11 = {"PointerAcceleration": "XLbInptPointerAcceleration", "LeftHanded": "XLbInptLeftHanded"}
        for key, value in keys.items():
            if key in x11:
                self.write("kcminputrc", ("Mouse",), x11[key], value)
            for group in self.pointer_groups():
                self.write("kcminputrc", group, key, value)
        if "acceleration" in values:
            self.write("kcminputrc", ("Mouse",), "XLbInptAccelProfileFlat", not values["acceleration"])
        if keys and self.system.wayland():
            self.apply_mouse_now(ctx, values)
        if "double_click_ms" in values:
            self.write("kdeglobals", ("KDE",), "DoubleClickInterval", values["double_click_ms"])
        if "cursor_size" in values:
            self.write("kcminputrc", ("Mouse",), "cursorSize", values["cursor_size"])
        if "cursor_theme" in values and self.cursor_theme_exists(values["cursor_theme"]):
            try:
                self.runner.run(["plasma-apply-cursortheme", values["cursor_theme"]])
            except OSError:
                self.write("kcminputrc", ("Mouse",), "cursorTheme", values["cursor_theme"])

    def apply_mouse_now(self, ctx: Context, values: dict) -> None:
        """Hand the new values to KWin, which otherwise reads them at the next sign-in."""
        manager = "/org/kde/KWin/InputDevice"
        get = "org.freedesktop.DBus.Properties.Get"
        try:
            names = self.call("org.kde.KWin", manager, get, "org.kde.KWin.InputDeviceManager", "devicesSysNames")
        except OSError:
            ctx.warn("Mouse: saved, and takes effect the next time you sign in.")
            return
        for name in re.findall(r"event\d+", names):
            path = f"{manager}/{name}"
            try:
                if self.call("org.kde.KWin", path, get, "org.kde.KWin.InputDevice", "pointer") not in ("True", "true"):
                    continue
                changes = []
                if "speed" in values:
                    changes.append(("pointerAcceleration", float(values["speed"])))
                if "acceleration" in values:
                    changes.append(("pointerAccelerationProfileFlat", not values["acceleration"]))
                    changes.append(("pointerAccelerationProfileAdaptive", values["acceleration"]))
                if "left_handed" in values:
                    changes.append(("leftHanded", values["left_handed"]))
                for prop, value in changes:
                    self.call("org.kde.KWin", path, "org.freedesktop.DBus.Properties.Set", "org.kde.KWin.InputDevice", prop, Variant(value))
            except OSError:
                continue

    # Keyboard

    def export_keyboard(self, ctx: Context, files: dict) -> dict:
        keyboard = self.config("kcminputrc").get(("Keyboard",), {})
        values: dict = {}
        if (delay := keyboard.get("RepeatDelay")) and delay.isdigit():
            values["repeat_delay_ms"] = int(delay)
        rate = _float(keyboard.get("RepeatRate"))
        if rate:
            values["repeat_interval_ms"] = round(1000 / rate)
        layout = self.config("kxkbrc").get(("Layout",), {})
        if layout.get("LayoutList") and layout.get("Use", "true") != "false":
            variants = layout.get("VariantList", "").split(",")
            values["layouts"] = [
                {"layout": name, "variant": variants[i] if i < len(variants) else ""}
                for i, name in enumerate(layout["LayoutList"].split(","))
                if name
            ]
        return values

    def apply_keyboard(self, ctx: Context, values: dict, section: dict) -> None:
        if "repeat_delay_ms" in values:
            self.write("kcminputrc", ("Keyboard",), "RepeatDelay", values["repeat_delay_ms"])
        if "repeat_interval_ms" in values:
            self.write("kcminputrc", ("Keyboard",), "RepeatRate", round(1000 / values["repeat_interval_ms"], 1))
        if "repeat_delay_ms" in values or "repeat_interval_ms" in values:
            self.write("kcminputrc", ("Keyboard",), "KeyRepeat", "repeat")
        layouts, unknown = xkb_layouts(values)
        if layouts:
            self.write("kxkbrc", ("Layout",), "Use", True)
            self.write("kxkbrc", ("Layout",), "LayoutList", ",".join(layout for layout, _ in layouts))
            self.write("kxkbrc", ("Layout",), "VariantList", ",".join(variant for _, variant in layouts))
        warn_unknown_layouts(ctx, unknown)
        # Ask KWin and the keyboard daemon to read the files again.
        for args in (
            ["dbus-send", "--session", "--type=signal", "/Layouts", "org.kde.keyboard.reloadConfig"],
            ["dbus-send", "--session", "--type=signal", "/KWin", "org.kde.KWin.reloadConfig"],
        ):
            try:
                self.runner.run(args)
            except OSError:
                pass


class Variant:
    """Marks a D-Bus argument that is sent as a variant, as property values are."""

    def __init__(self, value) -> None:
        self.value = value

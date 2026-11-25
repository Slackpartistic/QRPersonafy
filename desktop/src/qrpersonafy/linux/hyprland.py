"""Hyprland, the tiling Wayland compositor.

Hyprland has no settings app: people write its config file by hand. QRestoa keeps its own
settings in a file of its own next to it (qrestoa.lua for the Lua config of Hyprland 0.55 and
later, qrestoa.conf for the classic hyprland.conf), and adds one line to the end of the main
config that loads it, so restored settings win over earlier ones and the user's own file is
otherwise left alone. Changes are also applied straight away through hyprctl.

What Hyprland itself doesn't do comes from the usual tools: light/dark mode is GNOME's
color-scheme setting (which GTK, libadwaita and the desktop portal read), and the wallpaper is
whichever of hyprpaper or swww is in use. There's no standard taskbar (bars like Waybar are
set up by hand), so that's skipped.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..settings.base import Context
from .desktop import (
    GNOME_ACCENTS,
    GNOME_INTERFACE,
    Desktop,
    GSettings,
    nearest,
    read_image,
    set_color_scheme,
    theme_is_dark,
    toggle_dark,
    warn_unknown_layouts,
    xkb_layouts,
)

# Our settings, by Hyprland option name, with the values QRestoa last restored.
STATE_FILE = "qrestoa-settings.json"
MARKER = "QRestoa"

# hyprpaper's fit modes and the portable fit names. (hyprpaper calls stretching "fit".)
HYPRPAPER_FITS = {"cover": "fill", "contain": "fit", "fit": "stretch", "tile": "tile"}
HYPRPAPER_FROM_PORTABLE = {"fill": "cover", "fit": "contain", "stretch": "fit", "tile": "tile", "center": "contain", "span": "cover"}
# swww's --resize values.
SWWW_FROM_PORTABLE = {"fill": "crop", "fit": "fit", "stretch": "stretch", "tile": "crop", "center": "no", "span": "crop"}

# Option values only ever come from checked portable values, but they end up in a config file,
# so anything with characters a config line could misread is refused.
_SAFE = re.compile(r"^[A-Za-z0-9 ._+,#()\-]*$")


class Hyprland(Desktop):
    id = "hyprland"
    name = "Hyprland"
    session_names = ("hyprland",)
    missing = {
        "taskbar": (
            "Taskbar: Hyprland has no taskbar of its own (bars like Waybar are set up by hand), "
            "so pinned apps and the taskbar position were skipped."
        ),
    }

    def __init__(self, system) -> None:
        super().__init__(system)
        self.gs = GSettings(self.runner)

    # Where things are

    @property
    def folder(self) -> Path:
        return self.system.config_home / "hypr"

    def lua(self) -> bool:
        """Hyprland 0.55 and later read hyprland.lua when there is one, and 0.57 only that."""
        if (self.folder / "hyprland.lua").is_file():
            return True
        return not (self.folder / "hyprland.conf").is_file() and self.version() >= (0, 57)

    def version(self) -> tuple[int, int]:
        try:
            match = re.search(r"\b0\.(\d+)", self.runner.run(["hyprctl", "version", "-j"]))
        except OSError:
            match = None
        return (0, int(match.group(1))) if match else (0, 0)

    # Reading options from the running Hyprland

    def option(self, name: str):
        """An option's current value, from `hyprctl getoption -j`, or None."""
        try:
            data = json.loads(self.runner.run(["hyprctl", "getoption", name, "-j"]))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        for key in ("int", "float", "bool", "str", "custom", "gradient"):
            if key in data:
                return data[key]
        return None

    # Writing options: now, through hyprctl, and for next time, in our own config file

    def set_options(self, ctx: Context, values: dict, env: dict | None = None) -> None:
        values = {k: v for k, v in values.items() if _SAFE.match(_text(v))}
        env = {k: v for k, v in (env or {}).items() if _SAFE.match(_text(v))}
        if not values and not env:
            return
        state = self.load_state()
        state["options"].update(values)
        state["env"].update(env)
        try:
            self.save_state(state)
            self.write_config(state)
        except OSError as error:
            ctx.warn(f"Hyprland: couldn't save the settings for next time: {error}")
        self.apply_now(values)

    def load_state(self) -> dict:
        try:
            state = json.loads((self.folder / STATE_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        options = state.get("options") if isinstance(state.get("options"), dict) else {}
        env = state.get("env") if isinstance(state.get("env"), dict) else {}
        return {"options": options, "env": env}

    def save_state(self, state: dict) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / STATE_FILE).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    def write_config(self, state: dict) -> None:
        """Write qrestoa.lua or qrestoa.conf, and load it from the end of the main config."""
        if self.lua():
            (self.folder / "qrestoa.lua").write_text(lua_config(state), encoding="utf-8")
            self.include(self.folder / "hyprland.lua", 'require("qrestoa")', "qrestoa")
        else:
            (self.folder / "qrestoa.conf").write_text(conf_config(state), encoding="utf-8")
            self.include(self.folder / "hyprland.conf", "source = ~/.config/hypr/qrestoa.conf", "qrestoa.conf")

    def include(self, main: Path, line: str, name: str) -> None:
        if not main.is_file():
            # Hyprland writes its own example config on first start; adding ours to an empty
            # file would stop that, so leave it.
            return
        text = main.read_text(encoding="utf-8")
        if any(name in l and not l.lstrip().startswith(("#", "--")) for l in text.splitlines()):
            return
        comment = "--" if main.suffix == ".lua" else "#"
        addition = f"{comment} Added by {MARKER}: the settings it restored. Delete these two lines to stop using them.\n{line}\n"
        main.write_text(text + ("" if text.endswith("\n") else "\n") + "\n" + addition, encoding="utf-8")

    def apply_now(self, values: dict) -> None:
        if not values:
            return
        try:
            if self.lua():
                self.runner.run(["hyprctl", "eval", lua_table_call(values)])
            else:
                for name, value in values.items():
                    self.runner.run(["hyprctl", "keyword", name, _text(value)])
        except OSError:
            pass  # Hyprland isn't running here; the config file has them for next time

    # Wallpaper: swww, or hyprpaper (in its old or new config format)

    def running(self, program: str) -> bool:
        try:
            self.runner.run(["pgrep", "-x", program])
            return True
        except OSError:
            return False

    def swww(self) -> str | None:
        """swww, or awww as its newer versions are called, when its daemon is running."""
        for program in ("swww", "awww"):
            if self.running(f"{program}-daemon"):
                return program
        return None

    def monitors(self) -> list[str]:
        try:
            data = json.loads(self.runner.run(["hyprctl", "monitors", "-j"]))
        except (OSError, ValueError):
            return []
        names = [m.get("name") for m in data if isinstance(m, dict)] if isinstance(data, list) else []
        return [n for n in names if isinstance(n, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,64}", n)]

    def hyprpaper_conf(self) -> Path:
        return self.folder / "hyprpaper.conf"

    def export_wallpaper(self, ctx: Context, files: dict) -> dict:
        path, fit = None, None
        if program := self.swww():
            path = self.swww_image(program)
        if path is None:
            path, fit = read_hyprpaper(self.hyprpaper_conf(), self.system.home)
        read_image(ctx, files, path, self.name)
        return {"fit": fit} if fit else {}

    def swww_image(self, program: str) -> Path | None:
        try:
            text = self.runner.run([program, "query"])
        except OSError:
            return None
        match = re.search(r"image: (.+)$", text, re.MULTILINE)
        return Path(match.group(1).strip()) if match else None

    def apply_wallpaper(self, ctx: Context, values: dict, section: dict) -> None:
        image = self.save_wallpaper(section)
        if image is None:
            return
        fit = values.get("fit", "fill")
        if program := self.swww():
            # swww shows the last image again by itself after a restart.
            try:
                self.runner.run([program, "img", str(image), "--resize", SWWW_FROM_PORTABLE.get(fit, "crop")])
            except OSError as error:
                ctx.warn(f"Wallpaper: {program} couldn't show it: {error}")
            return
        conf = self.hyprpaper_conf()
        running = self.running("hyprpaper")
        if not conf.is_file() and not running:
            ctx.warn(
                f"Wallpaper: saved as {image}, but neither hyprpaper nor swww is running to show it. "
                "Point your wallpaper tool at that file."
            )
            return
        mode = HYPRPAPER_FROM_PORTABLE.get(fit, "cover")
        try:
            write_hyprpaper(conf, image, mode, self.monitors())
        except OSError as error:
            ctx.warn(f"Wallpaper: couldn't update hyprpaper.conf: {error}")
        if running:
            # hyprpaper 0.8 and later, then the "reload" request of earlier versions.
            prefix = "contain:" if mode == "contain" else ""
            for request in (["wallpaper", f",{image},{mode}"], ["reload", f",{prefix}{image}"]):
                try:
                    answer = self.runner.run(["hyprctl", "hyprpaper", *request])
                except OSError:
                    continue
                if "error" not in answer.lower() and "invalid" not in answer.lower():
                    break

    # Light/dark mode, through the settings GTK and the desktop portal read

    def export_theme(self, ctx: Context, files: dict) -> dict:
        scheme = self.gs.get(GNOME_INTERFACE, "color-scheme")
        if isinstance(scheme, str) and scheme != "default":
            dark = scheme == "prefer-dark"
        else:
            dark = theme_is_dark(self.gs.get(GNOME_INTERFACE, "gtk-theme"))
        return {"apps_dark": dark, "system_dark": dark}

    def apply_theme(self, ctx: Context, values: dict, section: dict) -> None:
        dark = values.get("apps_dark", values.get("system_dark"))
        if dark is None:
            return
        if not self.gs.has(GNOME_INTERFACE, "color-scheme"):
            ctx.warn("Light/dark mode: needs gsettings and GTK's settings, which weren't found here.")
            return
        set_color_scheme(self.gs, dark)
        theme = self.gs.get(GNOME_INTERFACE, "gtk-theme")
        if isinstance(theme, str) and (sibling := toggle_dark(self, theme, dark)) is not None:
            self.gs.set(GNOME_INTERFACE, "gtk-theme", sibling)

    # Accent color: the border of the focused window, and GNOME's accent for GTK apps

    def export_accent(self, ctx: Context, files: dict) -> dict:
        color = border_color(self.option("general:col.active_border"))
        return {"color": color} if color else {}

    def apply_accent(self, ctx: Context, values: dict, section: dict) -> None:
        if "color" not in values:
            return
        self.set_options(ctx, {"general:col.active_border": f"rgb({values['color'][1:].lower()})"})
        self.gs.set(GNOME_INTERFACE, "accent-color", nearest(values["color"], GNOME_ACCENTS))

    # Mouse

    def export_mouse(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        speed = self.option("input:sensitivity")
        if isinstance(speed, (int, float)) and not isinstance(speed, bool):
            values["speed"] = round(max(-1.0, min(1.0, float(speed))), 2)
        profile = self.option("input:accel_profile")
        if isinstance(profile, str):
            values["acceleration"] = profile.strip() != "flat"
        left = self.option("input:left_handed")
        if isinstance(left, (bool, int)):
            values["left_handed"] = bool(left)
        theme = self.gs.get(GNOME_INTERFACE, "cursor-theme") or self.system.env.get("XCURSOR_THEME")
        if isinstance(theme, str) and theme:
            values["cursor_theme"] = theme
        size = self.gs.get(GNOME_INTERFACE, "cursor-size") or self.system.env.get("XCURSOR_SIZE")
        if isinstance(size, int) or (isinstance(size, str) and size.isdigit()):
            values["cursor_size"] = int(size)
        return values

    def apply_mouse(self, ctx: Context, values: dict, section: dict) -> None:
        options: dict = {}
        if "speed" in values:
            options["input:sensitivity"] = round(float(values["speed"]), 2)
        if "acceleration" in values:
            options["input:accel_profile"] = "adaptive" if values["acceleration"] else "flat"
        if "left_handed" in values:
            options["input:left_handed"] = bool(values["left_handed"])
        env: dict = {}
        theme = values.get("cursor_theme")
        if theme and not self.cursor_theme_exists(theme):
            theme = None
        size = values.get("cursor_size")
        if theme:
            env["XCURSOR_THEME"] = theme
            self.gs.set(GNOME_INTERFACE, "cursor-theme", theme)
        if size:
            env["XCURSOR_SIZE"] = size
            self.gs.set(GNOME_INTERFACE, "cursor-size", size)
        self.set_options(ctx, options, env)
        if theme or size:
            current = theme or self.gs.get(GNOME_INTERFACE, "cursor-theme") or self.system.env.get("XCURSOR_THEME") or "default"
            try:
                self.runner.run(["hyprctl", "setcursor", str(current), str(size or 24)])
            except OSError:
                pass

    # Keyboard

    def export_keyboard(self, ctx: Context, files: dict) -> dict:
        values: dict = {}
        delay, rate = self.option("input:repeat_delay"), self.option("input:repeat_rate")
        if isinstance(delay, int) and not isinstance(delay, bool):
            values["repeat_delay_ms"] = delay
        if isinstance(rate, int) and not isinstance(rate, bool) and rate > 0:
            values["repeat_interval_ms"] = round(1000 / rate)
        layouts = self.option("input:kb_layout")
        if isinstance(layouts, str) and layouts.strip():
            variants = str(self.option("input:kb_variant") or "").split(",")
            values["layouts"] = [
                {"layout": layout.strip(), "variant": variants[i].strip() if i < len(variants) else ""}
                for i, layout in enumerate(layouts.split(","))
                if layout.strip()
            ]
        return values

    def apply_keyboard(self, ctx: Context, values: dict, section: dict) -> None:
        options: dict = {}
        if "repeat_delay_ms" in values:
            options["input:repeat_delay"] = int(values["repeat_delay_ms"])
        if "repeat_interval_ms" in values:
            options["input:repeat_rate"] = max(1, round(1000 / values["repeat_interval_ms"]))
        layouts, unknown = xkb_layouts(values)
        if layouts:
            options["input:kb_layout"] = ",".join(layout for layout, _ in layouts)
            options["input:kb_variant"] = ",".join(variant for _, variant in layouts)
        self.set_options(ctx, options)
        warn_unknown_layouts(ctx, unknown)


# Config text


def _text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def conf_config(state: dict) -> str:
    """qrestoa.conf in Hyprland's classic config language."""
    lines = [f"# Written by {MARKER} and loaded from the end of hyprland.conf. Edit or delete as you like.", ""]
    sections: dict[str, list[tuple[str, object]]] = {}
    for name, value in sorted(state["options"].items()):
        section, _, key = name.partition(":")
        sections.setdefault(section, []).append((key, value))
    for section, items in sections.items():
        lines.append(f"{section} {{")
        lines += [f"    {key} = {_text(value)}" for key, value in items]
        lines += ["}", ""]
    lines += [f"env = {name},{_text(value)}" for name, value in sorted(state["env"].items())]
    return "\n".join(lines).rstrip() + "\n"


def _lua_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return json.dumps(str(value))


def _lua_table(values: dict) -> str:
    """{"input:sensitivity": 0.5, "general:col.active_border": "rgb(...)"} as nested Lua tables."""
    tree: dict = {}
    for name, value in sorted(values.items()):
        node = tree
        parts = name.replace(":", ".").split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def render(node: dict, indent: str) -> str:
        inner = indent + "    "
        items = [f"{inner}{key} = {render(value, inner) if isinstance(value, dict) else _lua_value(value)}," for key, value in node.items()]
        return "{\n" + "\n".join(items) + f"\n{indent}}}"

    return render(tree, "")


def lua_table_call(values: dict) -> str:
    return f"hl.config({_lua_table(values)})"


def lua_config(state: dict) -> str:
    """qrestoa.lua for Hyprland's Lua config."""
    lines = [f"-- Written by {MARKER} and loaded from the end of hyprland.lua. Edit or delete as you like.", ""]
    if state["options"]:
        lines.append(lua_table_call(state["options"]))
    lines += [f"hl.env({json.dumps(name)}, {json.dumps(_text(value))})" for name, value in sorted(state["env"].items())]
    return "\n".join(lines).rstrip() + "\n"


def border_color(value) -> str | None:
    """The first color of a border setting: "rgba(33ccffee) rgba(00ff99ee) 45deg", "rgb(3584e4)"
    or "ff33ccff ff00ff99 45deg" (AARRGGBB, how hyprctl prints gradients)."""
    if not isinstance(value, str):
        return None
    if match := re.search(r"rgba?\(([0-9A-Fa-f]{6})", value):
        return "#" + match.group(1).upper()
    if match := re.search(r"(?:0x)?\b([0-9A-Fa-f]{8})\b", value):
        return "#" + match.group(1)[2:].upper()
    return None


# hyprpaper.conf: "preload = path" and "wallpaper = monitor,path" before 0.8, then blocks:
#   wallpaper {
#       monitor =
#       path = /path/to/image.png
#       fit_mode = cover
#   }


def read_hyprpaper(conf: Path, home: Path) -> tuple[Path | None, str | None]:
    try:
        text = conf.read_text(encoding="utf-8")
    except OSError:
        return None, None
    if block := re.search(r"^\s*wallpaper\s*\{([^}]*)\}", text, re.MULTILINE):
        path = re.search(r"^\s*path\s*=\s*(.+?)\s*$", block.group(1), re.MULTILINE)
        fit = re.search(r"^\s*fit_mode\s*=\s*(\w+)", block.group(1), re.MULTILINE)
        return (_expand(path.group(1), home) if path else None), HYPRPAPER_FITS.get(fit.group(1) if fit else "cover")
    if line := re.search(r"^\s*wallpaper\s*=\s*[^,\n]*,\s*(.+?)\s*$", text, re.MULTILINE):
        value = line.group(1)
        fit = "fit" if value.startswith("contain:") else "tile" if value.startswith("tile:") else "fill"
        return _expand(re.sub(r"^(contain|tile):", "", value), home), fit
    return None, None


def _expand(path: str, home: Path) -> Path:
    return home / path[2:] if path.startswith("~/") else Path(path)


def write_hyprpaper(conf: Path, image: Path, mode: str, monitors: list[str] | None = None) -> None:
    """Point hyprpaper at the image on every monitor, in the format the file already uses.

    In the new format one block names each monitor; "*" for all monitors works from hyprpaper
    0.8.2, and an empty name, which 0.8.0 and 0.8.1 used, gets lost by later versions.
    """
    text = conf.read_text(encoding="utf-8") if conf.is_file() else ""
    old_format = re.search(r"^\s*(preload|wallpaper)\s*=", text, re.MULTILINE) is not None
    if old_format:
        text = re.sub(rf"^# Set by {MARKER}\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*(preload|wallpaper|unload)\s*=.*\n?", "", text, flags=re.MULTILINE)
        prefix = "contain:" if mode == "contain" else "tile:" if mode == "tile" else ""
        addition = f"# Set by {MARKER}\npreload = {image}\nwallpaper = ,{prefix}{image}\n"
    else:
        text = re.sub(rf"^# Set by {MARKER}\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*wallpaper\s*\{[^}]*\}\n?", "", text, flags=re.MULTILINE)
        blocks = [f"wallpaper {{\n    monitor = {monitor}\n    path = {image}\n    fit_mode = {mode}\n}}\n" for monitor in monitors or ["*"]]
        addition = f"# Set by {MARKER}\n" + "".join(blocks)
    text = text.rstrip("\n")
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text((text + "\n\n" if text else "") + addition, encoding="utf-8")

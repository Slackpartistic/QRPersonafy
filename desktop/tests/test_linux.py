import json
import os
import shutil
import subprocess

import pytest

from qrpersonafy import portable
from qrpersonafy.gui.api import Api
from qrpersonafy.linux import UnknownDesktop, detect, linux_context
from qrpersonafy.linux import gvariant
from qrpersonafy.linux.apps import find_app, installed_apps
from qrpersonafy.linux.cinnamon import Cinnamon, Mate
from qrpersonafy.linux.gnome import Gnome
from qrpersonafy.linux.kde import Kde, read_kconfig
from qrpersonafy.linux.runner import FakeRunner
from qrpersonafy.linux.system import LinuxSystem
from qrpersonafy.linux.xfce import Xfce
from qrpersonafy.profile import apply_profile, export_profile
from qrpersonafy.settings import BY_NAME, Context
from qrpersonafy.summary import summarize

from test_roundtrip import PNG, configured_pc

UBUNTU_24_04 = {
    ("org.gnome.desktop.interface", "color-scheme"): "'default'",
    ("org.gnome.desktop.interface", "gtk-theme"): "'Yaru'",
    ("org.gnome.desktop.interface", "icon-theme"): "'Yaru'",
    ("org.gnome.desktop.interface", "cursor-theme"): "'Yaru'",
    ("org.gnome.desktop.interface", "cursor-size"): "24",
    ("org.gnome.desktop.background", "picture-uri"): "'file:///usr/share/backgrounds/warty-final-ubuntu.png'",
    ("org.gnome.desktop.background", "picture-uri-dark"): "'file:///usr/share/backgrounds/warty-final-ubuntu.png'",
    ("org.gnome.desktop.background", "picture-options"): "'zoom'",
    ("org.gnome.shell", "favorite-apps"): "['firefox_firefox.desktop', 'org.gnome.Nautilus.desktop']",
    ("org.gnome.shell.extensions.dash-to-dock", "dock-position"): "'LEFT'",
    ("org.gnome.shell.extensions.dash-to-dock", "dock-fixed"): "true",
    ("org.gnome.shell.extensions.dash-to-dock", "autohide"): "true",
    ("org.gnome.desktop.peripherals.mouse", "speed"): "0.0",
    ("org.gnome.desktop.peripherals.mouse", "accel-profile"): "'default'",
    ("org.gnome.desktop.peripherals.mouse", "left-handed"): "false",
    ("org.gnome.desktop.peripherals.mouse", "double-click"): "400",
    ("org.gnome.desktop.peripherals.keyboard", "delay"): "uint32 500",
    ("org.gnome.desktop.peripherals.keyboard", "repeat-interval"): "uint32 30",
    ("org.gnome.desktop.input-sources", "sources"): "[('xkb', 'us'), ('ibus', 'mozc-jp')]",
}


def add_app(system, app_id, name, categories=""):
    folder = system.data_home / "applications"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / app_id).write_text(f"[Desktop Entry]\nType=Application\nName={name}\nCategories={categories}\nExec=x\n")


def linux_pc(tmp_path, desktop="ubuntu:GNOME", gsettings=None, programs=()):
    runner = FakeRunner(set(programs), gsettings=dict(UBUNTU_24_04 if gsettings is None else gsettings))
    home = tmp_path / "home"
    system = LinuxSystem(runner, home, {"HOME": str(home), "XDG_CURRENT_DESKTOP": desktop, "XDG_DATA_DIRS": str(tmp_path / "none")})
    add_app(system, "firefox_firefox.desktop", "Firefox Web Browser", "Network;WebBrowser;")
    add_app(system, "org.gnome.Nautilus.desktop", "Files", "GNOME;Utility;FileManager;")
    add_app(system, "org.gnome.Terminal.desktop", "Terminal", "GNOME;System;TerminalEmulator;")
    return linux_context(system), runner


def windows_profile(make_ctx):
    ctx = configured_pc(make_ctx)
    ctx.system.powershell_output = json.dumps(
        [{"tag": "en-US", "tips": ["0409:00000409"]}, {"tag": "de-DE", "tips": ["0407:00000407"]}]
    )
    return export_profile(ctx, set(BY_NAME))


# GVariant text


def test_gvariant_reads_what_gsettings_prints():
    assert gvariant.parse("uint32 500") == 500
    assert gvariant.parse("@as []") == []
    assert gvariant.parse("[('xkb', 'us'), ('xkb', 'de+nodeadkeys')]") == [("xkb", "us"), ("xkb", "de+nodeadkeys")]
    assert gvariant.parse("'it\\'s'") == "it's"
    assert gvariant.parse("(<['event0', 'event3']>,)") == (["event0", "event3"],)
    assert gvariant.parse("-0.25") == -0.25 and gvariant.parse("true") is True


def test_gvariant_writes_safely_quoted_text():
    assert gvariant.format([("xkb", "us")]) == "[('xkb', 'us')]"
    assert gvariant.format("a'b") == "'a\\'b'"
    assert gvariant.parse(gvariant.format(["x\\y", "it's"])) == ["x\\y", "it's"]


# Detecting the desktop


@pytest.mark.parametrize(
    "session, expected",
    [("ubuntu:GNOME", Gnome), ("KDE", Kde), ("X-Cinnamon", Cinnamon), ("MATE", Mate), ("XFCE", Xfce), ("Budgie:GNOME", Gnome)],
)
def test_detects_the_desktop(tmp_path, session, expected):
    assert type(detect(LinuxSystem(FakeRunner(), tmp_path, {"XDG_CURRENT_DESKTOP": session}))) is expected


def test_unknown_desktop_changes_nothing_and_says_so_once(tmp_path, make_ctx):
    ctx, runner = linux_pc(tmp_path, desktop="sway")
    assert isinstance(ctx.desktop, UnknownDesktop)
    assert apply_profile(ctx, windows_profile(make_ctx), set(BY_NAME)) == []
    assert len(ctx.warnings) == 1 and "sway isn't supported yet" in ctx.warnings[0]
    assert not any(call[1] == "set" for call in runner.calls if call[0] == "gsettings")


# Windows and portable values


def test_windows_values_become_portable(make_ctx):
    settings = windows_profile(make_ctx)["settings"]
    assert portable.of("theme", settings["theme"]) == {"apps_dark": True, "system_dark": True}
    # The test PC's 0xFF0078D4 is stored as 0xAABBGGRR, so it's an orange.
    assert portable.of("accent", settings["accent"]) == {"color": "#D47800"}
    assert portable.of("wallpaper", settings["wallpaper"]) == {"fit": "fill"}
    assert portable.of("mouse", settings["mouse"])["speed"] == 0.4
    assert portable.of("keyboard", settings["keyboard"]) == {
        "repeat_delay_ms": 250,
        "layouts": [{"layout": "us", "variant": ""}, {"layout": "de", "variant": ""}],
    }
    assert portable.of("taskbar", settings["taskbar"])["pinned"] == [{"name": "Terminal"}]


def test_portable_values_round_trip_through_windows():
    original = {
        "theme": {"apps_dark": True, "system_dark": False},
        "accent": {"color": "#0078D4"},
        "wallpaper": {"fit": "tile"},
        "mouse": {"speed": -0.3, "acceleration": False, "left_handed": True, "double_click_ms": 500},
        "keyboard": {"repeat_delay_ms": 500, "repeat_interval_ms": 33, "layouts": [{"layout": "fr", "variant": ""}]},
    }
    for name, values in original.items():
        windows, notes = portable.to_windows(name, {"portable": values})
        assert notes == []
        assert portable.from_windows(name, windows) == values, name


def test_hostile_portable_values_are_dropped():
    assert portable.clean("accent", {"color": "red; rm -rf"}) == {}
    assert portable.clean("mouse", {"speed": 9, "cursor_theme": "../../etc", "left_handed": "yes"}) == {}
    assert portable.clean("keyboard", {"layouts": [{"layout": "us;evil"}, {"layout": "de", "variant": "$(x)"}, "x"]}) == {}
    assert portable.clean("taskbar", {"pinned": [{"id": "../x.desktop"}, {"name": "ok", "id": "a/b.desktop"}]}) == {"pinned": [{"name": "ok"}]}
    assert portable.of("theme", {"portable": "nope"}) == {}


# GNOME


def test_gnome_export(tmp_path):
    ctx, _ = linux_pc(tmp_path)
    profile = export_profile(ctx, set(BY_NAME))
    assert profile["system"].endswith("GNOME")
    assert "windows_build" not in profile and "start" not in profile["settings"]
    settings = {name: section["portable"] for name, section in profile["settings"].items()}
    assert settings["theme"] == {"apps_dark": False, "system_dark": False}
    assert settings["accent"] == {"color": "#E95420"}
    assert settings["taskbar"] == {
        "pinned": [{"id": "firefox_firefox.desktop", "name": "Firefox Web Browser"}, {"id": "org.gnome.Nautilus.desktop", "name": "Files"}],
        "position": "left",
        "autohide": False,
    }
    assert settings["keyboard"] == {"repeat_delay_ms": 500, "repeat_interval_ms": 30, "layouts": [{"layout": "us", "variant": ""}]}
    assert settings["mouse"]["cursor_theme"] == "Yaru"


def test_windows_profile_applies_on_ubuntu(tmp_path, make_ctx):
    ctx, runner = linux_pc(tmp_path)
    profile = windows_profile(make_ctx)
    applied = apply_profile(ctx, profile, set(BY_NAME))
    assert applied == ["wallpaper", "theme", "accent", "taskbar", "mouse", "keyboard"]
    gs = runner.gsettings
    assert gs[("org.gnome.desktop.interface", "color-scheme")] == "'prefer-dark'"
    # The orange accent on Ubuntu 24.04 is Yaru's own orange, now dark.
    assert gs[("org.gnome.desktop.interface", "gtk-theme")] == "'Yaru-dark'"
    assert gs[("org.gnome.desktop.interface", "icon-theme")] == "'Yaru'"
    assert gs[("org.gnome.desktop.background", "picture-options")] == "'zoom'"
    image = gs[("org.gnome.desktop.background", "picture-uri")].strip("'")
    assert image.startswith("file://") and image.endswith(".png")
    assert (ctx.system.data_home / "backgrounds" / "qrpersonafy").is_dir()
    assert gs[("org.gnome.shell", "favorite-apps")] == "['org.gnome.Terminal.desktop']"
    # The test PC saved no taskbar position, so the dock stays where it was.
    assert gs[("org.gnome.shell.extensions.dash-to-dock", "dock-position")] == "'LEFT'"
    assert gs[("org.gnome.desktop.peripherals.mouse", "speed")] == "0.4"
    assert gs[("org.gnome.desktop.peripherals.keyboard", "delay")] == "250"
    assert gs[("org.gnome.desktop.input-sources", "sources")] == "[('xkb', 'us'), ('xkb', 'de'), ('ibus', 'mozc-jp')]"
    assert any("Start menu" in w for w in ctx.warnings)


def test_windows_blue_picks_yarus_blue(tmp_path):
    ctx, runner = linux_pc(tmp_path)
    ctx.desktop.apply(ctx, "accent", {"portable": {"color": "#0078D4"}})
    assert runner.gsettings[("org.gnome.desktop.interface", "gtk-theme")] == "'Yaru-blue'"
    assert runner.gsettings[("org.gnome.desktop.interface", "icon-theme")] == "'Yaru-blue'"


def test_gnome_47_uses_the_accent_color_setting(tmp_path):
    gsettings = {**UBUNTU_24_04, ("org.gnome.desktop.interface", "accent-color"): "'blue'", ("org.gnome.desktop.interface", "gtk-theme"): "'Adwaita'"}
    ctx, runner = linux_pc(tmp_path, gsettings=gsettings)
    ctx.desktop.apply(ctx, "accent", {"portable": {"color": "#E81123"}})
    assert runner.gsettings[("org.gnome.desktop.interface", "accent-color")] == "'red'"
    assert ctx.warnings == []


def test_pins_match_windows_names(tmp_path):
    ctx, _ = linux_pc(tmp_path)
    apps = installed_apps(ctx.system)
    assert find_app({"name": "Firefox"}, apps) == "firefox_firefox.desktop"
    assert find_app({"name": "File Explorer"}, apps) == "org.gnome.Nautilus.desktop"
    assert find_app({"name": "Windows Terminal"}, apps) == "org.gnome.Terminal.desktop"
    assert find_app({"name": "Microsoft Edge"}, apps) is None
    assert find_app({"id": "org.gnome.Terminal.desktop", "name": "Anything"}, apps) == "org.gnome.Terminal.desktop"


# KDE


KDEGLOBALS = """
[Colors:Window]
BackgroundNormal=32,35,38

[General]
AccentColor=61,174,233

[KDE]
DoubleClickInterval=400
"""


def kde_pc(tmp_path):
    ctx, runner = linux_pc(tmp_path, desktop="KDE", gsettings={}, programs={"kwriteconfig6", "dbus-send", "plasma-apply-colorscheme"})
    config = ctx.system.config_home
    config.mkdir(parents=True, exist_ok=True)
    (config / "kdeglobals").write_text(KDEGLOBALS)
    (config / "kcminputrc").write_text("[Keyboard]\nRepeatDelay=600\nRepeatRate=25\n\n[Libinput][1133][49271][Logitech Mouse]\nPointerAcceleration=0.2\n")
    (config / "kxkbrc").write_text("[Layout]\nLayoutList=us,de\nVariantList=,nodeadkeys\nUse=true\n")
    (config / "plasma-org.kde.plasma.desktop-appletsrc").write_text(
        "[Containments][1][Wallpaper][org.kde.image][General]\nImage=file:///missing.png\nFillMode=1\n"
    )
    runner.outputs[("plasma-apply-colorscheme", "--list-schemes")] = " * BreezeClassic\n * BreezeDark (current color scheme)\n * BreezeLight\n"
    return ctx, runner


def test_kde_config_files_are_read(tmp_path):
    path = tmp_path / "rc"
    path.write_text("[A][b c]\nKey[$e]=$HOME/x\n# comment\n[Top]\nx=1=2\n")
    assert read_kconfig(path) == {("A", "b c"): {"Key": "$HOME/x"}, ("Top",): {"x": "1=2"}}


def test_kde_export(tmp_path):
    ctx, runner = kde_pc(tmp_path)
    runner.outputs[("dbus-send",)] = 'method return time=1\n   string "[{"location":"bottom","hiding":"none","launchers":"applications:firefox_firefox.desktop,preferred://filemanager"}]"\n'
    settings = {n: s["portable"] for n, s in export_profile(ctx, set(BY_NAME))["settings"].items()}
    assert settings["theme"] == {"apps_dark": True, "system_dark": True}
    assert settings["accent"] == {"color": "#3DAEE9"}
    assert settings["wallpaper"] == {"fit": "fit"}
    assert settings["mouse"] == {"speed": 0.2, "double_click_ms": 400}
    assert settings["keyboard"] == {
        "repeat_delay_ms": 600,
        "repeat_interval_ms": 40,
        "layouts": [{"layout": "us", "variant": ""}, {"layout": "de", "variant": "nodeadkeys"}],
    }
    assert settings["taskbar"]["pinned"] == [{"name": "File Manager"}, {"id": "firefox_firefox.desktop", "name": "Firefox Web Browser"}]
    assert settings["taskbar"]["position"] == "bottom" and settings["taskbar"]["autohide"] is False


def test_windows_profile_applies_on_kde(tmp_path, make_ctx):
    ctx, runner = kde_pc(tmp_path)
    runner.outputs[("dbus-send",)] = 'method return\n   string "ok"\n'
    apply_profile(ctx, windows_profile(make_ctx), set(BY_NAME))
    calls = [" ".join(c) for c in runner.calls]
    # Already dark, so the color scheme is left alone; the accent is set on top of it.
    assert not any(c == "plasma-apply-colorscheme BreezeDark" for c in calls)
    assert "plasma-apply-colorscheme --accent-color #D47800" in calls
    script = next(c for c in runner.calls if "org.kde.PlasmaShell.evaluateScript" in c)
    assert "org.kde.image" in script[-1] and '"fill": 2' in script[-1]
    assert "kwriteconfig6 --file kxkbrc --group Layout --key LayoutList --notify us,de" in calls
    assert "kwriteconfig6 --file kcminputrc --group Libinput --group 1133 --group 49271 --group Logitech Mouse --key PointerAcceleration --notify 0.4" in calls
    assert "kwriteconfig6 --file kcminputrc --group Keyboard --key RepeatDelay --notify 250" in calls
    pins = next(c for c in runner.calls if "evaluateScript" in " ".join(c) and "launchers" in c[-1] and "want" in c[-1])
    assert "applications:org.gnome.Terminal.desktop" in pins[-1]


def test_kde_switches_to_light(tmp_path):
    ctx, runner = kde_pc(tmp_path)
    ctx.desktop.apply(ctx, "theme", {"portable": {"apps_dark": False}})
    assert ["plasma-apply-colorscheme", "BreezeLight"] in runner.calls


# Cinnamon, MATE and Xfce


def test_cinnamon_mint_theme_colors_and_panel(tmp_path):
    gsettings = {
        ("org.cinnamon.desktop.interface", "gtk-theme"): "'Mint-Y-Aqua'",
        ("org.cinnamon.desktop.interface", "icon-theme"): "'Mint-Y-Aqua'",
        ("org.cinnamon.theme", "name"): "'Mint-Y-Aqua'",
        ("org.x.apps.portal", "color-scheme"): "'default'",
        ("org.cinnamon", "panels-enabled"): "['1:0:bottom']",
        ("org.cinnamon", "panels-autohide"): "['1:false']",
    }
    ctx, runner = linux_pc(tmp_path, desktop="X-Cinnamon", gsettings=gsettings)
    spices = ctx.system.config_home / "cinnamon" / "spices" / "grouped-window-list@cinnamon.org"
    spices.mkdir(parents=True)
    (spices / "2.json").write_text(json.dumps({"pinned-apps": {"type": "generic", "value": ["nemo.desktop"]}}))
    assert ctx.desktop.export(ctx, "accent") == {"portable": {"color": "#1F9EDE"}}
    ctx.desktop.apply(ctx, "theme", {"portable": {"apps_dark": True}})
    ctx.desktop.apply(ctx, "accent", {"portable": {"color": "#E81123"}})
    ctx.desktop.apply(ctx, "taskbar", {"portable": {"position": "top", "autohide": True, "pinned": [{"name": "Firefox"}]}})
    gs = runner.gsettings
    assert gs[("org.cinnamon.desktop.interface", "gtk-theme")] == "'Mint-Y-Dark-Red'"
    assert gs[("org.cinnamon.theme", "name")] == "'Mint-Y-Dark-Red'"
    assert gs[("org.cinnamon.desktop.interface", "icon-theme")] == "'Mint-Y-Red'"
    assert gs[("org.x.apps.portal", "color-scheme")] == "'prefer-dark'"
    assert gs[("org.cinnamon", "panels-enabled")] == "['1:0:top']"
    assert gs[("org.cinnamon", "panels-autohide")] == "['1:true']"
    assert json.loads((spices / "2.json").read_text())["pinned-apps"]["value"] == ["firefox_firefox.desktop"]


def test_mate_speed_and_repeat_rate(tmp_path):
    gsettings = {
        ("org.mate.peripherals-mouse", "motion-acceleration"): "-1.0",
        ("org.mate.peripherals-keyboard", "rate"): "30",
        ("org.mate.peripherals-keyboard", "delay"): "500",
    }
    ctx, runner = linux_pc(tmp_path, desktop="MATE", gsettings=gsettings)
    assert ctx.desktop.export(ctx, "mouse")["portable"] == {"speed": 0.0}
    assert ctx.desktop.export(ctx, "keyboard")["portable"] == {"repeat_delay_ms": 500, "repeat_interval_ms": 33}
    ctx.desktop.apply(ctx, "mouse", {"portable": {"speed": 1.0}})
    ctx.desktop.apply(ctx, "keyboard", {"portable": {"repeat_interval_ms": 20}})
    assert runner.gsettings[("org.mate.peripherals-mouse", "motion-acceleration")] == "10.0"
    assert runner.gsettings[("org.mate.peripherals-keyboard", "rate")] == "50"
    ctx.desktop.apply(ctx, "taskbar", {"portable": {"position": "top"}})
    assert "MATE's panel" in ctx.warnings[-1]


def test_xfce_sets_every_monitors_wallpaper(tmp_path):
    ctx, runner = linux_pc(tmp_path, desktop="XFCE", gsettings={}, programs={"xfconf-query"})
    runner.outputs[("xfconf-query", "-c", "xfce4-desktop", "-l")] = (
        "/backdrop/screen0/monitorVirtual-1/workspace0/last-image\n/backdrop/screen0/monitoreDP-1/workspace0/last-image\n"
    )
    ctx.desktop.apply(ctx, "wallpaper", {"portable": {"fit": "fill"}, "files": {"image": {"name": "w.png", "data": "iVBORw0KGgpwaXhlbHM="}}})
    sets = [c for c in runner.calls if "-s" in c]
    assert len([c for c in sets if c[4].endswith("last-image")]) == 2
    assert ["xfconf-query", "-c", "xfce4-desktop", "-p", "/backdrop/screen0/monitoreDP-1/workspace0/image-style", "-n", "-t", "int", "-s", "5"] in sets
    ctx.desktop.apply(ctx, "accent", {"portable": {"color": "#000000"}})
    assert "Xfce has no accent color" in ctx.warnings[-1]


# Linux profiles on Windows, and in the app


def test_linux_profile_applies_on_windows(tmp_path, make_ctx):
    linux, _ = linux_pc(tmp_path)
    profile = export_profile(linux, set(BY_NAME))
    profile["settings"]["accent"]["portable"]["color"] = "#3584E4"
    windows = make_ctx()
    applied = apply_profile(windows, profile, set(BY_NAME))
    assert "theme" in applied and "accent" in applied and "keyboard" in applied and "taskbar" not in applied
    reg = windows.registry
    assert reg.get(r"Software\Microsoft\Windows\DWM", "AccentColor").data == 0xFFE48435
    assert reg.get(r"Control Panel\Mouse", "MouseSensitivity").data == "10"
    assert reg.get(r"Control Panel\Keyboard", "KeyboardDelay").data == "1"
    assert any("Set-WinUserLanguageList" in call[1] for call in windows.system.calls if call[0] == "powershell")
    assert any("pin them by hand" in w for w in windows.warnings)


def test_app_review_unticks_what_this_desktop_cant_use(tmp_path, make_ctx):
    ctx, _ = linux_pc(tmp_path, desktop="XFCE", gsettings={}, programs={"xfconf-query"})
    api = Api(lambda: Context(None, ctx.system, desktop=ctx.desktop), lambda event: None)
    items = {i["name"]: i for i in api._review(windows_profile(make_ctx))["items"]}
    assert items["start"]["skip"] and items["accent"]["skip"] and items["taskbar"]["skip"]
    assert "skip" not in items["theme"] and items["start"]["details"] == "Not used on Xfce"


def test_summary_of_a_linux_profile(tmp_path):
    ctx, _ = linux_pc(tmp_path)
    profile = export_profile(ctx, set(BY_NAME))
    profile["settings"]["wallpaper"]["files"] = {"image": {"name": "w.png", "data": "iVBORw0KGgpwaXhlbHM="}}
    summary = summarize(profile)
    items = {i["name"]: i for i in summary["items"]}
    assert summary["system"].endswith("GNOME")
    assert items["accent"]["color"] == "#E95420"
    assert items["taskbar"]["details"] == "Left, 2 pinned apps"
    assert items["keyboard"]["details"] == "us"
    assert items["wallpaper"]["image"].startswith("data:image/png;base64,")


# The real gsettings, when this machine has GNOME's schemas


def _has_gnome_schemas() -> bool:
    if shutil.which("gsettings") is None:
        return False
    result = subprocess.run(["gsettings", "list-keys", "org.gnome.desktop.interface"], capture_output=True, text=True)
    return result.returncode == 0 and "color-scheme" in result.stdout


@pytest.mark.skipif(not _has_gnome_schemas(), reason="needs gsettings and GNOME's schemas")
def test_real_gsettings_round_trip(tmp_path, monkeypatch, make_ctx):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("GSETTINGS_BACKEND", "keyfile")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    ctx = linux_context(LinuxSystem(env=dict(os.environ)))
    assert isinstance(ctx.desktop, Gnome)
    apply_profile(ctx, windows_profile(make_ctx), set(BY_NAME))
    after = export_profile(linux_context(LinuxSystem(env=dict(os.environ))), set(BY_NAME))["settings"]
    assert after["theme"]["portable"]["apps_dark"] is True
    assert after["mouse"]["portable"]["speed"] == pytest.approx(0.4)
    assert after["keyboard"]["portable"]["layouts"] == [{"layout": "us", "variant": ""}, {"layout": "de", "variant": ""}]
    assert after["wallpaper"]["files"]["image"]["data"] == __import__("base64").b64encode(PNG).decode()

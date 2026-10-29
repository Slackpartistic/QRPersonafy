import json

from qrpersonafy.profile import apply_profile, check_profile, export_profile
from qrpersonafy.registry import REG_BINARY, REG_DWORD, REG_SZ, RegValue
from qrpersonafy.settings import BY_NAME
from qrpersonafy.settings.accent import DWM
from qrpersonafy.settings.keyboard import KEYBOARD
from qrpersonafy.settings.mouse import CURSORS, MOUSE
from qrpersonafy.settings.start import layout_folder
from qrpersonafy.settings.taskbar import ADVANCED, TASKBAND, pins_folder
from qrpersonafy.settings.theme import PERSONALIZE
from qrpersonafy.settings.wallpaper import DESKTOP
from qrpersonafy.system import SPI_SETDESKWALLPAPER, SPI_SETKEYBOARDDELAY, SPI_SETMOUSESPEED

PNG = b"\x89PNG\r\n\x1a\n" + b"pixels"


def configured_pc(make_ctx):
    ctx = make_ctx()
    reg = ctx.registry
    reg.set(PERSONALIZE, "AppsUseLightTheme", RegValue(REG_DWORD, 0))
    reg.set(PERSONALIZE, "SystemUsesLightTheme", RegValue(REG_DWORD, 0))
    reg.set(DWM, "AccentColor", RegValue(REG_DWORD, 0xFF0078D4))
    reg.set(ADVANCED, "TaskbarAl", RegValue(REG_DWORD, 0))
    reg.set(TASKBAND, "Favorites", RegValue(REG_BINARY, b"\x00\x01\x02"))
    reg.set(MOUSE, "MouseSensitivity", RegValue(REG_SZ, "14"))
    reg.set(CURSORS, "", RegValue(REG_SZ, "Windows Black"))
    reg.set(CURSORS, "Arrow", RegValue(REG_SZ, r"%SystemRoot%\cursors\arrow_r.cur"))
    reg.set(KEYBOARD, "KeyboardDelay", RegValue(REG_SZ, "0"))
    reg.set(DESKTOP, "WallpaperStyle", RegValue(REG_SZ, "10"))
    image = ctx.system.appdata / "Pictures" / "mountains.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(PNG)
    reg.set(DESKTOP, "Wallpaper", RegValue(REG_SZ, str(image)))
    pins = pins_folder(ctx)
    pins.mkdir(parents=True)
    (pins / "Terminal.lnk").write_bytes(b"shortcut")
    layout = layout_folder(ctx)
    layout.mkdir(parents=True)
    (layout / "start2.bin").write_bytes(b"start layout")
    ctx.system.powershell_output = json.dumps(
        [{"tag": "en-GB", "tips": ["0809:00000809"]}, {"tag": "fr-FR", "tips": "040C:0000040C"}]
    )
    return ctx


def test_export_then_apply_restores_everything(make_ctx):
    source = configured_pc(make_ctx)
    profile = export_profile(source, set(BY_NAME))
    # The profile must survive being sent as JSON.
    profile = check_profile(json.loads(json.dumps(profile)))
    assert not source.warnings

    target = make_ctx()
    applied = apply_profile(target, profile, set(BY_NAME))

    assert set(applied) == set(BY_NAME)
    assert not target.warnings
    for key, name in [
        (PERSONALIZE, "AppsUseLightTheme"),
        (DWM, "AccentColor"),
        (ADVANCED, "TaskbarAl"),
        (TASKBAND, "Favorites"),
        (MOUSE, "MouseSensitivity"),
        (CURSORS, ""),
        (CURSORS, "Arrow"),
        (KEYBOARD, "KeyboardDelay"),
        (DESKTOP, "WallpaperStyle"),
    ]:
        assert target.registry.get(key, name) == source.registry.get(key, name), (key, name)

    wallpaper = target.system.appdata / "QRPersonafy" / "wallpaper.png"
    assert wallpaper.read_bytes() == PNG
    assert (pins_folder(target) / "Terminal.lnk").read_bytes() == b"shortcut"
    assert (layout_folder(target) / "start2.bin").read_bytes() == b"start layout"

    calls = target.system.calls
    assert ("spi", SPI_SETDESKWALLPAPER, 0, str(wallpaper)) in calls
    assert ("spi", SPI_SETMOUSESPEED, 0, 14) in calls
    assert ("spi", SPI_SETKEYBOARDDELAY, 0, None) in calls
    assert ("broadcast", "ImmersiveColorSet") in calls
    assert ("stop_process", "StartMenuExperienceHost.exe") in calls
    # Taskbar and Start both need Explorer restarted, but it only happens once, at the end.
    assert calls.count(("restart_explorer",)) == 1
    assert calls[-1] == ("restart_explorer",)
    script = next(c[1] for c in calls if c[0] == "powershell")
    assert "New-WinUserLanguageList 'en-GB'" in script
    assert "$list.Add('fr-FR')" in script
    assert "$list[1].InputMethodTips.Add('040C:0000040C')" in script


def test_only_applies_chosen_settings(make_ctx):
    profile = export_profile(configured_pc(make_ctx), set(BY_NAME))
    target = make_ctx()
    assert apply_profile(target, profile, {"theme"}) == ["theme"]
    assert target.registry.get(PERSONALIZE, "AppsUseLightTheme") is not None
    assert target.registry.get(MOUSE, "MouseSensitivity") is None
    assert ("restart_explorer",) not in target.system.calls


def test_wallpaper_falls_back_to_windows_copy(make_ctx):
    ctx = make_ctx()
    ctx.registry.set(DESKTOP, "Wallpaper", RegValue(REG_SZ, r"C:\gone\old.jpg"))
    cached = ctx.system.appdata / "Microsoft" / "Windows" / "Themes" / "TranscodedWallpaper"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"\xff\xd8\xff" + b"jpeg")
    section = BY_NAME["wallpaper"].export(ctx)
    assert section["files"]["image"]["name"] == "wallpaper.jpg"


def test_read_only_value_becomes_warning(make_ctx):
    profile = export_profile(configured_pc(make_ctx), {"taskbar"})
    target = make_ctx()
    target.registry.read_only.add((ADVANCED.lower(), "taskbaral"))
    assert apply_profile(target, profile, {"taskbar"}) == ["taskbar"]
    assert any("TaskbarAl" in w for w in target.warnings)
    assert target.registry.get(TASKBAND, "Favorites") is not None

"""Start menu pins and layout options.

Windows 11 keeps Start pins in start2.bin (start.bin on older builds) inside the Start menu
app's folder. Apps that are not installed yet are dropped from the restored layout by Windows.
"""

from __future__ import annotations

from pathlib import Path

from .base import Context, Setting, pack_file, unpack_file
from .taskbar import ADVANCED

START = r"Software\Microsoft\Windows\CurrentVersion\Start"
LAYOUT_FILES = ("start2.bin", "start.bin")


def layout_folder(ctx: Context) -> Path:
    return (
        ctx.system.localappdata
        / "Packages"
        / "Microsoft.Windows.StartMenuExperienceHost_cw5n1h2txyewy"
        / "LocalState"
    )


class Start(Setting):
    name = "start"
    label = "Start menu"
    values = (
        (ADVANCED, "Start_Layout"),
        (ADVANCED, "Start_TrackDocs"),
        (ADVANCED, "Start_TrackProgs"),
        (ADVANCED, "Start_IrisRecommendations"),
        # Folders shown next to the power button.
        (START, "VisiblePlaces"),
    )

    def export_extra(self, ctx: Context, section: dict) -> None:
        folder = layout_folder(ctx)
        files = {
            name: pack_file(name, (folder / name).read_bytes())
            for name in LAYOUT_FILES
            if (folder / name).is_file()
        }
        if files:
            section["files"] = files
        else:
            ctx.warn("Start menu: no Start layout file found, saving options only")

    def apply_extra(self, ctx: Context, section: dict) -> None:
        files = section.get("files", {})
        layouts = [files[name] for name in LAYOUT_FILES if name in files]
        if not layouts:
            return
        # The Start menu holds the layout in memory and rewrites the file, so stop it first.
        # Windows starts it again the next time Start is opened.
        ctx.system.stop_process("StartMenuExperienceHost.exe")
        folder = layout_folder(ctx)
        folder.mkdir(parents=True, exist_ok=True)
        for logical in LAYOUT_FILES:
            if logical in files:
                _, data = unpack_file(files[logical])
                (folder / logical).write_bytes(data)

    def after_apply(self, ctx: Context) -> None:
        ctx.restart_explorer = True

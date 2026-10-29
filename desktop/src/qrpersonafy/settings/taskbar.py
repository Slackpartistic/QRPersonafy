"""Taskbar alignment, buttons, position and pinned apps."""

from __future__ import annotations

from pathlib import Path

from .base import Context, Setting, pack_file, unpack_file

ADVANCED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
SEARCH = r"Software\Microsoft\Windows\CurrentVersion\Search"
STUCK_RECTS = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3"
TASKBAND = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Taskband"


def pins_folder(ctx: Context) -> Path:
    return ctx.system.appdata / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar"


class Taskbar(Setting):
    name = "taskbar"
    label = "Taskbar"
    values = (
        (ADVANCED, "TaskbarAl"),
        (ADVANCED, "TaskbarGlomLevel"),
        (ADVANCED, "TaskbarSmallIcons"),
        (ADVANCED, "TaskbarSd"),
        (ADVANCED, "TaskbarBadges"),
        (ADVANCED, "ShowTaskViewButton"),
        (ADVANCED, "TaskbarDa"),
        (ADVANCED, "TaskbarMn"),
        (ADVANCED, "MMTaskbarEnabled"),
        (ADVANCED, "MMTaskbarMode"),
        (ADVANCED, "MMTaskbarGlomLevel"),
        (SEARCH, "SearchboxTaskbarMode"),
        # Position and auto-hide.
        (STUCK_RECTS, "Settings"),
        # Order and identity of pinned apps; the shortcuts themselves are files.
        (TASKBAND, "Favorites"),
        (TASKBAND, "FavoritesResolve"),
    )

    def apply(self, ctx: Context, section: dict) -> None:
        before = len(ctx.warnings)
        super().apply(ctx, section)
        # Windows protects the Widgets button from being changed by apps (it reports access denied),
        # so explain what to do instead of showing an error.
        for i in range(before, len(ctx.warnings)):
            if "\\TaskbarDa:" in ctx.warnings[i]:
                ctx.warnings[i] = (
                    "Taskbar: Windows doesn't let apps change the Widgets button. "
                    "Set it yourself in Settings > Personalization > Taskbar."
                )

    def export_extra(self, ctx: Context, section: dict) -> None:
        folder = pins_folder(ctx)
        if folder.is_dir():
            section["files"] = {
                f"pin:{path.name}": pack_file(path.name, path.read_bytes())
                for path in sorted(folder.glob("*.lnk"))
            }

    def apply_extra(self, ctx: Context, section: dict) -> None:
        folder = pins_folder(ctx)
        for logical, entry in section.get("files", {}).items():
            if not logical.startswith("pin:"):
                continue
            name, data = unpack_file(entry)
            if not name.lower().endswith(".lnk"):
                ctx.warn(f"Taskbar: skipped pinned item {name!r}, not a shortcut")
                continue
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)

    def after_apply(self, ctx: Context) -> None:
        ctx.restart_explorer = True

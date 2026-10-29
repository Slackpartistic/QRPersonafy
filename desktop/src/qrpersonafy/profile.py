"""Profiles: one JSON document holding the saved settings of one PC."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .settings import ALL, Context

FORMAT = "qrpersonafy-profile"
VERSION = 1


def export_profile(ctx: Context, names: set[str]) -> dict:
    return {
        "format": FORMAT,
        "version": VERSION,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app_version": __version__,
        "windows_build": ctx.system.windows_build(),
        "settings": {s.name: s.export(ctx) for s in ALL if s.name in names},
    }


Progress = Callable[[int, int, str], None]


def apply_profile(ctx: Context, profile: dict, names: set[str], progress: Progress | None = None) -> list[str]:
    """Apply the chosen settings from `profile` and return the names of those applied.

    `progress(done, total, label)` is called before each step.
    """
    applied = []
    sections = profile.get("settings", {})
    chosen = [s for s in ALL if s.name in names and s.name in sections]
    total = len(chosen) + 1
    for step, setting in enumerate(chosen):
        if progress:
            progress(step, total, setting.label)
        try:
            setting.apply(ctx, sections[setting.name])
        except (ValueError, TypeError, AttributeError) as error:
            ctx.warn(f"{setting.label}: skipped, the saved data is malformed ({error})")
            continue
        applied.append(setting.name)
    if progress:
        progress(len(chosen), total, "Finishing up")
    if ctx.restart_explorer:
        ctx.system.restart_explorer()
    if progress:
        progress(total, total, "Done")
    return applied


def backups_dir(ctx: Context) -> Path:
    return ctx.system.localappdata / "QRPersonafy" / "backups"


def back_up(ctx: Context, names: set[str]) -> Path:
    """Save the current values of the chosen settings, so applying a profile can be undone."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = backups_dir(ctx) / f"before-apply-{stamp}.json"
    save_profile(export_profile(ctx, names), path)
    return path


def latest_backup(ctx: Context) -> Path | None:
    folder = backups_dir(ctx)
    backups = sorted(folder.glob("before-apply-*.json")) if folder.is_dir() else []
    return backups[-1] if backups else None


def check_profile(profile: object) -> dict:
    if not isinstance(profile, dict) or profile.get("format") != FORMAT:
        raise ValueError("not a QRPersonafy profile")
    if profile.get("version") != VERSION:
        raise ValueError(f"unsupported profile version {profile.get('version')!r}, expected {VERSION}")
    if not isinstance(profile.get("settings"), dict):
        raise ValueError("profile has no settings")
    return profile


def load_profile(path: Path) -> dict:
    return check_profile(json.loads(path.read_text(encoding="utf-8")))


def save_profile(profile: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

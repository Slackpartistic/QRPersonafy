"""Shared machinery for a group of settings that can be exported to and applied from a profile.

A profile may come from a phone or a backup server, so it is treated as untrusted input:
applying one only ever writes the registry values and files a setting declares here,
never keys, value names or paths taken from the profile itself.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from ..registry import REG_DWORD, REG_EXPAND_SZ, REG_SZ, Registry, RegValue
from ..system import System


@dataclass
class Context:
    registry: Registry
    system: System
    warnings: list[str] = field(default_factory=list)
    # Set by settings that only show up after Explorer restarts, so it restarts once at the end.
    restart_explorer: bool = False

    def warn(self, message: str) -> None:
        self.warnings.append(message)


@dataclass(frozen=True)
class PlannedWrite:
    key: str
    name: str
    value: RegValue


class Setting:
    name: str = ""
    label: str = ""
    # Individual (key, value name) pairs to save and restore.
    values: tuple[tuple[str, str], ...] = ()
    # Keys whose every string or DWORD value is saved and restored.
    whole_keys: tuple[str, ...] = ()

    # Export

    def export(self, ctx: Context) -> dict:
        entries = []
        for key, name in self.values:
            value = ctx.registry.get(key, name)
            if value is not None:
                entries.append({"key": key, "name": name, **value.to_json()})
        for key in self.whole_keys:
            for name, value in sorted(ctx.registry.list_values(key).items()):
                if value.type in (REG_SZ, REG_EXPAND_SZ, REG_DWORD):
                    entries.append({"key": key, "name": name, **value.to_json()})
        section: dict = {"registry": entries}
        self.export_extra(ctx, section)
        return section

    def export_extra(self, ctx: Context, section: dict) -> None:
        """Add files or other data that do not live in the registry."""

    # Apply

    def plan(self, section: dict) -> list[PlannedWrite]:
        """The registry writes `section` asks for, limited to values this setting declares."""
        allowed = {(k.lower(), n.lower()): (k, n) for k, n in self.values}
        whole = {k.lower(): k for k in self.whole_keys}
        writes = []
        for entry in section.get("registry", []):
            key, name = entry.get("key"), entry.get("name")
            if not isinstance(key, str) or not isinstance(name, str):
                continue
            value = RegValue.from_json(entry)
            if (key.lower(), name.lower()) in allowed:
                key, name = allowed[(key.lower(), name.lower())]
            elif key.lower() in whole and value.type in (REG_SZ, REG_EXPAND_SZ, REG_DWORD):
                key = whole[key.lower()]
                if "\\" in name or len(name) > 255:
                    continue
            else:
                continue
            writes.append(PlannedWrite(key, name, value))
        return writes

    def apply(self, ctx: Context, section: dict) -> None:
        for write in self.plan(section):
            try:
                ctx.registry.set(write.key, write.name, write.value)
            except OSError as error:
                ctx.warn(f"{self.label}: could not set {write.key}\\{write.name}: {error}")
        self.apply_extra(ctx, section)
        self.after_apply(ctx)

    def apply_extra(self, ctx: Context, section: dict) -> None:
        """Restore files or other data that do not live in the registry."""

    def after_apply(self, ctx: Context) -> None:
        """Make the restored values take effect without signing out."""

    def describe(self, section: dict) -> list[str]:
        """Human-readable lines for `show` and dry runs."""
        lines = [f"{w.key}\\{w.name} = {_short(w.value)}" for w in self.plan(section)]
        for logical, file in section.get("files", {}).items():
            lines.append(f"file {logical}: {file.get('name')} ({len(file.get('data', '')) * 3 // 4} bytes)")
        return lines


def _short(value: RegValue) -> str:
    if isinstance(value.data, bytes):
        return f"<{len(value.data)} bytes>"
    return repr(value.data)


def pack_file(name: str, data: bytes) -> dict:
    return {"name": name, "data": base64.b64encode(data).decode("ascii")}


def unpack_file(entry: object) -> tuple[str, bytes]:
    """Decode a file from a profile, reducing its name to a bare file name."""
    if not isinstance(entry, dict) or not isinstance(entry.get("data"), str):
        raise ValueError("malformed file entry")
    name = PureWindowsPath(str(entry.get("name", ""))).name
    name = Path(name).name
    if name in ("", ".", ".."):
        raise ValueError(f"bad file name: {entry.get('name')!r}")
    return name, base64.b64decode(entry["data"], validate=True)


def dword(ctx: Context, key: str, name: str, default: int | None = None) -> int | None:
    """Read a value as an int, accepting the string form many Control Panel values use."""
    value = ctx.registry.get(key, name)
    if value is None:
        return default
    try:
        return int(value.data)
    except (TypeError, ValueError):
        return default

"""Linux support: one plug-in per desktop environment, picked from the running session.

Distributions don't matter much; desktops do. Ubuntu, Fedora and Debian with GNOME all keep
their settings the same way, while Kubuntu (KDE Plasma) keeps them elsewhere. Another desktop
can be added from outside this package by publishing a `Desktop` subclass under the
"qrpersonafy.desktops" entry point group.
"""

from __future__ import annotations

from importlib.metadata import entry_points

from ..settings.base import Context
from .cinnamon import Cinnamon, Mate
from .desktop import Desktop
from .gnome import Gnome
from .kde import Kde
from .system import LinuxSystem
from .xfce import Xfce

BUILT_IN: tuple[type[Desktop], ...] = (Kde, Cinnamon, Mate, Xfce, Gnome)


def desktop_classes() -> list[type[Desktop]]:
    classes: list[type[Desktop]] = []
    try:
        for entry in entry_points(group="qrpersonafy.desktops"):
            try:
                cls = entry.load()
            except Exception:  # a broken plug-in shouldn't stop the app
                continue
            if isinstance(cls, type) and issubclass(cls, Desktop):
                classes.append(cls)
    except Exception:
        pass
    return classes + list(BUILT_IN)


def session_names(env) -> list[str]:
    """The running desktop's names, e.g. ["ubuntu", "gnome"] for "ubuntu:GNOME"."""
    raw = env.get("XDG_CURRENT_DESKTOP") or env.get("XDG_SESSION_DESKTOP") or env.get("DESKTOP_SESSION") or ""
    names = [n.strip().lower() for n in raw.replace(";", ":").split(":") if n.strip()]
    if env.get("KDE_FULL_SESSION") == "true" and "kde" not in names:
        names.append("kde")
    return names


def detect(system: LinuxSystem) -> Desktop | None:
    names = session_names(system.env)
    for cls in desktop_classes():
        if cls.matches(names):
            return cls(system)
    return None


class UnknownDesktop(Desktop):
    """A desktop QRPersonafy doesn't know. Nothing is read or changed, and the app says so."""

    def __init__(self, system: LinuxSystem, names: list[str]) -> None:
        super().__init__(system)
        self.name = ":".join(names) or "this desktop"

    def apply(self, ctx: Context, name: str, section: dict) -> bool:
        if not any(w.startswith(self.name) for w in ctx.warnings):
            ctx.warn(
                f"{self.name} isn't supported yet, so nothing was changed. "
                "Supported desktops: GNOME, KDE Plasma, Cinnamon, MATE and Xfce."
            )
        return False

    def export(self, ctx: Context, name: str) -> dict | None:
        return None


def linux_context(system: LinuxSystem | None = None) -> Context:
    system = system or LinuxSystem()
    desktop = detect(system) or UnknownDesktop(system, session_names(system.env))
    return Context(None, system, desktop=desktop)


__all__ = ["BUILT_IN", "Desktop", "LinuxSystem", "UnknownDesktop", "detect", "linux_context", "session_names"]

"""What the window's JavaScript can call. Every public method is exposed to the page.

Transfers run on background threads; progress reaches the page as events through `emit`.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .. import __version__
from ..pairing import SESSION_SECONDS, PairingSession
from ..pairing_qr import qr_svg
from ..profile import apply_profile, back_up, check_profile, export_profile, latest_backup, load_profile, save_profile
from ..settings import BY_NAME, Context
from ..summary import summarize

# How long the phone is kept waiting while the user decides whether to apply what it sent.
DECISION_SECONDS = 9 * 60

Emit = Callable[[dict], None]


class Api:
    def __init__(self, make_context: Callable[[], Context], emit: Emit) -> None:
        self._make_context = make_context
        self._emit = emit
        self._session: PairingSession | None = None
        self._decision = threading.Event()
        self._decided: tuple[bool, set[str]] = (False, set())
        self._pending_file: dict | None = None
        # Set by the window so file dialogs can be shown.
        self._choose_file: Callable[[bool, str], str | None] | None = None

    # Page start

    def info(self) -> dict:
        return {"pc_name": socket.gethostname(), "version": __version__, "has_backup": self._has_backup()}

    # Save this PC to the phone

    def start_send(self) -> dict:
        self.cancel()
        ctx = self._make_context()
        profile = export_profile(ctx, set(BY_NAME))
        session = PairingSession("send", profile=profile)
        self._start(session, "send")
        return {**self._qr(session), "summary": summarize(profile), "warnings": ctx.warnings}

    # Restore from the phone

    def start_receive(self) -> dict:
        self.cancel()
        session = PairingSession("receive", on_receive=self._on_receive)
        self._start(session, "receive")
        return self._qr(session)

    def decide(self, apply: bool, names: list[str] | None = None) -> None:
        """Called by the page once the user has reviewed what the phone sent."""
        self._decided = (bool(apply), {n for n in names or [] if n in BY_NAME})
        self._decision.set()

    def _on_receive(self, profile: dict) -> tuple[int, dict]:
        try:
            check_profile(profile)
        except ValueError as error:
            self._emit({"type": "error", "message": f"Your phone sent something this app can't read: {error}"})
            return 400, {"error": str(error)}
        self._decision.clear()
        self._emit({"type": "received", "summary": summarize(profile)})
        if not self._decision.wait(DECISION_SECONDS):
            self._emit({"type": "error", "message": "Nothing was applied because no choice was made in time."})
            return 403, {"error": "no answer on the PC"}
        apply, names = self._decided
        if not apply or not names:
            return 403, {"error": "declined on the PC"}
        result = self._apply(profile, names)
        self._emit({"type": "applied", **result})
        return 200, {"applied": result["applied_names"], "warnings": result["warnings"]}

    # Undo and files

    def undo_last(self) -> dict:
        ctx = self._make_context()
        backup = latest_backup(ctx)
        if backup is None:
            return {"applied": [], "warnings": ["There is no backup to restore."]}
        applied = apply_profile(ctx, load_profile(backup), set(BY_NAME), self._progress)
        # Each backup undoes one restore; using it up lets the next undo go one step further back.
        backup.rename(backup.with_suffix(".used"))
        return {"applied": [BY_NAME[n].label for n in applied], "warnings": ctx.warnings, "has_backup": self._has_backup()}

    def export_file(self) -> dict:
        path = self._choose_file and self._choose_file(True, f"{socket.gethostname()}.qrpersonafy.json")
        if not path:
            return {"saved": None}
        ctx = self._make_context()
        save_profile(export_profile(ctx, set(BY_NAME)), Path(path))
        return {"saved": str(path), "warnings": ctx.warnings}

    def open_file(self) -> dict:
        path = self._choose_file and self._choose_file(False, "")
        if not path:
            return {"summary": None}
        try:
            self._pending_file = load_profile(Path(path))
        except (OSError, ValueError) as error:
            return {"summary": None, "error": f"Couldn't open that file: {error}"}
        return {"summary": summarize(self._pending_file)}

    def apply_file(self, names: list[str]) -> dict:
        if self._pending_file is None:
            return {"applied": [], "warnings": ["Open a file first."]}
        profile, self._pending_file = self._pending_file, None
        return self._apply(profile, {n for n in names if n in BY_NAME})

    # Shared

    def cancel(self) -> None:
        session, self._session = self._session, None
        if session is not None:
            session.deadline = time.monotonic()
        self._decided = (False, set())
        self._decision.set()

    def _apply(self, profile: dict, names: set[str]) -> dict:
        ctx = self._make_context()
        back_up(ctx, names)
        applied = apply_profile(ctx, profile, names, self._progress)
        return {
            "applied": [BY_NAME[n].label for n in applied],
            "applied_names": applied,
            "warnings": ctx.warnings,
            "has_backup": True,
        }

    def _progress(self, done: int, total: int, label: str) -> None:
        self._emit({"type": "progress", "done": done, "total": total, "label": label})

    def _has_backup(self) -> bool:
        try:
            return latest_backup(self._make_context()) is not None
        except Exception:
            return False

    def _qr(self, session: PairingSession) -> dict:
        return {"qr": qr_svg(session.uri()), "pc_name": socket.gethostname(), "seconds": SESSION_SECONDS}

    def _start(self, session: PairingSession, kind: str) -> None:
        self._session = session

        def run() -> None:
            done = session.serve()
            if self._session is session:
                self._session = None
                self._emit({"type": "finished", "kind": kind, "ok": done})

        threading.Thread(target=run, daemon=True).start()

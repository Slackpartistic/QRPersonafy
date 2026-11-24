"""Running the desktop's own tools (gsettings, kwriteconfig6, ...), with a recording fake for tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Protocol


def system_env() -> dict[str, str] | None:
    """The environment for the desktop's own tools.

    The packaged app (AppImage or tarball) carries its own copies of libraries such as GLib,
    and points LD_LIBRARY_PATH at them. Tools like gsettings and xfconf-query must use the
    system's copies instead: with the app's older GLib, gsettings quietly loses every change
    and xfconf-query doesn't start. PyInstaller keeps the original value in
    LD_LIBRARY_PATH_ORIG.
    """
    if not getattr(sys, "frozen", False) and "LD_LIBRARY_PATH_ORIG" not in os.environ:
        return None
    env = dict(os.environ)
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original:
        env["LD_LIBRARY_PATH"] = original
    else:
        env.pop("LD_LIBRARY_PATH", None)
    return env


class Runner(Protocol):
    def run(self, args: list[str]) -> str:
        """Run a command and return its output. Raises OSError if it fails or is missing."""

    def has(self, program: str) -> bool: ...


class SubprocessRunner:
    def run(self, args):
        try:
            completed = subprocess.run(args, capture_output=True, text=True, timeout=30, env=system_env())
        except (subprocess.TimeoutExpired, FileNotFoundError) as error:
            raise OSError(f"{args[0]}: {error}") from error
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout).strip().splitlines()
            raise OSError(f"{args[0]} failed: {message[-1] if message else completed.returncode}")
        return completed.stdout

    def has(self, program):
        return shutil.which(program) is not None


class FakeRunner:
    """Answers commands from a table, records them, and keeps a fake gsettings store.

    `outputs` maps a command (as a tuple, or its first words) to the text it prints, or to an
    exception to raise.
    """

    def __init__(self, programs: set[str] | None = None, gsettings: dict | None = None, relocatable: dict | None = None) -> None:
        self.programs = set(programs or ())
        self.outputs: dict[tuple, object] = {}
        self.calls: list[list[str]] = []
        # {(schema, key): "gvariant text"}
        self.gsettings: dict[tuple[str, str], str] = dict(gsettings or {})
        # Relocatable schemas, used as "schema:/path/": {schema: {key: "default gvariant text"}}
        self.relocatable: dict[str, dict[str, str]] = dict(relocatable or {})
        if self.gsettings or self.relocatable:
            self.programs.add("gsettings")

    def _known(self, schema: str, key: str) -> bool:
        if (schema, key) in self.gsettings:
            return True
        base, _, path = schema.partition(":")
        if path and key in self.relocatable.get(base, {}):
            self.gsettings[(schema, key)] = self.relocatable[base][key]
            return True
        return False

    def has(self, program):
        return program in self.programs

    def run(self, args):
        self.calls.append(list(args))
        if args[0] == "gsettings" and "gsettings" in self.programs:
            return self._gsettings(args[1:])
        for length in range(len(args), 0, -1):
            answer = self.outputs.get(tuple(args[:length]))
            if answer is not None:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        if args[0] not in self.programs:
            raise OSError(f"{args[0]}: not found")
        return ""

    def _gsettings(self, args):
        if args[0] == "list-schemas":
            return "".join(f"{s}\n" for s in sorted({s for s, _ in self.gsettings}))
        if args[0] == "list-keys":
            base, _, path = args[1].partition(":")
            keys = sorted(self.relocatable[base]) if path and base in self.relocatable else sorted(k for s, k in self.gsettings if s == args[1])
            if not keys:
                raise OSError(f"No such schema “{args[1]}”")
            return "".join(f"{k}\n" for k in keys)
        if args[0] in ("get", "set", "range"):
            if not self._known(args[1], args[2]):
                raise OSError(f"No such key “{args[2]}”")
            if args[0] == "get":
                return self.gsettings[(args[1], args[2])] + "\n"
            if args[0] == "range":
                return "type s\n"
            self.gsettings[(args[1], args[2])] = args[3]
            return ""
        raise OSError(f"gsettings {args[0]} not faked")

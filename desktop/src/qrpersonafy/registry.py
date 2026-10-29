"""Access to the current user's registry (HKCU), with an in-memory fake for tests."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol

# Value types, matching winreg's constants.
REG_SZ = 1
REG_EXPAND_SZ = 2
REG_BINARY = 3
REG_DWORD = 4
REG_MULTI_SZ = 7
REG_QWORD = 11

TYPE_NAMES = {
    REG_SZ: "REG_SZ",
    REG_EXPAND_SZ: "REG_EXPAND_SZ",
    REG_BINARY: "REG_BINARY",
    REG_DWORD: "REG_DWORD",
    REG_MULTI_SZ: "REG_MULTI_SZ",
    REG_QWORD: "REG_QWORD",
}
TYPES_BY_NAME = {name: code for code, name in TYPE_NAMES.items()}


@dataclass(frozen=True)
class RegValue:
    type: int
    data: object

    def to_json(self) -> dict:
        data = self.data
        if self.type == REG_BINARY:
            data = base64.b64encode(data).decode("ascii")
        return {"type": TYPE_NAMES[self.type], "data": data}

    @classmethod
    def from_json(cls, obj: dict) -> "RegValue":
        """Parse and type-check a value from a profile, which is untrusted input."""
        type_code = TYPES_BY_NAME.get(obj.get("type"))
        if type_code is None:
            raise ValueError(f"unsupported registry type: {obj.get('type')!r}")
        data = obj.get("data")
        if type_code == REG_BINARY:
            if not isinstance(data, str):
                raise ValueError("REG_BINARY data must be base64 text")
            data = base64.b64decode(data, validate=True)
        elif type_code in (REG_DWORD, REG_QWORD):
            limit = 2**32 if type_code == REG_DWORD else 2**64
            if not isinstance(data, int) or isinstance(data, bool) or not 0 <= data < limit:
                raise ValueError(f"{TYPE_NAMES[type_code]} data out of range: {data!r}")
        elif type_code == REG_MULTI_SZ:
            if not isinstance(data, list) or not all(isinstance(s, str) for s in data):
                raise ValueError("REG_MULTI_SZ data must be a list of strings")
        elif not isinstance(data, str):
            raise ValueError(f"{TYPE_NAMES[type_code]} data must be a string")
        return cls(type_code, data)


def normalize(type_code: int, data: object) -> RegValue | None:
    """Turn what winreg returns into a RegValue. winreg gives None for empty values."""
    if type_code not in TYPE_NAMES:
        return None
    if data is None:
        empty = {REG_BINARY: b"", REG_SZ: "", REG_EXPAND_SZ: "", REG_MULTI_SZ: []}
        if type_code not in empty:
            return None
        data = empty[type_code]
    return RegValue(type_code, data)


class Registry(Protocol):
    """HKCU registry. Keys are paths below HKEY_CURRENT_USER, e.g. r"Control Panel\\Mouse"."""

    def get(self, key: str, name: str) -> RegValue | None: ...

    def set(self, key: str, name: str, value: RegValue) -> None: ...

    def list_values(self, key: str) -> dict[str, RegValue]: ...


class WindowsRegistry:
    def __init__(self) -> None:
        import winreg

        self._winreg = winreg

    def get(self, key: str, name: str) -> RegValue | None:
        winreg = self._winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                data, type_code = winreg.QueryValueEx(handle, name)
        except FileNotFoundError:
            return None
        return normalize(type_code, data)

    def set(self, key: str, name: str, value: RegValue) -> None:
        winreg = self._winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
            winreg.SetValueEx(handle, name, 0, value.type, value.data)

    def list_values(self, key: str) -> dict[str, RegValue]:
        winreg = self._winreg
        values: dict[str, RegValue] = {}
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                index = 0
                while True:
                    try:
                        name, data, type_code = winreg.EnumValue(handle, index)
                    except OSError:
                        break
                    if (value := normalize(type_code, data)) is not None:
                        values[name] = value
                    index += 1
        except FileNotFoundError:
            pass
        return values


class FakeRegistry:
    """In-memory registry for tests and for dry runs off Windows."""

    def __init__(self, values: dict[tuple[str, str], RegValue] | None = None) -> None:
        self.values: dict[tuple[str, str], RegValue] = dict(values or {})
        self.read_only: set[tuple[str, str]] = set()

    def get(self, key: str, name: str) -> RegValue | None:
        return self.values.get((key.lower(), name.lower()))

    def set(self, key: str, name: str, value: RegValue) -> None:
        if (key.lower(), name.lower()) in self.read_only:
            raise PermissionError(f"access denied: {key}\\{name}")
        self.values[(key.lower(), name.lower())] = value

    def list_values(self, key: str) -> dict[str, RegValue]:
        return {name: value for (k, name), value in self.values.items() if k == key.lower()}

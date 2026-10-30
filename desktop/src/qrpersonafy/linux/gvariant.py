"""Reading and writing the GVariant text that `gsettings get` prints and `gsettings set` takes."""

from __future__ import annotations

import re

_TYPE_PREFIX = re.compile(r"(@[a-z(){}]+|uint32|int32|uint64|int64|uint16|int16|byte|double|objectpath|signature)\s+")
_NUMBER = re.compile(r"-?(0x[0-9a-fA-F]+|\d+(\.\d+)?([eE][-+]?\d+)?)")


def parse(text: str):
    """Parse a GVariant value: strings, numbers, booleans, arrays and tuples."""
    value, rest = _parse(text.strip())
    if rest.strip():
        raise ValueError(f"unexpected text after value: {rest!r}")
    return value


def _parse(text: str):
    text = text.lstrip()
    while (prefix := _TYPE_PREFIX.match(text)) is not None:
        text = text[prefix.end():].lstrip()
    if not text:
        raise ValueError("empty value")
    first = text[0]
    if first in "'\"":
        return _string(text)
    if first == "<":
        value, text = _parse(text[1:])
        text = text.lstrip()
        if not text.startswith(">"):
            raise ValueError("expected >")
        return value, text[1:]
    if first in "[(":
        close = "]" if first == "[" else ")"
        items, text = [], text[1:].lstrip()
        while not text.startswith(close):
            item, text = _parse(text)
            items.append(item)
            text = text.lstrip()
            if text.startswith(","):
                text = text[1:].lstrip()
            elif not text.startswith(close):
                raise ValueError(f"expected , or {close}")
        return (items if first == "[" else tuple(items)), text[1:]
    for word, value in (("true", True), ("false", False), ("nothing", None)):
        if text.startswith(word):
            return value, text[len(word):]
    if (number := _NUMBER.match(text)) is not None:
        raw = number.group(0)
        if raw.lstrip("-").startswith("0x"):
            return int(raw, 16), text[number.end():]
        return (float(raw) if any(c in raw for c in ".eE") else int(raw)), text[number.end():]
    raise ValueError(f"can't read GVariant value: {text[:30]!r}")


def _string(text: str):
    quote, out, i = text[0], [], 1
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            following = text[i + 1]
            out.append({"n": "\n", "t": "\t", "\\": "\\", "'": "'", '"': '"'}.get(following, following))
            i += 2
            continue
        if char == quote:
            return "".join(out), text[i + 1:]
        out.append(char)
        i += 1
    raise ValueError("unterminated string")


def string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def format(value) -> str:
    """GVariant text for a Python value. Lists of tuples become a(ss) and so on."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return string(value)
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, tuple):
        return "(" + ", ".join(format(v) for v in value) + ("," if len(value) == 1 else "") + ")"
    if isinstance(value, list):
        return "[" + ", ".join(format(v) for v in value) + "]"
    raise TypeError(f"can't write {type(value).__name__} as GVariant")

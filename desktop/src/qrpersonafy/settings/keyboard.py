"""Key repeat delay and rate, and the input languages and keyboard layouts."""

from __future__ import annotations

import json
import re

from ..system import SPI_SETKEYBOARDDELAY, SPI_SETKEYBOARDSPEED
from .base import Context, Setting, dword

KEYBOARD = r"Control Panel\Keyboard"

# Language tags such as "en-US" and input method tips such as "0409:00000409" or
# "0804:{GUID}{GUID}". Both are pasted into a PowerShell script, so they are checked strictly.
_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$")
_INPUT_TIP = re.compile(r"^[0-9A-Fa-f]{4}:[0-9A-Fa-f{}\-]{8,90}$")

EXPORT_LANGUAGES = (
    "Get-WinUserLanguageList | ForEach-Object "
    "{ [pscustomobject]@{ tag = $_.LanguageTag; tips = @($_.InputMethodTips) } } "
    "| ConvertTo-Json -Compress -Depth 3"
)


def parse_languages(raw: object) -> list[dict]:
    """Validate a language list from PowerShell or from a profile."""
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError("language list must be a list")
    languages = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("language entry must be an object")
        tag, tips = item.get("tag"), item.get("tips") or []
        if isinstance(tips, str):
            tips = [tips]
        if not isinstance(tag, str) or not _LANGUAGE_TAG.match(tag):
            raise ValueError(f"bad language tag: {tag!r}")
        if not all(isinstance(t, str) and _INPUT_TIP.match(t) for t in tips):
            raise ValueError(f"bad input method for {tag}: {tips!r}")
        languages.append({"tag": tag, "tips": list(tips)})
    if not languages:
        raise ValueError("language list is empty")
    return languages


def set_languages_script(languages: list[dict]) -> str:
    lines = [f"$list = New-WinUserLanguageList '{languages[0]['tag']}'"]
    for index, language in enumerate(languages):
        if index > 0:
            lines.append(f"$list.Add('{language['tag']}')")
        if language["tips"]:
            lines.append(f"$list[{index}].InputMethodTips.Clear()")
            lines.extend(f"$list[{index}].InputMethodTips.Add('{tip}')" for tip in language["tips"])
    lines.append("Set-WinUserLanguageList $list -Force")
    return "; ".join(lines)


class Keyboard(Setting):
    name = "keyboard"
    label = "Keyboard"
    values = (
        (KEYBOARD, "KeyboardDelay"),
        (KEYBOARD, "KeyboardSpeed"),
    )

    def export_extra(self, ctx: Context, section: dict) -> None:
        try:
            section["languages"] = parse_languages(json.loads(ctx.system.run_powershell(EXPORT_LANGUAGES)))
        except Exception as error:  # PowerShell missing or failing, or unexpected output
            ctx.warn(f"Keyboard: could not read input languages: {error}")

    def apply_extra(self, ctx: Context, section: dict) -> None:
        if "languages" not in section:
            return
        languages = parse_languages(section["languages"])
        try:
            ctx.system.run_powershell(set_languages_script(languages))
        except Exception as error:
            ctx.warn(f"Keyboard: could not set input languages: {error}")

    def after_apply(self, ctx: Context) -> None:
        for action, name in ((SPI_SETKEYBOARDDELAY, "KeyboardDelay"), (SPI_SETKEYBOARDSPEED, "KeyboardSpeed")):
            value = dword(ctx, KEYBOARD, name)
            if value is None:
                continue
            try:
                ctx.system.spi(action, value, None)
            except OSError as error:
                ctx.warn(f"Keyboard: {error}")

    def describe(self, section: dict) -> list[str]:
        lines = super().describe(section)
        for language in section.get("languages", []):
            lines.append(f"language {language.get('tag')}: {', '.join(language.get('tips', []))}")
        return lines

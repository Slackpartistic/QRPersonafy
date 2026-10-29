"""A profile can come from a phone or a server, so applying one must stay within bounds."""

import base64

import pytest

from qrpersonafy.profile import apply_profile, check_profile
from qrpersonafy.settings import BY_NAME
from qrpersonafy.settings.keyboard import parse_languages
from qrpersonafy.settings.mouse import CURSORS
from qrpersonafy.settings.taskbar import pins_folder
from qrpersonafy.settings.theme import PERSONALIZE


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def profile(settings: dict) -> dict:
    return check_profile({"format": "qrpersonafy-profile", "version": 1, "settings": settings})


def test_undeclared_registry_values_are_ignored(make_ctx):
    ctx = make_ctx()
    apply_profile(
        ctx,
        profile(
            {
                "theme": {
                    "registry": [
                        {"key": PERSONALIZE, "name": "AppsUseLightTheme", "type": "REG_DWORD", "data": 1},
                        {"key": r"Software\Microsoft\Windows\CurrentVersion\Run", "name": "evil",
                         "type": "REG_SZ", "data": "evil.exe"},
                        {"key": PERSONALIZE, "name": "SomethingElse", "type": "REG_DWORD", "data": 1},
                    ]
                },
                # Whole-key capture only accepts plain strings and numbers.
                "mouse": {"registry": [{"key": CURSORS, "name": "Arrow", "type": "REG_BINARY", "data": b64(b"x")}]},
            }
        ),
        set(BY_NAME),
    )
    written = {name for (_, name) in ctx.registry.values}
    assert written == {"appsuselighttheme"}


def test_file_names_cannot_escape_their_folder(make_ctx, tmp_path):
    ctx = make_ctx()
    apply_profile(
        ctx,
        profile(
            {
                "taskbar": {
                    "registry": [],
                    "files": {
                        "pin:a": {"name": r"..\..\..\Startup\evil.lnk", "data": b64(b"x")},
                        "pin:b": {"name": "../../evil.lnk", "data": b64(b"x")},
                        "pin:c": {"name": "payload.exe", "data": b64(b"x")},
                    },
                }
            }
        ),
        {"taskbar"},
    )
    written = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file())
    assert [p.name for p in written] == ["evil.lnk"]
    assert (pins_folder(ctx) / "evil.lnk").exists()
    assert any("payload.exe" in w for w in ctx.warnings)


@pytest.mark.parametrize(
    "languages",
    [
        [{"tag": "en-US'; Remove-Item C:\\ -Recurse; '", "tips": []}],
        [{"tag": "en-US", "tips": ["0409:00000409'); calc; ('"]}],
        [],
    ],
)
def test_language_list_is_validated(languages):
    with pytest.raises(ValueError):
        parse_languages(languages)


def test_malformed_section_is_skipped_with_warning(make_ctx):
    ctx = make_ctx()
    applied = apply_profile(
        ctx,
        profile(
            {
                "theme": {"registry": [{"key": PERSONALIZE, "name": "AppsUseLightTheme", "type": "REG_DWORD",
                                        "data": "not a number"}]},
                "accent": {"registry": []},
            }
        ),
        set(BY_NAME),
    )
    assert applied == ["accent"]
    assert any("malformed" in w for w in ctx.warnings)


@pytest.mark.parametrize("bad", [{}, {"format": "other"}, {"format": "qrpersonafy-profile", "version": 99,
                                                             "settings": {}}])
def test_rejects_non_profiles(bad):
    with pytest.raises(ValueError):
        check_profile(bad)

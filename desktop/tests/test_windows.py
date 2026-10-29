"""Runs against the real registry. Only on Windows, e.g. the CI's Windows runner."""

import json
import sys

import pytest

pytestmark = [
    pytest.mark.windows,
    pytest.mark.skipif(sys.platform != "win32", reason="needs Windows"),
]


@pytest.fixture
def ctx():
    from qrpersonafy.registry import WindowsRegistry
    from qrpersonafy.settings import Context
    from qrpersonafy.system import WindowsSystem

    return Context(WindowsRegistry(), WindowsSystem())


def test_export_reads_real_settings(ctx):
    from qrpersonafy.profile import check_profile, export_profile
    from qrpersonafy.settings import BY_NAME

    profile = check_profile(json.loads(json.dumps(export_profile(ctx, set(BY_NAME)))))
    assert profile["settings"]["mouse"]["registry"], "expected mouse settings in HKCU"
    assert profile["settings"]["keyboard"].get("languages"), ctx.warnings


def test_theme_round_trip(ctx):
    from qrpersonafy.profile import apply_profile, export_profile
    from qrpersonafy.registry import REG_DWORD, RegValue
    from qrpersonafy.settings.theme import PERSONALIZE

    original = export_profile(ctx, {"theme"})
    before = ctx.registry.get(PERSONALIZE, "AppsUseLightTheme")
    flipped = 0 if before is not None and before.data == 1 else 1
    try:
        ctx.registry.set(PERSONALIZE, "AppsUseLightTheme", RegValue(REG_DWORD, flipped))
        apply_profile(ctx, original, {"theme"})
        assert ctx.registry.get(PERSONALIZE, "AppsUseLightTheme") == before
    finally:
        if before is not None:
            ctx.registry.set(PERSONALIZE, "AppsUseLightTheme", before)

"""The desktop app's Python side, driven the way the page drives it, against fake Windows."""

import json
import threading
import urllib.request

import pytest

from qrpersonafy.gui.api import Api
from qrpersonafy.pairing import TO_PC, TO_PHONE, decode_key, open_envelope, seal
from qrpersonafy.profile import latest_backup
from qrpersonafy.registry import REG_DWORD, RegValue
from qrpersonafy.settings.theme import PERSONALIZE
from qrpersonafy.summary import summarize

from test_roundtrip import configured_pc


class Events:
    def __init__(self):
        self.items = []
        self.changed = threading.Condition()

    def __call__(self, event):
        with self.changed:
            self.items.append(event)
            self.changed.notify_all()

    def wait_for(self, kind, timeout=5):
        with self.changed:
            assert self.changed.wait_for(lambda: any(e["type"] == kind for e in self.items), timeout), self.items
            return next(e for e in self.items if e["type"] == kind)


def session_url(api, path="/v1/profile"):
    return f"http://127.0.0.1:{api._session.port}{path}"


def post(url, data):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


@pytest.fixture
def pc(make_ctx):
    ctx = configured_pc(make_ctx)
    return ctx


def test_send_shows_qr_and_summary_then_finishes(pc):
    events = Events()
    api = Api(lambda: pc, events)
    result = api.start_send()
    assert result["qr"].startswith("<svg") or "<svg" in result["qr"][:200]
    assert [i["name"] for i in result["summary"]["items"]] == [
        "wallpaper", "theme", "accent", "taskbar", "start", "mouse", "keyboard"]
    key = api._session.key
    with urllib.request.urlopen(session_url(api), timeout=5) as response:
        assert open_envelope(key, response.read(), TO_PHONE)["format"] == "qrpersonafy-profile"
    assert events.wait_for("finished") == {"type": "finished", "kind": "send", "ok": True}


def test_receive_waits_for_the_user_then_applies_only_chosen_settings(pc, make_ctx):
    target = make_ctx()
    events = Events()
    api = Api(lambda: target, events)
    from qrpersonafy.profile import export_profile
    from qrpersonafy.settings import BY_NAME

    incoming = export_profile(pc, set(BY_NAME))
    api.start_receive()
    reply = {}
    sender = threading.Thread(
        target=lambda: reply.update(result=post(session_url(api), seal(api._session.key, incoming, TO_PC))))
    sender.start()

    received = events.wait_for("received")
    assert received["summary"]["items"][0]["name"] == "wallpaper"
    api.decide(True, ["theme", "not-a-setting"])
    sender.join(10)

    assert reply["result"] == (200, {"applied": ["theme"], "warnings": []})
    assert events.wait_for("applied")["applied"] == ["Light/dark mode"]
    assert target.registry.get(PERSONALIZE, "AppsUseLightTheme") == RegValue(REG_DWORD, 0)
    assert target.registry.get(r"Control Panel\Mouse", "MouseSensitivity") is None
    assert latest_backup(target) is not None


def test_declining_tells_the_phone(make_ctx, pc):
    events = Events()
    api = Api(lambda: make_ctx(), events)
    from qrpersonafy.profile import export_profile

    api.start_receive()
    reply = {}
    sender = threading.Thread(target=lambda: reply.update(
        result=post(session_url(api), seal(api._session.key, export_profile(pc, {"theme"}), TO_PC))))
    sender.start()
    events.wait_for("received")
    api.decide(False, [])
    sender.join(10)
    assert reply["result"] == (403, {"error": "declined on the PC"})


def test_undo_restores_the_backup(make_ctx, pc):
    target = make_ctx()
    target.registry.set(PERSONALIZE, "AppsUseLightTheme", RegValue(REG_DWORD, 1))
    api = Api(lambda: target, Events())
    from qrpersonafy.profile import export_profile

    api._pending_file = export_profile(pc, {"theme"})
    assert api.apply_file(["theme"])["applied"] == ["Light/dark mode"]
    assert target.registry.get(PERSONALIZE, "AppsUseLightTheme").data == 0
    assert api.info()["has_backup"]

    result = api.undo_last()
    assert target.registry.get(PERSONALIZE, "AppsUseLightTheme").data == 1
    assert result["has_backup"] is False
    assert api.undo_last()["applied"] == []


def test_cancel_stops_a_waiting_session(make_ctx):
    import time
    import urllib.error

    events = Events()
    api = Api(lambda: make_ctx(), events)
    api.start_receive()
    url = session_url(api, "/v1/ping")
    api.cancel()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
        except urllib.error.HTTPError:
            pass  # still answering
        except (urllib.error.URLError, ConnectionError):
            break  # the server has shut down
        time.sleep(0.1)
    else:
        pytest.fail("session still serving after cancel")
    assert all(e["type"] != "finished" for e in events.items)


def test_summary_is_friendly(pc):
    from qrpersonafy.profile import export_profile
    from qrpersonafy.settings import BY_NAME

    items = {i["name"]: i for i in summarize(export_profile(pc, set(BY_NAME)))["items"]}
    assert items["wallpaper"]["image"].startswith("data:image/png;base64,")
    assert items["theme"] == {"name": "theme", "label": "Light/dark mode", "details": "Dark mode", "dark": True}
    assert items["accent"]["color"] == "#D47800"
    assert items["taskbar"]["list"] == ["Terminal"] and items["taskbar"]["details"] == "Left, 1 pinned app"
    assert items["mouse"]["details"] == "Pointer speed 14/20, Windows Black cursors"
    assert items["keyboard"]["list"] == ["en-GB", "fr-FR"]


def test_summary_survives_hostile_profiles():
    summary = summarize({"settings": {"theme": {"registry": "nope"}, "accent": [], "wallpaper": {"files": {"image": {"data": "!!"}}}}})
    assert [i["name"] for i in summary["items"]] == ["wallpaper", "theme"]


def test_applying_reports_progress_step_by_step(make_ctx, pc):
    from qrpersonafy.profile import export_profile

    events = Events()
    api = Api(make_ctx, events)
    api._pending_file = export_profile(pc, {"theme", "accent", "wallpaper"})
    api.apply_file(["theme", "accent", "wallpaper"])
    steps = [(e["done"], e["total"], e["label"]) for e in events.items if e["type"] == "progress"]
    assert steps == [
        (0, 4, "Wallpaper"),
        (1, 4, "Light/dark mode"),
        (2, 4, "Accent color"),
        (3, 4, "Finishing up"),
        (4, 4, "Done"),
    ]


def test_downloaded_marks_are_removed_from_bundled_dlls(tmp_path):
    from qrpersonafy.gui.app import unblock_dlls

    runtime = tmp_path / "_internal" / "pythonnet" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "Python.Runtime.dll").write_bytes(b"MZ")
    # Off Windows the stream is an ordinary file with the same name, which is enough to check the path.
    (runtime / "Python.Runtime.dll:Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\n")
    (tmp_path / "_internal" / "unmarked.dll").write_bytes(b"MZ")

    assert unblock_dlls(tmp_path / "_internal") == 1
    assert sorted(p.name for p in runtime.iterdir()) == ["Python.Runtime.dll"]

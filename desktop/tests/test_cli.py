import json

from qrpersonafy.cli import main


def test_show_and_dry_run(tmp_path, capsys):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "format": "qrpersonafy-profile",
                "version": 1,
                "created": "2026-10-29T00:00:00+00:00",
                "settings": {
                    "theme": {
                        "registry": [
                            {
                                "key": r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                                "name": "AppsUseLightTheme",
                                "type": "REG_DWORD",
                                "data": 0,
                            }
                        ]
                    },
                    "keyboard": {"registry": [], "languages": [{"tag": "en-US", "tips": ["0409:00000409"]}]},
                },
            }
        )
    )
    assert main(["show", str(path)]) == 0
    out = capsys.readouterr().out
    assert "AppsUseLightTheme = 0" in out
    assert "language en-US: 0409:00000409" in out

    assert main(["apply", str(path), "--dry-run", "--only", "keyboard"]) == 0
    out = capsys.readouterr().out
    assert "AppsUseLightTheme" not in out
    assert "en-US" in out


def test_bad_profile_is_an_error(tmp_path, capsys):
    path = tmp_path / "profile.json"
    path.write_text("{}")
    assert main(["show", str(path)]) == 1
    assert "not a QRPersonafy profile" in capsys.readouterr().err

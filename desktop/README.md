# QRPersonafy desktop tool

Saves this PC's personalization and applies it on another PC, either through the QRPersonafy
phone app (scan a QR code) or as a plain profile file.

## The app

Most people should use the app: download it, unzip it anywhere, and double-click
`QRPersonafy.exe` (keep the `_internal` folder next to it). No Python
or terminal needed. It shows a QR code for your phone, lets you review settings before
anything changes, backs up your current look first, and has an Undo button. A file option
is there for moving settings without a phone.

Until releases are published, the latest build is the `qrpersonafy-windows` artifact of the
"Desktop app" workflow on GitHub Actions. Windows SmartScreen may warn that the app is
unrecognized because it isn't signed yet: choose **More info**, then **Run anyway**.

To run the app from source: `python -m pip install -e .` then `qrpersonafy-gui`. To build
the .exe yourself: `python -m pip install ".[build]"` and run the `pyinstaller` command from
[.github/workflows/desktop.yml](../.github/workflows/desktop.yml).

## Command line

Everything the app does is also available as commands.

Needs Python 3.10 or newer on Windows 10 or 11.

```
cd desktop
python -m pip install -e .
```

If `qrpersonafy` isn't found afterwards, run it as `python -m qrpersonafy`.

## Use

With the phone app:

```
qrpersonafy send       # shows a QR code; scan it in the app to save this PC's settings
qrpersonafy receive    # shows a QR code; scan it and pick saved settings to apply here
```

The first time, Windows Firewall asks whether to allow Python on the network: allow it on
private networks. `receive` shows what it got and asks before applying anything. How the
transfer works is described in [docs/pairing-protocol.md](../docs/pairing-protocol.md).

With files:

```
qrpersonafy export -o my-pc.json          # save everything
qrpersonafy show my-pc.json               # see what was saved
qrpersonafy apply my-pc.json --dry-run    # see what would change
qrpersonafy apply my-pc.json              # apply it
qrpersonafy apply my-pc.json --only theme,accent,wallpaper
```

Before applying, the tool saves your current settings to
`%LOCALAPPDATA%\QRPersonafy\backups\`, so you can undo with `qrpersonafy apply <backup file>`.
Applying taskbar or Start settings restarts Explorer, so the taskbar disappears for a moment.

## What is saved

| Setting | Contents |
| --- | --- |
| `wallpaper` | The image itself and how it fits the screen |
| `theme` | Light/dark mode for apps and Windows, transparency |
| `accent` | Accent color, and whether it shows on Start, the taskbar and title bars |
| `taskbar` | Alignment, buttons, position, auto-hide and pinned apps |
| `start` | Pinned apps (Windows 11 `start2.bin`) and layout options |
| `mouse` | Pointer speed and acceleration, button swap, double-click, scrolling, cursor scheme |
| `keyboard` | Repeat delay and rate, input languages and keyboard layouts |

## Known limits

- Pinned apps only come back for apps that are installed on the new PC.
- Slideshow and Spotlight wallpapers are saved as the single image currently showing.
- Some newer Windows builds block writing a few taskbar values (such as the Widgets button);
  those are reported as warnings and the rest still applies.
- Windows 10's Start tiles are not restored yet.

## Profiles are untrusted input

A profile can arrive from a phone or a backup server, so `apply` only writes the registry values
and files listed in `src/qrpersonafy/settings/`. Unknown keys, unexpected value types and file
names with folder parts are ignored, and input language codes are checked before they reach
PowerShell.

## Develop

```
pip install -e ".[test]"
python -m pytest
```

Tests use an in-memory registry, so they run anywhere. `tests/test_windows.py` also runs
against the real registry when on Windows.

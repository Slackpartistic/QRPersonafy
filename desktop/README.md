# QRPersonafy desktop tool

Saves this PC's personalization to a profile file and applies it on another PC. Later steps
will add the QR pairing with the phone app; for now profiles are plain files you can copy.

## Install

Needs Python 3.10 or newer on Windows 10 or 11.

```
cd desktop
pip install -e .
```

## Use

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

# QRPersonafy on Linux

The Linux app works on any distribution. What matters is the **desktop environment**, because
that's what decides where settings live: Ubuntu, Fedora Workstation and Debian all run GNOME and
keep settings the same way, while Kubuntu, Fedora KDE and openSUSE run KDE Plasma.

## Supported desktops

| Setting | GNOME | KDE Plasma 5/6 | Cinnamon | MATE | Xfce |
| --- | --- | --- | --- | --- | --- |
| Wallpaper and fit | yes | yes | yes | yes | yes, every monitor |
| Light/dark mode | yes | Breeze light/dark | yes | if the theme has a dark twin | if the theme has a dark twin |
| Accent color | GNOME 47+, or Ubuntu's Yaru colors | yes | Mint-Y colors | Mint-Y colors | no (theme decides) |
| Taskbar | dock favorites; Ubuntu Dock position and auto-hide | panel position, auto-hide, pinned apps | panel position, auto-hide, pinned apps | not yet | not yet |
| Mouse | speed, acceleration, buttons, double-click, cursor | same, live on Wayland | same | same | speed, buttons, double-click, cursor |
| Keyboard | repeat, layouts (input methods kept) | repeat, layouts | repeat, layouts | repeat, layouts | repeat, layouts |

GNOME covers Ubuntu, Fedora Workstation, Debian, Zorin, Pop!_OS 22.04, and also works for
Budgie and Pantheon, which use GNOME's settings. Cinnamon is Linux Mint's default. Other
desktops (COSMIC, LXQt, tiling window managers) aren't supported yet: the app says so and
changes nothing.

Start menu pins have no Linux equivalent and are skipped with a note. The app unticks
anything the desktop can't use when it shows what's about to change.

## Moving between Windows and Linux

A profile saved on either system applies on the other. Windows profiles keep raw registry
values; Linux profiles keep a "portable" block in each setting. Each side translates:

| Windows | Linux |
| --- | --- |
| Pointer speed 1–20 (10 is normal) | speed −1 to 1 (0 is normal) |
| "Enhance pointer precision" | acceleration on, or the flat profile when off |
| Swap mouse buttons | left-handed |
| Key repeat delay 0–3 and speed 0–31 | delay and interval in milliseconds |
| Keyboard layouts (e.g. `0407:00000407`) | XKB layouts (`de`); about 50 common layouts are mapped, input methods such as Japanese are reported instead |
| Accent color | the closest color the desktop offers, when it has a fixed palette |
| Pinned taskbar shortcuts | apps found by name (`Firefox` matches "Firefox Web Browser"); File Explorer, Terminal, Settings and Microsoft Store stand in for the Linux app doing the same job |
| Taskbar position and auto-hide | dock or panel position and auto-hide |
| Apps and Windows light/dark | one switch; the "apps" setting wins |

Going the other way, Windows can't pin apps from a Linux profile (it needs shortcut files Linux
doesn't have) and keeps its taskbar at the bottom; it says so.

The portable format is described at the top of
[desktop/src/qrpersonafy/portable.py](../desktop/src/qrpersonafy/portable.py). Like the rest of a
profile it's untrusted input: every value is type and range checked, and names that reach
desktop tools are passed as separate arguments, never through a shell.

## Adding a desktop

Each desktop is a `Desktop` subclass in
[desktop/src/qrpersonafy/linux/](../desktop/src/qrpersonafy/linux/) with an
`export_<setting>(ctx, files)` and `apply_<setting>(ctx, values, section)` method per setting
it supports, and the names it uses in `XDG_CURRENT_DESKTOP`. Settings without methods are
skipped with a message. A separate package can add one without changing this repo by
publishing the class under the `qrpersonafy.desktops` entry point group:

```toml
[project.entry-points."qrpersonafy.desktops"]
lxqt = "qrpersonafy_lxqt:Lxqt"
```

Tests run each desktop against a fake command runner (`linux/runner.py`), plus GNOME
against the real `gsettings` when the machine has GNOME's schemas.

## Firewall

Pairing needs the phone to reach the PC on a random port. Ubuntu, Mint, Debian and Fedora
Workstation allow that by default. If yours blocks it (openSUSE, some Arch setups, or Ubuntu
with `ufw` turned on), the phone says it couldn't reach the PC. Allow your phone's address while you
pair (with ufw: `sudo ufw allow from 192.168.1.23`, using the address in the phone's Wi-Fi
settings), or use the file option instead.

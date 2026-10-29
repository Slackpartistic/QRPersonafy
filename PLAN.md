# QRPersonafy: Project Plan

Restore your Windows personalization on a fresh install by scanning a QR code with your phone.

## Goal

An open-source tool that saves your Windows look and feel, keeps it on your phone, and puts it back on a new Windows install in a minute. No Microsoft account and no vendor cloud. You own your data.

## Why this exists

- **Windows Backup** (built in) restores themes, Start pins and some settings, but only through a Microsoft account and OneDrive.
- **Single-purpose tools** such as Sordum's *Backup Start Menu Layout* cover one setting each.
- **USMT** (User State Migration Tool) is built for IT departments, not individuals.

No open-source tool keeps settings on the phone, restores them with a QR scan, and backs up to storage the user controls.

## Scope (v1)

| Area | Included |
| --- | --- |
| Wallpaper | Image and fit mode |
| Theme | Light/dark mode for apps and system |
| Accent color | Color, and whether it shows on Start, taskbar and title bars |
| Taskbar | Pinned apps, alignment, visible buttons |
| Start menu | Pinned apps and layout |
| Mouse | Pointer speed, scheme, button swap, scroll lines |
| Keyboard | Repeat delay and rate, input languages/layouts |

Out of scope for v1: files, installed apps, browser data.

## Architecture

```
 Windows PC (desktop app)             Phone (mobile app)            Own server (optional)
 ------------------------             ------------------            ---------------------
 export settings -> profile  --QR-->  stores encrypted profile  -->  encrypted backup blob
 apply profile <- settings   <-Wi-Fi- sends profile back        <--  restore after phone reset
```

- **Desktop app:** Python. Reads and writes the registry and settings files, and shows the pairing QR code.
- **Mobile app:** Flutter. Scans the QR code, holds the profiles, and handles backup.
- **Pairing:** the QR code holds the PC's local address and a one-time key. The profile moves over the local network, encrypted with that key.
- **Backup:** the phone encrypts profiles before uploading them, so the server only ever sees ciphertext. Targets: a small Docker server we provide, Nextcloud or any WebDAV share.

## Steps

1. **Windows export and import.** A Python CLI that exports the in-scope settings to a single profile file and applies it on another PC. Tested in a Windows VM. Start and taskbar layouts are the riskiest part, so they come first.
2. **Phone app and QR pairing.** A Flutter app that scans the desktop's QR code and sends and receives profiles over Wi-Fi.
3. **Self-hosted backup.** End-to-end encrypted backup from the phone to the user's own storage, plus a setup guide.
4. **Open-source release.** License, README, contribution guide, and installers for both apps.

## Open questions

- License choice (MIT or GPL-3.0).
- Whether the desktop app should be packaged as a single .exe (PyInstaller) or through winget.
- Whether to support several saved profiles per phone.

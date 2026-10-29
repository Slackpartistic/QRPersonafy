# QRPersonafy

Restore your Windows personalization on a fresh install by scanning a QR code with your phone.

QRPersonafy saves your wallpaper, light/dark mode, accent color, taskbar and Start layouts, and mouse and keyboard settings. It keeps them on your phone, and puts them back on a new Windows install. No Microsoft account and no vendor cloud: your data stays on your phone, with optional encrypted backup to a server you run yourself.

> **Status:** planning. See [PLAN.md](PLAN.md) for scope, architecture and roadmap.

## How it will work

1. Install the desktop app on your Windows PC and the mobile app on your phone.
2. The desktop app shows a QR code. Scan it with your phone to save your current settings.
3. On a fresh Windows install, open the desktop app, scan its QR code, and your settings are applied.

## Components

- **Desktop app** (Python): exports and applies Windows settings.
- **Mobile app** (Flutter): stores profiles and pairs with the PC by QR code.
- **Backup server** (optional, self-hosted): stores end-to-end encrypted backups.

## Contributing

The project is just getting started. Issues and ideas are welcome.

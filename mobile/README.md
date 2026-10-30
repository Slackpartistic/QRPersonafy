# QRPersonafy phone app

Flutter app that keeps your PCs' saved settings and moves them to and from the desktop tool by scanning its QR code. Android is the tested platform; the iOS project builds but has not been tried on a device.

## Install a test build (Android)

Every push builds an APK. Open the repository's **Actions** tab, pick the latest **Mobile app** run, download the `qrpersonafy-android` artifact, unzip it, and open `app-release.apk` on your phone. Android asks you to allow installing apps from that source.

The test build is signed with a development key, so it can't be installed over a later store build.

## Use

1. **Save a PC:** open QRPersonafy on the PC and choose **Save this PC**. On the phone tap **Scan PC code**, scan, name it, save.
2. **Restore a PC:** open QRPersonafy on the new PC and choose **Restore from phone**. Scan, pick a saved PC, tap **Send**, then choose **Apply to this PC** on the PC.

The phone and PC must be on the same Wi-Fi. When testing with a virtual machine, set its network adapter to **Bridged** so the phone can reach it.

## Privacy

- Transfers are encrypted with a one-time key from the QR code ([protocol](../docs/pairing-protocol.md)).
- Saved profiles are encrypted on the phone with a key kept in Android's secure storage.
- Android cloud backup is turned off for the app. Instead, you can back up to your own server (tap the cloud icon): Nextcloud, any WebDAV server, or the Docker server in [backup-server/](../backup-server/README.md). Backups are encrypted on the phone with a key shown once as a recovery code ([format](../docs/backup.md)).

## Develop

```
flutter pub get
flutter analyze
flutter test
```

`tool/cross_check.dart` talks to a real desktop session: run `qrpersonafy send` or `receive`, then `dart run tool/cross_check.dart '<text of the QR code>'`.

# Backup format

The phone backs up to any WebDAV folder the user chooses (the Docker server in
[backup-server/](../backup-server/), Nextcloud, …). The server is untrusted: it only ever
sees ciphertext and file names that are random ids.

## Key

When backup is set up on an empty folder, the phone makes a random 256-bit **backup key**.
It is shown once as a **recovery code** (base32, 52 characters in groups of four,
`ABCD-EFGH-…`) and kept in Android secure storage together with the server login. It is not
the phone's at-rest key, which never leaves the phone and is lost with it.

## Files

All files use the envelope from [pairing-protocol.md](pairing-protocol.md) (`QRP1`, nonce,
AES-256-GCM of gzipped JSON) with the backup key and AAD `QRP1|backup`.

| File | Contents |
| --- | --- |
| `key-check.qrpb` | `{"format": "qrpersonafy-backup", "version": 1}`. Lets a new phone check a recovery code before downloading anything else. |
| `<id>.qrpb` | `{"meta": {...}, "profile": {...}, "thumbnail": "<base64 PNG>"}` for one saved PC. `<id>` is the profile's 16-hex-digit id on the phone; `meta` is the phone's list entry (name, PC name, date, settings, accent, dark mode). |

## Sync

- **Back up** uploads every saved PC whose `<id>.qrpb` isn't in the folder yet. It runs after
  a PC is saved and from **Back up now**. Renaming a PC uploads it again.
- **Restore** downloads every `<id>.qrpb` whose id isn't on the phone. Ids that aren't 16 hex
  digits are ignored, so a hostile server can't choose file paths on the phone.
- **Delete** on the phone also deletes `<id>.qrpb` from the folder.
- Nothing is ever deleted from the server automatically, so a new, empty phone can't wipe a
  backup.

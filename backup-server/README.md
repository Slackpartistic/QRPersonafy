# Back up QRPersonafy to your own server

The phone app can keep a copy of your saved PCs on a server you control, so they survive a
lost, reset or replaced phone. There is no QRPersonafy cloud.

Everything is encrypted on the phone before it is uploaded, with a key only your phone and
your **recovery code** know. The server stores unreadable files, and whoever runs it can't
open them. How it works: [docs/backup.md](../docs/backup.md).

You need one of these:

- **A Nextcloud or ownCloud account** you already have. Skip to [Use Nextcloud](#use-nextcloud).
- **Any PC, NAS or Raspberry Pi** that can run Docker and stays on. Follow the next section.
- **Any other WebDAV server** (Synology WebDAV Server, Apache mod_dav, …). Use its folder
  address the same way.

## Run the QRPersonafy backup server (Docker)

1. Install Docker ([Docker Desktop](https://docs.docker.com/get-docker/) on Windows or Mac, or
   Docker Engine on Linux).
2. Download this folder (`backup-server`) onto that machine.
3. Copy `.env.example` to `.env` and set your own user name and a long password.
4. In this folder, run:

   ```
   docker compose up -d
   ```

5. Find the machine's address on your network, e.g. `192.168.1.20` (on Windows: `ipconfig`, the
   IPv4 address; on Linux: `hostname -I`).
6. On the phone, open QRPersonafy, tap the **cloud** icon (or **Restore from your backup** on
   a new phone) and enter:
   - **Server address:** `http://192.168.1.20:8080/QRPersonafy`
   - **User name** and **Password** from your `.env`
7. Tap **Connect**, then **write down the recovery code** it shows. You need it on a new phone.

Backups are stored in `./data`. Copy that folder somewhere safe now and then if you want a
second copy; it's already encrypted.

On Windows, allow Docker through the firewall when asked, on private networks.

### Reaching it from outside your home

The setup above works when the phone is on the same network as the server. The files are
end-to-end encrypted either way, but plain `http://` sends the server password readably,
so don't open port 8080 to the internet. To back up from anywhere, either:

- put both the server and the phone on [Tailscale](https://tailscale.com) and use the
  server's Tailscale address, or
- put the server behind a reverse proxy with HTTPS, such as
  [Caddy](https://caddyserver.com/docs/quick-starts/reverse-proxy), and use the
  `https://` address.

### Update or stop

```
docker compose pull && docker compose up -d   # update
docker compose down                           # stop (your backups stay in ./data)
```

## Use Nextcloud

1. In Nextcloud, open **Settings → Security** and create an **app password** for
   QRPersonafy. Don't use your main password.
2. Find your WebDAV address: in the Files app, open **Files settings** (bottom left).
   It looks like `https://cloud.example.com/remote.php/dav/files/USERNAME/`.
3. On the phone, open QRPersonafy, tap the **cloud** icon and enter:
   - **Server address:** your WebDAV address followed by `QRPersonafy`, e.g.
     `https://cloud.example.com/remote.php/dav/files/USERNAME/QRPersonafy`
   - **User name:** your Nextcloud user name
   - **Password:** the app password
4. Tap **Connect** and write down the recovery code.

## On a new phone

Install QRPersonafy, tap **New phone? Restore from your backup**, enter the same server
details, then your recovery code. Your saved PCs come back.

## If you lose the recovery code

The backups can't be opened without it, by you or anyone else. If your phone still works,
open the backup screen and tap **Show recovery code**. If not, the backups are gone; start
a new backup in an empty folder.

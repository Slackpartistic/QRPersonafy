# Pairing protocol (v1)

How the desktop tool and the phone app move a profile between each other over the local network. The QR code is the only secret channel: it carries a one-time key, and everything sent over Wi-Fi is encrypted with that key.

## Roles

The **desktop is always the server** and shows the QR code. The **phone is always the client** and scans it.

| Desktop command | Direction | What the phone does |
| --- | --- | --- |
| `qrpersonafy send` | PC → phone | Downloads this PC's profile and stores it |
| `qrpersonafy receive` | phone → PC | Uploads a stored profile, which the PC applies |

## QR code

The QR code holds a URI:

```
qrpersonafy://pair?v=1&m=send&h=192.168.1.20,10.0.0.5&p=48213&k=<key>&n=DESKTOP-ABC
```

| Field | Meaning |
| --- | --- |
| `v` | Protocol version, `1` |
| `m` | `send` (phone downloads) or `receive` (phone uploads) |
| `h` | Comma-separated IPv4 addresses of the PC; the phone tries each |
| `p` | TCP port |
| `k` | 32-byte random key, base64url without padding (43 characters) |
| `n` | PC name, shown on the phone; display only |

A session lasts until one transfer succeeds or 10 minutes pass. Every session has a new key.

## Envelope

Every request or response body that carries a profile is an envelope:

```
"QRP1" (4 bytes) || nonce (12 bytes) || AES-256-GCM ciphertext with 16-byte tag
```

- Plaintext: the profile JSON, UTF-8, gzip-compressed.
- Additional authenticated data: `QRP1|to-phone` for `send`, `QRP1|to-pc` for `receive`. This stops a message for one direction from being replayed in the other.
- Nonce: 12 random bytes, new for every envelope.

`protocol/envelope-v1.json` holds a fixed example that both the Python and Dart tests check, so the two implementations stay compatible.

## HTTP

Plain HTTP on the PC's local address. Confidentiality and integrity come from the envelope, not from TLS.

| Mode | Request | Success | Errors |
| --- | --- | --- | --- |
| both | `GET /v1/ping` | `200`, `{"v": 1, "mode": "send"}` or `"receive"` | none; never uses up the session |
| `send` | `GET /v1/profile` | `200`, body is an envelope (`to-phone`) | `410` session already used or expired |
| `receive` | `POST /v1/profile`, body is an envelope (`to-pc`) | `200`, body `{"applied": [...], "warnings": [...]}` | `400` cannot decrypt or not a profile, `403` user declined, `410` used or expired, `413` too large |

The phone pings every address from the QR code at once and uses the first that answers, so an address it can't reach (another network adapter, a VM's internal network) costs no extra time. Any HTTP answer counts as reachable.

A `send` session closes after the first successful download. A `receive` session closes after the first envelope that decrypts, whether or not the user accepts it. Bodies over 64 MB are refused.

## Security notes

- Anyone on the same network can reach the port, but without the key from the QR code they can neither read a profile nor send one the PC will accept.
- On `receive`, the PC shows what the profile contains and asks before applying. The usual profile checks apply (only declared settings are written), and current settings are backed up first.
- Windows Firewall asks the first time the desktop tool listens. Allow it on private networks.

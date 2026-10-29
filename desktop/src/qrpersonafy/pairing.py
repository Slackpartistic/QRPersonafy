"""Moving profiles between this PC and the phone app. See docs/pairing-protocol.md."""

from __future__ import annotations

import base64
import gzip
import json
import os
import secrets
import socket
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"QRP1"
TO_PHONE = b"QRP1|to-phone"
TO_PC = b"QRP1|to-pc"
NONCE_SIZE = 12
MAX_BODY = 64 * 1024 * 1024
SESSION_SECONDS = 10 * 60


class EnvelopeError(ValueError):
    pass


def new_key() -> bytes:
    return secrets.token_bytes(32)


def encode_key(key: bytes) -> str:
    return base64.urlsafe_b64encode(key).rstrip(b"=").decode("ascii")


def decode_key(text: str) -> bytes:
    key = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    if len(key) != 32:
        raise ValueError("key must be 32 bytes")
    return key


def seal(key: bytes, profile: dict, direction: bytes, nonce: bytes | None = None) -> bytes:
    plaintext = gzip.compress(json.dumps(profile, separators=(",", ":")).encode("utf-8"), mtime=0)
    nonce = nonce or os.urandom(NONCE_SIZE)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, plaintext, direction)


def open_envelope(key: bytes, data: bytes, direction: bytes) -> dict:
    if len(data) < len(MAGIC) + NONCE_SIZE + 16 or not data.startswith(MAGIC):
        raise EnvelopeError("not a QRPersonafy envelope")
    nonce = data[len(MAGIC) : len(MAGIC) + NONCE_SIZE]
    try:
        plaintext = AESGCM(key).decrypt(nonce, data[len(MAGIC) + NONCE_SIZE :], direction)
    except InvalidTag:
        raise EnvelopeError("could not decrypt: wrong key or tampered data") from None
    try:
        return json.loads(gzip.decompress(plaintext))
    except (OSError, ValueError) as error:
        raise EnvelopeError(f"decrypted data is not a profile: {error}") from None


def pair_uri(mode: str, hosts: list[str], port: int, key: bytes, name: str) -> str:
    query = urlencode({"v": 1, "m": mode, "h": ",".join(hosts), "p": port, "k": encode_key(key), "n": name})
    return f"qrpersonafy://pair?{query}"


def local_ipv4s() -> list[str]:
    """This PC's LAN addresses, most likely first."""
    addresses = []
    try:
        # Connecting a UDP socket sends nothing; it only picks the outgoing interface.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            addresses.append(probe.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in addresses and not address.startswith("127."):
                addresses.append(address)
    except OSError:
        pass
    return addresses


# Called with a received profile; returns (HTTP status, JSON reply).
OnReceive = Callable[[dict], tuple[int, dict]]


class PairingSession:
    """One send or receive transfer, served over HTTP until it succeeds or expires."""

    def __init__(self, mode: str, *, profile: dict | None = None, on_receive: OnReceive | None = None,
                 port: int = 0, key: bytes | None = None, timeout: float = SESSION_SECONDS) -> None:
        if mode == "send" and profile is None or mode == "receive" and on_receive is None:
            raise ValueError("send needs a profile, receive needs on_receive")
        self.mode = mode
        self.key = key or new_key()
        self.deadline = time.monotonic() + timeout
        self.done = False
        self.result: dict | None = None
        self._payload = seal(self.key, profile, TO_PHONE) if mode == "send" else b""
        self._on_receive = on_receive
        self._server = HTTPServer(("0.0.0.0", port), self._handler())
        self._server.timeout = 0.5

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def uri(self, hosts: list[str] | None = None, name: str | None = None) -> str:
        return pair_uri(self.mode, hosts or local_ipv4s() or ["127.0.0.1"], self.port, self.key,
                        name or socket.gethostname())

    def serve(self) -> bool:
        """Block until one transfer succeeds (True) or the session expires (False)."""
        try:
            while not self.done and time.monotonic() < self.deadline:
                self._server.handle_request()
        finally:
            self._server.server_close()
        return self.done

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        session = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # keep the terminal for the QR code
                pass

            def _reply(self, status: int, body: bytes, content_type: str = "application/json") -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _json(self, status: int, obj: dict) -> None:
                self._reply(status, json.dumps(obj).encode("utf-8"))

            def _closed(self) -> bool:
                if session.done or time.monotonic() >= session.deadline:
                    self._json(410, {"error": "session is over, start a new one on the PC"})
                    return True
                return False

            def do_GET(self):
                if self.path == "/v1/ping":
                    # Lets the phone find which of the PC's addresses it can reach, without using up the session.
                    return self._json(200, {"v": 1, "mode": session.mode})
                if self.path != "/v1/profile" or session.mode != "send":
                    return self._json(404, {"error": "not found"})
                if self._closed():
                    return
                self._reply(200, session._payload, "application/octet-stream")
                session.done = True

            def do_POST(self):
                if self.path != "/v1/profile" or session.mode != "receive":
                    return self._json(404, {"error": "not found"})
                if self._closed():
                    return
                try:
                    length = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    length = -1
                if length < 0:
                    return self._json(411, {"error": "Content-Length required"})
                if length > MAX_BODY:
                    return self._json(413, {"error": "profile too large"})
                body = self.rfile.read(length)
                try:
                    profile = open_envelope(session.key, body, TO_PC)
                except EnvelopeError as error:
                    return self._json(400, {"error": str(error)})
                # A correct key proves the sender scanned this session's QR code: one try only.
                session.done = True
                status, reply = session._on_receive(profile)
                session.result = reply
                self._json(status, reply)

        return Handler

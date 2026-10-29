import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from qrpersonafy.pairing import (
    TO_PC,
    TO_PHONE,
    EnvelopeError,
    PairingSession,
    decode_key,
    encode_key,
    new_key,
    open_envelope,
    seal,
)

VECTOR = json.loads((Path(__file__).parents[2] / "protocol" / "envelope-v1.json").read_text())
PROFILE = {"format": "qrpersonafy-profile", "version": 1, "settings": {"theme": {"registry": []}}}


def test_shared_vector():
    key = decode_key(VECTOR["key"])
    envelope = bytes.fromhex(VECTOR["envelope_hex"])
    assert open_envelope(key, envelope, TO_PHONE) == VECTOR["profile"]
    # Gzip output varies between zlib builds, so a fresh seal can't be compared byte for byte.
    resealed = seal(key, VECTOR["profile"], TO_PHONE, bytes.fromhex(VECTOR["nonce_hex"]))
    assert resealed[:16] == envelope[:16]
    assert open_envelope(key, resealed, TO_PHONE) == VECTOR["profile"]


def test_envelope_rejects_wrong_key_direction_and_tampering():
    key = new_key()
    envelope = seal(key, PROFILE, TO_PC)
    assert open_envelope(key, envelope, TO_PC) == PROFILE
    with pytest.raises(EnvelopeError):
        open_envelope(new_key(), envelope, TO_PC)
    with pytest.raises(EnvelopeError):
        open_envelope(key, envelope, TO_PHONE)
    tampered = envelope[:-1] + bytes([envelope[-1] ^ 1])
    with pytest.raises(EnvelopeError):
        open_envelope(key, tampered, TO_PC)
    with pytest.raises(EnvelopeError):
        open_envelope(key, b"junk", TO_PC)


def test_key_encoding():
    key = new_key()
    assert len(encode_key(key)) == 43
    assert decode_key(encode_key(key)) == key


def run(session):
    thread = threading.Thread(target=session.serve, daemon=True)
    thread.start()
    return thread, f"http://127.0.0.1:{session.port}/v1/profile"


def request(url, data=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def test_send_serves_profile_once():
    session = PairingSession("send", profile=PROFILE)
    thread, url = run(session)
    ping = url.replace("/v1/profile", "/v1/ping")
    assert request(ping) == (200, b'{"v": 1, "mode": "send"}')
    assert request(ping)[0] == 200 and not session.done
    assert "m=send" in session.uri(["10.0.0.5"], "PC") and "h=10.0.0.5" in session.uri(["10.0.0.5"], "PC")
    status, body = request(url)
    assert status == 200
    assert open_envelope(session.key, body, TO_PHONE) == PROFILE
    thread.join(timeout=5)
    assert session.done and not thread.is_alive()


def test_receive_rejects_bad_envelopes_then_accepts_good_one():
    received = []
    session = PairingSession("receive", on_receive=lambda p: (received.append(p), (200, {"applied": ["theme"]}))[1])
    thread, url = run(session)

    status, body = request(url, seal(new_key(), PROFILE, TO_PC))
    assert status == 400 and not session.done
    status, body = request(url, seal(session.key, PROFILE, TO_PHONE))
    assert status == 400 and not session.done

    status, body = request(url, seal(session.key, PROFILE, TO_PC))
    assert status == 200 and json.loads(body) == {"applied": ["theme"]}
    assert received == [PROFILE]
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_receive_wrong_method_and_expiry():
    session = PairingSession("receive", on_receive=lambda p: (200, {}), timeout=1.5)
    thread, url = run(session)
    assert request(url)[0] == 404
    time.sleep(1.6)
    thread.join(timeout=5)
    assert not session.done and not thread.is_alive()

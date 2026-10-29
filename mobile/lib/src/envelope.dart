// Encrypted envelopes shared with the desktop tool. See docs/pairing-protocol.md.

import 'dart:convert';
import 'dart:io' show gzip;
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';

final _magic = ascii.encode('QRP1');
const _nonceSize = 12;
const _tagSize = 16;

/// Additional authenticated data for each direction, so a message can't be replayed the other way.
final toPhone = ascii.encode('QRP1|to-phone');
final toPc = ascii.encode('QRP1|to-pc');

/// Used for profiles stored on the phone, encrypted with the phone's own key.
final atRest = ascii.encode('QRP1|at-rest');

final _aes = AesGcm.with256bits();

class EnvelopeException implements Exception {
  EnvelopeException(this.message);
  final String message;
  @override
  String toString() => message;
}

Future<Uint8List> seal(List<int> key, Object? json, List<int> aad, {List<int>? nonce}) async {
  final plaintext = gzip.encode(utf8.encode(jsonEncode(json)));
  final box = await _aes.encrypt(
    plaintext,
    secretKey: SecretKey(key),
    nonce: nonce ?? _aes.newNonce(),
    aad: aad,
  );
  return Uint8List.fromList([..._magic, ...box.nonce, ...box.cipherText, ...box.mac.bytes]);
}

Future<Object?> openEnvelope(List<int> key, List<int> data, List<int> aad) async {
  if (data.length < _magic.length + _nonceSize + _tagSize ||
      !_startsWith(data, _magic)) {
    throw EnvelopeException('Not a QRPersonafy envelope');
  }
  final nonceEnd = _magic.length + _nonceSize;
  final box = SecretBox(
    data.sublist(nonceEnd, data.length - _tagSize),
    nonce: data.sublist(_magic.length, nonceEnd),
    mac: Mac(data.sublist(data.length - _tagSize)),
  );
  final List<int> plaintext;
  try {
    plaintext = await _aes.decrypt(box, secretKey: SecretKey(key), aad: aad);
  } on SecretBoxAuthenticationError {
    throw EnvelopeException('Could not decrypt: wrong key or damaged data');
  }
  try {
    return jsonDecode(utf8.decode(gzip.decode(plaintext)));
  } on FormatException catch (error) {
    throw EnvelopeException('Decrypted data is not a profile: ${error.message}');
  }
}

bool _startsWith(List<int> data, List<int> prefix) {
  for (var i = 0; i < prefix.length; i++) {
    if (data[i] != prefix[i]) return false;
  }
  return true;
}

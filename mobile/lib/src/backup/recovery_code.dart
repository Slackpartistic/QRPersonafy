// The backup key, written as a code people can copy down: 32 random bytes in base32,
// in groups of four, e.g. "K7QF-3M2A-…".

import 'dart:math';

const _alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

List<int> newBackupKey() {
  final random = Random.secure();
  return List.generate(32, (_) => random.nextInt(256));
}

String formatRecoveryCode(List<int> key) {
  final buffer = StringBuffer();
  var bits = 0, value = 0;
  for (final byte in key) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      buffer.write(_alphabet[(value >> (bits - 5)) & 31]);
      bits -= 5;
    }
  }
  if (bits > 0) buffer.write(_alphabet[(value << (5 - bits)) & 31]);
  final text = buffer.toString();
  return [for (var i = 0; i < text.length; i += 4) text.substring(i, min(i + 4, text.length))].join('-');
}

/// Reads a typed recovery code. Spaces, dashes and case don't matter, and the digits people
/// often type for look-alike letters (0, 1, 8) are read as O, I and B.
List<int> parseRecoveryCode(String code) {
  final text = code
      .toUpperCase()
      .replaceAll(RegExp(r'[\s-]'), '')
      .replaceAll('0', 'O')
      .replaceAll('1', 'I')
      .replaceAll('8', 'B');
  if (text.length != 52 || text.split('').any((c) => !_alphabet.contains(c))) {
    throw const FormatException('A recovery code has 52 letters and digits, like ABCD-EFGH-…');
  }
  final bytes = <int>[];
  var bits = 0, value = 0;
  for (final char in text.split('')) {
    value = ((value << 5) | _alphabet.indexOf(char)) & 0xFFFF;
    bits += 5;
    if (bits >= 8) {
      bytes.add((value >> (bits - 8)) & 0xFF);
      bits -= 8;
    }
  }
  return bytes.sublist(0, 32);
}

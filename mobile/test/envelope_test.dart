import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:qrpersonafy/src/envelope.dart';

void main() {
  // Written by the desktop tool's tests; see docs/pairing-protocol.md.
  final vector = jsonDecode(File('../protocol/envelope-v1.json').readAsStringSync()) as Map<String, dynamic>;
  final key = base64Url.decode(base64Url.normalize(vector['key'] as String));

  List<int> hex(String s) => [for (var i = 0; i < s.length; i += 2) int.parse(s.substring(i, i + 2), radix: 16)];

  test('opens the envelope the desktop tool made', () async {
    final opened = await openEnvelope(key, hex(vector['envelope_hex'] as String), toPhone);
    expect(opened, vector['profile']);
  });

  test('round trips and rejects wrong key, direction and tampering', () async {
    final profile = {'format': 'qrpersonafy-profile', 'version': 1, 'settings': {}};
    final sealed = await seal(key, profile, toPc);
    expect(await openEnvelope(key, sealed, toPc), profile);
    await expectLater(openEnvelope(key, sealed, toPhone), throwsA(isA<EnvelopeException>()));
    await expectLater(openEnvelope(List.filled(32, 7), sealed, toPc), throwsA(isA<EnvelopeException>()));
    final tampered = [...sealed]..[sealed.length - 1] ^= 1;
    await expectLater(openEnvelope(key, tampered, toPc), throwsA(isA<EnvelopeException>()));
    await expectLater(openEnvelope(key, [1, 2, 3], toPc), throwsA(isA<EnvelopeException>()));
  });
}

import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:qrpersonafy/src/envelope.dart';
import 'package:qrpersonafy/src/pairing.dart';

final key = List<int>.generate(32, (i) => i);
final keyText = base64Url.encode(key).replaceAll('=', '');
final profile = {'format': 'qrpersonafy-profile', 'version': 1, 'settings': {'theme': {'registry': []}}};

PairRequest request(String mode, {String hosts = '10.0.0.9,192.168.1.20'}) =>
    PairRequest.parse('qrpersonafy://pair?v=1&m=$mode&h=$hosts&p=48213&k=$keyText&n=DESKTOP-1');

void main() {
  group('PairRequest.parse', () {
    test('reads every field', () {
      final r = request('send');
      expect(r.mode, PairMode.send);
      expect(r.hosts, ['10.0.0.9', '192.168.1.20']);
      expect(r.port, 48213);
      expect(r.key, key);
      expect(r.pcName, 'DESKTOP-1');
      expect(r.url('10.0.0.9').toString(), 'http://10.0.0.9:48213/v1/profile');
    });

    test('drops hosts that are not IPv4 addresses', () {
      expect(request('send', hosts: 'evil.example,999.1.1.1,10.0.0.9').hosts, ['10.0.0.9']);
    });

    for (final bad in [
      'https://example.com',
      'qrpersonafy://pair?v=2&m=send&h=10.0.0.9&p=1&k=$keyText',
      'qrpersonafy://pair?v=1&m=steal&h=10.0.0.9&p=1&k=$keyText',
      'qrpersonafy://pair?v=1&m=send&h=evil.example&p=1&k=$keyText',
      'qrpersonafy://pair?v=1&m=send&h=10.0.0.9&p=70000&k=$keyText',
      'qrpersonafy://pair?v=1&m=send&h=10.0.0.9&p=1&k=short',
    ]) {
      test('rejects $bad', () => expect(() => PairRequest.parse(bad), throwsFormatException));
    }
  });

  group('PairingClient', () {
    test('download uses whichever address answers, without waiting on dead ones', () async {
      final requests = <String>[];
      final client = MockClient((req) async {
        requests.add('${req.url.host}${req.url.path}');
        if (req.url.host == '10.0.0.9') {
          // An address the phone can't reach just hangs; the 4 s ping timeout must not be needed.
          await Completer<void>().future;
        }
        if (req.url.path == '/v1/ping') return http.Response('{"v":1,"mode":"send"}', 200);
        return http.Response.bytes(await seal(key, profile, toPhone), 200);
      });
      final stopwatch = Stopwatch()..start();
      final result = await PairingClient(client: client).download(request('send'));
      expect(result, profile);
      expect(stopwatch.elapsed, lessThan(const Duration(seconds: 2)));
      expect(requests, containsAllInOrder(['192.168.1.20/v1/ping', '192.168.1.20/v1/profile']));
      expect(requests, isNot(contains('10.0.0.9/v1/profile')));
    });

    test('reports an unreachable PC when no address answers', () async {
      final client = MockClient((req) async => throw http.ClientException('unreachable'));
      await expectLater(
        PairingClient(client: client).download(request('send')),
        throwsA(isA<PairingException>().having((e) => e.message, 'message', contains('same Wi-Fi'))),
      );
    });

    test('download explains an expired code', () async {
      final client = MockClient(
          (req) async => req.url.path == '/v1/ping' ? http.Response('{}', 200) : http.Response('{"error":"over"}', 410));
      await expectLater(
        PairingClient(client: client).download(request('send')),
        throwsA(isA<PairingException>().having((e) => e.message, 'message', contains('expired'))),
      );
    });

    test('download rejects data sealed for the other direction', () async {
      final client = MockClient((req) async => req.url.path == '/v1/ping'
          ? http.Response('{}', 200)
          : http.Response.bytes(await seal(key, profile, toPc), 200));
      await expectLater(PairingClient(client: client).download(request('send')), throwsA(isA<PairingException>()));
    });

    test('upload sends an envelope the PC can open and reads the result', () async {
      final client = MockClient((req) async {
        if (req.method == 'GET') return http.Response('{"error":"not found"}', 404);
        expect(await openEnvelope(key, req.bodyBytes, toPc), profile);
        return http.Response('{"applied":["theme"],"warnings":["w"]}', 200);
      });
      final result = await PairingClient(client: client).upload(request('receive'), profile);
      expect(result.applied, ['theme']);
      expect(result.warnings, ['w']);
    });

    test('upload reports a decline on the PC', () async {
      final client = MockClient((req) async =>
          req.method == 'GET' ? http.Response('', 404) : http.Response('{"error":"declined on the PC"}', 403));
      await expectLater(
        PairingClient(client: client).upload(request('receive'), profile),
        throwsA(isA<PairingException>().having((e) => e.message, 'message', 'Cancelled on the PC.')),
      );
    });
  });
}

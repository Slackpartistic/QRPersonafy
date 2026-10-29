// Talking to the desktop tool over Wi-Fi after scanning its QR code. See docs/pairing-protocol.md.

import 'dart:async';
import 'dart:convert';
import 'dart:io' show SocketException;

import 'package:http/http.dart' as http;

import 'envelope.dart';

enum PairMode {
  /// The PC sends its settings; the phone saves them.
  send,

  /// The PC waits for settings; the phone uploads a saved profile.
  receive,
}

class PairRequest {
  PairRequest({required this.mode, required this.hosts, required this.port, required this.key, required this.pcName});

  final PairMode mode;
  final List<String> hosts;
  final int port;
  final List<int> key;
  final String pcName;

  static final _ipv4 = RegExp(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$');

  /// Parses the QR code text, e.g. qrpersonafy://pair?v=1&m=send&h=192.168.1.20&p=48213&k=...&n=PC
  static PairRequest parse(String text) {
    final uri = Uri.tryParse(text.trim());
    if (uri == null || uri.scheme != 'qrpersonafy' || uri.host != 'pair') {
      throw const FormatException("This isn't a QRPersonafy code");
    }
    final q = uri.queryParameters;
    if (q['v'] != '1') {
      throw const FormatException('This code is from a newer version of QRPersonafy. Update the app.');
    }
    final mode = switch (q['m']) {
      'send' => PairMode.send,
      'receive' => PairMode.receive,
      _ => throw const FormatException('Unknown pairing mode'),
    };
    final hosts = (q['h'] ?? '').split(',').where((h) {
      final match = _ipv4.firstMatch(h);
      return match != null && match.groups([1, 2, 3, 4]).every((p) => int.parse(p!) <= 255);
    }).toList();
    final port = int.tryParse(q['p'] ?? '');
    final keyText = q['k'] ?? '';
    final List<int> key;
    try {
      key = base64Url.decode(base64Url.normalize(keyText));
    } on FormatException {
      throw const FormatException('Damaged pairing key');
    }
    if (hosts.isEmpty || port == null || port < 1 || port > 65535 || key.length != 32) {
      throw const FormatException('Incomplete pairing code');
    }
    final name = (q['n'] ?? '').trim();
    return PairRequest(
      mode: mode,
      hosts: hosts,
      port: port,
      key: key,
      pcName: name.isEmpty ? 'PC' : (name.length > 64 ? name.substring(0, 64) : name),
    );
  }

  Uri url(String host) => Uri(scheme: 'http', host: host, port: port, path: '/v1/profile');
}

class PairingException implements Exception {
  PairingException(this.message);
  final String message;
  @override
  String toString() => message;
}

class ReceiveResult {
  ReceiveResult({required this.applied, required this.warnings});
  final List<String> applied;
  final List<String> warnings;
}

const _unreachable =
    "Couldn't reach the PC. Check that the phone and PC are on the same Wi-Fi, and that Windows "
    'Firewall allowed QRPersonafy on private networks.';

class PairingClient {
  PairingClient({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  /// Downloads the profile a PC in `send` mode is offering.
  Future<Map<String, dynamic>> download(PairRequest request) async {
    final host = await _reachableHost(request);
    final http.Response response;
    try {
      response = await _client.get(request.url(host)).timeout(const Duration(minutes: 2));
    } on Object catch (error) {
      if (_isNetworkError(error)) throw PairingException(_unreachable);
      rethrow;
    }
    if (response.statusCode != 200) throw PairingException(_errorText(response));
    return _open(request.key, response.bodyBytes, toPhone);
  }

  /// Uploads a profile to a PC in `receive` mode, which asks its user before applying it.
  Future<ReceiveResult> upload(PairRequest request, Map<String, dynamic> profile) async {
    final host = await _reachableHost(request);
    final body = await seal(request.key, profile, toPc);
    final http.Response response;
    try {
      response = await _client
          .post(request.url(host), body: body, headers: {'Content-Type': 'application/octet-stream'})
          .timeout(const Duration(minutes: 10));
    } on TimeoutException {
      throw PairingException('The PC did not answer. Check whether it is still waiting.');
    } on Object catch (error) {
      if (_isNetworkError(error)) throw PairingException(_unreachable);
      rethrow;
    }
    if (response.statusCode == 403) throw PairingException('Cancelled on the PC.');
    if (response.statusCode != 200) throw PairingException(_errorText(response));
    final reply = _json(response.body);
    return ReceiveResult(
      applied: [for (final s in reply['applied'] as List? ?? const []) '$s'],
      warnings: [for (final s in reply['warnings'] as List? ?? const []) '$s'],
    );
  }

  /// Pings every address from the QR code at once and returns the first that answers.
  /// Any HTTP answer counts, so desktops that predate /v1/ping still work.
  Future<String> _reachableHost(PairRequest request) {
    final found = Completer<String>();
    var pending = request.hosts.length;
    for (final host in request.hosts) {
      _client
          .get(request.url(host).replace(path: '/v1/ping'))
          .timeout(const Duration(seconds: 4))
          .then<void>((_) {
        if (!found.isCompleted) found.complete(host);
      }, onError: (Object _) {
        if (--pending == 0 && !found.isCompleted) found.completeError(PairingException(_unreachable));
      });
    }
    return found.future;
  }

  Future<Map<String, dynamic>> _open(List<int> key, List<int> data, List<int> aad) async {
    try {
      final profile = await openEnvelope(key, data, aad);
      if (profile is Map<String, dynamic> && profile['format'] == 'qrpersonafy-profile') return profile;
      throw PairingException('The PC sent something that is not a profile.');
    } on EnvelopeException catch (error) {
      throw PairingException(error.message);
    }
  }

  static bool _isNetworkError(Object error) =>
      error is SocketException || error is TimeoutException || error is http.ClientException;

  static Map<String, dynamic> _json(String body) {
    try {
      final value = jsonDecode(body);
      return value is Map<String, dynamic> ? value : const {};
    } on FormatException {
      return const {};
    }
  }

  static String _errorText(http.Response response) {
    if (response.statusCode == 410) return 'That QR code has expired or was already used. Start again on the PC.';
    final error = _json(response.body)['error'];
    return error is String ? 'The PC said: $error' : 'The PC answered with an error (${response.statusCode}).';
  }
}

// Manual check against a running desktop session: dart run tool/cross_check.dart '<qr uri>'
import 'dart:io';

import 'package:qrpersonafy/src/pairing.dart';

Future<void> main(List<String> args) async {
  final request = PairRequest.parse(args.single);
  final client = PairingClient();
  if (request.mode == PairMode.send) {
    final profile = await client.download(request);
    stdout.writeln('downloaded settings: ${(profile['settings'] as Map).keys.toList()}');
  } else {
    final result = await client.upload(request, {'format': 'qrpersonafy-profile', 'version': 1, 'settings': {'theme': {}}});
    stdout.writeln('applied: ${result.applied}');
  }
}

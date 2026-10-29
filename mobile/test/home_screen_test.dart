import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrpersonafy/src/app.dart';
import 'package:qrpersonafy/src/pairing.dart';
import 'package:qrpersonafy/src/profile_store.dart';

import 'profile_store_test.dart' show FixedKeyStore;

/// Lets the store's real file I/O finish, which fake async time in widget tests can't.
Future<void> settleIo(WidgetTester tester, Finder target) async {
  for (var i = 0; i < 40 && target.evaluate().isEmpty; i++) {
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 50)));
    await tester.pump();
  }
}

void main() {
  testWidgets('home screen lists saved PCs', (tester) async {
    final dir = Directory.systemTemp.createTempSync('qrp');
    addTearDown(() => dir.deleteSync(recursive: true));
    final store = ProfileStore(Directory('${dir.path}/profiles'), FixedKeyStore());

    await tester.pumpWidget(QrPersonafyApp(store: store, client: PairingClient()));
    await settleIo(tester, find.textContaining('No saved PCs yet'));
    expect(find.textContaining('No saved PCs yet'), findsOneWidget);
    expect(find.text('Scan PC code'), findsOneWidget);

    await tester.runAsync(() => store.save(
          {'format': 'qrpersonafy-profile', 'version': 1, 'settings': {'theme': {}}},
          name: 'Gaming PC',
          pcName: 'DESKTOP-1',
        ));
    await tester.pumpWidget(QrPersonafyApp(key: UniqueKey(), store: store, client: PairingClient()));
    await settleIo(tester, find.text('Gaming PC'));
    expect(find.text('Gaming PC'), findsOneWidget);
  });
}

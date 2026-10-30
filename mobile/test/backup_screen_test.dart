import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrpersonafy/src/backup/backup_service.dart';
import 'package:qrpersonafy/src/profile_store.dart';
import 'package:qrpersonafy/src/screens/backup_screen.dart';

import 'backup_test.dart' show FakeDav, KeyStoreOf;
import 'home_screen_test.dart' show settleIo;

void main() {
  testWidgets('setting up backup shows the recovery code, then the backup status', (tester) async {
    final dir = Directory.systemTemp.createTempSync('qrp');
    addTearDown(() => dir.deleteSync(recursive: true));
    final dav = FakeDav();
    final settings = MemoryBackupSettingsStore();
    final backup = BackupService(ProfileStore(Directory('${dir.path}/p'), KeyStoreOf(1)), settings, client: dav.client);

    await tester.pumpWidget(MaterialApp(home: BackupScreen(backup: backup)));
    await settleIo(tester, find.text('Connect'));
    await tester.enterText(find.widgetWithText(TextField, 'Server address'),
        'https://cloud.example/remote.php/dav/files/me/QRPersonafy');
    await tester.enterText(find.widgetWithText(TextField, 'User name'), 'me');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'secret');
    await tester.tap(find.text('Connect'));
    await settleIo(tester, find.text('Save your recovery code'));

    final code = (await tester.runAsync(backup.recoveryCode))!;
    expect(find.textContaining(code.substring(0, 19)), findsOneWidget);
    await tester.tap(find.text("I've saved it"));
    await settleIo(tester, find.text('Backup is on'));
    expect(find.text('Back up now'), findsOneWidget);
    expect(dav.files.keys, contains(keyCheckFile));
  });
}

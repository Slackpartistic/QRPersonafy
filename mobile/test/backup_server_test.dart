// Backs up and restores through a real WebDAV server. CI runs it against backup-server/;
// locally, set QRP_DAV_URL, QRP_DAV_USER and QRP_DAV_PASSWORD to try another server.

import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:qrpersonafy/src/backup/backup_service.dart';
import 'package:qrpersonafy/src/profile_store.dart';

import 'backup_test.dart' show KeyStoreOf;
import 'look_test.dart' show profile;

void main() {
  final env = Platform.environment;
  final url = env['QRP_DAV_URL'];

  test('a new phone restores from the real backup server', () async {
    final dir = Directory.systemTemp.createTempSync('qrp');
    addTearDown(() => dir.deleteSync(recursive: true));
    final server = Uri.parse(url!);
    final user = env['QRP_DAV_USER']!, password = env['QRP_DAV_PASSWORD']!;

    final oldPhone = ProfileStore(Directory('${dir.path}/old'), KeyStoreOf(1),
        thumbnailer: (image) async => Uint8List.fromList([1, 2, 3]));
    final saved = await oldPhone.save(profile, name: 'Gaming PC', pcName: 'win11-1');
    final oldBackup = BackupService(oldPhone, MemoryBackupSettingsStore(), client: http.Client());
    final created = await oldBackup.connect(server, user, password) as NewBackup;
    expect(await oldBackup.backUp(), 1);

    final newPhone = ProfileStore(Directory('${dir.path}/new'), KeyStoreOf(2));
    final newBackup = BackupService(newPhone, MemoryBackupSettingsStore(), client: http.Client());
    expect(await newBackup.connect(server, user, password), isA<ExistingBackup>());
    await newBackup.unlock(server, user, password, created.recoveryCode);
    expect(await newBackup.restore(), 1);
    expect((await newPhone.list()).single.name, 'Gaming PC');
    expect(await newPhone.thumbnail(saved.id), [1, 2, 3]);

    await newBackup.forget(saved.id);
    expect(await newBackup.restore(), 0);
  }, skip: url == null ? 'set QRP_DAV_URL to run against a real server' : false);
}

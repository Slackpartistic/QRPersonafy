import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:qrpersonafy/src/backup/backup_service.dart';
import 'package:qrpersonafy/src/backup/recovery_code.dart';
import 'package:qrpersonafy/src/backup/webdav.dart';
import 'package:qrpersonafy/src/profile_store.dart';

import 'look_test.dart' show profile;

class KeyStoreOf implements KeyStore {
  KeyStoreOf(this.byte);
  final int byte;
  @override
  Future<List<int>> loadOrCreateKey() async => List.filled(32, byte);
}

/// An in-memory WebDAV server, answering like Nextcloud does.
class FakeDav {
  final files = <String, Uint8List>{};
  bool folder = false;
  final requests = <String>[];
  String password = 'secret';

  late final client = MockClient((request) async {
    requests.add('${request.method} ${request.url.path}');
    if (request.headers['Authorization'] != 'Basic ${_basic('me', password)}') return http.Response('', 401);
    final path = Uri.decodeFull(request.url.path);
    const base = '/remote.php/dav/files/me/QRPersonafy/';
    final name = path.startsWith(base) ? path.substring(base.length) : null;
    switch (request.method) {
      case 'MKCOL':
        if (folder) return http.Response('', 405);
        folder = true;
        return http.Response('', 201);
      case 'PROPFIND':
        if (!folder) return http.Response('', 404);
        final entries = [
          '<d:response><d:href>$base</d:href></d:response>',
          for (final f in files.keys) '<d:response><d:href>$base${Uri.encodeComponent(f)}</d:href></d:response>',
        ];
        return http.Response('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">${entries.join()}</d:multistatus>', 207);
      case 'PUT':
        files[name!] = request.bodyBytes;
        return http.Response('', 201);
      case 'GET':
        final data = files[name];
        return data == null ? http.Response('', 404) : http.Response.bytes(data, 200);
      case 'DELETE':
        return files.remove(name) == null ? http.Response('', 404) : http.Response('', 204);
    }
    return http.Response('', 405);
  });

  static String _basic(String user, String password) => base64.encode(utf8.encode('$user:$password'));
}

final url = Uri.parse('https://cloud.example/remote.php/dav/files/me/QRPersonafy');

void main() {
  late Directory dir;
  setUp(() => dir = Directory.systemTemp.createTempSync('qrp'));
  tearDown(() => dir.deleteSync(recursive: true));

  ProfileStore phone(String name, int key) =>
      ProfileStore(Directory('${dir.path}/$name'), KeyStoreOf(key), thumbnailer: (image) async => Uint8List.fromList([7, ...image]));

  test('recovery codes round trip and forgive typing', () {
    final key = newBackupKey();
    final code = formatRecoveryCode(key);
    expect(code.replaceAll('-', ''), hasLength(52));
    expect(parseRecoveryCode(code), key);
    expect(parseRecoveryCode(code.toLowerCase().replaceAll('-', ' ')), key);
    expect(parseRecoveryCode(code.replaceAll('O', '0').replaceAll('I', '1')), key);
    expect(() => parseRecoveryCode('ABCD'), throwsFormatException);
  });

  test('a new phone gets its PCs back from the backup with the recovery code', () async {
    final dav = FakeDav();
    final oldPhone = phone('old', 1);
    final saved = await oldPhone.save(profile, name: 'Gaming PC', pcName: 'win11-1');
    final backup = BackupService(oldPhone, MemoryBackupSettingsStore(), client: dav.client);

    final result = await backup.connect(url, 'me', 'secret');
    expect(result, isA<NewBackup>());
    final code = (result as NewBackup).recoveryCode;
    expect(await backup.backUp(), 1);
    expect(await backup.backUp(), 0, reason: 'already backed up');
    expect(dav.files.keys, unorderedEquals([keyCheckFile, '${saved.id}.qrpb']));
    expect(String.fromCharCodes(dav.files['${saved.id}.qrpb']!), isNot(contains('Gaming PC')));

    final newPhone = phone('new', 2);
    final restore = BackupService(newPhone, MemoryBackupSettingsStore(), client: dav.client);
    expect(await restore.connect(url, 'me', 'secret'), isA<ExistingBackup>());
    await expectLater(
      restore.unlock(url, 'me', 'secret', formatRecoveryCode(newBackupKey())),
      throwsA(isA<BackupException>()),
    );
    expect(await restore.settings(), isNull);
    await restore.unlock(url, 'me', 'secret', code);

    expect(await restore.restore(), 1);
    expect(await restore.restore(), 0, reason: 'already on the phone');
    final restored = (await newPhone.list()).single;
    expect(restored.name, 'Gaming PC');
    expect(restored.accent, 0xFF0078D4);
    expect(await newPhone.load(saved.id), profile);
    expect(await newPhone.thumbnail(saved.id), await oldPhone.thumbnail(saved.id));

    await backup.update(await oldPhone.rename(saved, 'Gaming rig'));
    final third = phone('third', 3);
    final thirdBackup = BackupService(third, MemoryBackupSettingsStore(), client: dav.client);
    await thirdBackup.unlock(url, 'me', 'secret', code);
    await thirdBackup.restore();
    expect((await third.list()).single.name, 'Gaming rig');

    await restore.forget(saved.id);
    expect(dav.files.keys, [keyCheckFile]);
  });

  test('wrong password and odd file names', () async {
    final dav = FakeDav();
    final store = phone('p', 1);
    final backup = BackupService(store, MemoryBackupSettingsStore(), client: dav.client);
    await expectLater(backup.connect(url, 'me', 'nope'), throwsA(isA<BackupException>()));
    await backup.connect(url, 'me', 'secret');
    dav.files['../../evil.qrpb'] = Uint8List(10);
    dav.files['notes.txt'] = Uint8List(1);
    expect(await backup.restore(), 0);
  });

  test('reads names from real-world PROPFIND replies', () {
    const rclone = '<?xml version="1.0" encoding="UTF-8"?><D:multistatus xmlns:D="DAV:">'
        '<D:response><D:href>/</D:href></D:response>'
        '<D:response><D:href>/key-check.qrpb</D:href></D:response>'
        '<D:response><D:href>/0123456789abcdef.qrpb</D:href></D:response>'
        '<D:response><D:href>/sub/</D:href></D:response></D:multistatus>';
    expect(WebDavClient.parseNames(rclone, Uri.parse('http://pc:8080/')),
        ['key-check.qrpb', '0123456789abcdef.qrpb']);
    const absolute = '<d:multistatus xmlns:d="DAV:"><d:response><d:href>https://x/a%20b/</d:href></d:response>'
        '<d:response><d:href>https://x/a%20b/c%20d.qrpb</d:href></d:response></d:multistatus>';
    expect(WebDavClient.parseNames(absolute, Uri.parse('https://x/a%20b/')), ['c d.qrpb']);
  });
}


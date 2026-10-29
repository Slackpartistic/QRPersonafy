import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:qrpersonafy/src/profile_store.dart';

class FixedKeyStore implements KeyStore {
  @override
  Future<List<int>> loadOrCreateKey() async => List.filled(32, 3);
}

void main() {
  late Directory dir;
  late ProfileStore store;

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('qrp');
    store = ProfileStore(Directory('${dir.path}/profiles'), FixedKeyStore());
  });
  tearDown(() => dir.delete(recursive: true));

  final profile = {
    'format': 'qrpersonafy-profile',
    'version': 1,
    'windows_build': '10.0.26100',
    'settings': {'wallpaper': {}, 'theme': {}},
  };

  test('saves, lists, loads, renames and deletes', () async {
    expect(await store.list(), isEmpty);
    final saved = await store.save(profile, name: 'Work laptop', pcName: 'DESKTOP-1');
    expect(saved.settings, ['wallpaper', 'theme']);

    final listed = await store.list();
    expect(listed.single.name, 'Work laptop');
    expect(listed.single.windowsBuild, '10.0.26100');
    expect(await store.load(saved.id), profile);

    await store.rename(saved, 'Home PC');
    expect((await store.list()).single.name, 'Home PC');

    await store.delete(saved.id);
    expect(await store.list(), isEmpty);
  });

  test('files on disk are encrypted', () async {
    final saved = await store.save(profile, name: 'Secret name', pcName: 'DESKTOP-1');
    for (final ext in ['meta', 'qrp']) {
      final bytes = await File('${dir.path}/profiles/${saved.id}.$ext').readAsBytes();
      expect(String.fromCharCodes(bytes).contains('Secret name'), isFalse);
      expect(String.fromCharCodes(bytes).contains('windows_build'), isFalse);
    }
  });

  test('skips files it cannot decrypt', () async {
    await store.save(profile, name: 'Good', pcName: 'PC');
    await File('${dir.path}/profiles/junk.meta').writeAsString('not encrypted');
    expect((await store.list()).map((p) => p.name), ['Good']);
  });
}

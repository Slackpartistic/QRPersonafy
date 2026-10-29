import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:qrpersonafy/src/look.dart';
import 'package:qrpersonafy/src/profile_store.dart';

import 'profile_store_test.dart' show FixedKeyStore;

Map<String, dynamic> _entry(String key, String name, Object data) =>
    {'key': key, 'name': name, 'type': 'REG_DWORD', 'data': data};

final profile = <String, dynamic>{
  'format': 'qrpersonafy-profile',
  'version': 1,
  'windows_build': '10.0.26100',
  'settings': {
    'accent': {
      'registry': [_entry(r'Software\Microsoft\Windows\DWM', 'AccentColor', 0xFFD47800)],
    },
    'theme': {
      'registry': [
        _entry(r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize', 'SystemUsesLightTheme', 0),
      ],
    },
    'wallpaper': {
      'files': {
        'image': {'name': 'wallpaper.png', 'data': base64.encode([1, 2, 3])},
      },
    },
  },
};

void main() {
  test('reads accent, dark mode and wallpaper', () {
    final look = ProfileLook.of(profile);
    expect(look.accent, 0xFF0078D4);
    expect(look.dark, isTrue);
    expect(look.wallpaper, [1, 2, 3]);
  });

  test('ignores missing or hostile values', () {
    expect(ProfileLook.of({}).accent, isNull);
    final look = ProfileLook.of({
      'settings': {
        'accent': {'registry': 'nope'},
        'theme': {
          'registry': [42, _entry(r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize', 'SystemUsesLightTheme', 'x')],
        },
        'wallpaper': {
          'files': {
            'image': {'data': '***'},
          },
        },
      },
    });
    expect(look.accent, isNull);
    expect(look.dark, isNull);
    expect(look.wallpaper, isNull);
  });

  test('the store keeps the look and an encrypted thumbnail', () async {
    final dir = await Directory.systemTemp.createTemp('qrp');
    addTearDown(() => dir.delete(recursive: true));
    final store = ProfileStore(Directory('${dir.path}/p'), FixedKeyStore(),
        thumbnailer: (image) async => Uint8List.fromList([9, ...image]));

    final saved = await store.save(profile, name: 'Desk', pcName: 'PC');
    final listed = (await store.list()).single;
    expect(listed.accent, 0xFF0078D4);
    expect(listed.dark, isTrue);
    expect(await store.thumbnail(saved.id), [9, 1, 2, 3]);

    await store.delete(saved.id);
    expect(await store.thumbnail(saved.id), isNull);
    expect(dir.listSync(recursive: true).whereType<File>(), isEmpty);
  });
}

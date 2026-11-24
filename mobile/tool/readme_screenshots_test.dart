// Makes the phone pictures for the README (docs/images/phone.png), with the real screens and
// sample data. Run from mobile/:
//
//   flutter test --update-goldens tool/readme_screenshots_test.dart
//   python3 tool/stitch_screenshots.py
//
// The first writes one picture per screen to tool/screenshots/; the second joins them.
// It lives in tool/ so the normal `flutter test` run doesn't pick it up.

import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrpersonafy/src/app.dart';
import 'package:qrpersonafy/src/backup/backup_service.dart';
import 'package:qrpersonafy/src/pairing.dart';
import 'package:qrpersonafy/src/profile_store.dart';
import 'package:qrpersonafy/src/screens/transfer_screen.dart';

const _size = Size(400, 851);
const _pixelRatio = 1.1;

class _Keys implements KeyStore {
  @override
  Future<List<int>> loadOrCreateKey() async => List.filled(32, 7);
}

/// Stands in for a PC: hands out [profile] and "applies" whatever is sent.
class _FakePc extends PairingClient {
  _FakePc(this.profile);

  final Map<String, dynamic> profile;

  @override
  Future<Map<String, dynamic>> download(PairRequest request) async => profile;

  @override
  Future<ReceiveResult> upload(PairRequest request, Map<String, dynamic> profile) async => ReceiveResult(
        applied: ['wallpaper', 'theme', 'accent', 'taskbar'],
        warnings: [
          "Taskbar: Windows doesn't let apps change the Widgets button. Set it yourself in Settings > "
              'Personalization > Taskbar.',
        ],
      );
}

Future<void> _loadFonts() async {
  final fonts = '${Platform.environment['FLUTTER_ROOT']}/bin/cache/artifacts/material_fonts';
  Future<ByteData> read(String name) async => ByteData.sublistView(File('$fonts/$name').readAsBytesSync());
  final roboto = FontLoader('Roboto');
  for (final style in ['Regular', 'Medium', 'Bold', 'Light']) {
    roboto.addFont(read('Roboto-$style.ttf'));
  }
  await roboto.load();
  await (FontLoader('MaterialIcons')..addFont(read('MaterialIcons-Regular.otf'))).load();
}

Future<List<int>> _gradient(Color from, Color to) async {
  final recorder = ui.PictureRecorder();
  const rect = Rect.fromLTWH(0, 0, 640, 360);
  Canvas(recorder).drawRect(
    rect,
    Paint()..shader = ui.Gradient.linear(rect.topCenter, rect.bottomCenter, [from, to]),
  );
  final image = await recorder.endRecording().toImage(640, 360);
  final data = await image.toByteData(format: ui.ImageByteFormat.png);
  return data!.buffer.asUint8List();
}

Map<String, dynamic> _profile(List<int> wallpaper, {required int accentAbgr, required bool dark, required List<String> also}) {
  const personalize = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize';
  return {
    'format': 'qrpersonafy-profile',
    'version': 1,
    'settings': {
      'wallpaper': {
        'files': {
          'image': {'name': 'wallpaper.png', 'data': base64.encode(wallpaper)},
        },
      },
      'theme': {
        'registry': [
          {'key': personalize, 'name': 'AppsUseLightTheme', 'type': 'REG_DWORD', 'data': dark ? 0 : 1},
          {'key': personalize, 'name': 'SystemUsesLightTheme', 'type': 'REG_DWORD', 'data': dark ? 0 : 1},
        ],
      },
      'accent': {
        'registry': [
          {'key': r'Software\Microsoft\Windows\DWM', 'name': 'AccentColor', 'type': 'REG_DWORD', 'data': accentAbgr},
        ],
      },
      for (final name in also) name: <String, dynamic>{},
    },
  };
}

Future<void> _settle(WidgetTester tester, [int rounds = 10]) async {
  for (var i = 0; i < rounds; i++) {
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 50)));
    await tester.pump(const Duration(milliseconds: 100));
  }
  await tester.pump(const Duration(seconds: 1));
}

Future<void> _shot(String name) =>
    expectLater(find.byType(MaterialApp), matchesGoldenFile('screenshots/$name.png'));

void main() {
  testWidgets('README phone screenshots', (tester) async {
    tester.view.physicalSize = _size * _pixelRatio;
    tester.view.devicePixelRatio = _pixelRatio;
    addTearDown(tester.view.reset);
    await tester.runAsync(_loadFonts);
    WidgetsApp.debugAllowBannerOverride = false; // no DEBUG ribbon
    addTearDown(() => WidgetsApp.debugAllowBannerOverride = true);

    final dir = Directory.systemTemp.createTempSync('qrestoa-shots');
    addTearDown(() => dir.deleteSync(recursive: true));
    final store = ProfileStore(Directory('${dir.path}/profiles'), _Keys());
    final backup = BackupService(store, MemoryBackupSettingsStore());

    final blue = (await tester.runAsync(() => _gradient(const Color(0xFF2B2BD9), const Color(0xFF3A7A9A))))!;
    final green = (await tester.runAsync(() => _gradient(const Color(0xFF5ACB6A), const Color(0xFF1F6B2A))))!;
    // Windows keeps the accent color as 0xAABBGGRR.
    final gaming = _profile(blue,
        accentAbgr: 0xFFD47800, dark: true, also: ['taskbar', 'start', 'mouse', 'keyboard']);
    final work = _profile(green, accentAbgr: 0xFF2E9E3C, dark: false, also: []);
    final pc = _FakePc(gaming);

    PairRequest request(PairMode mode, String name) =>
        PairRequest(mode: mode, hosts: ['192.168.1.20'], port: 48213, key: List.filled(32, 1), pcName: name);
    Widget app() => QrestoaApp(key: UniqueKey(), store: store, client: pc, backup: backup);
    Widget transfer(PairRequest r) => MaterialApp(
          key: UniqueKey(),
          debugShowCheckedModeBanner: false,
          theme: Theme.of(tester.element(find.byType(Scaffold).first)),
          home: TransferScreen(request: r, store: store, client: pc),
        );

    // 1. Welcome
    await tester.pumpWidget(app());
    await _settle(tester);
    await _shot('1-welcome');

    // 2. Saving a PC (uses the app's own theme, taken from the screen above)
    await tester.pumpWidget(transfer(request(PairMode.send, 'win11-1')));
    await _settle(tester);
    await _shot('2-save');

    // 3. Saved PCs
    await tester.runAsync(() async {
      await store.save(gaming, name: 'Gaming PC', pcName: 'win11-1');
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await store.save(work, name: 'Work laptop', pcName: 'LAPTOP-1');
    });
    await tester.pumpWidget(app());
    await _settle(tester, 30);
    await _shot('3-saved');

    // 4. Restoring: pick a look
    await tester.pumpWidget(transfer(request(PairMode.receive, 'win11-2')));
    await _settle(tester, 30);
    await tester.tap(find.text('Gaming PC'));
    await _settle(tester);
    await _shot('4-restore');

    // 5. Done
    await tester.tap(find.text('Send to win11-2'));
    await _settle(tester);
    await _shot('5-done');
  });
}

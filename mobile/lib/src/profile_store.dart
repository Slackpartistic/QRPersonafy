// Profiles saved on the phone. Each one is two files encrypted with a key kept in the
// phone's secure storage (Android Keystore): a small `.meta` for the list, and the `.qrp` profile.

import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'envelope.dart';
import 'look.dart';

const settingLabels = {
  'wallpaper': 'Wallpaper',
  'theme': 'Light/dark mode',
  'accent': 'Accent color',
  'taskbar': 'Taskbar',
  'start': 'Start menu',
  'mouse': 'Mouse',
  'keyboard': 'Keyboard',
};

class SavedProfile {
  SavedProfile({
    required this.id,
    required this.name,
    required this.pcName,
    required this.savedAt,
    required this.settings,
    required this.windowsBuild,
    this.accent,
    this.dark,
  });

  final String id;
  final String name;
  final String pcName;
  final DateTime savedAt;
  final List<String> settings;
  final String windowsBuild;

  /// What the PC looked like, for previews. Missing for profiles saved by older versions.
  final int? accent;
  final bool? dark;

  SavedProfile copyWith({String? name}) => SavedProfile(
        id: id,
        name: name ?? this.name,
        pcName: pcName,
        savedAt: savedAt,
        settings: settings,
        windowsBuild: windowsBuild,
        accent: accent,
        dark: dark,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'pc_name': pcName,
        'saved_at': savedAt.toIso8601String(),
        'settings': settings,
        'windows_build': windowsBuild,
        if (accent != null) 'accent': accent,
        if (dark != null) 'dark': dark,
      };

  static SavedProfile fromJson(Map<String, dynamic> json) => SavedProfile(
        id: json['id'] as String,
        name: json['name'] as String,
        pcName: json['pc_name'] as String,
        savedAt: DateTime.parse(json['saved_at'] as String),
        settings: [for (final s in json['settings'] as List) s as String],
        windowsBuild: json['windows_build'] as String,
        accent: json['accent'] is int ? json['accent'] as int : null,
        dark: json['dark'] is bool ? json['dark'] as bool : null,
      );
}

abstract class KeyStore {
  Future<List<int>> loadOrCreateKey();
}

class SecureKeyStore implements KeyStore {
  static const _name = 'qrpersonafy_storage_key_v1';
  final _storage = const FlutterSecureStorage();

  @override
  Future<List<int>> loadOrCreateKey() async {
    final existing = await _storage.read(key: _name);
    if (existing != null) return base64.decode(existing);
    final key = await (await AesGcm.with256bits().newSecretKey()).extractBytes();
    await _storage.write(key: _name, value: base64.encode(key));
    return key;
  }
}

class ProfileStore {
  ProfileStore(this.directory, this.keys, {this.thumbnailer = makeThumbnail});

  final Directory directory;
  final KeyStore keys;
  final Future<Uint8List?> Function(Uint8List image) thumbnailer;
  List<int>? _key;

  Future<List<int>> _getKey() async => _key ??= await keys.loadOrCreateKey();

  File _meta(String id) => File('${directory.path}/$id.meta');
  File _data(String id) => File('${directory.path}/$id.qrp');
  File _thumb(String id) => File('${directory.path}/$id.thumb');

  /// Saved profiles, newest first. Files that can't be read are skipped.
  Future<List<SavedProfile>> list() async {
    if (!await directory.exists()) return [];
    final key = await _getKey();
    final profiles = <SavedProfile>[];
    await for (final entity in directory.list()) {
      if (entity is! File || !entity.path.endsWith('.meta')) continue;
      try {
        final json = await openEnvelope(key, await entity.readAsBytes(), atRest);
        profiles.add(SavedProfile.fromJson(json as Map<String, dynamic>));
      } on Object {
        continue;
      }
    }
    profiles.sort((a, b) => b.savedAt.compareTo(a.savedAt));
    return profiles;
  }

  Future<SavedProfile> save(Map<String, dynamic> profile, {required String name, required String pcName}) async {
    final settings = profile['settings'];
    final look = ProfileLook.of(profile);
    final saved = SavedProfile(
      id: _newId(),
      name: name,
      pcName: pcName,
      savedAt: DateTime.now(),
      settings: settings is Map ? [for (final k in settings.keys) '$k'] : const [],
      windowsBuild: '${profile['windows_build'] ?? 'unknown'}',
      accent: look.accent,
      dark: look.dark,
    );
    await directory.create(recursive: true);
    final key = await _getKey();
    await _data(saved.id).writeAsBytes(await seal(key, profile, atRest), flush: true);
    await _writeMeta(saved);
    final wallpaper = look.wallpaper;
    final thumbnail = wallpaper == null ? null : await thumbnailer(wallpaper);
    if (thumbnail != null) {
      await _thumb(saved.id).writeAsBytes(await seal(key, {'png': base64.encode(thumbnail)}, atRest), flush: true);
    }
    return saved;
  }

  Future<Map<String, dynamic>> load(String id) async {
    final json = await openEnvelope(await _getKey(), await _data(id).readAsBytes(), atRest);
    return json as Map<String, dynamic>;
  }

  /// A small PNG of the profile's wallpaper, if it has one.
  Future<Uint8List?> thumbnail(String id) async {
    try {
      final json = await openEnvelope(await _getKey(), await _thumb(id).readAsBytes(), atRest);
      return base64.decode((json as Map)['png'] as String);
    } on Object {
      return null;
    }
  }

  /// Adds a profile from a backup, keeping its id so it isn't restored twice.
  Future<void> addFromBackup(SavedProfile saved, Map<String, dynamic> profile, Uint8List? thumbnail) async {
    // The id becomes a file name, and a backup is only as trustworthy as the server it came from.
    if (!isValidId(saved.id)) throw const FormatException('Bad profile id in backup');
    await directory.create(recursive: true);
    final key = await _getKey();
    await _data(saved.id).writeAsBytes(await seal(key, profile, atRest), flush: true);
    if (thumbnail != null) {
      await _thumb(saved.id).writeAsBytes(await seal(key, {'png': base64.encode(thumbnail)}, atRest), flush: true);
    }
    await _writeMeta(saved);
  }

  static bool isValidId(String id) => RegExp(r'^[0-9a-f]{16}$').hasMatch(id);

  Future<SavedProfile> rename(SavedProfile profile, String name) async {
    final renamed = profile.copyWith(name: name);
    await _writeMeta(renamed);
    return renamed;
  }

  Future<void> delete(String id) async {
    for (final file in [_meta(id), _data(id), _thumb(id)]) {
      if (await file.exists()) await file.delete();
    }
  }

  Future<int> sizeOf(String id) async {
    final file = _data(id);
    return await file.exists() ? file.length() : 0;
  }

  Future<void> _writeMeta(SavedProfile profile) async {
    await _meta(profile.id).writeAsBytes(await seal(await _getKey(), profile.toJson(), atRest), flush: true);
  }

  static String _newId() {
    final random = Random.secure();
    return List.generate(16, (_) => random.nextInt(16).toRadixString(16)).join();
  }
}

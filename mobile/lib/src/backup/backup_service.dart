// Backs up saved PCs to the user's own WebDAV server, end-to-end encrypted with a key that
// only the phone (and the recovery code the user wrote down) knows. See docs/backup.md.

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../envelope.dart';
import '../profile_store.dart';
import 'recovery_code.dart';
import 'webdav.dart';

/// Additional authenticated data for backup files.
final inBackup = ascii.encode('QRP1|backup');

/// A small file in the backup folder that shows a recovery code is the right one.
const keyCheckFile = 'key-check.qrpb';
const backupExtension = '.qrpb';
const _keyCheck = {'format': 'qrpersonafy-backup', 'version': 1};

class BackupSettings {
  const BackupSettings({required this.url, required this.user, required this.password, required this.key, this.lastBackup});

  final Uri url;
  final String user;
  final String password;
  final List<int> key;
  final DateTime? lastBackup;

  BackupSettings withLastBackup(DateTime time) =>
      BackupSettings(url: url, user: user, password: password, key: key, lastBackup: time);

  Map<String, dynamic> toJson() => {
        'url': '$url',
        'user': user,
        'password': password,
        'key': base64.encode(key),
        if (lastBackup != null) 'last_backup': lastBackup!.toIso8601String(),
      };

  static BackupSettings fromJson(Map<String, dynamic> json) => BackupSettings(
        url: Uri.parse(json['url'] as String),
        user: json['user'] as String,
        password: json['password'] as String,
        key: base64.decode(json['key'] as String),
        lastBackup: json['last_backup'] == null ? null : DateTime.parse(json['last_backup'] as String),
      );
}

abstract class BackupSettingsStore {
  Future<BackupSettings?> load();
  Future<void> save(BackupSettings settings);
  Future<void> clear();
}

/// Keeps the server login and backup key in Android's secure storage.
class SecureBackupSettingsStore implements BackupSettingsStore {
  static const _name = 'qrpersonafy_backup_v1';
  final _storage = const FlutterSecureStorage();

  @override
  Future<BackupSettings?> load() async {
    final text = await _storage.read(key: _name);
    return text == null ? null : BackupSettings.fromJson(jsonDecode(text) as Map<String, dynamic>);
  }

  @override
  Future<void> save(BackupSettings settings) => _storage.write(key: _name, value: jsonEncode(settings.toJson()));

  @override
  Future<void> clear() => _storage.delete(key: _name);
}

/// What connecting to a server found.
sealed class ConnectResult {}

/// The folder was empty: a new backup key was made. Show its recovery code once.
class NewBackup extends ConnectResult {
  NewBackup(this.recoveryCode);
  final String recoveryCode;
}

/// The folder already has backups: ask for their recovery code and call [BackupService.unlock].
class ExistingBackup extends ConnectResult {}

class BackupService {
  BackupService(this.store, this.settingsStore, {this.client});

  final ProfileStore store;
  final BackupSettingsStore settingsStore;
  final http.Client? client;

  Future<BackupSettings?> settings() => settingsStore.load();

  WebDavClient _dav(Uri url, String user, String password) => WebDavClient(url, user, password, client: client);

  Future<ConnectResult> connect(Uri url, String user, String password) async {
    if (!url.isScheme('http') && !url.isScheme('https')) {
      throw BackupException('The server address should start with https:// or http://');
    }
    final dav = _dav(url, user, password);
    await dav.ensureFolder();
    if ((await dav.list()).contains(keyCheckFile)) return ExistingBackup();
    final key = newBackupKey();
    await dav.put(keyCheckFile, await seal(key, _keyCheck, inBackup));
    await settingsStore.save(BackupSettings(url: dav.folder, user: user, password: password, key: key));
    return NewBackup(formatRecoveryCode(key));
  }

  /// Joins an existing backup with its recovery code. Throws if the code doesn't match it.
  Future<void> unlock(Uri url, String user, String password, String recoveryCode) async {
    final key = parseRecoveryCode(recoveryCode);
    final dav = _dav(url, user, password);
    final check = await dav.get(keyCheckFile);
    if (check == null) throw BackupException('There is no QRPersonafy backup in that folder.');
    try {
      await openEnvelope(key, check, inBackup);
    } on EnvelopeException {
      throw BackupException("That recovery code doesn't match the backups in this folder.");
    }
    await settingsStore.save(BackupSettings(url: dav.folder, user: user, password: password, key: key));
  }

  Future<String?> recoveryCode() async {
    final settings = await settingsStore.load();
    return settings == null ? null : formatRecoveryCode(settings.key);
  }

  Future<void> disconnect() => settingsStore.clear();

  Future<(BackupSettings, WebDavClient)> _connected() async {
    final settings = await settingsStore.load();
    if (settings == null) throw BackupException('Backup is not set up.');
    return (settings, _dav(settings.url, settings.user, settings.password));
  }

  /// Uploads saved PCs that aren't in the backup yet. Returns how many were uploaded.
  Future<int> backUp() async {
    final (settings, dav) = await _connected();
    final remote = (await dav.list()).toSet();
    var uploaded = 0;
    for (final saved in await store.list()) {
      final name = '${saved.id}$backupExtension';
      if (remote.contains(name)) continue;
      await _upload(settings, dav, saved);
      uploaded++;
    }
    await settingsStore.save(settings.withLastBackup(DateTime.now()));
    return uploaded;
  }

  Future<void> _upload(BackupSettings settings, WebDavClient dav, SavedProfile saved) async {
    final thumbnail = await store.thumbnail(saved.id);
    final blob = {
      'meta': saved.toJson(),
      'profile': await store.load(saved.id),
      if (thumbnail != null) 'thumbnail': base64.encode(thumbnail),
    };
    await dav.put('${saved.id}$backupExtension', await seal(settings.key, blob, inBackup));
  }

  /// Uploads one saved PC again, e.g. after it was renamed, if backup is set up.
  Future<void> update(SavedProfile saved) async {
    final settings = await settingsStore.load();
    if (settings == null) return;
    await _upload(settings, _dav(settings.url, settings.user, settings.password), saved);
  }

  /// Backs up if backup is set up, without bothering the user if it fails.
  Future<void> backUpQuietly() async {
    try {
      if (await settingsStore.load() != null) await backUp();
    } on Object {
      // The next backup tries again.
    }
  }

  /// Downloads PCs from the backup that aren't on this phone. Returns how many were added.
  Future<int> restore() async {
    final (settings, dav) = await _connected();
    final local = {for (final saved in await store.list()) saved.id};
    var restored = 0;
    for (final name in await dav.list()) {
      if (!name.endsWith(backupExtension) || name == keyCheckFile) continue;
      final id = name.substring(0, name.length - backupExtension.length);
      if (!ProfileStore.isValidId(id) || local.contains(id)) continue;
      final data = await dav.get(name);
      if (data == null) continue;
      final blob = await openEnvelope(settings.key, data, inBackup);
      if (blob is! Map<String, dynamic> || blob['meta'] is! Map<String, dynamic> || blob['profile'] is! Map<String, dynamic>) {
        throw BackupException('$name in the backup is damaged.');
      }
      final saved = SavedProfile.fromJson(blob['meta'] as Map<String, dynamic>);
      if (saved.id != id) throw BackupException('$name in the backup is damaged.');
      final thumbnail = blob['thumbnail'] is String ? base64.decode(blob['thumbnail'] as String) : null;
      await store.addFromBackup(saved, blob['profile'] as Map<String, dynamic>, thumbnail);
      restored++;
    }
    return restored;
  }

  /// Removes a deleted PC from the backup too, if backup is set up.
  Future<void> forget(String id) async {
    if (await settingsStore.load() == null) return;
    final (_, dav) = await _connected();
    await dav.delete('$id$backupExtension');
  }
}

class MemoryBackupSettingsStore implements BackupSettingsStore {
  BackupSettings? value;

  @override
  Future<BackupSettings?> load() async => value;

  @override
  Future<void> save(BackupSettings settings) async => value = settings;

  @override
  Future<void> clear() async => value = null;
}


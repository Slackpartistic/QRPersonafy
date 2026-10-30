import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import 'src/app.dart';
import 'src/backup/backup_service.dart';
import 'src/pairing.dart';
import 'src/profile_store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final support = await getApplicationSupportDirectory();
  final store = ProfileStore(Directory('${support.path}/profiles'), SecureKeyStore());
  final backup = BackupService(store, SecureBackupSettingsStore());
  runApp(QrPersonafyApp(store: store, client: PairingClient(), backup: backup));
}

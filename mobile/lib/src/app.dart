import 'package:flutter/material.dart';

import 'backup/backup_service.dart';
import 'pairing.dart';
import 'profile_store.dart';
import 'screens/home_screen.dart';

class QrPersonafyApp extends StatelessWidget {
  const QrPersonafyApp({super.key, required this.store, required this.client, required this.backup});

  final ProfileStore store;
  final PairingClient client;
  final BackupService backup;

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF3B6FD8);
    return MaterialApp(
      title: 'QRPersonafy',
      theme: ThemeData(colorSchemeSeed: seed, useMaterial3: true),
      darkTheme: ThemeData(colorSchemeSeed: seed, brightness: Brightness.dark, useMaterial3: true),
      home: HomeScreen(store: store, client: client, backup: backup),
    );
  }
}

String formatDate(DateTime date) {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  final local = date.toLocal();
  return '${local.day} ${months[local.month - 1]} ${local.year}';
}

String formatSize(int bytes) {
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
  return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
}

String settingsSummary(List<String> settings) =>
    settings.map((s) => settingLabels[s] ?? s).join(', ');

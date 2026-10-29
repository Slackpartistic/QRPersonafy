import 'package:flutter/material.dart';

import '../app.dart';
import '../pairing.dart';
import '../profile_store.dart';
import 'profile_screen.dart';
import 'scan_screen.dart';
import 'transfer_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.store, required this.client});

  final ProfileStore store;
  final PairingClient client;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<SavedProfile>> _profiles = widget.store.list();

  void _reload() => setState(() => _profiles = widget.store.list());

  Future<void> _scan() async {
    final request = await Navigator.of(context).push<PairRequest>(
      MaterialPageRoute(builder: (_) => const ScanScreen()),
    );
    if (request == null || !mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => TransferScreen(request: request, store: widget.store, client: widget.client)),
    );
    _reload();
  }

  Future<void> _open(SavedProfile profile) async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ProfileScreen(profile: profile, store: widget.store)),
    );
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('QRPersonafy')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _scan,
        icon: const Icon(Icons.qr_code_scanner),
        label: const Text('Scan PC code'),
      ),
      body: FutureBuilder<List<SavedProfile>>(
        future: _profiles,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return _Message(icon: Icons.error_outline, text: 'Could not read saved profiles.\n${snapshot.error}');
          }
          final profiles = snapshot.data;
          if (profiles == null) return const Center(child: CircularProgressIndicator());
          if (profiles.isEmpty) {
            return const _Message(
              icon: Icons.devices,
              text: 'No saved PCs yet.\n\nOn your PC, run  qrpersonafy send  and scan the code it shows '
                  'to save its look and feel here.',
            );
          }
          return ListView.builder(
            padding: const EdgeInsets.only(bottom: 96),
            itemCount: profiles.length,
            itemBuilder: (context, i) {
              final p = profiles[i];
              return ListTile(
                leading: const CircleAvatar(child: Icon(Icons.desktop_windows_outlined)),
                title: Text(p.name),
                subtitle: Text('${formatDate(p.savedAt)} · ${p.settings.length} settings'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _open(p),
              );
            },
          );
        },
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 56, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 16),
            Text(text, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyLarge),
          ],
        ),
      ),
    );
  }
}

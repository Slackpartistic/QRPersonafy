import 'package:flutter/material.dart';

import '../app.dart';
import '../backup/backup_service.dart';
import '../pairing.dart';
import '../profile_store.dart';
import '../widgets/common.dart';
import 'backup_screen.dart';
import 'profile_screen.dart';
import 'scan_screen.dart';
import 'transfer_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.store, required this.client, required this.backup});

  final ProfileStore store;
  final PairingClient client;
  final BackupService backup;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<SavedProfile>> _profiles = widget.store.list();

  void _reload() => setState(() => _profiles = widget.store.list());

  Future<void> _scan() async {
    final request = await Navigator.of(context)
        .push<PairRequest>(MaterialPageRoute(builder: (_) => const ScanScreen()));
    if (request == null || !mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TransferScreen(request: request, store: widget.store, client: widget.client),
      ),
    );
    _reload();
    await widget.backup.backUpQuietly();
  }

  Future<void> _open(SavedProfile profile) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ProfileScreen(profile: profile, store: widget.store, backup: widget.backup),
      ),
    );
    _reload();
  }

  Future<void> _openBackup() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => BackupScreen(backup: widget.backup)));
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<List<SavedProfile>>(
        future: _profiles,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return StatusView(kind: StatusKind.bad, title: 'Could not read your saved PCs', text: '${snapshot.error}');
          }
          final profiles = snapshot.data;
          if (profiles == null) return const Center(child: CircularProgressIndicator());
          if (profiles.isEmpty) return _Welcome(onScan: _scan, onRestore: _openBackup);
          return CustomScrollView(
            slivers: [
              SliverAppBar.large(
                title: const Text('Your PCs'),
                actions: [
                  IconButton(onPressed: _openBackup, icon: const Icon(Icons.cloud_outlined), tooltip: 'Backup'),
                ],
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                sliver: SliverToBoxAdapter(
                  child: Text(
                    'To restore a look, open QRPersonafy on the PC, choose Restore from phone, then scan.',
                    style: Theme.of(context).textTheme.bodyMedium
                        ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
                  ),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 104),
                sliver: SliverList.separated(
                  itemCount: profiles.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 16),
                  itemBuilder: (context, i) => ProfileCard(
                    key: ValueKey(profiles[i].id),
                    profile: profiles[i],
                    store: widget.store,
                    onTap: () => _open(profiles[i]),
                  ),
                ),
              ),
            ],
          );
        },
      ),
      floatingActionButton: FutureBuilder<List<SavedProfile>>(
        future: _profiles,
        builder: (context, snapshot) => (snapshot.data?.isNotEmpty ?? false)
            ? FloatingActionButton.extended(
                onPressed: _scan,
                icon: const Icon(Icons.qr_code_scanner),
                label: const Text('Scan PC code'),
              )
            : const SizedBox.shrink(),
      ),
    );
  }
}

class _Welcome extends StatelessWidget {
  const _Welcome({required this.onScan, required this.onRestore});

  final VoidCallback onScan;
  final VoidCallback onRestore;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Padding(padding: EdgeInsets.symmetric(horizontal: 24), child: PcPreview(radius: 20)),
            const SizedBox(height: 32),
            Text('Take your Windows look anywhere', style: theme.textTheme.headlineMedium),
            const SizedBox(height: 12),
            Text(
              "Save a PC's wallpaper, colors, taskbar, Start, mouse and keyboard settings on this phone, "
              'and put them back on any PC in a minute.',
              style: theme.textTheme.bodyLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 28),
            const Steps(
              steps: ['Open QRPersonafy on your PC', 'Choose Save this PC', 'Tap Scan PC code and point at the code'],
            ),
            const SizedBox(height: 32),
            FilledButton.icon(
              onPressed: onScan,
              icon: const Icon(Icons.qr_code_scanner),
              label: const Text('Scan PC code'),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
            ),
            const SizedBox(height: 16),
            TextButton.icon(
              onPressed: onRestore,
              icon: const Icon(Icons.cloud_download_outlined),
              label: const Text('New phone? Restore from your backup'),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(Icons.lock_outline, size: 18, color: theme.colorScheme.onSurfaceVariant),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Everything is encrypted on this phone. Backups go only to a server you choose.',
                    style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// A saved PC with a preview of its desktop.
class ProfileCard extends StatefulWidget {
  const ProfileCard({super.key, required this.profile, required this.store, this.onTap, this.selected});

  final SavedProfile profile;
  final ProfileStore store;
  final VoidCallback? onTap;

  /// When not null, the card is part of a choice and shows whether it is the chosen one.
  final bool? selected;

  @override
  State<ProfileCard> createState() => _ProfileCardState();
}

class _ProfileCardState extends State<ProfileCard> {
  late final _thumbnail = widget.store.thumbnail(widget.profile.id);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final p = widget.profile;
    final selected = widget.selected;
    return Card.outlined(
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(
          color: selected == true ? theme.colorScheme.primary : theme.colorScheme.outlineVariant,
          width: selected == true ? 2 : 1,
        ),
      ),
      child: InkWell(
        onTap: widget.onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              FutureBuilder(
                future: _thumbnail,
                builder: (context, snapshot) =>
                    PcPreview(wallpaper: snapshot.data, accent: p.accent, dark: p.dark, radius: 12),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(p.name, style: theme.textTheme.titleMedium, overflow: TextOverflow.ellipsis),
                        Text(
                          'Saved ${formatDate(p.savedAt)} · ${p.settings.length} settings',
                          style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                        ),
                      ],
                    ),
                  ),
                  if (selected != null)
                    Icon(
                      selected ? Icons.check_circle : Icons.circle_outlined,
                      color: selected ? theme.colorScheme.primary : theme.colorScheme.outline,
                    )
                  else
                    const Icon(Icons.chevron_right),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

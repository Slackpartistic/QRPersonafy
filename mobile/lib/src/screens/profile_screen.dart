import 'package:flutter/material.dart';

import '../app.dart';
import '../profile_store.dart';
import '../widgets/common.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, required this.profile, required this.store});

  final SavedProfile profile;
  final ProfileStore store;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late SavedProfile _profile = widget.profile;
  late final Future<int> _size = widget.store.sizeOf(widget.profile.id);
  late final _thumbnail = widget.store.thumbnail(widget.profile.id);

  Future<void> _rename() async {
    final controller = TextEditingController(text: _profile.name);
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Rename'),
        content: TextField(controller: controller, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Save')),
        ],
      ),
    );
    controller.dispose();
    if (name == null || name.isEmpty) return;
    final renamed = await widget.store.rename(_profile, name);
    setState(() => _profile = renamed);
  }

  Future<void> _delete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete ${_profile.name}?'),
        content: const Text('These saved settings will be removed from this phone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.store.delete(_profile.id);
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_profile.name),
        actions: [
          IconButton(onPressed: _rename, icon: const Icon(Icons.edit_outlined), tooltip: 'Rename'),
          IconButton(onPressed: _delete, icon: const Icon(Icons.delete_outline), tooltip: 'Delete'),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          FutureBuilder(
            future: _thumbnail,
            builder: (context, snapshot) =>
                PcPreview(wallpaper: snapshot.data, accent: _profile.accent, dark: _profile.dark),
          ),
          const SizedBox(height: 20),
          SettingChips(settings: _profile.settings),
          const SizedBox(height: 20),
          Card.outlined(
            child: Column(
              children: [
                ListTile(leading: const Icon(Icons.computer), title: const Text('From'), subtitle: Text(_profile.pcName)),
                ListTile(
                  leading: const Icon(Icons.event_outlined),
                  title: const Text('Saved'),
                  subtitle: Text(formatDate(_profile.savedAt)),
                ),
                ListTile(
                  leading: const Icon(Icons.info_outline),
                  title: const Text('Windows build'),
                  subtitle: Text(_profile.windowsBuild),
                ),
                FutureBuilder<int>(
                  future: _size,
                  builder: (context, snapshot) => ListTile(
                    leading: const Icon(Icons.lock_outline),
                    title: const Text('Size, encrypted'),
                    subtitle: Text(snapshot.hasData ? formatSize(snapshot.data!) : '…'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Text('Put this look on a PC', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          const Steps(steps: [
            'Open QRPersonafy on the PC',
            'Choose Restore from phone',
            'Scan the code and pick this PC',
          ]),
        ],
      ),
    );
  }
}

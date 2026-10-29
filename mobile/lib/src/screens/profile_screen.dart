import 'package:flutter/material.dart';

import '../app.dart';
import '../profile_store.dart';

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
        children: [
          ListTile(title: const Text('From'), subtitle: Text(_profile.pcName)),
          ListTile(title: const Text('Saved'), subtitle: Text(formatDate(_profile.savedAt))),
          ListTile(title: const Text('Windows build'), subtitle: Text(_profile.windowsBuild)),
          FutureBuilder<int>(
            future: _size,
            builder: (context, snapshot) =>
                ListTile(title: const Text('Size'), subtitle: Text(snapshot.hasData ? formatSize(snapshot.data!) : '…')),
          ),
          const Divider(),
          for (final s in _profile.settings)
            ListTile(leading: const Icon(Icons.check), title: Text(settingLabels[s] ?? s)),
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text('To restore these, run  qrpersonafy receive  on the PC and scan its code.'),
          ),
        ],
      ),
    );
  }
}

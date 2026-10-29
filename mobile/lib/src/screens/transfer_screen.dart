import 'package:flutter/material.dart';

import '../look.dart';
import '../pairing.dart';
import '../profile_store.dart';
import '../widgets/common.dart';
import 'home_screen.dart' show ProfileCard;

/// After a scan: saves the PC's settings (send mode) or sends a saved profile to the PC (receive mode).
class TransferScreen extends StatelessWidget {
  const TransferScreen({super.key, required this.request, required this.store, required this.client});

  final PairRequest request;
  final ProfileStore store;
  final PairingClient client;

  @override
  Widget build(BuildContext context) {
    return request.mode == PairMode.send
        ? _SaveFromPc(request: request, store: store, client: client)
        : _RestoreToPc(request: request, store: store, client: client);
  }
}

Widget _backHome(BuildContext context, String label) =>
    FilledButton(onPressed: () => Navigator.of(context).pop(), child: Text(label));

String _errorText(Object error) => error is PairingException ? error.message : '$error';

class _SaveFromPc extends StatefulWidget {
  const _SaveFromPc({required this.request, required this.store, required this.client});

  final PairRequest request;
  final ProfileStore store;
  final PairingClient client;

  @override
  State<_SaveFromPc> createState() => _SaveFromPcState();
}

class _SaveFromPcState extends State<_SaveFromPc> {
  late final _name = TextEditingController(text: widget.request.pcName);
  Map<String, dynamic>? _profile;
  ProfileLook? _look;
  String? _error;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    widget.client.download(widget.request).then(
          (profile) => setState(() {
            _profile = profile;
            _look = ProfileLook.of(profile);
          }),
          onError: (Object error) => setState(() => _error = _errorText(error)),
        );
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    setState(() => _saving = true);
    try {
      await widget.store.save(_profile!, name: name.isEmpty ? widget.request.pcName : name,
          pcName: widget.request.pcName);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Saved ${_name.text.trim()}')));
      Navigator.of(context).pop();
    } on Object catch (error) {
      setState(() {
        _saving = false;
        _error = 'Could not save: $error';
      });
    }
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pc = widget.request.pcName;
    final profile = _profile;
    final look = _look;
    final settings = profile?['settings'];
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text('Save $pc')),
      body: _error != null
          ? StatusView(kind: StatusKind.bad, title: 'That didn\'t work', text: _error, action: _backHome(context, 'Back'))
          : profile == null || look == null
              ? StatusView(
                  kind: StatusKind.busy,
                  title: 'Getting settings from $pc',
                  text: 'Keep QRPersonafy open on the PC.',
                )
              : ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    PcPreview(wallpaper: look.wallpaper, accent: look.accent, dark: look.dark),
                    const SizedBox(height: 24),
                    Text('Here is $pc', style: theme.textTheme.headlineSmall),
                    const SizedBox(height: 4),
                    Text('These settings will be saved on this phone, encrypted.',
                        style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
                    const SizedBox(height: 16),
                    SettingChips(settings: settings is Map ? [for (final k in settings.keys) '$k'] : const []),
                    const SizedBox(height: 28),
                    TextField(
                      controller: _name,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(
                        labelText: 'Name it',
                        helperText: 'For example: Gaming PC or Work laptop',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: _saving ? null : _save,
                      icon: const Icon(Icons.download_done),
                      label: const Text('Save on this phone'),
                      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
                    ),
                  ],
                ),
    );
  }
}

class _RestoreToPc extends StatefulWidget {
  const _RestoreToPc({required this.request, required this.store, required this.client});

  final PairRequest request;
  final ProfileStore store;
  final PairingClient client;

  @override
  State<_RestoreToPc> createState() => _RestoreToPcState();
}

class _RestoreToPcState extends State<_RestoreToPc> {
  late final Future<List<SavedProfile>> _profiles = widget.store.list();
  SavedProfile? _chosen;
  bool _sending = false;
  ReceiveResult? _result;
  String? _error;

  Future<void> _send() async {
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final profile = await widget.store.load(_chosen!.id);
      final result = await widget.client.upload(widget.request, profile);
      setState(() => _result = result);
    } on Object catch (error) {
      setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pc = widget.request.pcName;
    final result = _result;
    final theme = Theme.of(context);
    final Widget body;
    if (result != null) {
      body = StatusView(
        kind: StatusKind.good,
        title: 'Applied to $pc',
        text: result.applied.isEmpty ? 'Nothing needed changing.' : null,
        action: _backHome(context, 'Done'),
        child: Column(
          children: [
            SettingChips(settings: result.applied),
            if (result.warnings.isNotEmpty) ...[
              const SizedBox(height: 20),
              Card.filled(
                color: theme.colorScheme.tertiaryContainer,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final w in result.warnings)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Text(w, style: TextStyle(color: theme.colorScheme.onTertiaryContainer)),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      );
    } else if (_error != null) {
      body = StatusView(kind: StatusKind.bad, title: 'That didn\'t work', text: _error, action: _backHome(context, 'Back'));
    } else if (_sending) {
      body = StatusView(
        kind: StatusKind.busy,
        title: 'Check your PC',
        text: 'Choose Apply to this PC on $pc to finish.',
      );
    } else {
      body = FutureBuilder<List<SavedProfile>>(
        future: _profiles,
        builder: (context, snapshot) {
          final profiles = snapshot.data;
          if (profiles == null) return const Center(child: CircularProgressIndicator());
          if (profiles.isEmpty) {
            return StatusView(
              kind: StatusKind.bad,
              title: 'No saved PCs yet',
              text: 'Save a PC first: open QRPersonafy on it, choose Save this PC, then scan.',
              action: _backHome(context, 'Back'),
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
                child: Text('Which look should $pc get?', style: theme.textTheme.titleLarge),
              ),
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                  itemCount: profiles.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 12),
                  itemBuilder: (context, i) => ProfileCard(
                    profile: profiles[i],
                    store: widget.store,
                    selected: _chosen?.id == profiles[i].id,
                    onTap: () => setState(() => _chosen = profiles[i]),
                  ),
                ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: FilledButton.icon(
                    onPressed: _chosen == null ? null : _send,
                    icon: const Icon(Icons.send),
                    label: Text('Send to $pc'),
                    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
                  ),
                ),
              ),
            ],
          );
        },
      );
    }
    return Scaffold(appBar: AppBar(title: Text('Restore to $pc')), body: body);
  }
}

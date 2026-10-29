import 'package:flutter/material.dart';

import '../app.dart';
import '../pairing.dart';
import '../profile_store.dart';

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
  String? _error;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    widget.client.download(widget.request).then(
          (profile) => setState(() => _profile = profile),
          onError: (Object error) => setState(() => _error = '$error'),
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
    final profile = _profile;
    final settings = profile?['settings'];
    return Scaffold(
      appBar: AppBar(title: Text('Save ${widget.request.pcName}')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: _error != null
            ? _Status(icon: Icons.error_outline, text: _error!)
            : profile == null
                ? _Status(busy: true, text: 'Getting settings from ${widget.request.pcName}…')
                : ListView(
                    children: [
                      Text('Received from ${widget.request.pcName}', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 8),
                      Text(settingsSummary(settings is Map ? [for (final k in settings.keys) '$k'] : const [])),
                      const SizedBox(height: 24),
                      TextField(
                        controller: _name,
                        decoration: const InputDecoration(labelText: 'Name', border: OutlineInputBorder()),
                      ),
                      const SizedBox(height: 24),
                      FilledButton.icon(
                        onPressed: _saving ? null : _save,
                        icon: const Icon(Icons.save_alt),
                        label: const Text('Save on this phone'),
                      ),
                    ],
                  ),
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
      setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pc = widget.request.pcName;
    final result = _result;
    return Scaffold(
      appBar: AppBar(title: Text('Restore to $pc')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: result != null
            ? _Status(
                icon: Icons.check_circle_outline,
                text: 'Applied to $pc: ${settingsSummary(result.applied)}'
                    '${result.warnings.isEmpty ? '' : '\n\nWarnings:\n${result.warnings.join('\n')}'}',
              )
            : _error != null
                ? _Status(icon: Icons.error_outline, text: _error!)
                : _sending
                    ? _Status(busy: true, text: 'Sent. Confirm on $pc to apply the settings.')
                    : FutureBuilder<List<SavedProfile>>(
                        future: _profiles,
                        builder: (context, snapshot) {
                          final profiles = snapshot.data;
                          if (profiles == null) return const Center(child: CircularProgressIndicator());
                          if (profiles.isEmpty) {
                            return const _Status(
                              icon: Icons.inbox_outlined,
                              text: 'No saved PCs on this phone yet. Run  qrpersonafy send  on a PC first.',
                            );
                          }
                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text('Which settings should $pc get?', style: Theme.of(context).textTheme.titleMedium),
                              const SizedBox(height: 8),
                              Expanded(
                                child: RadioGroup<String>(
                                  groupValue: _chosen?.id,
                                  onChanged: (id) =>
                                      setState(() => _chosen = profiles.firstWhere((p) => p.id == id)),
                                  child: ListView(
                                    children: [
                                      for (final p in profiles)
                                        RadioListTile<String>(
                                          value: p.id,
                                          title: Text(p.name),
                                          subtitle: Text(formatDate(p.savedAt)),
                                        ),
                                    ],
                                  ),
                                ),
                              ),
                              FilledButton.icon(
                                onPressed: _chosen == null ? null : _send,
                                icon: const Icon(Icons.send_to_mobile),
                                label: Text('Send to $pc'),
                              ),
                            ],
                          );
                        },
                      ),
      ),
    );
  }
}

class _Status extends StatelessWidget {
  const _Status({required this.text, this.icon, this.busy = false});

  final String text;
  final IconData? icon;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (busy) const CircularProgressIndicator() else Icon(icon, size: 56),
          const SizedBox(height: 16),
          Text(text, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyLarge),
        ],
      ),
    );
  }
}

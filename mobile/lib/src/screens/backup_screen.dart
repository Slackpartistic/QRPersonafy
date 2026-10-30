import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app.dart';
import '../backup/backup_service.dart';
import '../backup/webdav.dart';

/// Sets up, runs and restores the backup to the user's own server.
class BackupScreen extends StatefulWidget {
  const BackupScreen({super.key, required this.backup});

  final BackupService backup;

  @override
  State<BackupScreen> createState() => _BackupScreenState();
}

class _BackupScreenState extends State<BackupScreen> {
  BackupSettings? _settings;
  bool _loaded = false;
  bool _busy = false;
  String? _error;

  // Shown once, right after a new backup is created.
  String? _newCode;

  // Set when the server already has backups and their recovery code is needed.
  bool _needCode = false;

  final _url = TextEditingController();
  final _user = TextEditingController();
  final _password = TextEditingController();
  final _code = TextEditingController();

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    for (final c in [_url, _user, _password, _code]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _reload() async {
    final settings = await widget.backup.settings();
    if (!mounted) return;
    setState(() {
      _settings = settings;
      _loaded = true;
    });
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } on BackupException catch (error) {
      _error = error.message;
    } on FormatException catch (error) {
      _error = error.message;
    } on Object catch (error) {
      _error = '$error';
    }
    await _reload();
    if (mounted) setState(() => _busy = false);
  }

  void _toast(String text) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  Uri get _serverUrl => Uri.parse(_url.text.trim());

  Future<void> _connect() => _run(() async {
        final result = await widget.backup.connect(_serverUrl, _user.text.trim(), _password.text);
        switch (result) {
          case NewBackup(:final recoveryCode):
            _newCode = recoveryCode;
            await widget.backup.backUp();
          case ExistingBackup():
            _needCode = true;
        }
      });

  Future<void> _unlock() => _run(() async {
        await widget.backup.unlock(_serverUrl, _user.text.trim(), _password.text, _code.text);
        _needCode = false;
        final restored = await widget.backup.restore();
        if (mounted) _toast(restored == 0 ? 'Connected. Nothing new to restore.' : 'Restored $restored PCs');
      });

  Future<void> _backUp() => _run(() async {
        final uploaded = await widget.backup.backUp();
        if (mounted) _toast(uploaded == 0 ? 'Everything is already backed up' : 'Backed up $uploaded PCs');
      });

  Future<void> _restore() => _run(() async {
        final restored = await widget.backup.restore();
        if (mounted) _toast(restored == 0 ? 'Nothing new to restore' : 'Restored $restored PCs');
      });

  Future<void> _showCode() async {
    final code = await widget.backup.recoveryCode();
    if (code == null || !mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Recovery code'),
        content: _CodeBox(code: code),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
      ),
    );
  }

  Future<void> _disconnect() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Stop backing up?'),
        content: const Text('Your backups stay on the server. To use them again you will need the recovery code.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Stop')),
        ],
      ),
    );
    if (confirmed == true) await _run(widget.backup.disconnect);
  }

  @override
  Widget build(BuildContext context) {
    final Widget body;
    if (!_loaded) {
      body = const Center(child: CircularProgressIndicator());
    } else if (_newCode != null) {
      body = _NewCode(code: _newCode!, onDone: () => setState(() => _newCode = null));
    } else if (_settings != null) {
      body = _Connected(
        settings: _settings!,
        busy: _busy,
        error: _error,
        onBackUp: _backUp,
        onRestore: _restore,
        onShowCode: _showCode,
        onDisconnect: _disconnect,
      );
    } else {
      body = _SetUp(
        url: _url,
        user: _user,
        password: _password,
        code: _code,
        needCode: _needCode,
        busy: _busy,
        error: _error,
        onConnect: _needCode ? _unlock : _connect,
        onBack: () => setState(() => _needCode = false),
      );
    }
    return Scaffold(appBar: AppBar(title: const Text('Backup')), body: body);
  }
}

class _SetUp extends StatelessWidget {
  const _SetUp({
    required this.url,
    required this.user,
    required this.password,
    required this.code,
    required this.needCode,
    required this.busy,
    required this.error,
    required this.onConnect,
    required this.onBack,
  });

  final TextEditingController url, user, password, code;
  final bool needCode, busy;
  final String? error;
  final VoidCallback onConnect, onBack;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final muted = theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Icon(needCode ? Icons.key_outlined : Icons.cloud_outlined, size: 48, color: theme.colorScheme.primary),
        const SizedBox(height: 16),
        Text(needCode ? 'Enter your recovery code' : 'Back up to your own server', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(
          needCode
              ? 'This folder already has QRPersonafy backups. Type the recovery code you saved when you set them up.'
              : 'Keep a copy of your saved PCs on a server you control, such as Nextcloud or the QRPersonafy backup '
                  'server. Everything is encrypted on this phone first, so the server can\'t read it.',
          style: muted,
        ),
        const SizedBox(height: 24),
        if (needCode)
          TextField(
            controller: code,
            autofocus: true,
            textCapitalization: TextCapitalization.characters,
            autocorrect: false,
            decoration: const InputDecoration(labelText: 'Recovery code', hintText: 'ABCD-EFGH-…', border: OutlineInputBorder()),
          )
        else ...[
          TextField(
            controller: url,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: 'Server address',
              hintText: 'https://cloud.example.com/remote.php/dav/files/you/QRPersonafy',
              helperText: 'The WebDAV folder for your backups',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: user,
            autocorrect: false,
            decoration: const InputDecoration(labelText: 'User name', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: password,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Password',
              helperText: 'For Nextcloud, use an app password',
              border: OutlineInputBorder(),
            ),
          ),
        ],
        if (error != null) ...[
          const SizedBox(height: 16),
          Text(error!, style: TextStyle(color: theme.colorScheme.error)),
        ],
        const SizedBox(height: 24),
        FilledButton(
          onPressed: busy ? null : onConnect,
          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
          child: busy
              ? const SizedBox.square(dimension: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
              : Text(needCode ? 'Restore my PCs' : 'Connect'),
        ),
        if (needCode) TextButton(onPressed: busy ? null : onBack, child: const Text('Use a different server')),
      ],
    );
  }
}

class _NewCode extends StatelessWidget {
  const _NewCode({required this.code, required this.onDone});

  final String code;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Icon(Icons.key, size: 48, color: theme.colorScheme.primary),
        const SizedBox(height: 16),
        Text('Save your recovery code', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(
          "You'll need it to restore your PCs on a new phone. Write it down or keep it in a password manager. "
          "Without it, nobody can open your backups, not even you.",
          style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 24),
        _CodeBox(code: code),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: onDone,
          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
          child: const Text("I've saved it"),
        ),
      ],
    );
  }
}

class _CodeBox extends StatelessWidget {
  const _CodeBox({required this.code});

  final String code;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Four groups per line, so lines never break inside a group.
    final groups = code.split('-');
    final lines = [for (var i = 0; i < groups.length; i += 4) groups.skip(i).take(4).join('-')];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
          child: SelectableText(
            lines.join('\n'),
            textAlign: TextAlign.center,
            style: theme.textTheme.titleMedium?.copyWith(fontFamily: 'monospace', height: 1.6, letterSpacing: 1),
          ),
        ),
        const SizedBox(height: 8),
        TextButton.icon(
          onPressed: () {
            Clipboard.setData(ClipboardData(text: code));
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied')));
          },
          icon: const Icon(Icons.copy),
          label: const Text('Copy'),
        ),
      ],
    );
  }
}

class _Connected extends StatelessWidget {
  const _Connected({
    required this.settings,
    required this.busy,
    required this.error,
    required this.onBackUp,
    required this.onRestore,
    required this.onShowCode,
    required this.onDisconnect,
  });

  final BackupSettings settings;
  final bool busy;
  final String? error;
  final VoidCallback onBackUp, onRestore, onShowCode, onDisconnect;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final last = settings.lastBackup;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Row(
          children: [
            CircleAvatar(
              radius: 26,
              backgroundColor: error == null ? theme.colorScheme.primaryContainer : theme.colorScheme.errorContainer,
              child: busy
                  ? const SizedBox.square(dimension: 24, child: CircularProgressIndicator(strokeWidth: 3))
                  : Icon(error == null ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
                      color: error == null ? theme.colorScheme.onPrimaryContainer : theme.colorScheme.onErrorContainer),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Text(busy ? 'Working…' : (error == null ? 'Backup is on' : 'Backup needs attention'),
                  style: theme.textTheme.headlineSmall),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text(
          error ?? (last == null ? 'Not backed up yet.' : 'Last backup ${formatDate(last)}. New PCs are backed up when you save them.'),
          style: TextStyle(color: error == null ? theme.colorScheme.onSurfaceVariant : theme.colorScheme.error),
        ),
        const SizedBox(height: 16),
        Card.outlined(
          child: ListTile(
            leading: const Icon(Icons.dns_outlined),
            title: Text(settings.url.authority),
            subtitle: Text('${settings.user} · ${settings.url.path}', overflow: TextOverflow.ellipsis),
          ),
        ),
        const SizedBox(height: 20),
        FilledButton.icon(
          onPressed: busy ? null : onBackUp,
          icon: const Icon(Icons.cloud_upload_outlined),
          label: const Text('Back up now'),
          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: busy ? null : onRestore,
          icon: const Icon(Icons.cloud_download_outlined),
          label: const Text('Restore missing PCs'),
          style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
        ),
        const SizedBox(height: 20),
        TextButton.icon(onPressed: onShowCode, icon: const Icon(Icons.key_outlined), label: const Text('Show recovery code')),
        TextButton.icon(
          onPressed: busy ? null : onDisconnect,
          icon: const Icon(Icons.cloud_off_outlined),
          label: const Text('Stop backing up'),
        ),
      ],
    );
  }
}

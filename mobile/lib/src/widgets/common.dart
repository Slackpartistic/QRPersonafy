import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../profile_store.dart';

/// A little picture of a PC's desktop: its wallpaper (or its accent color) with a taskbar
/// in its light or dark mode.
class PcPreview extends StatelessWidget {
  const PcPreview({super.key, this.wallpaper, this.accent, this.dark, this.radius = 16});

  final Uint8List? wallpaper;
  final int? accent;
  final bool? dark;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final accentColor = accent == null ? scheme.primary : Color(accent!);
    final isDark = dark ?? false;
    final image = wallpaper;
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        child: Stack(
          fit: StackFit.expand,
          children: [
            if (image != null)
              Image.memory(image, fit: BoxFit.cover, cacheWidth: 720, gaplessPlayback: true,
                  errorBuilder: (_, _, _) => _Gradient(accentColor))
            else
              _Gradient(accentColor),
            Align(
              alignment: Alignment.bottomCenter,
              child: FractionallySizedBox(
                heightFactor: 0.14,
                widthFactor: 1,
                child: ColoredBox(
                  color: (isDark ? const Color(0xFF1F1F23) : const Color(0xFFF3F3F3)).withValues(alpha: 0.92),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      for (var i = 0; i < 5; i++)
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 3),
                          child: FractionallySizedBox(
                            heightFactor: 0.5,
                            child: AspectRatio(
                              aspectRatio: 1,
                              child: DecoratedBox(
                                decoration: BoxDecoration(
                                  color: i == 0 ? accentColor : (isDark ? Colors.white24 : Colors.black12),
                                  borderRadius: BorderRadius.circular(3),
                                ),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Gradient extends StatelessWidget {
  const _Gradient(this.color);

  final Color color;

  @override
  Widget build(BuildContext context) {
    final hsl = HSLColor.fromColor(color);
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            hsl.withLightness((hsl.lightness + 0.2).clamp(0, 0.85)).toColor(),
            hsl.withLightness((hsl.lightness - 0.15).clamp(0.1, 1)).toColor(),
          ],
        ),
      ),
    );
  }
}

/// The settings in a profile, as small chips.
class SettingChips extends StatelessWidget {
  const SettingChips({super.key, required this.settings});

  final List<String> settings;

  static const _icons = {
    'wallpaper': Icons.wallpaper,
    'theme': Icons.contrast,
    'accent': Icons.palette_outlined,
    'taskbar': Icons.view_agenda_outlined,
    'start': Icons.grid_view,
    'mouse': Icons.mouse_outlined,
    'keyboard': Icons.keyboard_outlined,
  };

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final s in settings)
          Chip(
            avatar: Icon(_icons[s] ?? Icons.check, size: 18),
            label: Text(settingLabels[s] ?? s),
            visualDensity: VisualDensity.compact,
          ),
      ],
    );
  }
}

enum StatusKind { busy, good, bad }

/// A centered state: busy, done or failed, with an optional action.
class StatusView extends StatelessWidget {
  const StatusView({super.key, required this.kind, required this.title, this.text, this.child, this.action});

  final StatusKind kind;
  final String title;
  final String? text;
  final Widget? child;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final (icon, fg, bg) = switch (kind) {
      StatusKind.good => (Icons.check_rounded, scheme.onPrimaryContainer, scheme.primaryContainer),
      StatusKind.bad => (Icons.priority_high_rounded, scheme.onErrorContainer, scheme.errorContainer),
      StatusKind.busy => (null, scheme.primary, scheme.surfaceContainerHighest),
    };
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 88,
              height: 88,
              decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
              padding: const EdgeInsets.all(22),
              child: icon == null
                  ? CircularProgressIndicator(strokeWidth: 4, color: fg)
                  : Icon(icon, size: 44, color: fg),
            ),
            const SizedBox(height: 24),
            Text(title, textAlign: TextAlign.center, style: theme.textTheme.headlineSmall),
            if (text != null) ...[
              const SizedBox(height: 8),
              Text(text!, textAlign: TextAlign.center,
                  style: theme.textTheme.bodyLarge?.copyWith(color: scheme.onSurfaceVariant)),
            ],
            if (child != null) ...[const SizedBox(height: 20), child!],
            if (action != null) ...[const SizedBox(height: 28), action!],
          ],
        ),
      ),
    );
  }
}

/// Numbered steps, for explaining what to do on the PC.
class Steps extends StatelessWidget {
  const Steps({super.key, required this.steps});

  final List<String> steps;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < steps.length; i++)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 14,
                  backgroundColor: scheme.primary,
                  foregroundColor: scheme.onPrimary,
                  child: Text('${i + 1}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                ),
                const SizedBox(width: 14),
                Expanded(child: Text(steps[i], style: Theme.of(context).textTheme.bodyLarge)),
              ],
            ),
          ),
      ],
    );
  }
}

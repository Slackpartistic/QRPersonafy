// Reads the parts of a profile that show what a PC looks like: accent color, light or dark
// mode and the wallpaper. Profiles come from a PC over the network, so anything odd is ignored.

import 'dart:convert';
import 'dart:typed_data';
import 'dart:ui' as ui;

const _dwm = r'Software\Microsoft\Windows\DWM';
const _personalize = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize';

class ProfileLook {
  const ProfileLook({this.accent, this.dark, this.wallpaper});

  /// ARGB, ready for `Color(accent)`.
  final int? accent;
  final bool? dark;

  /// The wallpaper image file as saved on the PC.
  final Uint8List? wallpaper;

  static ProfileLook of(Map<String, dynamic> profile) {
    final settings = profile['settings'];
    if (settings is! Map) return const ProfileLook();
    int? accent;
    final abgr = _value(settings['accent'], _dwm, 'AccentColor');
    if (abgr is int) {
      // Windows stores 0xAABBGGRR.
      final red = abgr & 0xFF, green = (abgr >> 8) & 0xFF, blue = (abgr >> 16) & 0xFF;
      accent = 0xFF000000 | (red << 16) | (green << 8) | blue;
    }
    final light = _value(settings['theme'], _personalize, 'SystemUsesLightTheme') ??
        _value(settings['theme'], _personalize, 'AppsUseLightTheme');
    return ProfileLook(
      accent: accent,
      dark: light is int ? light == 0 : null,
      wallpaper: _wallpaper(settings['wallpaper']),
    );
  }

  static Object? _value(Object? section, String key, String name) {
    if (section is! Map || section['registry'] is! List) return null;
    for (final entry in section['registry'] as List) {
      if (entry is Map &&
          '${entry['key']}'.toLowerCase() == key.toLowerCase() &&
          '${entry['name']}'.toLowerCase() == name.toLowerCase()) {
        return entry['data'];
      }
    }
    return null;
  }

  static Uint8List? _wallpaper(Object? section) {
    if (section is! Map || section['files'] is! Map) return null;
    final image = (section['files'] as Map)['image'];
    if (image is! Map || image['data'] is! String) return null;
    try {
      return base64.decode(image['data'] as String);
    } on FormatException {
      return null;
    }
  }
}

/// A small PNG of [image] for lists, or null if it isn't an image Flutter can decode.
Future<Uint8List?> makeThumbnail(Uint8List image, {int width = 480}) async {
  try {
    final codec = await ui.instantiateImageCodec(image, targetWidth: width);
    final frame = await codec.getNextFrame();
    final data = await frame.image.toByteData(format: ui.ImageByteFormat.png);
    frame.image.dispose();
    codec.dispose();
    return data?.buffer.asUint8List();
  } on Object {
    return null;
  }
}

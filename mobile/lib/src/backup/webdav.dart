// A small WebDAV client: just what backups need. Works with Nextcloud, ownCloud, rclone and
// other WebDAV servers.

import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

class BackupException implements Exception {
  BackupException(this.message);
  final String message;
  @override
  String toString() => message;
}

class WebDavClient {
  WebDavClient(Uri folder, String user, String password, {http.Client? client})
      : folder = folder.path.endsWith('/') ? folder : folder.replace(path: '${folder.path}/'),
        _auth = 'Basic ${base64.encode(utf8.encode('$user:$password'))}',
        _client = client ?? http.Client();

  /// The folder backups go in. Always ends with a slash.
  final Uri folder;
  final String _auth;
  final http.Client _client;

  static const _timeout = Duration(seconds: 60);

  Uri _file(String name) => folder.resolve(Uri.encodeComponent(name));

  Future<http.StreamedResponse> _send(String method, Uri url, {List<int>? body, Map<String, String>? headers}) async {
    final request = http.Request(method, url)
      ..headers['Authorization'] = _auth
      ..headers.addAll(headers ?? const {});
    if (body != null) request.bodyBytes = body;
    try {
      final response = await _client.send(request).timeout(_timeout);
      if (response.statusCode == 401 || response.statusCode == 403) {
        throw BackupException('The server refused the user name or password.');
      }
      return response;
    } on BackupException {
      rethrow;
    } on Object catch (error) {
      throw BackupException("Couldn't reach the backup server: $error");
    }
  }

  Never _fail(String what, http.StreamedResponse response) =>
      throw BackupException('$what failed: the server answered ${response.statusCode} ${response.reasonPhrase ?? ''}'.trim());

  /// Creates the backup folder if it doesn't exist yet.
  Future<void> ensureFolder() async {
    final response = await _send('MKCOL', folder);
    await response.stream.drain<void>();
    // 405 means it already exists.
    if (response.statusCode != 201 && response.statusCode != 405) _fail('Creating the backup folder', response);
  }

  /// Names of the files in the backup folder.
  Future<List<String>> list() async {
    final response = await _send('PROPFIND', folder, headers: {'Depth': '1', 'Content-Type': 'application/xml'},
        body: utf8.encode('<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>'));
    final body = await response.stream.bytesToString();
    if (response.statusCode == 404) return [];
    if (response.statusCode != 207) _fail('Listing backups', response);
    return parseNames(body, folder);
  }

  Future<void> put(String name, List<int> data) async {
    final response = await _send('PUT', _file(name),
        body: data, headers: {'Content-Type': 'application/octet-stream'});
    await response.stream.drain<void>();
    if (response.statusCode >= 300) _fail('Uploading a backup', response);
  }

  /// The file's contents, or null if it doesn't exist.
  Future<Uint8List?> get(String name) async {
    final response = await _send('GET', _file(name));
    final data = await response.stream.toBytes();
    if (response.statusCode == 404) return null;
    if (response.statusCode != 200) _fail('Downloading a backup', response);
    return data;
  }

  Future<void> delete(String name) async {
    final response = await _send('DELETE', _file(name));
    await response.stream.drain<void>();
    if (response.statusCode >= 300 && response.statusCode != 404) _fail('Deleting a backup', response);
  }

  static final _href = RegExp(r'<(?:[A-Za-z0-9_-]+:)?href>\s*([^<]*?)\s*</(?:[A-Za-z0-9_-]+:)?href>', caseSensitive: false);

  /// File names from a PROPFIND reply, leaving out the folder itself and subfolders.
  static List<String> parseNames(String xml, Uri folder) {
    final names = <String>[];
    for (final match in _href.allMatches(xml)) {
      final href = match.group(1)!.replaceAll('&amp;', '&');
      final path = Uri.decodeFull(Uri.parse(href).path);
      if (path.endsWith('/')) continue; // the folder itself, or a subfolder
      final name = path.substring(path.lastIndexOf('/') + 1);
      if (name.isNotEmpty) names.add(name);
    }
    return names;
  }
}

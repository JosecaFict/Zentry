import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  TokenStorage([FlutterSecureStorage? storage])
    : _storage =
          storage ??
          const FlutterSecureStorage(
            iOptions: IOSOptions(
              accessibility: KeychainAccessibility.first_unlock,
            ),
            aOptions: AndroidOptions(resetOnError: true),
          );

  static const _key = 'zentry_access_token';
  static const _profileKey = 'zentry_offline_profile';
  final FlutterSecureStorage _storage;

  Future<String?> read() => _storage.read(key: _key);
  Future<void> write(String token) => _storage.write(key: _key, value: token);
  Future<void> clear() async {
    await _storage.delete(key: _key);
    await _storage.delete(key: _profileKey);
  }

  Future<void> cacheProfile(String token, Map<String, dynamic> profile) =>
      _storage.write(
        key: _profileKey,
        value: jsonEncode({'token': token, 'profile': profile}),
      );

  Future<Map<String, dynamic>?> readOfflineProfile() async {
    final token = await read();
    final cached = await _storage.read(key: _profileKey);
    if (token == null || cached == null) return null;
    try {
      final parts = token.split('.');
      if (parts.length != 3) return null;
      final claims = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      );
      final expiry = claims['exp'];
      if (expiry is! int ||
          expiry * 1000 <= DateTime.now().millisecondsSinceEpoch) {
        return null;
      }
      final data = jsonDecode(cached);
      return data['token'] == token
          ? data['profile'] as Map<String, dynamic>?
          : null;
    } on FormatException {
      return null;
    }
  }
}

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final tenantStorageProvider = Provider<TenantStorage>((ref) => TenantStorage());

class TenantStorage {
  TenantStorage([FlutterSecureStorage? storage])
    : _storage =
          storage ??
          const FlutterSecureStorage(
            iOptions: IOSOptions(
              accessibility: KeychainAccessibility.first_unlock,
            ),
            aOptions: AndroidOptions(resetOnError: true),
          );

  static const _key = 'zentry_tenant_slug';
  static const _contextKey = 'zentry_tenant_context';
  final FlutterSecureStorage _storage;

  Future<String?> read() => _storage.read(key: _key);
  Future<void> write(String slug) => _storage.write(key: _key, value: slug);
  Future<void> clear() async {
    await _storage.delete(key: _key);
    await _storage.delete(key: _contextKey);
  }

  Future<void> cacheContext(Map<String, dynamic> data) =>
      _storage.write(key: _contextKey, value: jsonEncode(data));

  Future<Map<String, dynamic>?> readContext(String slug) async {
    final value = await _storage.read(key: _contextKey);
    if (value == null) return null;
    final data = jsonDecode(value) as Map<String, dynamic>;
    return data['slug'] == slug ? data : null;
  }
}

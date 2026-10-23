import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final tenantStorageProvider = Provider<TenantStorage>((ref) => TenantStorage());

class TenantStorage {
  TenantStorage([FlutterSecureStorage? storage])
      : _storage = storage ??
            const FlutterSecureStorage(
              iOptions: IOSOptions(
                accessibility: KeychainAccessibility.first_unlock,
              ),
              aOptions: AndroidOptions(resetOnError: true),
            );

  static const _key = 'zentry_tenant_slug';
  final FlutterSecureStorage _storage;

  Future<String?> read() => _storage.read(key: _key);
  Future<void> write(String slug) => _storage.write(key: _key, value: slug);
  Future<void> clear() => _storage.delete(key: _key);
}

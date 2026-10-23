import 'dart:async';

import 'package:capricho_store/core/auth/token_storage.dart';
import 'package:capricho_store/core/config/environment.dart';
import 'package:capricho_store/core/tenant/tenant_storage.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final tokenStorageProvider = Provider<TokenStorage>((ref) => TokenStorage());

/// Stream de eventos de expiración de sesión (401 en endpoints protegidos)
final sessionExpiredEventProvider = StreamController<void>.broadcast();

final dioProvider = Provider<Dio>((ref) {
  final storage = ref.watch(tokenStorageProvider);
  final tenantStorage = ref.watch(tenantStorageProvider);
  final dio = Dio(
    BaseOptions(
      baseUrl: Environment.apiBaseUrl,
      connectTimeout: const Duration(seconds: 12),
      receiveTimeout: const Duration(seconds: 15),
      headers: const {'Accept': 'application/json'},
    ),
  );

  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) async {
        final tenantSlug = await tenantStorage.read();
        if (tenantSlug != null && tenantSlug.isNotEmpty) {
          options.headers['X-Tenant-Slug'] = tenantSlug;
        }
        final token = await storage.read();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        if (error.response?.statusCode == 401) {
          final path = error.requestOptions.path;
          final hasToken = (await storage.read()) != null;
          // Solo disparar expiración si había una sesión previa activa y no es login/registro
          if (hasToken &&
              !path.contains('/auth/login') &&
              !path.contains('/auth/register')) {
            await storage.clear();
            sessionExpiredEventProvider.add(null);
          }
        }
        handler.next(error);
      },
    ),
  );

  return dio;
});

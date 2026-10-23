import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/core/tenant/tenant_storage.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class TenantIdentity {
  const TenantIdentity({
    required this.name,
    required this.slug,
    this.logoUrl,
    this.primaryColor = '#064FE8',
    this.primaryDarkColor = '#0039B8',
  });

  final String name;
  final String slug;
  final String? logoUrl;
  final String primaryColor;
  final String primaryDarkColor;

  factory TenantIdentity.fromJson(Map<String, dynamic> json) => TenantIdentity(
        name: json['nombre'] as String,
        slug: json['slug'] as String,
        logoUrl: json['logo_url'] as String?,
        primaryColor: json['color_primario'] as String? ?? '#064FE8',
        primaryDarkColor:
            json['color_primario_oscuro'] as String? ?? '#0039B8',
      );

  Color get color => _hexColor(primaryColor, const Color(0xFF064FE8));

  static Color _hexColor(String value, Color fallback) {
    final normalized = value.replaceFirst('#', '');
    final parsed = int.tryParse(normalized, radix: 16);
    return parsed == null ? fallback : Color(0xFF000000 | parsed);
  }
}

class TenantState {
  const TenantState({
    this.selected,
    this.results = const [],
    this.initialized = false,
    this.loading = false,
    this.error,
  });

  final TenantIdentity? selected;
  final List<TenantIdentity> results;
  final bool initialized;
  final bool loading;
  final String? error;

  TenantState copyWith({
    TenantIdentity? selected,
    List<TenantIdentity>? results,
    bool? initialized,
    bool? loading,
    String? error,
    bool clearSelected = false,
    bool clearError = false,
  }) =>
      TenantState(
        selected: clearSelected ? null : (selected ?? this.selected),
        results: results ?? this.results,
        initialized: initialized ?? this.initialized,
        loading: loading ?? this.loading,
        error: clearError ? null : (error ?? this.error),
      );
}

final tenantControllerProvider =
    NotifierProvider<TenantController, TenantState>(TenantController.new);

class TenantController extends Notifier<TenantState> {
  @override
  TenantState build() => const TenantState();

  Future<void> restore() async {
    final slug = await ref.read(tenantStorageProvider).read();
    if (slug == null || slug.isEmpty) {
      state = const TenantState(initialized: true);
      return;
    }
    try {
      final response = await ref.read(dioProvider).get<Map<String, dynamic>>(
            '/tenant/context',
          );
      state = TenantState(
        selected: TenantIdentity.fromJson(response.data!),
        initialized: true,
      );
    } catch (_) {
      await ref.read(tenantStorageProvider).clear();
      await ref.read(tokenStorageProvider).clear();
      state = const TenantState(
        initialized: true,
        error: 'La empresa guardada ya no está disponible.',
      );
    }
  }

  Future<void> search(String query) async {
    final clean = query.trim();
    if (clean.length < 2) {
      state = state.copyWith(
        results: const [],
        loading: false,
        clearError: true,
      );
      return;
    }
    state = state.copyWith(loading: true, clearError: true);
    try {
      final response = await ref.read(dioProvider).get<List<dynamic>>(
        '/public/tenants',
        queryParameters: {'query': clean},
      );
      final results = response.data!
          .cast<Map<String, dynamic>>()
          .map(TenantIdentity.fromJson)
          .toList(growable: false);
      state = state.copyWith(results: results, loading: false);
    } on DioException catch (error) {
      state = state.copyWith(
        loading: false,
        error: ApiException.fromDio(error).toString().replaceAll('ApiException: ', ''),
      );
    }
  }

  Future<void> select(TenantIdentity tenant) async {
    await ref.read(tokenStorageProvider).clear();
    await ref.read(tenantStorageProvider).write(tenant.slug);
    state = TenantState(selected: tenant, initialized: true);
  }

  Future<void> clear() async {
    await ref.read(tokenStorageProvider).clear();
    await ref.read(tenantStorageProvider).clear();
    state = const TenantState(initialized: true);
  }
}

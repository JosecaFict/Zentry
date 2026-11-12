import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final catalogRepositoryProvider = Provider<CatalogRepository>(
  (ref) => CatalogRepository(
    ref.watch(dioProvider),
    cache: ref.watch(offlineDatabaseProvider),
    tenantSlug: ref.watch(
      tenantControllerProvider.select((state) => state.selected?.slug),
    ),
  ),
);

/// Consulta el catálogo en la API y guarda cada respuesta en SQLite.
/// Si no hay red (o el servidor falla), devuelve la última respuesta guardada
/// para que las pantallas sigan funcionando sin conexión.
class CatalogRepository {
  const CatalogRepository(this._dio, {this.cache, this.tenantSlug});

  final Dio _dio;

  /// Base local donde se guardan las respuestas; sin ella no hay modo offline.
  final OfflineDatabase? cache;

  /// Empresa activa: separa la caché para no mezclar catálogos.
  final String? tenantSlug;

  Future<ProductPage> products(CatalogQuery query) {
    // [CU-04] Consultar catálogo con filtros
    final params = query.toQuery();
    return _cached(
      _key('products', params),
      () async => (await _dio.get<Map<String, dynamic>>(
        '/products',
        queryParameters: params,
      )).data,
      (json) => ProductPage.fromJson(json! as Map<String, dynamic>),
    );
  }

  Future<Product> product(int id, {int? branchId}) {
    // [CU-04] Ver detalle de prenda y stock por sucursal
    final params = <String, dynamic>{'sucursal': ?branchId};
    return _cached(
      _key('products/$id', params),
      () async => (await _dio.get<Map<String, dynamic>>(
        '/products/$id',
        queryParameters: params,
      )).data,
      (json) => Product.fromJson(json! as Map<String, dynamic>),
    );
  }

  Future<List<BranchItem>> branches() => _cached(
    // [CU-03] Listar sucursales activas
    'branches',
    () async => (await _dio.get<List<dynamic>>('/branches')).data,
    (json) => _list(json, BranchItem.fromJson),
  );

  Future<List<CategoryItem>> categories() => _cached(
    // [CU-04] Listar categorías
    'categories',
    () async => (await _dio.get<List<dynamic>>('/categories')).data,
    (json) =>
        _list(json, CategoryItem.fromJson).where((cat) => cat.active).toList(),
  );

  Future<List<BrandItem>> brands() => _cached(
    // [CU-04] Listar marcas
    'brands',
    () async => (await _dio.get<List<dynamic>>('/brands')).data,
    (json) =>
        _list(json, BrandItem.fromJson).where((brand) => brand.active).toList(),
  );

  Future<List<SizeItem>> sizes() => _cached(
    // [CU-04] Listar tallas
    'sizes',
    () async => (await _dio.get<List<dynamic>>('/sizes')).data,
    (json) => _list(json, SizeItem.fromJson),
  );

  Future<List<ColorItem>> colors() => _cached(
    // [CU-04] Listar colores
    'colors',
    () async => (await _dio.get<List<dynamic>>('/colors')).data,
    (json) => _list(json, ColorItem.fromJson),
  );

  Future<List<SeasonItem>> seasons() => _cached(
    // [CU-04] Listar temporadas
    'seasons',
    () async => (await _dio.get<List<dynamic>>('/seasons')).data,
    (json) => _list(json, SeasonItem.fromJson),
  );

  Future<List<ProductImage>> productImages(int productId) => _cached(
    // [CU-04] Consultar imágenes de prenda
    'products/$productId/images',
    () async =>
        (await _dio.get<List<dynamic>>('/products/$productId/images')).data,
    (json) => _list(json, ProductImage.fromJson),
  );

  Future<List<ProductVariant>> productVariants(
    // [CU-04] Consultar variantes y stock
    int productId, {
    int? branchId,
  }) {
    final params = <String, dynamic>{'sucursal': ?branchId};
    return _cached(
      _key('products/$productId/variants', params),
      () async => (await _dio.get<List<dynamic>>(
        '/products/$productId/variants',
        queryParameters: params,
      )).data,
      (json) => _list(json, ProductVariant.fromJson),
    );
  }

  Future<List<ProductMeasurement>> productMeasurements(int productId) =>
      _cached(
        // [CU-18] Consultar medidas de patronaje para probador AR
        'products/$productId/measurements',
        () async =>
            (await _dio.get<List<dynamic>>('/products/$productId/measurements'))
                .data,
        (json) => _list(json, ProductMeasurement.fromJson),
      );

  /// Red primero; si falla por conexión, usa la última respuesta guardada.
  Future<T> _cached<T>(
    String key,
    Future<Object?> Function() fetch,
    T Function(Object? json) parse,
  ) async {
    final cache = this.cache;
    final tenant = tenantSlug;
    try {
      final data = await fetch();
      final result = parse(data);
      if (cache != null && tenant != null) {
        try {
          await cache.putCatalogCache(tenant, key, jsonEncode(data));
        } catch (error) {
          // La caché nunca debe romper una consulta que sí respondió.
          developer.log(
            'No se pudo guardar $key en caché: $error',
            name: 'Catalog',
          );
        }
      }
      return result;
    } on DioException catch (error) {
      if (cache == null || tenant == null || !isNetworkError(error)) {
        throw ApiException.fromDio(error);
      }
      final cached = await _readCache(cache, tenant, key);
      if (cached == null) throw ApiException.fromDio(error);
      return parse(jsonDecode(cached));
    }
  }

  static Future<String?> _readCache(
    OfflineDatabase cache,
    String tenant,
    String key,
  ) async {
    try {
      return (await cache.catalogCache(tenant, key))?.json;
    } catch (error) {
      developer.log(
        'No se pudo leer $key de la caché: $error',
        name: 'Catalog',
      );
      return null;
    }
  }

  /// Errores en los que conviene usar la caché: sin red, tiempo agotado o
  /// servidor caído. Los 4xx (permiso, no encontrado, validación) se respetan.
  static bool isNetworkError(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionError:
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return true;
      case DioExceptionType.unknown:
        return error.error is SocketException || error.error is HttpException;
      case DioExceptionType.badResponse:
        return (error.response?.statusCode ?? 0) >= 500;
      case DioExceptionType.badCertificate:
      case DioExceptionType.cancel:
      case DioExceptionType.transformTimeout:
        return false;
    }
  }

  /// Clave estable: mismo endpoint y mismos filtros → misma clave.
  static String _key(String path, Map<String, dynamic> params) {
    if (params.isEmpty) return path;
    final entries = params.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    return '$path?${entries.map((e) => '${e.key}=${e.value}').join('&')}';
  }

  static List<T> _list<T>(
    Object? json,
    T Function(Map<String, dynamic>) fromJson,
  ) => (json as List<dynamic>? ?? const [])
      .map((item) => fromJson(item as Map<String, dynamic>))
      .toList();
}

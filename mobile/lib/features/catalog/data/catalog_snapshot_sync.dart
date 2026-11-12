import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/catalog/data/catalog_repository.dart';
import 'package:capricho_store/features/catalog/data/catalog_snapshot.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Cada cuánto se vuelve a descargar el catálogo completo con conexión.
const catalogSnapshotMaxAge = Duration(hours: 6);

/// Espera mínima tras un intento fallido, para no reintentar cada 30 s.
const catalogSnapshotRetryDelay = Duration(minutes: 5);

/// Tope de páginas por consulta (100 productos c/u): evita bucles infinitos.
const catalogSnapshotMaxPages = 100;

/// Descarga todo el catálogo de la empresa activa y lo guarda en SQLite.
class CatalogSnapshotDownloader {
  CatalogSnapshotDownloader(this._repository, this._database, this._store);

  final CatalogRepository _repository;
  final OfflineDatabase _database;
  final CatalogSnapshotStore _store;

  /// Devuelve la cantidad de productos guardados. Si [isCurrent] devuelve
  /// false antes de guardar (cambió la empresa), no se guarda nada.
  Future<int> download(String tenantSlug, {bool Function()? isCurrent}) async {
    // Filtros (categorías, marcas, tallas…): se guardan con las mismas claves
    // que leen las pantallas, así los selectores funcionan sin conexión.
    final metadata = await Future.wait([
      _repository.categories(),
      _repository.brands(),
      _repository.sizes(),
      _repository.colors(),
      _optional(_repository.seasons),
      _optional(_repository.branches),
    ]);
    final seasons = metadata[4] as List<SeasonItem>;
    final branches = metadata[5] as List<BranchItem>;

    final products = await _allPages(const {});
    final tags = <({String kind, String tag, int productId})>[];
    final downloaded = <String>{};

    Future<void> collect(
      String kind,
      String tag,
      Map<String, Object> filter,
    ) async {
      try {
        for (final product in await _allPages(filter)) {
          tags.add((kind: kind, tag: tag, productId: product.id));
        }
        downloaded.add(tag);
      } catch (error) {
        // Sin esta etiqueta, ese filtro simplemente no se resuelve offline.
        developer.log('No se pudo descargar $tag: $error', name: 'Catalog');
      }
    }

    for (final season in seasons) {
      await collect('season', CatalogSnapshot.seasonTag(season.name), {
        'temporada': season.name,
      });
    }
    for (final branch in branches) {
      await collect('branch', CatalogSnapshot.branchTag(branch.id), {
        'sucursal': branch.id,
      });
    }

    if (!(isCurrent?.call() ?? true)) {
      throw StateError('La empresa cambió durante la descarga del catálogo');
    }
    await _database.replaceCatalogSnapshot(
      tenantSlug: tenantSlug,
      products: [
        for (final p in products) (id: p.id, json: jsonEncode(p.json)),
      ],
      tags: tags,
      downloadedTags: downloaded,
      syncedAt: DateTime.now(),
    );
    _store.invalidate(tenantSlug);
    return products.length;
  }

  Future<List<({int id, Map<String, dynamic> json})>> _allPages(
    Map<String, Object> filter,
  ) async {
    final result = <({int id, Map<String, dynamic> json})>[];
    final seen = <int>{};
    for (var page = 1; page <= catalogSnapshotMaxPages; page++) {
      final data = await _repository.rawProductsPage({
        ...filter,
        'page': page,
        'page_size': 100,
        'sort': 'nombre',
      });
      for (final raw in data['items'] as List<dynamic>? ?? const []) {
        final json = Map<String, dynamic>.from(raw as Map);
        final id = json['id_producto'] as int;
        if (seen.add(id)) result.add((id: id, json: json));
      }
      final pages = data['pages'] as int? ?? 0;
      if (page >= pages) break;
    }
    return result;
  }

  static Future<List<T>> _optional<T>(Future<List<T>> Function() load) async {
    try {
      return await load();
    } catch (_) {
      // Ej.: /branches puede requerir sesión; no impide el resto.
      return <T>[];
    }
  }
}

final catalogSnapshotDownloaderProvider = Provider<CatalogSnapshotDownloader>(
  (ref) => CatalogSnapshotDownloader(
    ref.watch(catalogRepositoryProvider),
    ref.watch(offlineDatabaseProvider),
    ref.watch(catalogSnapshotStoreProvider),
  ),
);

class CatalogSnapshotState {
  const CatalogSnapshotState({
    this.syncing = false,
    this.syncedAt,
    this.productCount = 0,
    this.error,
  });

  final bool syncing;

  /// Última descarga completa exitosa (null = nunca).
  final DateTime? syncedAt;
  final int productCount;
  final String? error;
}

/// Mantiene al día la copia completa del catálogo, en segundo plano.
///
/// Con cada chequeo de conexión exitoso revisa si la copia tiene más de
/// [catalogSnapshotMaxAge] (o no existe) y, si es así, la vuelve a descargar.
final catalogSnapshotControllerProvider =
    NotifierProvider<CatalogSnapshotController, CatalogSnapshotState>(
      CatalogSnapshotController.new,
    );

class CatalogSnapshotController extends Notifier<CatalogSnapshotState> {
  Future<void>? _running;
  DateTime? _lastFailure;

  String? get _tenant => ref.read(tenantControllerProvider).selected?.slug;

  @override
  CatalogSnapshotState build() {
    ref.listen(connectivityControllerProvider, (previous, next) {
      if (next.online && next.checkedAt != previous?.checkedAt) {
        unawaited(maybeSync());
      }
    });
    ref.listen(
      tenantControllerProvider.select((state) => state.selected?.slug),
      (previous, next) {
        if (previous == next) return;
        _lastFailure = null;
        state = const CatalogSnapshotState();
        unawaited(_loadInfo().then((_) => maybeSync()));
      },
    );
    Future.microtask(_loadInfo);
    return const CatalogSnapshotState();
  }

  Future<void> _loadInfo() async {
    final tenant = _tenant;
    if (tenant == null) return;
    try {
      final info = await ref
          .read(offlineDatabaseProvider)
          .catalogSnapshotInfo(tenant);
      if (!ref.mounted || _tenant != tenant || info == null) return;
      state = CatalogSnapshotState(
        syncing: state.syncing,
        syncedAt: info.syncedAt,
        productCount: info.productCount,
      );
    } catch (_) {}
  }

  /// Descarga si la copia no existe o está vieja, y no falló hace poco.
  Future<void> maybeSync({DateTime? now}) {
    final current = now ?? DateTime.now();
    final syncedAt = state.syncedAt;
    final fresh =
        syncedAt != null &&
        current.difference(syncedAt) < catalogSnapshotMaxAge;
    final failedRecently =
        _lastFailure != null &&
        current.difference(_lastFailure!) < catalogSnapshotRetryDelay;
    if (fresh || failedRecently) return _running ?? Future.value();
    return syncNow();
  }

  /// Descarga ahora (si ya hay una descarga en curso, devuelve esa).
  Future<void> syncNow() => _running ??= _sync().whenComplete(() {
    _running = null;
  });

  Future<void> _sync() async {
    final tenant = _tenant;
    if (tenant == null || !ref.read(connectivityControllerProvider).online) {
      return;
    }
    state = CatalogSnapshotState(
      syncing: true,
      syncedAt: state.syncedAt,
      productCount: state.productCount,
    );
    try {
      final count = await ref
          .read(catalogSnapshotDownloaderProvider)
          .download(tenant, isCurrent: () => ref.mounted && _tenant == tenant);
      if (!ref.mounted || _tenant != tenant) return;
      _lastFailure = null;
      state = CatalogSnapshotState(
        syncedAt: DateTime.now(),
        productCount: count,
      );
    } catch (error) {
      developer.log('Descarga del catálogo falló: $error', name: 'Catalog');
      if (!ref.mounted) return;
      _lastFailure = DateTime.now();
      state = CatalogSnapshotState(
        syncedAt: state.syncedAt,
        productCount: state.productCount,
        error: error.toString(),
      );
    }
  }
}

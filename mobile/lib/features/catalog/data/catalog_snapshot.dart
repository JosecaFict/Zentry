import 'dart:convert';

import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';

/// Copia completa del catálogo de una empresa, descargada en segundo plano.
/// Permite responder `products(query)` con cualquier filtro sin conexión.
class CatalogSnapshot {
  CatalogSnapshot({
    required this.syncedAt,
    required this.products,
    required this.tags,
    required this.downloadedTags,
  });

  final DateTime syncedAt;

  /// JSON de cada producto, tal como lo devuelve `/products`.
  final List<Map<String, dynamic>> products;

  /// `season:<nombre en minúsculas>` o `branch:<id>` → ids de producto.
  final Map<String, Set<int>> tags;

  /// Etiquetas que sí se descargaron (aunque no tengan productos). Si un
  /// filtro pide una etiqueta que no está aquí, no se puede resolver offline.
  final Set<String> downloadedTags;

  static String seasonTag(String name) => 'season:${name.trim().toLowerCase()}';
  static String branchTag(int id) => 'branch:$id';

  static CatalogSnapshot fromStored(
    ({
      DateTime syncedAt,
      List<String> products,
      Map<String, Set<int>> tags,
      Set<String> downloadedTags,
    })
    stored,
  ) => CatalogSnapshot(
    syncedAt: stored.syncedAt,
    products: [
      for (final json in stored.products)
        Map<String, dynamic>.from(jsonDecode(json) as Map),
    ],
    tags: stored.tags,
    downloadedTags: stored.downloadedTags,
  );

  Map<String, dynamic>? product(int id) {
    for (final product in products) {
      if (product['id_producto'] == id) return product;
    }
    return null;
  }

  /// Aplica los mismos filtros, orden y paginación que el backend
  /// (`catalog/repository.py: list_products`) y devuelve el JSON de una
  /// página, listo para `ProductPage.fromJson`.
  Map<String, dynamic> query(CatalogQuery query) {
    bool same(Object? value, String? expected) =>
        value?.toString().trim().toLowerCase() ==
        expected!.trim().toLowerCase();
    bool has(String? value) => value != null && value.trim().isNotEmpty;
    bool anyVariant(Map<String, dynamic> product, String field, String value) =>
        (product['variantes'] as List<dynamic>? ?? const []).any((raw) {
          final variant = raw as Map;
          return variant['activo'] != false && same(variant[field], value);
        });
    Set<int>? members(String tag) =>
        downloadedTags.contains(tag) ? (tags[tag] ?? const <int>{}) : null;

    final season = has(query.season) ? members(seasonTag(query.season!)) : null;
    // Sucursal sin datos descargados: se muestra todo antes que nada.
    final branch = query.branchId == null
        ? null
        : members(branchTag(query.branchId!));

    final filtered = products.where((product) {
      final id = product['id_producto'] as int;
      if (has(query.category) && !same(product['categoria'], query.category)) {
        return false;
      }
      if (has(query.audience) &&
          product['publico_objetivo'] != query.audience) {
        return false;
      }
      if (has(query.brand) && !same(product['marca'], query.brand)) {
        return false;
      }
      if (query.fittingEnabled != null &&
          product['permite_vestidor'] != query.fittingEnabled) {
        return false;
      }
      if (has(query.size) && !anyVariant(product, 'talla', query.size!)) {
        return false;
      }
      if (has(query.color) && !anyVariant(product, 'color', query.color!)) {
        return false;
      }
      if (has(query.season) && !(season?.contains(id) ?? false)) {
        return false;
      }
      if (branch != null && !branch.contains(id)) return false;
      return true;
    }).toList();

    filtered.sort((a, b) {
      final order = _compare(a, b, query.sort);
      return order != 0
          ? order
          : (a['id_producto'] as int).compareTo(b['id_producto'] as int);
    });

    final pageSize = query.pageSize < 1 ? 20 : query.pageSize;
    final start = (query.page - 1) * pageSize;
    final items = start >= filtered.length
        ? const <Map<String, dynamic>>[]
        : filtered.sublist(start, (start + pageSize).clamp(0, filtered.length));
    return {
      'items': items,
      'page': query.page,
      'page_size': pageSize,
      'total': filtered.length,
      'pages': filtered.isEmpty ? 0 : (filtered.length / pageSize).ceil(),
    };
  }

  static int _compare(
    Map<String, dynamic> a,
    Map<String, dynamic> b,
    String sort,
  ) {
    final descending = sort.startsWith('-');
    final field = descending ? sort.substring(1) : sort;
    final int result = switch (field) {
      'precio' => _price(a).compareTo(_price(b)),
      'created_at' => '${a['created_at'] ?? ''}'.compareTo(
        '${b['created_at'] ?? ''}',
      ),
      _ => '${a['nombre'] ?? ''}'.toLowerCase().compareTo(
        '${b['nombre'] ?? ''}'.toLowerCase(),
      ),
    };
    return descending ? -result : result;
  }

  /// El backend ordena por precio vigente, con 0 si no tiene.
  static num _price(Map<String, dynamic> product) =>
      num.tryParse('${product['precio_actual'] ?? ''}') ?? 0;
}

/// Lee la copia completa de SQLite y la mantiene en memoria mientras no
/// cambie, para no decodificar todo el catálogo en cada consulta.
class CatalogSnapshotStore {
  CatalogSnapshotStore(this._database);

  final OfflineDatabase _database;
  final Map<String, CatalogSnapshot> _memory = {};

  Future<CatalogSnapshot?> load(String tenantSlug) async {
    final info = await _database.catalogSnapshotInfo(tenantSlug);
    if (info == null) return null;
    final cached = _memory[tenantSlug];
    if (cached != null && cached.syncedAt == info.syncedAt) return cached;
    final stored = await _database.catalogSnapshot(tenantSlug);
    if (stored == null) return null;
    final snapshot = CatalogSnapshot.fromStored(stored);
    _memory[tenantSlug] = snapshot;
    return snapshot;
  }

  /// La sincronización acaba de guardar una copia nueva.
  void invalidate(String tenantSlug) => _memory.remove(tenantSlug);
}

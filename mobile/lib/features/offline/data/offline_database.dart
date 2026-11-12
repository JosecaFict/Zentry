import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../domain/offline_models.dart';

final offlineDatabaseProvider = Provider<OfflineDatabase>((ref) {
  final database = OfflineDatabase();
  ref.onDispose(database.close);
  return database;
});

class _RawDriftDatabase extends GeneratedDatabase {
  _RawDriftDatabase(super.executor);

  @override
  int get schemaVersion => 1;

  @override
  Iterable<TableInfo> get allTables => const <TableInfo>[];
}

class OfflineDatabase {
  OfflineDatabase([this._directory]);

  final Directory? _directory;
  Future<_RawDriftDatabase>? _database;

  Future<_RawDriftDatabase> get _db => _database ??= _open();

  Future<_RawDriftDatabase> _open() async {
    final directory = _directory ?? await getApplicationDocumentsDirectory();
    final file = File(p.join(directory.path, 'zentry_offline.sqlite'));
    final db = _RawDriftDatabase(NativeDatabase.createInBackground(file));
    await db.customStatement('PRAGMA foreign_keys = ON');
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS offline_scope (
        scope_key TEXT PRIMARY KEY,
        tenant_slug TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        device_id TEXT NOT NULL,
        catalog_version TEXT,
        last_catalog_sync_at TEXT,
        last_successful_sync_at TEXT
      )
    ''');
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS offline_branch (
        scope_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        FOREIGN KEY (scope_key) REFERENCES offline_scope(scope_key) ON DELETE CASCADE
      )
    ''');
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS offline_catalog (
        scope_key TEXT NOT NULL,
        variant_id INTEGER NOT NULL,
        sku TEXT NOT NULL,
        product TEXT NOT NULL,
        size TEXT NOT NULL,
        color TEXT NOT NULL,
        price REAL NOT NULL,
        physical_stock INTEGER NOT NULL,
        reserved_stock INTEGER NOT NULL,
        available_stock INTEGER NOT NULL,
        updated_at TEXT,
        PRIMARY KEY (scope_key, variant_id),
        FOREIGN KEY (scope_key) REFERENCES offline_scope(scope_key) ON DELETE CASCADE
      )
    ''');
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS offline_customer (
        scope_key TEXT NOT NULL,
        customer_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        PRIMARY KEY (scope_key, customer_id),
        FOREIGN KEY (scope_key) REFERENCES offline_scope(scope_key) ON DELETE CASCADE
      )
    ''');
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS offline_operation (
        id_operation TEXT PRIMARY KEY,
        scope_key TEXT NOT NULL,
        type TEXT NOT NULL,
        client_date TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        error_code TEXT,
        error_message TEXT,
        batch_id TEXT,
        result_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (scope_key) REFERENCES offline_scope(scope_key) ON DELETE CASCADE
      )
    ''');
    await db.customStatement(
      'CREATE INDEX IF NOT EXISTS ix_offline_operation_scope_status '
      'ON offline_operation(scope_key, status)',
    );
    // Instalaciones previas: las columnas se agregan sin perder la cola.
    final operationColumns = {
      for (final column
          in await db
              .customSelect('PRAGMA table_info(offline_operation)')
              .get())
        column.read<String>('name'),
    };
    for (final column in const [
      'acknowledged_at', // Alerta revisada (fase 2).
      'resolution', // REAPLICADA / ANULADA por un supervisor (fase 5).
      'resolution_note',
    ]) {
      if (!operationColumns.contains(column)) {
        await db.customStatement(
          'ALTER TABLE offline_operation ADD COLUMN $column TEXT',
        );
      }
    }
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS catalog_cache (
        tenant_slug TEXT NOT NULL,
        cache_key TEXT NOT NULL,
        json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_slug, cache_key)
      )
    ''');
    // Copia completa del catálogo para filtrar sin conexión (fase 3).
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS catalog_product (
        tenant_slug TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        position INTEGER NOT NULL,
        json TEXT NOT NULL,
        PRIMARY KEY (tenant_slug, product_id)
      )
    ''');
    // Pertenencia que no viene en el JSON del producto: temporada y sucursal.
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS catalog_product_tag (
        tenant_slug TEXT NOT NULL,
        kind TEXT NOT NULL,
        tag TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        PRIMARY KEY (tenant_slug, kind, tag, product_id)
      )
    ''');
    await db.customStatement('''
      CREATE TABLE IF NOT EXISTS catalog_snapshot (
        tenant_slug TEXT PRIMARY KEY,
        synced_at TEXT NOT NULL,
        product_count INTEGER NOT NULL,
        downloaded_tags TEXT NOT NULL
      )
    ''');
    await _ensureImageTable(db);
    return db;
  }

  /// Imagen principal guardada en la carpeta de documentos (fase 4).
  /// Se guarda solo el nombre del archivo: en iOS la ruta absoluta del
  /// contenedor cambia entre actualizaciones.
  Future<void> _ensureImageTable(_RawDriftDatabase db) => db.customStatement('''
    CREATE TABLE IF NOT EXISTS catalog_image (
      tenant_slug TEXT NOT NULL,
      url TEXT NOT NULL,
      file_name TEXT NOT NULL,
      bytes INTEGER NOT NULL,
      downloaded_at TEXT NOT NULL,
      PRIMARY KEY (tenant_slug, url)
    )
  ''');

  Future<void> putCatalogImage(
    String tenantSlug,
    String url,
    String fileName,
    int bytes,
  ) async {
    final db = await _db;
    await db.customStatement(
      'INSERT OR REPLACE INTO catalog_image '
      '(tenant_slug, url, file_name, bytes, downloaded_at) VALUES (?, ?, ?, ?, ?)',
      [
        tenantSlug,
        url,
        fileName,
        bytes,
        DateTime.now().toUtc().toIso8601String(),
      ],
    );
  }

  /// url → nombre de archivo de las imágenes guardadas de la empresa.
  Future<Map<String, String>> catalogImages(String tenantSlug) async {
    final db = await _db;
    final rows = await db
        .customSelect(
          'SELECT url, file_name FROM catalog_image WHERE tenant_slug = ?',
          variables: [Variable.withString(tenantSlug)],
        )
        .get();
    return {
      for (final row in rows)
        row.read<String>('url'): row.read<String>('file_name'),
    };
  }

  Future<void> deleteCatalogImages(
    String tenantSlug,
    Iterable<String> urls,
  ) async {
    final db = await _db;
    await db.transaction(() async {
      for (final url in urls) {
        await db.customStatement(
          'DELETE FROM catalog_image WHERE tenant_slug = ? AND url = ?',
          [tenantSlug, url],
        );
      }
    });
  }

  /// Reemplaza la copia completa del catálogo de una empresa en una sola
  /// transacción: si algo falla, queda la copia anterior intacta.
  Future<void> replaceCatalogSnapshot({
    required String tenantSlug,
    required List<({int id, String json})> products,
    required List<({String kind, String tag, int productId})> tags,
    required Set<String> downloadedTags,
    required DateTime syncedAt,
  }) async {
    final db = await _db;
    await db.transaction(() async {
      final tenant = [tenantSlug];
      await db.customStatement(
        'DELETE FROM catalog_product WHERE tenant_slug = ?',
        tenant,
      );
      await db.customStatement(
        'DELETE FROM catalog_product_tag WHERE tenant_slug = ?',
        tenant,
      );
      for (var i = 0; i < products.length; i++) {
        await db.customStatement(
          'INSERT OR REPLACE INTO catalog_product '
          '(tenant_slug, product_id, position, json) VALUES (?, ?, ?, ?)',
          [tenantSlug, products[i].id, i, products[i].json],
        );
      }
      for (final tag in tags) {
        await db.customStatement(
          'INSERT OR IGNORE INTO catalog_product_tag '
          '(tenant_slug, kind, tag, product_id) VALUES (?, ?, ?, ?)',
          [tenantSlug, tag.kind, tag.tag, tag.productId],
        );
      }
      await db.customStatement(
        'INSERT INTO catalog_snapshot '
        '(tenant_slug, synced_at, product_count, downloaded_tags) VALUES (?, ?, ?, ?) '
        'ON CONFLICT (tenant_slug) DO UPDATE SET synced_at = excluded.synced_at, '
        'product_count = excluded.product_count, downloaded_tags = excluded.downloaded_tags',
        [
          tenantSlug,
          syncedAt.toUtc().toIso8601String(),
          products.length,
          jsonEncode(downloadedTags.toList()..sort()),
        ],
      );
    });
  }

  /// Fecha y tamaño de la última copia completa (null si nunca se descargó).
  Future<({DateTime syncedAt, int productCount})?> catalogSnapshotInfo(
    String tenantSlug,
  ) async {
    final row = await (await _db)
        .customSelect(
          'SELECT synced_at, product_count FROM catalog_snapshot '
          'WHERE tenant_slug = ?',
          variables: [Variable.withString(tenantSlug)],
        )
        .getSingleOrNull();
    if (row == null) return null;
    return (
      syncedAt: DateTime.parse(row.read<String>('synced_at')),
      productCount: row.read<int>('product_count'),
    );
  }

  /// Lee la copia completa: productos en el orden del servidor y etiquetas
  /// (`season:<nombre>` / `branch:<id>` → ids de producto).
  Future<
    ({
      DateTime syncedAt,
      List<String> products,
      Map<String, Set<int>> tags,
      Set<String> downloadedTags,
    })?
  >
  catalogSnapshot(String tenantSlug) async {
    final db = await _db;
    final meta = await db
        .customSelect(
          'SELECT synced_at, downloaded_tags FROM catalog_snapshot WHERE tenant_slug = ?',
          variables: [Variable.withString(tenantSlug)],
        )
        .getSingleOrNull();
    if (meta == null) return null;
    final products = await db
        .customSelect(
          'SELECT json FROM catalog_product WHERE tenant_slug = ? ORDER BY position',
          variables: [Variable.withString(tenantSlug)],
        )
        .get();
    final tagRows = await db
        .customSelect(
          'SELECT tag, product_id FROM catalog_product_tag WHERE tenant_slug = ?',
          variables: [Variable.withString(tenantSlug)],
        )
        .get();
    final tags = <String, Set<int>>{};
    for (final row in tagRows) {
      tags
          .putIfAbsent(row.read<String>('tag'), () => <int>{})
          .add(row.read<int>('product_id'));
    }
    final downloaded = jsonDecode(meta.read<String>('downloaded_tags')) as List;
    return (
      syncedAt: DateTime.parse(meta.read<String>('synced_at')),
      products: [for (final row in products) row.read<String>('json')],
      tags: tags,
      downloadedTags: downloaded.cast<String>().toSet(),
    );
  }

  /// JSON de un producto de la copia completa (para el detalle sin conexión).
  Future<String?> catalogSnapshotProduct(
    String tenantSlug,
    int productId,
  ) async {
    final row = await (await _db)
        .customSelect(
          'SELECT json FROM catalog_product WHERE tenant_slug = ? AND product_id = ?',
          variables: [
            Variable.withString(tenantSlug),
            Variable.withInt(productId),
          ],
        )
        .getSingleOrNull();
    return row?.read<String>('json');
  }

  /// Guarda la respuesta cruda (JSON) de un endpoint del catálogo.
  Future<void> putCatalogCache(
    String tenantSlug,
    String key,
    String json,
  ) async {
    await (await _db).customStatement(
      'INSERT INTO catalog_cache (tenant_slug, cache_key, json, updated_at) '
      'VALUES (?, ?, ?, ?) ON CONFLICT (tenant_slug, cache_key) DO UPDATE SET '
      'json = excluded.json, updated_at = excluded.updated_at',
      [tenantSlug, key, json, DateTime.now().toUtc().toIso8601String()],
    );
  }

  /// Lee la última respuesta guardada de un endpoint del catálogo.
  Future<({String json, DateTime updatedAt})?> catalogCache(
    String tenantSlug,
    String key,
  ) async {
    final row = await (await _db)
        .customSelect(
          'SELECT json, updated_at FROM catalog_cache '
          'WHERE tenant_slug = ? AND cache_key = ?',
          variables: [
            Variable.withString(tenantSlug),
            Variable.withString(key),
          ],
        )
        .getSingleOrNull();
    if (row == null) return null;
    return (
      json: row.read<String>('json'),
      updatedAt: DateTime.parse(row.read<String>('updated_at')),
    );
  }

  Future<List<({int id, String name, String address})>> preparedBranches(
    String tenantSlug,
    int userId,
  ) async {
    final rows = await (await _db)
        .customSelect(
          'SELECT s.branch_id, b.name, b.address FROM offline_scope s '
          'LEFT JOIN offline_branch b ON b.scope_key = s.scope_key '
          'WHERE s.tenant_slug = ? AND s.user_id = ? '
          'AND (s.last_catalog_sync_at IS NOT NULL OR EXISTS '
          '(SELECT 1 FROM offline_operation o WHERE o.scope_key = s.scope_key)) '
          'ORDER BY s.last_catalog_sync_at DESC NULLS LAST, s.branch_id',
          variables: [
            Variable.withString(tenantSlug),
            Variable.withInt(userId),
          ],
        )
        .get();
    return rows.map((row) {
      final id = row.read<int>('branch_id');
      return (
        id: id,
        name: row.readNullable<String>('name') ?? 'Sucursal #$id',
        address: row.readNullable<String>('address') ?? '',
      );
    }).toList();
  }

  Future<void> saveBranch(
    OfflineScope scope,
    String name,
    String address,
  ) async {
    await (await _db).customStatement(
      'INSERT INTO offline_branch (scope_key, name, address) VALUES (?, ?, ?) '
      'ON CONFLICT (scope_key) DO UPDATE SET name = excluded.name, address = excluded.address',
      [scope.key, name, address],
    );
  }

  Future<String> ensureScope(OfflineScope scope) async {
    final db = await _db;
    final existing = await db
        .customSelect(
          'SELECT device_id FROM offline_scope WHERE scope_key = ?',
          variables: [Variable.withString(scope.key)],
        )
        .getSingleOrNull();
    if (existing != null) return existing.read<String>('device_id');
    final deviceId = const Uuid().v4();
    await db.customStatement(
      'INSERT INTO offline_scope '
      '(scope_key, tenant_slug, user_id, branch_id, device_id) VALUES (?, ?, ?, ?, ?)',
      [scope.key, scope.tenantSlug, scope.userId, scope.branchId, deviceId],
    );
    return deviceId;
  }

  Future<void> replaceSnapshot({
    required OfflineScope scope,
    required String version,
    required DateTime generatedAt,
    required List<OfflineCatalogItem> catalog,
    required List<OfflineCustomer> customers,
  }) async {
    final db = await _db;
    await ensureScope(scope);
    await db.transaction(() async {
      await db.customStatement(
        'DELETE FROM offline_catalog WHERE scope_key = ?',
        [scope.key],
      );
      for (final item in catalog) {
        await db.customStatement(
          'INSERT INTO offline_catalog '
          '(scope_key, variant_id, sku, product, size, color, price, physical_stock, '
          'reserved_stock, available_stock, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
          [
            scope.key,
            item.variantId,
            item.sku,
            item.product,
            item.size,
            item.color,
            item.price,
            item.physicalStock,
            item.reservedStock,
            item.availableStock,
            item.updatedAt?.toIso8601String(),
          ],
        );
      }
      await db.customStatement(
        'DELETE FROM offline_customer WHERE scope_key = ?',
        [scope.key],
      );
      for (final customer in customers) {
        await db.customStatement(
          'INSERT INTO offline_customer '
          '(scope_key, customer_id, name, email, phone) VALUES (?, ?, ?, ?, ?)',
          [
            scope.key,
            customer.id,
            customer.name,
            customer.email,
            customer.phone,
          ],
        );
      }
      await db.customStatement(
        'UPDATE offline_scope SET catalog_version = ?, last_catalog_sync_at = ? '
        'WHERE scope_key = ?',
        [version, generatedAt.toIso8601String(), scope.key],
      );
    });
  }

  Future<List<OfflineCatalogItem>> catalog(OfflineScope scope) async {
    final rows = await (await _db)
        .customSelect(
          'SELECT * FROM offline_catalog WHERE scope_key = ? ORDER BY product, size, color',
          variables: [Variable.withString(scope.key)],
        )
        .get();
    return rows
        .map(
          (row) => OfflineCatalogItem(
            variantId: row.read<int>('variant_id'),
            sku: row.read<String>('sku'),
            product: row.read<String>('product'),
            size: row.read<String>('size'),
            color: row.read<String>('color'),
            price: (row.data['price'] as num).toDouble(),
            physicalStock: row.read<int>('physical_stock'),
            reservedStock: row.read<int>('reserved_stock'),
            availableStock: row.read<int>('available_stock'),
            updatedAt: DateTime.tryParse(
              row.readNullable<String>('updated_at') ?? '',
            ),
          ),
        )
        .toList(growable: false);
  }

  Future<List<OfflineCustomer>> customers(OfflineScope scope) async {
    final rows = await (await _db)
        .customSelect(
          'SELECT * FROM offline_customer WHERE scope_key = ? ORDER BY name',
          variables: [Variable.withString(scope.key)],
        )
        .get();
    return rows
        .map(
          (row) => OfflineCustomer(
            id: row.read<int>('customer_id'),
            name: row.read<String>('name'),
            email: row.read<String>('email'),
            phone: row.readNullable<String>('phone'),
          ),
        )
        .toList(growable: false);
  }

  /// Guarda un cliente recién creado en caja, para elegirlo también sin red.
  Future<void> saveCustomer(OfflineScope scope, OfflineCustomer customer) async {
    final db = await _db;
    await db.customStatement(
      'INSERT OR REPLACE INTO offline_customer '
      '(scope_key, customer_id, name, email, phone) VALUES (?, ?, ?, ?, ?)',
      [scope.key, customer.id, customer.name, customer.email, customer.phone],
    );
  }

  Future<void> queueOperation({
    required OfflineScope scope,
    required OfflineOperationType type,
    required Map<String, dynamic> payload,
  }) async {
    final db = await _db;
    await ensureScope(scope);
    final now = DateTime.now().toUtc().toIso8601String();
    await db.customStatement(
      'INSERT INTO offline_operation '
      '(id_operation, scope_key, type, client_date, payload_json, status, created_at, updated_at) '
      'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      [
        const Uuid().v4(),
        scope.key,
        type == OfflineOperationType.sale ? 'VENTA' : 'RESERVA',
        now,
        jsonEncode(payload),
        'PENDIENTE',
        now,
        now,
      ],
    );
  }

  Future<List<OfflineOperation>> operations(OfflineScope scope) async {
    final rows = await (await _db)
        .customSelect(
          'SELECT * FROM offline_operation WHERE scope_key = ? ORDER BY created_at DESC',
          variables: [Variable.withString(scope.key)],
        )
        .get();
    return rows.map(_operationFromRow).toList(growable: false);
  }

  Future<({String id, List<OfflineOperation> operations})?> claimSyncBatch(
    OfflineScope scope,
  ) async {
    final db = await _db;
    return db.transaction(() async {
      final unfinished = await db
          .customSelect(
            "SELECT batch_id FROM offline_operation WHERE scope_key = ? "
            "AND status = 'ENVIANDO' AND batch_id IS NOT NULL ORDER BY created_at LIMIT 1",
            variables: [Variable.withString(scope.key)],
          )
          .getSingleOrNull();
      if (unfinished != null) {
        final id = unfinished.read<String>('batch_id');
        final rows = await db
            .customSelect(
              'SELECT * FROM offline_operation WHERE scope_key = ? AND batch_id = ?',
              variables: [
                Variable.withString(scope.key),
                Variable.withString(id),
              ],
            )
            .get();
        return (id: id, operations: rows.map(_operationFromRow).toList());
      }
      final rows = await db
          .customSelect(
            "SELECT * FROM offline_operation WHERE scope_key = ? AND status = 'PENDIENTE' "
            'ORDER BY created_at LIMIT 100',
            variables: [Variable.withString(scope.key)],
          )
          .get();
      if (rows.isEmpty) return null;
      final operations = rows.map(_operationFromRow).toList();
      final id = const Uuid().v4();
      final now = DateTime.now().toUtc().toIso8601String();
      for (final operation in operations) {
        await db.customStatement(
          "UPDATE offline_operation SET status = 'ENVIANDO', batch_id = ?, "
          'attempts = attempts + 1, updated_at = ? WHERE id_operation = ?',
          [id, now, operation.id],
        );
      }
      return (id: id, operations: operations);
    });
  }

  Future<void> applyResponses(List<dynamic> responses) async {
    final db = await _db;
    final now = DateTime.now().toUtc().toIso8601String();
    await db.transaction(() async {
      for (final raw in responses) {
        final item = Map<String, dynamic>.from(raw as Map);
        await db.customStatement(
          'UPDATE offline_operation SET status = ?, error_code = ?, error_message = ?, '
          'result_json = ?, updated_at = ? WHERE id_operation = ?',
          [
            item['estado'] as String? ?? 'RECHAZADA',
            item['codigo_error'],
            item['mensaje_error'],
            item['resultado'] == null ? null : jsonEncode(item['resultado']),
            now,
            item['id_operacion'],
          ],
        );
      }
    });
  }

  /// Sucursales de esta empresa y usuario con operaciones por enviar.
  Future<List<OfflineScope>> pendingScopes(
    String tenantSlug,
    int userId,
  ) async {
    final rows = await (await _db)
        .customSelect(
          'SELECT DISTINCT s.branch_id FROM offline_scope s '
          'JOIN offline_operation o ON o.scope_key = s.scope_key '
          "WHERE s.tenant_slug = ? AND s.user_id = ? "
          "AND o.status IN ('PENDIENTE', 'ENVIANDO') ORDER BY s.branch_id",
          variables: [
            Variable.withString(tenantSlug),
            Variable.withInt(userId),
          ],
        )
        .get();
    return rows
        .map(
          (row) => OfflineScope(
            tenantSlug: tenantSlug,
            userId: userId,
            branchId: row.read<int>('branch_id'),
          ),
        )
        .toList(growable: false);
  }

  /// Operaciones rechazadas o en conflicto que nadie revisó todavía.
  Future<List<OfflineFailure>> unacknowledgedFailures(
    String tenantSlug,
    int userId,
  ) async {
    final db = await _db;
    final rows = await db
        .customSelect(
          'SELECT o.*, s.branch_id FROM offline_operation o '
          'JOIN offline_scope s ON s.scope_key = o.scope_key '
          'WHERE s.tenant_slug = ? AND s.user_id = ? '
          "AND o.status IN ('CONFLICTO', 'RECHAZADA') AND o.acknowledged_at IS NULL "
          'ORDER BY o.updated_at DESC',
          variables: [
            Variable.withString(tenantSlug),
            Variable.withInt(userId),
          ],
        )
        .get();
    if (rows.isEmpty) return const [];
    final labels = await _variantLabels(
      db,
      rows.map((row) => row.read<String>('scope_key')).toSet(),
    );
    return rows
        .map((row) {
          final operation = _operationFromRow(row);
          final scopeKey = row.read<String>('scope_key');
          final items = [
            for (final raw
                in operation.payload['items'] as List<dynamic>? ?? const [])
              labels['$scopeKey:${(raw as Map)['id_variante']}'] ??
                  'Variante #${raw['id_variante']}',
          ];
          return OfflineFailure(
            operation: operation,
            branchId: row.read<int>('branch_id'),
            items: items,
          );
        })
        .toList(growable: false);
  }

  Future<Map<String, String>> _variantLabels(
    _RawDriftDatabase db,
    Set<String> scopeKeys,
  ) async {
    final placeholders = List.filled(scopeKeys.length, '?').join(', ');
    final rows = await db
        .customSelect(
          'SELECT scope_key, variant_id, product, size, color FROM offline_catalog '
          'WHERE scope_key IN ($placeholders)',
          variables: [for (final key in scopeKeys) Variable.withString(key)],
        )
        .get();
    return {
      for (final row in rows)
        '${row.read<String>('scope_key')}:${row.read<int>('variant_id')}':
            '${row.read<String>('product')} ${row.read<String>('size')} '
            '${row.read<String>('color')}',
    };
  }

  /// Marca como revisada una operación fallida: deja de alertar, pero no se borra.
  /// Operaciones fallidas que el servidor todavía puede resolver (un
  /// supervisor aún no decidió). Se consultan para actualizar el teléfono.
  Future<List<String>> unresolvedFailedIds(
    String tenantSlug,
    int userId,
  ) async {
    final rows = await (await _db)
        .customSelect(
          'SELECT o.id_operation FROM offline_operation o '
          'JOIN offline_scope s ON s.scope_key = o.scope_key '
          'WHERE s.tenant_slug = ? AND s.user_id = ? '
          "AND o.status IN ('CONFLICTO', 'RECHAZADA') AND o.resolution IS NULL "
          'ORDER BY o.updated_at DESC LIMIT 100',
          variables: [
            Variable.withString(tenantSlug),
            Variable.withInt(userId),
          ],
        )
        .get();
    return [for (final row in rows) row.read<String>('id_operation')];
  }

  /// Un supervisor resolvió la operación: si la reaplicó queda como aplicada;
  /// en ambos casos la alerta deja de mostrarse.
  Future<void> applyServerResolution(
    String operationId, {
    required String action,
    String? note,
  }) async {
    final now = DateTime.now().toUtc().toIso8601String();
    await (await _db).customStatement(
      'UPDATE offline_operation SET resolution = ?, resolution_note = ?, '
      "status = CASE WHEN ? = 'REAPLICADA' THEN 'APLICADA' ELSE status END, "
      'acknowledged_at = COALESCE(acknowledged_at, ?), updated_at = ? '
      'WHERE id_operation = ?',
      [action, note, action, now, now, operationId],
    );
  }

  Future<void> acknowledge(String operationId) async {
    final now = DateTime.now().toUtc().toIso8601String();
    await (await _db).customStatement(
      'UPDATE offline_operation SET acknowledged_at = ?, updated_at = ? '
      'WHERE id_operation = ?',
      [now, now, operationId],
    );
  }

  Future<void> markSuccessfulSync(OfflineScope scope) async {
    await (await _db).customStatement(
      'UPDATE offline_scope SET last_successful_sync_at = ? WHERE scope_key = ?',
      [DateTime.now().toUtc().toIso8601String(), scope.key],
    );
  }

  // No existe "reintentar" local: el servidor ya registró la operación con su
  // id y rechazaría un lote nuevo que la incluya (409), bloqueando la cola.
  // Las operaciones fallidas se resuelven en el servidor (supervisor).

  Future<void> discard(String operationId) async {
    await (await _db).customStatement(
      'DELETE FROM offline_operation WHERE id_operation = ?',
      [operationId],
    );
  }

  OfflineOperation _operationFromRow(QueryRow row) => OfflineOperation(
    id: row.read<String>('id_operation'),
    type: row.read<String>('type') == 'VENTA'
        ? OfflineOperationType.sale
        : OfflineOperationType.reservation,
    clientDate: DateTime.parse(row.read<String>('client_date')),
    payload: OfflineOperation.decodeMap(row.read<String>('payload_json')),
    status: OfflineOperationStatus.fromApi(row.read<String>('status')),
    attempts: row.read<int>('attempts'),
    createdAt: DateTime.parse(row.read<String>('created_at')),
    errorCode: row.readNullable<String>('error_code'),
    errorMessage: row.readNullable<String>('error_message'),
    batchId: row.readNullable<String>('batch_id'),
    result: _decodeNullableMap(row.readNullable<String>('result_json')),
    acknowledgedAt: DateTime.tryParse(
      row.readNullable<String>('acknowledged_at') ?? '',
    ),
    resolution: row.readNullable<String>('resolution'),
    resolutionNote: row.readNullable<String>('resolution_note'),
  );

  static Map<String, dynamic>? _decodeNullableMap(String? value) =>
      value == null ? null : OfflineOperation.decodeMap(value);

  Future<void> close() async {
    final db = await _database;
    await db?.close();
  }
}

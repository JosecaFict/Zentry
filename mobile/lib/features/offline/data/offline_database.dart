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
  Future<_RawDriftDatabase>? _database;

  Future<_RawDriftDatabase> get _db => _database ??= _open();

  Future<_RawDriftDatabase> _open() async {
    final directory = await getApplicationDocumentsDirectory();
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
    return db;
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

  Future<List<OfflineOperation>> pendingOperations(OfflineScope scope) async {
    final rows = await (await _db)
        .customSelect(
          "SELECT * FROM offline_operation WHERE scope_key = ? AND status = 'PENDIENTE' "
          'ORDER BY created_at LIMIT 100',
          variables: [Variable.withString(scope.key)],
        )
        .get();
    return rows.map(_operationFromRow).toList(growable: false);
  }

  Future<void> markSending(String batchId, List<String> ids) async {
    final db = await _db;
    final now = DateTime.now().toUtc().toIso8601String();
    for (final id in ids) {
      await db.customStatement(
        "UPDATE offline_operation SET status = 'ENVIANDO', batch_id = ?, "
        'attempts = attempts + 1, updated_at = ? WHERE id_operation = ?',
        [batchId, now, id],
      );
    }
  }

  Future<void> releaseBatch(String batchId, String message) async {
    await (await _db).customStatement(
      "UPDATE offline_operation SET status = 'PENDIENTE', batch_id = NULL, "
      'error_message = ?, updated_at = ? WHERE batch_id = ?',
      [message, DateTime.now().toUtc().toIso8601String(), batchId],
    );
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

  Future<void> markSuccessfulSync(OfflineScope scope) async {
    await (await _db).customStatement(
      'UPDATE offline_scope SET last_successful_sync_at = ? WHERE scope_key = ?',
      [DateTime.now().toUtc().toIso8601String(), scope.key],
    );
  }

  Future<void> retry(String operationId) async {
    await (await _db).customStatement(
      "UPDATE offline_operation SET status = 'PENDIENTE', error_code = NULL, "
      'error_message = NULL, batch_id = NULL, updated_at = ? WHERE id_operation = ?',
      [DateTime.now().toUtc().toIso8601String(), operationId],
    );
  }

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
  );

  static Map<String, dynamic>? _decodeNullableMap(String? value) =>
      value == null ? null : OfflineOperation.decodeMap(value);

  Future<void> close() async {
    final db = await _database;
    await db?.close();
  }
}

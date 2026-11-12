import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/notifications/local_notifications.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/data/offline_sync_repository.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:capricho_store/features/offline/presentation/offline_sync_controller.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqlite3/sqlite3.dart';

import '../../core/connectivity_controller_test.dart' show FakeProbe;

/// Backend falso de `/sync/batches`: la primera operación se aplica y el
/// resto queda en conflicto por stock (dos vendedores, una sola prenda).
class _SyncBackend implements HttpClientAdapter {
  final List<String> submitted = [];
  bool down = false;

  /// Decisiones del supervisor: id de operación → (acción, nota).
  final Map<String, (String, String?)> resolutions = {};
  final List<List<String>> statusQueries = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (down) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'Sin conexión',
      );
    }
    Object body = <String, dynamic>{};
    if (options.path == '/sync/batches') {
      final data = options.data as Map<String, dynamic>;
      for (final op in data['operaciones'] as List) {
        submitted.add((op as Map)['id_operacion'] as String);
      }
    } else if (options.path.endsWith('/confirm')) {
      final ops = [
        for (var i = 0; i < submitted.length; i++)
          i == 0
              ? {'id_operacion': submitted[i], 'estado': 'APLICADA'}
              : {
                  'id_operacion': submitted[i],
                  'estado': 'CONFLICTO',
                  'codigo_error': 'STOCK_INSUFICIENTE',
                  'mensaje_error': 'Stock insuficiente para completar la venta',
                },
      ];
      body = {
        'operaciones': ops,
        'total_aplicadas': 1,
        'total_conflictos': ops.length - 1,
        'total_rechazadas': 0,
      };
      submitted.clear();
    } else if (options.path == '/sync/operations/status') {
      final ids = List<String>.from(options.queryParameters['ids'] as List);
      statusQueries.add(ids);
      body = [
        for (final id in ids)
          {
            'id_operacion': id,
            'estado': resolutions[id]?.$1 == 'REAPLICADA'
                ? 'APLICADA'
                : 'CONFLICTO',
            'codigo_error': null,
            'mensaje_error': null,
            'conflicto_estado': switch (resolutions[id]?.$1) {
              'REAPLICADA' => 'RESUELTO',
              'ANULADA' => 'DESCARTADO',
              _ => 'PENDIENTE',
            },
            'accion': resolutions[id]?.$1,
            'resolucion': resolutions[id]?.$2,
          },
      ];
    }
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _FakeNotifier implements LocalNotifier {
  final List<({String title, String body, String? route})> shown = [];

  @override
  Stream<String> get onTap => const Stream.empty();

  @override
  Future<bool> ensureInitialized() async => true;

  @override
  Future<void> show({
    required int id,
    required String title,
    required String body,
    String? route,
  }) async => shown.add((title: title, body: body, route: route));
}

class _Cashier extends AuthController {
  @override
  AuthState build() => const AuthState(
    initialized: true,
    user: AppUser(
      id: 1,
      names: 'Cuenta',
      surnames: 'Demo',
      email: 'demo@example.com',
      status: 'ACTIVO',
      roles: ['CAJERO'],
      permissions: ['ventas.ver', 'ventas.crear', 'pagos.registrar'],
    ),
  );
}

class _Customer extends AuthController {
  @override
  AuthState build() => const AuthState(
    initialized: true,
    user: AppUser(
      id: 1,
      names: 'Cliente',
      surnames: 'Demo',
      email: 'cliente@example.com',
      status: 'ACTIVO',
      roles: ['CLIENTE'],
      permissions: [],
    ),
  );
}

class _Tenant extends TenantController {
  @override
  TenantState build() => const TenantState(
    selected: TenantIdentity(name: 'Demo', slug: 'demo'),
  );
}

const _scope = OfflineScope(tenantSlug: 'demo', userId: 1, branchId: 2);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory directory;
  late OfflineDatabase database;
  late _SyncBackend backend;
  late _FakeNotifier notifier;
  late FakeProbe probe;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('zentry-sync-');
    database = OfflineDatabase(directory);
    backend = _SyncBackend();
    notifier = _FakeNotifier();
    probe = FakeProbe();
    await database.replaceSnapshot(
      scope: _scope,
      version: 'v1',
      generatedAt: DateTime.utc(2026, 11, 11),
      catalog: const [
        OfflineCatalogItem(
          variantId: 7,
          sku: 'POLO-M',
          product: 'Polo básico',
          size: 'M',
          color: 'Negro',
          price: 99.9,
          physicalStock: 1,
          reservedStock: 0,
          availableStock: 1,
        ),
      ],
      customers: const [],
    );
  });

  tearDown(() async {
    await database.close();
    await directory.delete(recursive: true);
  });

  ProviderContainer container({AuthController Function()? auth}) {
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
      ..httpClientAdapter = backend;
    final container = ProviderContainer(
      overrides: [
        offlineDatabaseProvider.overrideWithValue(database),
        offlineSyncRepositoryProvider.overrideWithValue(
          OfflineSyncRepository(dio),
        ),
        networkProbeProvider.overrideWithValue(probe),
        localNotifierProvider.overrideWithValue(notifier),
        authControllerProvider.overrideWith(auth ?? _Cashier.new),
        tenantControllerProvider.overrideWith(_Tenant.new),
      ],
    );
    container.listen(offlineSyncControllerProvider, (_, _) {});
    addTearDown(() {
      container.dispose();
      probe.changes.close();
    });
    return container;
  }

  Future<void> sell() => database.queueOperation(
    scope: _scope,
    type: OfflineOperationType.sale,
    payload: {
      'id_sucursal': 2,
      'items': [
        {'id_variante': 7, 'cantidad': 1},
      ],
    },
  );

  test(
    'al volver la conexión envía la cola y alerta la venta rechazada',
    () async {
      await sell();
      await sell();
      final c = container();
      await pumpEventQueue();

      // Primer chequeo de conexión: dispara la sincronización automática.
      await c.read(connectivityControllerProvider.notifier).check();
      await pumpEventQueue();
      await c.read(offlineSyncControllerProvider.notifier).syncNow();

      final state = c.read(offlineSyncControllerProvider);
      expect(state.lastOutcome?.applied, 1);
      expect(state.lastOutcome?.conflicts, 1);
      expect(state.failures, hasLength(1));
      final failure = state.failures.single;
      expect(failure.title, 'Venta no registrada · Polo básico M Negro');
      expect(
        failure.operation.failureReason,
        'No había stock: otra venta o reserva se registró antes.',
      );

      expect(notifier.shown, hasLength(1));
      expect(notifier.shown.single.title, contains('Polo básico M Negro'));
      expect(notifier.shown.single.body, contains('No había stock'));
      expect(notifier.shown.single.route, offlineAlertRoute);
      expect(await database.pendingScopes('demo', 1), isEmpty);
    },
  );

  test('no repite la notificación y la alerta sigue hasta revisarla', () async {
    await sell();
    await sell();
    final c = container();
    await pumpEventQueue();
    final sync = c.read(offlineSyncControllerProvider.notifier);
    await sync.syncNow();
    await sync.refreshFailures();
    await sync.syncNow();
    expect(notifier.shown, hasLength(1));
    expect(c.read(offlineSyncControllerProvider).failures, hasLength(1));

    final id = c
        .read(offlineSyncControllerProvider)
        .failures
        .single
        .operation
        .id;
    await sync.acknowledge(id);
    expect(c.read(offlineSyncControllerProvider).failures, isEmpty);
    // Revisada no es borrada: la operación sigue en el historial.
    final operations = await database.operations(_scope);
    expect(
      operations.where((op) => op.id == id).single.acknowledgedAt,
      isNotNull,
    );
  });

  test(
    'las alertas de una sesión anterior se muestran sin notificar',
    () async {
      await sell();
      await sell();
      final first = container();
      await pumpEventQueue();
      await first.read(offlineSyncControllerProvider.notifier).syncNow();
      first.dispose();
      notifier.shown.clear();

      probe = FakeProbe();
      final second = container();
      // SQLite corre en otro isolate: esperar a que termine la carga inicial.
      for (var i = 0; i < 200; i++) {
        if (second.read(offlineSyncControllerProvider).failures.isNotEmpty) {
          break;
        }
        await Future<void>.delayed(const Duration(milliseconds: 10));
      }
      expect(second.read(offlineSyncControllerProvider).failures, hasLength(1));
      // Un chequeo posterior tampoco la notifica: ya se conocía al abrir.
      await second
          .read(offlineSyncControllerProvider.notifier)
          .refreshFailures();
      expect(notifier.shown, isEmpty);
    },
  );

  test('sin conexión no intenta enviar y la cola queda pendiente', () async {
    await sell();
    probe.backend = false;
    final c = container();
    await c.read(connectivityControllerProvider.notifier).check();
    final outcome = await c
        .read(offlineSyncControllerProvider.notifier)
        .syncNow();
    expect(outcome, isNull);
    expect(await database.pendingScopes('demo', 1), hasLength(1));
  });

  test('si la red falla a mitad, se reintenta en el próximo chequeo', () async {
    await sell();
    final c = container();
    await pumpEventQueue();
    backend.down = true;
    await c.read(offlineSyncControllerProvider.notifier).syncNow();
    expect(c.read(offlineSyncControllerProvider).lastError, isNotNull);
    expect(await database.pendingScopes('demo', 1), hasLength(1));

    backend.down = false;
    final outcome = await c
        .read(offlineSyncControllerProvider.notifier)
        .syncNow();
    expect(outcome?.applied, 1);
    expect(await database.pendingScopes('demo', 1), isEmpty);
  });

  test(
    'un cliente (sin acceso offline) no sincroniza ni recibe alertas',
    () async {
      await sell();
      final c = container(auth: _Customer.new);
      await pumpEventQueue();
      final outcome = await c
          .read(offlineSyncControllerProvider.notifier)
          .syncNow();
      expect(outcome, isNull);
      expect(c.read(offlineSyncControllerProvider).failures, isEmpty);
    },
  );

  test('sin catálogo local, la alerta usa el id de la variante', () async {
    await database.replaceSnapshot(
      scope: _scope,
      version: 'v2',
      generatedAt: DateTime.utc(2026, 11, 11),
      catalog: const [],
      customers: const [],
    );
    await sell();
    await sell();
    final c = container();
    await pumpEventQueue();
    await c.read(offlineSyncControllerProvider.notifier).syncNow();
    final failure = c.read(offlineSyncControllerProvider).failures.single;
    expect(failure.items, ['Variante #7']);
  });

  group('resolución del supervisor (fase 5)', () {
    Future<(ProviderContainer, OfflineFailure)> conflicted() async {
      await sell();
      await sell();
      final c = container();
      await pumpEventQueue();
      await c.read(offlineSyncControllerProvider.notifier).syncNow();
      return (c, c.read(offlineSyncControllerProvider).failures.single);
    }

    test('si la reaplica, queda registrada y la alerta desaparece', () async {
      final (c, failure) = await conflicted();
      backend.resolutions[failure.operation.id] = ('REAPLICADA', null);

      await c
          .read(offlineSyncControllerProvider.notifier)
          .refreshServerStatus();

      expect(c.read(offlineSyncControllerProvider).failures, isEmpty);
      final op = (await database.operations(_scope))
          .singleWhere((op) => op.id == failure.operation.id);
      expect(op.status, OfflineOperationStatus.applied);
      expect(op.resolution, 'REAPLICADA');
    });

    test('si la anula, guarda la nota y la alerta desaparece', () async {
      final (c, failure) = await conflicted();
      backend.resolutions[failure.operation.id] = (
        'ANULADA',
        'Se devolvió el dinero',
      );

      await c
          .read(offlineSyncControllerProvider.notifier)
          .refreshServerStatus();

      expect(c.read(offlineSyncControllerProvider).failures, isEmpty);
      final op = (await database.operations(_scope))
          .singleWhere((op) => op.id == failure.operation.id);
      expect(op.status, OfflineOperationStatus.conflict);
      expect(op.resolution, 'ANULADA');
      expect(op.resolutionNote, 'Se devolvió el dinero');
      expect(op.acknowledgedAt, isNotNull);
    });

    test(
      'mientras no se resuelva, la alerta sigue y se vuelve a consultar',
      () async {
        final (c, failure) = await conflicted();
        final sync = c.read(offlineSyncControllerProvider.notifier);

        expect(await sync.refreshServerStatus(), 0);
        expect(c.read(offlineSyncControllerProvider).failures, hasLength(1));
        expect(backend.statusQueries.last, [failure.operation.id]);

        // Ya resuelta, no se vuelve a preguntar por ella.
        backend.resolutions[failure.operation.id] = ('REAPLICADA', null);
        await sync.refreshServerStatus();
        backend.statusQueries.clear();
        await sync.refreshServerStatus();
        expect(backend.statusQueries, isEmpty);
      },
    );

    test('sin conexión no consulta', () async {
      final (c, _) = await conflicted();
      probe.backend = false;
      await c.read(connectivityControllerProvider.notifier).check();
      backend.statusQueries.clear();
      expect(
        await c
            .read(offlineSyncControllerProvider.notifier)
            .refreshServerStatus(),
        0,
      );
      expect(backend.statusQueries, isEmpty);
    });
  });

  test(
    'migra una base anterior agregando la columna sin perder la cola',
    () async {
      final legacyDir = await Directory.systemTemp.createTemp('zentry-legacy-');
      addTearDown(() => legacyDir.delete(recursive: true));
      final file =
          '${legacyDir.path}${Platform.pathSeparator}zentry_offline.sqlite';
      final legacy = sqlite3.open(file);
      legacy.execute('''
      CREATE TABLE offline_scope (scope_key TEXT PRIMARY KEY, tenant_slug TEXT NOT NULL,
        user_id INTEGER NOT NULL, branch_id INTEGER NOT NULL, device_id TEXT NOT NULL,
        catalog_version TEXT, last_catalog_sync_at TEXT, last_successful_sync_at TEXT);
      CREATE TABLE offline_operation (id_operation TEXT PRIMARY KEY, scope_key TEXT NOT NULL,
        type TEXT NOT NULL, client_date TEXT NOT NULL, payload_json TEXT NOT NULL,
        status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, error_code TEXT,
        error_message TEXT, batch_id TEXT, result_json TEXT, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL);
      INSERT INTO offline_scope VALUES ('demo:1:2', 'demo', 1, 2, 'device', NULL, NULL, NULL);
      INSERT INTO offline_operation VALUES ('op-1', 'demo:1:2', 'VENTA', '2026-11-10T10:00:00Z',
        '{"items":[]}', 'CONFLICTO', 1, 'STOCK_INSUFICIENTE', 'Sin stock', NULL, NULL,
        '2026-11-10T10:00:00Z', '2026-11-10T10:00:00Z');
    ''');
      legacy.close();

      final migrated = OfflineDatabase(legacyDir);
      addTearDown(migrated.close);
      final failures = await migrated.unacknowledgedFailures('demo', 1);
      expect(failures.single.operation.id, 'op-1');
      await migrated.acknowledge('op-1');
      expect(await migrated.unacknowledgedFailures('demo', 1), isEmpty);
    },
  );
}

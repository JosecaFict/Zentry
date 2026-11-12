import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/notifications/local_notifications.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/admin/data/admin_repository.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/data/offline_sync_repository.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:capricho_store/features/offline/presentation/offline_controller.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../core/connectivity_controller_test.dart' show FakeProbe;

/// Backend falso: sucursales, registro del dispositivo, catálogo y clientes.
class _Backend implements HttpClientAdapter {
  int catalogCalls = 0;
  int stock = 4;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final Object body = switch (options.path) {
      '/branches' => [
        {'id_sucursal': 2, 'nombre': 'Centro', 'direccion': 'Av. 1'},
      ],
      '/sync/catalog' => () {
        catalogCalls++;
        return {
          'id_sucursal': 2,
          'generado_at': '2026-11-12T10:00:00Z',
          'version': 'v$catalogCalls',
          'items': [
            {
              'id_variante': 7,
              'sku': 'POLO-M',
              'producto': 'Polo básico',
              'talla': 'M',
              'color': 'Negro',
              'precio': '99.90',
              'stock_fisico': stock,
              'stock_reservado': 0,
              'stock_disponible': stock,
            },
          ],
        };
      }(),
      '/customers' => <Object>[],
      _ => <String, dynamic>{},
    };
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

class _Notifier implements LocalNotifier {
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
  }) async {}
}

class _Seller extends AuthController {
  @override
  AuthState build() => const AuthState(
    initialized: true,
    user: AppUser(
      id: 1,
      names: 'Ana',
      surnames: 'Vendedora',
      email: 'ana@example.com',
      status: 'ACTIVO',
      roles: ['CAJERO'],
      permissions: ['ventas.ver', 'ventas.crear', 'pagos.registrar'],
      idSucursal: 2,
    ),
  );
}

class _Tenant extends TenantController {
  @override
  TenantState build() => const TenantState(
    selected: TenantIdentity(name: 'Demo', slug: 'demo'),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory directory;
  late OfflineDatabase database;
  late _Backend backend;
  late FakeProbe probe;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('zentry-prepare-');
    database = OfflineDatabase(directory);
    backend = _Backend();
    probe = FakeProbe();
  });

  tearDown(() async {
    await database.close();
    await directory.delete(recursive: true);
  });

  Future<ProviderContainer> open() async {
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
      ..httpClientAdapter = backend;
    final container = ProviderContainer(
      overrides: [
        offlineDatabaseProvider.overrideWithValue(database),
        offlineSyncRepositoryProvider.overrideWithValue(
          OfflineSyncRepository(dio),
        ),
        adminRepositoryProvider.overrideWithValue(AdminRepository(dio)),
        networkProbeProvider.overrideWithValue(probe),
        localNotifierProvider.overrideWithValue(_Notifier()),
        authControllerProvider.overrideWith(_Seller.new),
        tenantControllerProvider.overrideWith(_Tenant.new),
      ],
    );
    addTearDown(() {
      container.dispose();
      probe.changes.close();
    });
    // Primero se conoce el estado real de la red, como en la app.
    container.listen(connectivityControllerProvider, (_, _) {});
    while (!container.read(connectivityControllerProvider).checked) {
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    container.listen(offlineControllerProvider, (_, _) {});
    return container;
  }

  Future<OfflineState> settled(ProviderContainer container) async {
    for (var i = 0; i < 400; i++) {
      final state = container.read(offlineControllerProvider);
      if (!state.loading && !state.busy && !state.refreshing) {
        // Un respiro más por si queda una descarga encadenada.
        await Future<void>.delayed(const Duration(milliseconds: 20));
        final again = container.read(offlineControllerProvider);
        if (!again.busy && !again.refreshing) return again;
      }
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    fail('La pantalla offline no terminó de cargar');
  }

  test(
    'con internet descarga el catálogo solo, sin pulsar "Preparar"',
    () async {
      final container = await open();
      final state = await settled(container);

      expect(backend.catalogCalls, 1);
      expect(state.branchId, 2);
      expect(state.prepared, isTrue);
      expect(state.catalog.single.availableStock, 4);
      expect(state.message, contains('listas para vender'));
      expect(state.error, isNull);

      // Ya se puede agregar la prenda al carrito de la venta.
      final controller = container.read(offlineControllerProvider.notifier);
      controller.setQuantity(state.catalog.single, 2);
      expect(container.read(offlineControllerProvider).cartUnits, 2);
    },
  );

  test('sin internet y sin catálogo guardado no intenta descargar', () async {
    probe.backend = false;
    // La sucursal ya se usó antes en este teléfono, pero sin catálogo.
    await database.ensureScope(
      const OfflineScope(tenantSlug: 'demo', userId: 1, branchId: 2),
    );
    final container = await open();
    final state = await settled(container);

    expect(backend.catalogCalls, 0);
    expect(state.online, isFalse);
    expect(state.prepared, isFalse);
    expect(state.error, isNull);
  });

  test(
    'con catálogo guardado actualiza el stock en segundo plano',
    () async {
      final first = await open();
      await settled(first);
      first.dispose();

      backend.stock = 1;
      probe = FakeProbe();
      final container = await open();
      final state = await settled(container);

      expect(backend.catalogCalls, 2);
      expect(state.catalog.single.availableStock, 1);
      // Actualizar con catálogo ya guardado no muestra mensajes ni bloquea.
      expect(state.message, isNull);
    },
  );
}

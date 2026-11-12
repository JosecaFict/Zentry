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

  /// Ventas presenciales recibidas (`POST /sales/pos`).
  final List<Map<String, dynamic>> sales = [];

  /// Cómo responde la venta: 'ok', 'sin_stock' o 'sin_red'.
  String saleMode = 'ok';

  ResponseBody _json(Object body, [int status = 200]) => ResponseBody.fromString(
    jsonEncode(body),
    status,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (options.path == '/sales/pos') {
      if (saleMode == 'sin_red') {
        throw DioException.connectionError(
          requestOptions: options,
          reason: 'Sin conexión',
        );
      }
      if (saleMode == 'sin_stock') {
        return _json({
          'detail': 'Stock insuficiente para completar la venta',
        }, 409);
      }
      final data = Map<String, dynamic>.from(options.data as Map);
      sales.add(data);
      return _json({
        'id_venta': 501,
        'id_cliente': data['id_cliente'],
        'cliente_nombre': data['id_cliente'] == null ? null : 'Rosa Pérez',
        'sucursal': 'Centro',
        'empleado_nombre': 'Ana Vendedora',
        'metodo_pago': 'EFECTIVO',
        'total': '199.80',
        'fecha_venta': '2026-11-12T15:00:00Z',
        'items': [
          {
            'producto': 'Polo básico',
            'talla': 'M',
            'color': 'Negro',
            'cantidad': 2,
            'subtotal': '199.80',
          },
        ],
      }, 201);
    }
    if (options.path == '/customers/quick') {
      final data = Map<String, dynamic>.from(options.data as Map);
      return _json({
        'id_cliente': 77,
        'nombre_completo': '${data['nombres']} ${data['apellidos']}'.trim(),
        'correo': data['correo'] ?? '',
        'telefono': data['telefono'],
      }, 201);
    }
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

  /// Espera a que la pantalla cumpla [done] y quede sin descargas en curso.
  /// Espera una condición concreta (no "que esté quieta"): entre que termina
  /// de cargar y empieza la descarga automática hay un instante sin trabajo.
  Future<OfflineState> settled(
    ProviderContainer container, [
    bool Function(OfflineState state)? done,
  ]) async {
    final watch = Stopwatch()..start();
    while (watch.elapsed < const Duration(seconds: 10)) {
      final state = container.read(offlineControllerProvider);
      if (!state.loading &&
          !state.busy &&
          !state.refreshing &&
          (done?.call(state) ?? true)) {
        return state;
      }
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    fail('La pantalla offline no terminó de cargar');
  }

  test(
    'con internet descarga el catálogo solo, sin pulsar "Preparar"',
    () async {
      final container = await open();
      final state = await settled(container, (state) => state.prepared);

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
      await settled(first, (state) => state.prepared);
      first.dispose();

      backend.stock = 1;
      probe = FakeProbe();
      final container = await open();
      final state = await settled(
        container,
        (state) => state.catalog.singleOrNull?.availableStock == 1,
      );

      expect(backend.catalogCalls, 2);
      expect(state.catalog.single.availableStock, 1);
      // Actualizar con catálogo ya guardado no muestra mensajes ni bloquea.
      expect(state.message, isNull);
    },
  );

  group('venta presencial con internet', () {
    Future<(ProviderContainer, OfflineController)> ready() async {
      final container = await open();
      final state = await settled(container, (state) => state.prepared);
      final controller = container.read(offlineControllerProvider.notifier);
      controller.setQuantity(state.catalog.single, 2);
      return (container, controller);
    }

    test('se registra al momento y muestra el comprobante', () async {
      final (container, controller) = await ready();

      expect(await controller.queue(), isTrue);

      final state = container.read(offlineControllerProvider);
      expect(backend.sales.single['items'], [
        {'id_variante': 7, 'cantidad': 2},
      ]);
      expect(backend.sales.single['registrar_efectivo'], isTrue);
      expect(state.lastSale?.id, 501);
      expect(state.lastSale?.total, 199.80);
      expect(state.lastSale?.lines.single.description, 'Polo básico M Negro');
      expect(state.cart, isEmpty);
      expect(state.message, 'Venta #501 registrada.');
      // No queda nada pendiente en el teléfono.
      const scope = OfflineScope(tenantSlug: 'demo', userId: 1, branchId: 2);
      expect(await database.operations(scope), isEmpty);
    });

    test('sin stock en el servidor: avisa y no guarda nada', () async {
      final (container, controller) = await ready();
      backend.saleMode = 'sin_stock';

      expect(await controller.queue(), isFalse);

      final state = container.read(offlineControllerProvider);
      expect(state.error, 'Stock insuficiente para completar la venta');
      expect(state.cart, {7: 2}, reason: 'el carrito queda para corregirlo');
      expect(state.lastSale, isNull);
      const scope = OfflineScope(tenantSlug: 'demo', userId: 1, branchId: 2);
      expect(await database.operations(scope), isEmpty);
    });

    test('si no llega al servidor, se guarda en el teléfono', () async {
      final (container, controller) = await ready();
      backend.saleMode = 'sin_red';

      expect(await controller.queue(), isTrue);

      final state = container.read(offlineControllerProvider);
      expect(state.message, contains('quedó guardada en este dispositivo'));
      expect(state.cart, isEmpty);
      const scope = OfflineScope(tenantSlug: 'demo', userId: 1, branchId: 2);
      final saved = await database.operations(scope);
      expect(saved.single.type, OfflineOperationType.sale);
      expect(saved.single.payload['items'], [
        {'id_variante': 7, 'cantidad': 2},
      ]);
    });

    test('cliente nuevo desde la caja queda elegido y guardado', () async {
      final (container, controller) = await ready();

      expect(
        await controller.createCustomer(
          names: 'Rosa',
          surnames: 'Pérez',
          phone: '70000000',
        ),
        isTrue,
      );

      final state = container.read(offlineControllerProvider);
      expect(state.customerId, 77);
      expect(state.customers.map((c) => c.name), contains('Rosa Pérez'));
      const scope = OfflineScope(tenantSlug: 'demo', userId: 1, branchId: 2);
      expect((await database.customers(scope)).single.id, 77);

      expect(await controller.queue(), isTrue);
      expect(backend.sales.single['id_cliente'], 77);
      expect(
        container.read(offlineControllerProvider).lastSale?.customer,
        'Rosa Pérez',
      );
    });
  });
}

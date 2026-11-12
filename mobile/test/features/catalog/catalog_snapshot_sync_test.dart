import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/catalog/data/catalog_repository.dart';
import 'package:capricho_store/features/catalog/data/catalog_snapshot.dart';
import 'package:capricho_store/features/catalog/data/catalog_snapshot_sync.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../core/connectivity_controller_test.dart' show FakeProbe;
import 'catalog_snapshot_test.dart' show product;

/// Backend falso con 250 productos (3 páginas de 100), 1 temporada y
/// 1 sucursal. Filtra por `temporada` y `sucursal` como el real.
class _CatalogBackend implements HttpClientAdapter {
  _CatalogBackend() {
    for (var id = 1; id <= 250; id++) {
      products.add(product(id, 'Prenda ${id.toString().padLeft(3, '0')}'));
    }
  }

  final List<Map<String, dynamic>> products = [];
  final Set<int> summer = {1, 2, 3};
  final Set<int> branch2 = {5, 150};
  bool online = true;
  bool failSeasonFilter = false;
  int productRequests = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (!online) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'Sin conexión',
      );
    }
    final q = options.queryParameters;
    final Object body = switch (options.path) {
      '/categories' => [
        {'id_categoria': 1, 'nombre': 'Poleras', 'activo': true},
      ],
      '/brands' => [
        {'id_marca': 1, 'nombre': 'Capricho', 'activo': true},
      ],
      '/sizes' => [
        {'id_talla': 1, 'codigo': 'M', 'orden': 1},
      ],
      '/colors' => [
        {'id_color': 1, 'nombre': 'Negro', 'codigo_hex': '#000'},
      ],
      '/seasons' => [
        {'id_temporada': 1, 'nombre': 'Verano', 'anio': 2026},
      ],
      '/branches' => [
        {'id_sucursal': 2, 'nombre': 'Centro', 'direccion': 'Av. 1'},
      ],
      '/products' => _page(q),
      _ => const <String, dynamic>{},
    };
    if (body is Map && body['error'] == true) {
      return ResponseBody.fromString('{"detail":"falla"}', 500, headers: _json);
    }
    return ResponseBody.fromString(jsonEncode(body), 200, headers: _json);
  }

  Map<String, dynamic> _page(Map<String, dynamic> q) {
    productRequests++;
    if (q['temporada'] != null && failSeasonFilter) return {'error': true};
    var items = products;
    if (q['temporada'] != null) {
      items = items.where((p) => summer.contains(p['id_producto'])).toList();
    }
    if (q['sucursal'] != null) {
      items = items.where((p) => branch2.contains(p['id_producto'])).toList();
    }
    final page = int.parse('${q['page'] ?? 1}');
    final size = int.parse('${q['page_size'] ?? 20}');
    final start = (page - 1) * size;
    return {
      'items': items.skip(start).take(size).toList(),
      'page': page,
      'page_size': size,
      'total': items.length,
      'pages': (items.length / size).ceil(),
    };
  }

  static const _json = {
    Headers.contentTypeHeader: [Headers.jsonContentType],
  };

  @override
  void close({bool force = false}) {}
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
  late _CatalogBackend backend;
  late FakeProbe probe;
  late ProviderContainer container;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('zentry-snapshot-');
    database = OfflineDatabase(directory);
    backend = _CatalogBackend();
    probe = FakeProbe();
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
      ..httpClientAdapter = backend;
    container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        offlineDatabaseProvider.overrideWithValue(database),
        networkProbeProvider.overrideWithValue(probe),
        tenantControllerProvider.overrideWith(_Tenant.new),
      ],
    );
    container.listen(catalogSnapshotControllerProvider, (_, _) {});
  });

  tearDown(() async {
    container.dispose();
    await probe.changes.close();
    await database.close();
    await directory.delete(recursive: true);
  });

  CatalogRepository repo() => container.read(catalogRepositoryProvider);

  Future<void> goOffline() async {
    backend.online = false;
    probe.backend = false;
    await container.read(connectivityControllerProvider.notifier).check();
  }

  test(
    'descarga todas las páginas y la pertenencia a temporada y sucursal',
    () async {
      await container
          .read(catalogSnapshotControllerProvider.notifier)
          .syncNow();

      final state = container.read(catalogSnapshotControllerProvider);
      expect(state.productCount, 250);
      expect(state.syncedAt, isNotNull);
      final stored = CatalogSnapshot.fromStored(
        (await database.catalogSnapshot('demo'))!,
      );
      expect(stored.products, hasLength(250));
      expect(stored.tags['season:verano'], {1, 2, 3});
      expect(stored.tags['branch:2'], {5, 150});
    },
  );

  test('sin conexión filtra combinaciones que nunca se consultaron', () async {
    await container.read(catalogSnapshotControllerProvider.notifier).syncNow();
    await goOffline();

    final summer = await repo().products(
      const CatalogQuery(season: 'Verano', sort: '-nombre'),
    );
    expect(summer.items.map((p) => p.id), [3, 2, 1]);

    final branch = await repo().products(const CatalogQuery(branchId: 2));
    expect(branch.items.map((p) => p.id), [5, 150]);

    final page3 = await repo().products(
      const CatalogQuery(page: 3, pageSize: 100),
    );
    expect(page3.items, hasLength(50));
    expect(page3.pages, 3);
  });

  test('sin conexión abre el detalle de un producto nunca visitado', () async {
    await container.read(catalogSnapshotControllerProvider.notifier).syncNow();
    await goOffline();

    final detail = await repo().product(200);
    expect(detail.name, 'Prenda 200');
    final variants = await repo().productVariants(200);
    expect(variants.single.size, 'M');
    // Los selectores de filtros también quedaron guardados.
    expect((await repo().categories()).single.name, 'Poleras');
  });

  test('usa la respuesta exacta si es más reciente que la copia', () async {
    await container.read(catalogSnapshotControllerProvider.notifier).syncNow();
    // El servidor cambia un nombre y el usuario abre esa página con conexión.
    backend.products[0] = product(1, 'Prenda 001 renovada');
    await repo().products(const CatalogQuery(pageSize: 5));
    await goOffline();

    final page = await repo().products(const CatalogQuery(pageSize: 5));
    expect(page.items.first.name, 'Prenda 001 renovada');
  });

  test('sin copia ni respuesta guardada, el error se propaga', () async {
    await goOffline();
    expect(
      () => repo().products(const CatalogQuery(season: 'Verano')),
      throwsA(isA<ApiException>()),
    );
  });

  test(
    'si falla una temporada, el resto se guarda y ese filtro no inventa',
    () async {
      backend.failSeasonFilter = true;
      await container
          .read(catalogSnapshotControllerProvider.notifier)
          .syncNow();
      expect(
        container.read(catalogSnapshotControllerProvider).productCount,
        250,
      );
      await goOffline();

      final summer = await repo().products(
        const CatalogQuery(season: 'Verano'),
      );
      expect(summer.items, isEmpty);
      final all = await repo().products(const CatalogQuery());
      expect(all.total, 250);
    },
  );

  test('no vuelve a descargar mientras la copia es reciente', () async {
    final controller = container.read(
      catalogSnapshotControllerProvider.notifier,
    );
    await controller.syncNow();
    final requests = backend.productRequests;

    await controller.maybeSync();
    expect(backend.productRequests, requests);

    await controller.maybeSync(
      now: DateTime.now().add(
        catalogSnapshotMaxAge + const Duration(minutes: 1),
      ),
    );
    expect(backend.productRequests, greaterThan(requests));
  });

  test('tras un fallo espera antes de reintentar', () async {
    final controller = container.read(
      catalogSnapshotControllerProvider.notifier,
    );
    backend.online = false;
    await controller.syncNow();
    expect(container.read(catalogSnapshotControllerProvider).error, isNotNull);

    backend.online = true;
    final requests = backend.productRequests;
    await controller.maybeSync();
    expect(backend.productRequests, requests);

    await controller.maybeSync(
      now: DateTime.now().add(
        catalogSnapshotRetryDelay + const Duration(seconds: 1),
      ),
    );
    expect(container.read(catalogSnapshotControllerProvider).productCount, 250);
  });

  test('si cambia la empresa durante la descarga, no guarda nada', () async {
    final downloader = container.read(catalogSnapshotDownloaderProvider);
    await expectLater(
      downloader.download('demo', isCurrent: () => false),
      throwsStateError,
    );
    expect(await database.catalogSnapshotInfo('demo'), isNull);
  });
}

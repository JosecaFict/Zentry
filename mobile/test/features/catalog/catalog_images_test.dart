import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/catalog/data/catalog_images.dart';
import 'package:capricho_store/features/catalog/data/catalog_snapshot_sync.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_image.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;

import '../../core/connectivity_controller_test.dart' show FakeProbe;
import 'catalog_snapshot_test.dart' show product;

const _cloud = 'https://res.cloudinary.com/demo/image/upload/v1/polo';

/// Servidor de imágenes falso: responde bytes de "imagen" y registra las URLs.
class _ImageServer implements HttpClientAdapter {
  final List<String> requested = [];
  String contentType = 'image/jpeg';
  bool down = false;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requested.add(options.uri.toString());
    if (down) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'Sin conexión',
      );
    }
    return ResponseBody.fromBytes(
      utf8.encode('bytes de ${options.uri}'),
      200,
      headers: {
        Headers.contentTypeHeader: [contentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _Tenant extends TenantController {
  @override
  TenantState build() => const TenantState(
    selected: TenantIdentity(name: 'Demo', slug: 'demo'),
  );
}

Map<String, dynamic> withImage(int id, String? url) => product(id, 'Prenda $id')
  ..['imagen_principal'] = url == null
      ? null
      : {'secure_url': url, 'id_color': null, 'es_principal': true};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('URLs y nombres de archivo', () {
    test('pide a Cloudinary una versión de 800 px', () {
      expect(
        offlineImageUrl('$_cloud/1.jpg'),
        'https://res.cloudinary.com/demo/image/upload/c_limit,w_800,q_auto/v1/polo/1.jpg',
      );
      expect(
        offlineImageUrl('https://otra.cdn.com/a.png'),
        'https://otra.cdn.com/a.png',
      );
    });

    test('el nombre de archivo es estable y conserva la extensión', () {
      final name = offlineImageFileName('$_cloud/1.jpg');
      expect(name, offlineImageFileName('$_cloud/1.jpg'));
      expect(name, isNot(offlineImageFileName('$_cloud/2.jpg')));
      expect(name, endsWith('.jpg'));
      expect(offlineImageFileName('https://x.com/foto?id=3'), endsWith('.img'));
    });
  });

  group('descarga de imágenes principales', () {
    late Directory directory;
    late Directory root;
    late OfflineDatabase database;
    late _ImageServer server;
    late FakeProbe probe;
    late ProviderContainer container;

    Future<void> saveSnapshot(List<Map<String, dynamic>> products) =>
        database.replaceCatalogSnapshot(
          tenantSlug: 'demo',
          products: [
            for (final product in products)
              (id: product['id_producto'] as int, json: jsonEncode(product)),
          ],
          tags: const [],
          downloadedTags: const {},
          syncedAt: DateTime.now(),
        );

    setUp(() async {
      directory = await Directory.systemTemp.createTemp('zentry-images-');
      root = Directory(p.join(directory.path, 'catalog_images'));
      database = OfflineDatabase(directory);
      server = _ImageServer();
      probe = FakeProbe();
      container = ProviderContainer(
        overrides: [
          offlineDatabaseProvider.overrideWithValue(database),
          networkProbeProvider.overrideWithValue(probe),
          tenantControllerProvider.overrideWith(_Tenant.new),
          catalogImageRootProvider.overrideWithValue(() async => root),
          catalogSnapshotControllerProvider.overrideWith(_NoSnapshotSync.new),
          catalogImageDioProvider.overrideWithValue(
            Dio(BaseOptions(responseType: ResponseType.bytes))
              ..httpClientAdapter = server,
          ),
        ],
      );
      container.listen(catalogImagesControllerProvider, (_, _) {});
    });

    tearDown(() async {
      container.dispose();
      await probe.changes.close();
      await database.close();
      await directory.delete(recursive: true);
    });

    CatalogImagesController controller() =>
        container.read(catalogImagesControllerProvider.notifier);
    CatalogImagesState state() =>
        container.read(catalogImagesControllerProvider);

    test('con WiFi guarda la imagen principal de cada producto', () async {
      await saveSnapshot([
        withImage(1, '$_cloud/1.jpg'),
        withImage(2, '$_cloud/2.jpg'),
        withImage(3, null),
      ]);
      await controller().maybeDownload();

      expect(
        state().paths.keys,
        unorderedEquals(['$_cloud/1.jpg', '$_cloud/2.jpg']),
      );
      expect(state().missing, 0);
      expect(state().downloading, isFalse);
      for (final path in state().paths.values) {
        expect(File(path).existsSync(), isTrue);
        expect(p.isWithin(root.path, path), isTrue);
      }
      // Se descargó la versión liviana, no la original.
      expect(server.requested, everyElement(contains('w_800')));
      expect((await database.catalogImages('demo')), hasLength(2));
      // Sin archivos temporales a medio escribir.
      expect(
        root.listSync(recursive: true).where((f) => f.path.endsWith('.part')),
        isEmpty,
      );
    });

    test('con datos móviles no descarga nada', () async {
      probe.unmetered = false;
      await saveSnapshot([withImage(1, '$_cloud/1.jpg')]);
      await controller().maybeDownload();
      expect(server.requested, isEmpty);
      expect(state().paths, isEmpty);
    });

    test('solo descarga lo que falta', () async {
      await saveSnapshot([withImage(1, '$_cloud/1.jpg')]);
      await controller().maybeDownload();
      await saveSnapshot([
        withImage(1, '$_cloud/1.jpg'),
        withImage(2, '$_cloud/2.jpg'),
      ]);
      server.requested.clear();
      await controller().maybeDownload();
      expect(server.requested, hasLength(1));
      expect(server.requested.single, contains('polo/2.jpg'));
    });

    test('borra las imágenes de productos que ya no existen', () async {
      await saveSnapshot([
        withImage(1, '$_cloud/1.jpg'),
        withImage(2, '$_cloud/2.jpg'),
      ]);
      await controller().maybeDownload();
      final removed = state().paths['$_cloud/2.jpg']!;

      await saveSnapshot([withImage(1, '$_cloud/1.jpg')]);
      await controller().maybeDownload();
      expect(File(removed).existsSync(), isFalse);
      expect(state().paths.keys, ['$_cloud/1.jpg']);
      expect((await database.catalogImages('demo')).keys, ['$_cloud/1.jpg']);
    });

    test('si el archivo se borró del disco, lo vuelve a descargar', () async {
      await saveSnapshot([withImage(1, '$_cloud/1.jpg')]);
      await controller().maybeDownload();
      await File(state().paths['$_cloud/1.jpg']!).delete();
      server.requested.clear();
      await controller().maybeDownload();
      expect(server.requested, hasLength(1));
      expect(File(state().paths['$_cloud/1.jpg']!).existsSync(), isTrue);
    });

    test(
      'rechaza respuestas que no son imágenes y espera antes de reintentar',
      () async {
        await saveSnapshot([withImage(1, '$_cloud/1.jpg')]);
        server.contentType = 'text/html';
        await controller().maybeDownload();
        expect(state().paths, isEmpty);
        expect(state().error, isNotNull);

        server.contentType = 'image/jpeg';
        server.requested.clear();
        await controller().maybeDownload();
        expect(server.requested, isEmpty);

        await controller().maybeDownload(
          now: DateTime.now().add(const Duration(minutes: 6)),
        );
        expect(state().paths, hasLength(1));
      },
    );

    test('al reabrir la app recupera las imágenes guardadas', () async {
      await saveSnapshot([withImage(1, '$_cloud/1.jpg')]);
      await controller().maybeDownload();
      final saved = state().paths['$_cloud/1.jpg'];

      final again = ProviderContainer(
        overrides: [
          offlineDatabaseProvider.overrideWithValue(database),
          networkProbeProvider.overrideWithValue(probe),
          tenantControllerProvider.overrideWith(_Tenant.new),
          catalogImageRootProvider.overrideWithValue(() async => root),
          catalogSnapshotControllerProvider.overrideWith(_NoSnapshotSync.new),
        ],
      );
      addTearDown(again.dispose);
      again.listen(catalogImagesControllerProvider, (_, _) {});
      for (var i = 0; i < 200; i++) {
        if (again.read(catalogImagesControllerProvider).paths.isNotEmpty) break;
        await Future<void>.delayed(const Duration(milliseconds: 10));
      }
      expect(
        again.read(catalogImagesControllerProvider).paths['$_cloud/1.jpg'],
        saved,
      );
    });
  });

  group('AdaptiveImage', () {
    Future<void> pump(
      WidgetTester tester, {
      required bool online,
      Map<String, String> saved = const {},
    }) => tester.pumpWidget(
      ProviderScope(
        overrides: [
          connectivityControllerProvider.overrideWith(
            () => _FixedConnectivity(online),
          ),
          catalogImagesControllerProvider.overrideWith(
            () => _FixedImages(saved),
          ),
        ],
        child: const MaterialApp(
          home: AdaptiveImage(
            imageUrl: '$_cloud/1.jpg',
            width: 100,
            height: 100,
          ),
        ),
      ),
    );

    testWidgets('sin conexión muestra la copia guardada', (tester) async {
      await pump(tester, online: false, saved: {'$_cloud/1.jpg': '/tmp/x.jpg'});
      expect(find.byType(CachedNetworkImage), findsNothing);
      final image = tester.widget<Image>(find.byType(Image));
      expect((image.image as FileImage).file.path, '/tmp/x.jpg');
    });

    testWidgets('con conexión usa la imagen de red en calidad completa', (
      tester,
    ) async {
      await pump(tester, online: true, saved: {'$_cloud/1.jpg': '/tmp/x.jpg'});
      final network = tester.widget<CachedNetworkImage>(
        find.byType(CachedNetworkImage),
      );
      expect(network.imageUrl, '$_cloud/1.jpg');
      expect(network.cacheManager, same(catalogImageCacheManager));
    });

    testWidgets('sin conexión ni copia, intenta la caché de red', (
      tester,
    ) async {
      await pump(tester, online: false);
      expect(find.byType(CachedNetworkImage), findsOneWidget);
    });
  });
}

class _FixedConnectivity extends ConnectivityController {
  _FixedConnectivity(this.online);
  final bool online;

  @override
  ConnectivityState build() => ConnectivityState(
    online: online,
    checked: true,
    checkedAt: DateTime(2026),
  );
}

class _FixedImages extends CatalogImagesController {
  _FixedImages(this.saved);
  final Map<String, String> saved;

  @override
  CatalogImagesState build() => CatalogImagesState(paths: saved);
}

/// Evita que la descarga del catálogo completo llame al servidor real.
class _NoSnapshotSync extends CatalogSnapshotController {
  @override
  CatalogSnapshotState build() => const CatalogSnapshotState();
}

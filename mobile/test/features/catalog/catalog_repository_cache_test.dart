import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/features/catalog/data/catalog_repository.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Adaptador falso: responde con [responses] mientras [online] sea true;
/// si no, simula que no hay red.
class _FakeAdapter implements HttpClientAdapter {
  bool online = true;
  int statusCode = 200;
  final Map<String, Object> responses = {};
  final List<String> requested = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requested.add(options.uri.toString());
    if (!online) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'Sin conexión',
      );
    }
    final body = responses[options.path] ?? const <String, dynamic>{};
    return ResponseBody.fromString(
      jsonEncode(body),
      statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Map<String, dynamic> _product(int id, String name) => {
  'id_producto': id,
  'nombre': name,
  'categoria': 'POLERA',
  'marca': 'Capricho',
  'publico_objetivo': 'MUJER',
  'descripcion': null,
  'permite_vestidor': false,
  'activo': true,
  'precio_actual': '99.90',
  'imagen_principal': null,
  'variantes': <dynamic>[],
  'tallas_disponibles': ['M'],
  'colores_disponibles': ['Negro'],
};

void main() {
  late Directory directory;
  late OfflineDatabase database;
  late _FakeAdapter adapter;
  late Dio dio;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('zentry-catalog-');
    database = OfflineDatabase(directory);
    adapter = _FakeAdapter();
    dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
      ..httpClientAdapter = adapter;
  });

  tearDown(() async {
    await database.close();
    await directory.delete(recursive: true);
  });

  CatalogRepository repo(String? tenant) =>
      CatalogRepository(dio, cache: database, tenantSlug: tenant);

  test('sin conexión devuelve el catálogo guardado con conexión', () async {
    adapter.responses['/products'] = {
      'items': [_product(1, 'Polo básico')],
      'page': 1,
      'total': 1,
      'pages': 1,
    };
    adapter.responses['/products/1'] = _product(1, 'Polo básico');
    adapter.responses['/categories'] = [
      {'id_categoria': 3, 'nombre': 'Poleras', 'activo': true},
    ];

    const query = CatalogQuery(category: 'POLERA');
    final online = await repo('demo').products(query);
    await repo('demo').product(1);
    await repo('demo').categories();
    expect(online.items.single.name, 'Polo básico');

    adapter.online = false;
    final offline = await repo('demo').products(query);
    final detail = await repo('demo').product(1);
    final categories = await repo('demo').categories();

    expect(offline.items.single.name, 'Polo básico');
    expect(detail.price, 99.90);
    expect(categories.single.name, 'Poleras');
  });

  test('sin conexión y sin caché propaga el error', () async {
    adapter.online = false;
    expect(
      () => repo('demo').products(const CatalogQuery()),
      throwsA(isA<ApiException>()),
    );
  });

  test('la caché se separa por empresa', () async {
    adapter.responses['/categories'] = [
      {'id_categoria': 3, 'nombre': 'Poleras', 'activo': true},
    ];
    await repo('empresa-a').categories();

    adapter.online = false;
    expect(() => repo('empresa-b').categories(), throwsA(isA<ApiException>()));
    expect((await repo('empresa-a').categories()).single.name, 'Poleras');
  });

  test('filtros distintos no comparten caché', () async {
    adapter.responses['/products'] = {
      'items': [_product(1, 'Polo básico')],
      'page': 1,
      'total': 1,
      'pages': 1,
    };
    await repo('demo').products(const CatalogQuery(category: 'POLERA'));

    adapter.online = false;
    expect(
      () => repo('demo').products(const CatalogQuery(category: 'PANTALON')),
      throwsA(isA<ApiException>()),
    );
  });

  test('un 404 no se tapa con la caché', () async {
    adapter.responses['/products/1'] = _product(1, 'Polo básico');
    await repo('demo').product(1);

    adapter.statusCode = 404;
    expect(() => repo('demo').product(1), throwsA(isA<ApiException>()));
  });

  test('un 500 usa la caché', () async {
    adapter.responses['/products/1'] = _product(1, 'Polo básico');
    await repo('demo').product(1);

    adapter.statusCode = 503;
    expect((await repo('demo').product(1)).name, 'Polo básico');
  });

  test('sin empresa seleccionada no guarda ni lee caché', () async {
    adapter.responses['/sizes'] = [
      {'id_talla': 1, 'codigo': 'M', 'orden': 1},
    ];
    await repo(null).sizes();

    adapter.online = false;
    expect(() => repo(null).sizes(), throwsA(isA<ApiException>()));
  });
}

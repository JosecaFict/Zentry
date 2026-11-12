import 'package:capricho_store/features/catalog/data/catalog_snapshot.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> product(
  int id,
  String name, {
  String category = 'Poleras',
  String brand = 'Capricho',
  String audience = 'MUJER',
  String? price = '100.00',
  bool fitting = false,
  String created = '2026-01-01T00:00:00Z',
  List<(String size, String color, bool active)> variants = const [
    ('M', 'Negro', true),
  ],
}) => {
  'id_producto': id,
  'nombre': name,
  'categoria': category,
  'marca': brand,
  'publico_objetivo': audience,
  'descripcion': null,
  'permite_vestidor': fitting,
  'activo': true,
  'precio_actual': price,
  'imagen_principal': null,
  'created_at': created,
  'variantes': [
    for (final (i, v) in variants.indexed)
      {
        'id_variante': id * 10 + i,
        'id_producto': id,
        'id_talla': i,
        'talla': v.$1,
        'id_color': i,
        'color': v.$2,
        'codigo_hex': null,
        'sku': 'SKU-$id-$i',
        'codigo_barras': null,
        'activo': v.$3,
      },
  ],
  'tallas_disponibles': [for (final v in variants) v.$1],
  'colores_disponibles': [for (final v in variants) v.$2],
};

void main() {
  final snapshot = CatalogSnapshot(
    syncedAt: DateTime.utc(2026, 11, 11),
    products: [
      product(
        1,
        'Polo básico',
        price: '80.00',
        created: '2026-03-01T00:00:00Z',
        variants: const [('M', 'Negro', true), ('L', 'Blanco', true)],
      ),
      product(
        2,
        'abrigo largo',
        category: 'Abrigos',
        brand: 'Norte',
        audience: 'HOMBRE',
        price: '350.50',
        fitting: true,
        created: '2026-05-01T00:00:00Z',
        variants: const [('S', 'Gris', true), ('XL', 'Negro', false)],
      ),
      product(
        3,
        'Camisa lino',
        price: null,
        created: '2026-01-15T00:00:00Z',
        variants: const [('M', 'Azul', true)],
      ),
    ],
    tags: {
      'season:verano 2026': {1, 3},
      'branch:2': {2},
    },
    downloadedTags: {'season:verano 2026', 'season:invierno', 'branch:2'},
  );

  List<int> ids(CatalogQuery query) => [
    for (final item in snapshot.query(query)['items'] as List)
      (item as Map)['id_producto'] as int,
  ];

  test('sin filtros ordena por nombre sin importar mayúsculas', () {
    expect(ids(const CatalogQuery()), [2, 3, 1]);
  });

  test('categoría y marca comparan sin distinguir mayúsculas', () {
    expect(ids(const CatalogQuery(category: 'poleras')), [3, 1]);
    expect(ids(const CatalogQuery(brand: 'NORTE')), [2]);
  });

  test('público objetivo y vestidor', () {
    expect(ids(const CatalogQuery(audience: 'HOMBRE')), [2]);
    expect(ids(const CatalogQuery(fittingEnabled: true)), [2]);
    expect(ids(const CatalogQuery(fittingEnabled: false)), [3, 1]);
  });

  test('talla y color solo cuentan variantes activas, como el backend', () {
    expect(ids(const CatalogQuery(size: 'm')), [3, 1]);
    expect(ids(const CatalogQuery(color: 'negro')), [1]);
    expect(ids(const CatalogQuery(size: 'XL')), isEmpty);
  });

  test('temporada usa la pertenencia descargada', () {
    expect(ids(const CatalogQuery(season: 'Verano 2026')), [3, 1]);
    expect(ids(const CatalogQuery(season: 'invierno')), isEmpty);
    // Temporada que no se descargó: no se puede saber, no se inventa.
    expect(ids(const CatalogQuery(season: 'otoño')), isEmpty);
  });

  test('sucursal descargada filtra; sin datos muestra todo', () {
    expect(ids(const CatalogQuery(branchId: 2)), [2]);
    expect(ids(const CatalogQuery(branchId: 9)), [2, 3, 1]);
  });

  test('ordena por precio (sin precio = 0) y por fecha', () {
    expect(ids(const CatalogQuery(sort: 'precio')), [3, 1, 2]);
    expect(ids(const CatalogQuery(sort: '-precio')), [2, 1, 3]);
    expect(ids(const CatalogQuery(sort: '-created_at')), [2, 1, 3]);
    expect(ids(const CatalogQuery(sort: 'created_at')), [3, 1, 2]);
    expect(ids(const CatalogQuery(sort: '-nombre')), [1, 3, 2]);
  });

  test('pagina igual que el backend', () {
    final first = snapshot.query(const CatalogQuery(pageSize: 2));
    expect(first['total'], 3);
    expect(first['pages'], 2);
    expect((first['items'] as List), hasLength(2));
    final second = snapshot.query(const CatalogQuery(pageSize: 2, page: 2));
    expect((second['items'] as List).single['id_producto'], 1);
    final beyond = snapshot.query(const CatalogQuery(pageSize: 2, page: 5));
    expect(beyond['items'], isEmpty);
    expect(ProductPage.fromJson(second).items.single.name, 'Polo básico');
  });

  test('combina filtros', () {
    expect(
      ids(const CatalogQuery(category: 'Poleras', size: 'M', color: 'Azul')),
      [3],
    );
  });

  test('sin resultados devuelve 0 páginas', () {
    final page = snapshot.query(const CatalogQuery(brand: 'Inexistente'));
    expect(page['total'], 0);
    expect(page['pages'], 0);
  });
}

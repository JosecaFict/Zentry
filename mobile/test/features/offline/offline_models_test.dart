import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('OfflineScope', () {
    test('aísla los datos por tenant, usuario y sucursal', () {
      const scope = OfflineScope(
        tenantSlug: 'casa-elena',
        userId: 23,
        branchId: 2,
      );

      expect(scope.key, 'casa-elena:23:2');
    });
  });

  group('OfflineCatalogItem', () {
    test('convierte el snapshot del backend', () {
      final item = OfflineCatalogItem.fromJson({
        'id_variante': 71,
        'sku': 'CASA-BL01-M-01',
        'producto': 'Blusa Alma',
        'talla': 'M',
        'color': 'Negro',
        'precio': '249.00',
        'stock_fisico': 12,
        'stock_reservado': 2,
        'stock_disponible': 10,
        'updated_at': '2026-10-30T12:00:00Z',
      });

      expect(item.variantId, 71);
      expect(item.price, 249);
      expect(item.availableStock, 10);
    });
  });

  group('OfflineOperation', () {
    test('cuenta las unidades de una venta local', () {
      final operation = OfflineOperation(
        id: 'operation-id',
        type: OfflineOperationType.sale,
        clientDate: DateTime.utc(2026, 10, 30),
        payload: const {
          'items': [
            {'id_variante': 1, 'cantidad': 2},
            {'id_variante': 2, 'cantidad': 3},
          ],
        },
        status: OfflineOperationStatus.pending,
        attempts: 0,
        createdAt: DateTime.utc(2026, 10, 30),
      );

      expect(operation.units, 5);
      expect(operation.label, 'Venta');
    });

    test('interpreta los estados del protocolo', () {
      expect(
        OfflineOperationStatus.fromApi('CONFLICTO'),
        OfflineOperationStatus.conflict,
      );
      expect(
        OfflineOperationStatus.fromApi('CONFIRMADA'),
        OfflineOperationStatus.confirmed,
      );
    });
  });
}

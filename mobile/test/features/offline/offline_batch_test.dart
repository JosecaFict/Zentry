import 'dart:convert';
import 'dart:io';

import 'package:capricho_store/core/auth/token_storage.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/core/tenant/tenant_storage.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:capricho_store/features/offline/presentation/offline_controller.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class _TestOffline extends OfflineController {
  @override
  OfflineState build() => const OfflineState(
    loading: false,
    online: false,
    branchId: 2,
    cart: {7: 1},
    catalog: [
      OfflineCatalogItem(
        variantId: 7,
        sku: 'POLO-M',
        product: 'Polo',
        size: 'M',
        color: 'Azul',
        price: 125.50,
        physicalStock: 3,
        reservedStock: 0,
        availableStock: 3,
      ),
    ],
  );
}

class _TestAuth extends AuthController {
  @override
  AuthState build() => const AuthState(
    initialized: true,
    user: AppUser(
      id: 1,
      names: 'Cuenta',
      surnames: 'Demo',
      email: 'demo@example.com',
      status: 'ACTIVO',
      roles: ['ADMIN'],
      permissions: [],
    ),
  );
}

class _TestTenant extends TenantController {
  @override
  TenantState build() => const TenantState(
    selected: TenantIdentity(name: 'Demo', slug: 'demo'),
  );
}

void main() {
  test(
    'reabre el contexto local solo para la empresa y sesión guardadas',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      String tokenAt(DateTime expiry) {
        final claims = jsonEncode({
          'exp': expiry.millisecondsSinceEpoch ~/ 1000,
        });
        return 'header.${base64Url.encode(utf8.encode(claims))}.signature';
      }

      final now = DateTime.now();
      final token = tokenAt(now.add(const Duration(hours: 1)));
      final session = TokenStorage();
      await session.write(token);
      await session.cacheProfile(token, {'id_usuario': 1});
      final tenant = TenantStorage();
      await tenant.write('demo');
      await tenant.cacheContext({'slug': 'demo', 'nombre': 'Demo'});

      expect(await TokenStorage().readOfflineProfile(), {'id_usuario': 1});
      expect((await TenantStorage().readContext('demo'))?['nombre'], 'Demo');
      expect(await TenantStorage().readContext('otra-empresa'), isNull);

      final expired = tokenAt(now.subtract(const Duration(hours: 1)));
      await session.write(expired);
      expect(await TokenStorage().readOfflineProfile(), isNull);
      await session.cacheProfile(expired, {'id_usuario': 1});
      expect(await TokenStorage().readOfflineProfile(), isNull);
      await session.clear();
      expect(await session.read(), isNull);
    },
  );

  test('veinte intentos simultáneos de guardar crean una sola venta', () async {
    final directory = await Directory.systemTemp.createTemp('zentry-offline-');
    final database = OfflineDatabase(directory);
    final container = ProviderContainer(
      overrides: [
        offlineDatabaseProvider.overrideWithValue(database),
        offlineControllerProvider.overrideWith(_TestOffline.new),
        authControllerProvider.overrideWith(_TestAuth.new),
        tenantControllerProvider.overrideWith(_TestTenant.new),
      ],
    );
    final subscription = container.listen(offlineControllerProvider, (_, _) {});
    addTearDown(() async {
      subscription.close();
      container.dispose();
      await database.close();
      await directory.delete(recursive: true);
    });
    final controller = container.read(offlineControllerProvider.notifier);

    final saved = await Future.wait(
      List.generate(20, (_) => controller.queue()),
    );
    const scope = OfflineScope(tenantSlug: 'demo', userId: 1, branchId: 2);
    expect(saved.where((success) => success), hasLength(1));
    final operations = await database.operations(scope);
    expect(operations, hasLength(1));
    expect(operations.single.payload['precios_cobrados'], {'7': 12550});
    expect(operations.single.payload['total_cobrado_centavos'], 12550);
  });

  test(
    'recupera el mismo lote y sus operaciones tras reabrir SQLite',
    () async {
      final directory = await Directory.systemTemp.createTemp(
        'zentry-offline-',
      );
      var database = OfflineDatabase(directory);
      addTearDown(() async {
        await database.close();
        await directory.delete(recursive: true);
      });
      const scope = OfflineScope(tenantSlug: 'demo', userId: 1, branchId: 2);
      Future<void> queue(OfflineOperationType type) => database.queueOperation(
        scope: scope,
        type: type,
        payload: {'id_sucursal': scope.branchId},
      );
      await queue(OfflineOperationType.sale);
      await queue(OfflineOperationType.reservation);
      final first = (await database.claimSyncBatch(scope))!;
      expect(first.operations, hasLength(2));

      await database.close();
      database = OfflineDatabase(directory);
      await queue(OfflineOperationType.sale);
      final recovered = (await database.claimSyncBatch(scope))!;
      expect((await database.preparedBranches('demo', 1)).single.id, 2);
      expect(await database.preparedBranches('other', 1), isEmpty);
      expect(await database.preparedBranches('demo', 2), isEmpty);
      expect(recovered.id, first.id);
      expect(
        recovered.operations.map((operation) => operation.id),
        unorderedEquals(first.operations.map((operation) => operation.id)),
      );
      await database.applyResponses([
        for (final operation in recovered.operations)
          {'id_operacion': operation.id, 'estado': 'APLICADA'},
      ]);
      final next = (await database.claimSyncBatch(scope))!;
      expect(next.id, isNot(first.id));
      expect(next.operations, hasLength(1));
    },
  );
}

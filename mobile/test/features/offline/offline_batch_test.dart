import 'dart:io';

import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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

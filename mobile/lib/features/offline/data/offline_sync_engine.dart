import 'dart:async';

import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/data/offline_sync_repository.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final offlineSyncEngineProvider = Provider<OfflineSyncEngine>(
  (ref) => OfflineSyncEngine(
    ref.watch(offlineDatabaseProvider),
    ref.watch(offlineSyncRepositoryProvider),
  ),
);

/// Envía la cola offline de una sucursal al backend.
///
/// Lo usan la pantalla Offline (botón "Sincronizar") y la sincronización
/// automática global. Las ejecuciones se encolan una detrás de otra para que
/// nunca se envíe el mismo lote dos veces en paralelo.
class OfflineSyncEngine {
  OfflineSyncEngine(this._database, this._repository);

  final OfflineDatabase _database;
  final OfflineSyncRepository _repository;
  Future<void> _tail = Future.value();

  /// Máximo de lotes por llamada, para no quedar en un bucle si algo falla.
  static const maxBatchesPerRun = 20;

  Future<OfflineSyncOutcome> syncScope(OfflineScope scope) =>
      _serialized(() => _sync(scope));

  Future<T> _serialized<T>(Future<T> Function() action) {
    final result = _tail.then((_) => action());
    _tail = result.then<void>((_) {}, onError: (_) {});
    return result;
  }

  Future<OfflineSyncOutcome> _sync(OfflineScope scope) async {
    var outcome = const OfflineSyncOutcome();
    for (var i = 0; i < maxBatchesPerRun; i++) {
      final batch = await _database.claimSyncBatch(scope);
      if (batch == null) break;
      final deviceId = await _database.ensureScope(scope);
      await _repository.submitBatch(
        batchId: batch.id,
        deviceId: deviceId,
        operations: batch.operations,
      );
      final confirmed = await _repository.confirmBatch(
        batchId: batch.id,
        deviceId: deviceId,
      );
      await _database.applyResponses(
        confirmed['operaciones'] as List<dynamic>? ?? const [],
      );
      await _database.markSuccessfulSync(scope);
      outcome =
          outcome +
          OfflineSyncOutcome(
            applied: _int(confirmed['total_aplicadas']),
            conflicts: _int(confirmed['total_conflictos']),
            rejected: _int(confirmed['total_rechazadas']),
            batches: 1,
          );
    }
    return outcome;
  }

  static int _int(Object? value) => value is num ? value.toInt() : 0;
}

import 'dart:async';

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/data/offline_sync_repository.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Ruta de la pantalla de conflictos (también la abre el push del backend).
const syncConflictsRoute = '/admin/conflictos';

/// El usuario puede revisar conflictos (encargado o administrador).
final canReviewSyncConflictsProvider = Provider<bool>((ref) {
  final user = ref.watch(authControllerProvider.select((state) => state.user));
  return user?.canReviewSyncConflicts ?? false;
});

/// Conflictos pendientes de la sucursal (o de todas, para administradores).
final syncConflictsProvider =
    AsyncNotifierProvider<SyncConflictsController, List<SyncConflict>>(
      SyncConflictsController.new,
    );

/// Cantidad de pendientes, para el badge del panel.
final pendingSyncConflictsProvider = Provider<int>(
  (ref) => ref.watch(syncConflictsProvider).value?.length ?? 0,
);

/// Historial de conflictos ya resueltos o anulados.
final resolvedSyncConflictsProvider =
    FutureProvider.autoDispose<List<SyncConflict>>((ref) async {
      ref.watch(syncConflictsProvider); // Se recarga al resolver uno.
      final conflicts = await ref
          .read(offlineSyncRepositoryProvider)
          .conflicts(estado: 'TODOS');
      return conflicts.where((conflict) => !conflict.pending).toList();
    });

class SyncConflictsController extends AsyncNotifier<List<SyncConflict>> {
  @override
  Future<List<SyncConflict>> build() async {
    final allowed = ref.watch(canReviewSyncConflictsProvider);
    ref.watch(tenantControllerProvider.select((state) => state.selected?.slug));
    // Al volver la conexión, se actualiza la lista.
    ref.listen(connectivityControllerProvider.select((state) => state.online), (
      previous,
      online,
    ) {
      if (previous == false && online) unawaited(refresh());
    });
    if (!allowed) return const [];
    return ref.read(offlineSyncRepositoryProvider).conflicts();
  }

  Future<void> refresh() async {
    if (!ref.read(canReviewSyncConflictsProvider)) return;
    state = await AsyncValue.guard(
      () => ref.read(offlineSyncRepositoryProvider).conflicts(),
    );
  }

  /// Devuelve null si salió bien, o el mensaje de error para mostrarlo.
  Future<String?> resolve(
    SyncConflict conflict, {
    required String action,
    String? note,
  }) async {
    try {
      await ref
          .read(offlineSyncRepositoryProvider)
          .resolveConflict(conflict.id, action: action, note: note);
    } on ApiException catch (error) {
      // Si otro supervisor lo resolvió primero, la lista se actualiza igual.
      if (error.statusCode == 409) unawaited(refresh());
      return error.message;
    } catch (error) {
      return error.toString();
    }
    final current = state.value ?? const <SyncConflict>[];
    state = AsyncData([
      for (final item in current)
        if (item.id != conflict.id) item,
    ]);
    unawaited(refresh());
    return null;
  }
}

import 'dart:async';
import 'dart:developer' as developer;

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/notifications/local_notifications.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/data/offline_sync_engine.dart';
import 'package:capricho_store/features/offline/data/offline_sync_repository.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Ruta que abre una alerta de venta rechazada.
const offlineAlertRoute = '/admin/offline';

class OfflineSyncState {
  const OfflineSyncState({
    this.failures = const [],
    this.syncing = false,
    this.revision = 0,
    this.lastOutcome,
    this.lastError,
  });

  /// Operaciones rechazadas o en conflicto que nadie revisó.
  final List<OfflineFailure> failures;
  final bool syncing;

  /// Aumenta cada vez que termina una sincronización (para recargar pantallas).
  final int revision;
  final OfflineSyncOutcome? lastOutcome;
  final String? lastError;

  OfflineSyncState copyWith({
    List<OfflineFailure>? failures,
    bool? syncing,
    int? revision,
    OfflineSyncOutcome? lastOutcome,
    String? lastError,
    bool clearError = false,
  }) => OfflineSyncState(
    failures: failures ?? this.failures,
    syncing: syncing ?? this.syncing,
    revision: revision ?? this.revision,
    lastOutcome: lastOutcome ?? this.lastOutcome,
    lastError: clearError ? null : (lastError ?? this.lastError),
  );
}

/// Sincronización automática de la cola offline y alertas de rechazos.
///
/// - Cada vez que [ConnectivityController] confirma conexión (al volver la
///   señal, al abrir la app y cada 30 s) envía las operaciones pendientes de
///   todas las sucursales del usuario.
/// - Si alguna operación queda rechazada o en conflicto, la agrega a
///   [OfflineSyncState.failures] (banner + badge) y muestra una notificación
///   local. La alerta sigue visible hasta que alguien la marque como revisada.
final offlineSyncControllerProvider =
    NotifierProvider<OfflineSyncController, OfflineSyncState>(
      OfflineSyncController.new,
    );

class OfflineSyncController extends Notifier<OfflineSyncState> {
  /// Operaciones de las que ya se avisó, para no notificar dos veces.
  final Set<String> _notified = {};
  Future<OfflineSyncOutcome?>? _running;

  @override
  OfflineSyncState build() {
    ref.listen(connectivityControllerProvider, (previous, next) {
      if (next.online && next.checkedAt != previous?.checkedAt) {
        unawaited(syncNow().then((_) => refreshServerStatus()));
      }
    });
    ref.listen(_identityProvider, (previous, next) {
      if (previous == next) return;
      _notified.clear();
      state = const OfflineSyncState();
      unawaited(refreshFailures(notify: false));
    });
    Future.microtask(() => refreshFailures(notify: false));
    return const OfflineSyncState();
  }

  ({String tenant, int userId})? get _identity => ref.read(_identityProvider);

  /// Envía ahora todo lo pendiente. Si ya hay una sincronización en curso,
  /// devuelve esa misma.
  Future<OfflineSyncOutcome?> syncNow() =>
      _running ??= _syncAll().whenComplete(() => _running = null);

  Future<OfflineSyncOutcome?> _syncAll() async {
    final identity = _identity;
    if (identity == null || !ref.read(connectivityControllerProvider).online) {
      return null;
    }
    final database = ref.read(offlineDatabaseProvider);
    final List<OfflineScope> scopes;
    try {
      scopes = await database.pendingScopes(identity.tenant, identity.userId);
    } catch (error) {
      developer.log('No se pudo leer la cola offline: $error', name: 'Sync');
      return null;
    }
    if (scopes.isEmpty || !ref.mounted) return null;
    state = state.copyWith(syncing: true, clearError: true);
    var outcome = const OfflineSyncOutcome();
    String? lastError;
    for (final scope in scopes) {
      try {
        outcome = outcome + await syncScope(scope, refresh: false);
      } catch (error) {
        // Se reintenta en el próximo chequeo de conexión (30 s).
        lastError = error.toString();
        developer.log('Sincronización automática falló: $error', name: 'Sync');
      }
      if (!ref.mounted) return outcome;
    }
    state = state.copyWith(
      syncing: false,
      revision: state.revision + 1,
      lastOutcome: outcome,
      lastError: lastError,
    );
    await refreshFailures();
    return outcome;
  }

  /// Sincroniza una sucursal (lo usa también el botón de la pantalla Offline).
  Future<OfflineSyncOutcome> syncScope(
    OfflineScope scope, {
    bool refresh = true,
  }) async {
    final outcome = await ref.read(offlineSyncEngineProvider).syncScope(scope);
    if (refresh && ref.mounted) {
      state = state.copyWith(
        revision: state.revision + 1,
        lastOutcome: outcome,
      );
      await refreshFailures();
    }
    return outcome;
  }

  /// Recarga las operaciones fallidas sin revisar. Con [notify], muestra una
  /// notificación local por cada fallo nuevo.
  Future<void> refreshFailures({bool notify = true}) async {
    final identity = _identity;
    if (identity == null) {
      if (state.failures.isNotEmpty) state = state.copyWith(failures: const []);
      return;
    }
    final List<OfflineFailure> failures;
    try {
      failures = await ref
          .read(offlineDatabaseProvider)
          .unacknowledgedFailures(identity.tenant, identity.userId);
    } catch (error) {
      developer.log('No se pudieron leer las alertas: $error', name: 'Sync');
      return;
    }
    if (!ref.mounted || _identity != identity) return;
    final fresh = failures
        .where((failure) => _notified.add(failure.operation.id))
        .toList();
    state = state.copyWith(failures: failures);
    if (notify && fresh.isNotEmpty) await _notify(fresh);
  }

  Future<void> _notify(List<OfflineFailure> fresh) async {
    final notifier = ref.read(localNotifierProvider);
    if (fresh.length > 3) {
      await notifier.show(
        id: offlineAlertRoute.hashCode,
        title: '⚠ ${fresh.length} operaciones no se registraron',
        body: 'Toca para revisar el motivo de cada una.',
        route: offlineAlertRoute,
      );
      return;
    }
    for (final failure in fresh) {
      await notifier.show(
        id: failure.operation.id.hashCode,
        title: '⚠ ${failure.title}',
        body: 'Motivo: ${failure.operation.failureReason}',
        route: offlineAlertRoute,
      );
    }
  }

  /// Pregunta al servidor si un supervisor ya resolvió (reaplicó o anuló)
  /// alguna operación fallida y actualiza el teléfono. Devuelve cuántas se
  /// resolvieron.
  Future<int> refreshServerStatus() async {
    final identity = _identity;
    if (identity == null || !ref.read(connectivityControllerProvider).online) {
      return 0;
    }
    final database = ref.read(offlineDatabaseProvider);
    try {
      final ids = await database.unresolvedFailedIds(
        identity.tenant,
        identity.userId,
      );
      if (ids.isEmpty) return 0;
      final statuses = await ref
          .read(offlineSyncRepositoryProvider)
          .operationStatus(ids);
      var resolved = 0;
      for (final status in statuses.where((s) => s.resolved)) {
        await database.applyServerResolution(
          status.id,
          action: status.action!,
          note: status.note,
        );
        resolved++;
      }
      if (resolved > 0 && ref.mounted && _identity == identity) {
        state = state.copyWith(revision: state.revision + 1);
        await refreshFailures(notify: false);
      }
      return resolved;
    } catch (error) {
      // Se reintenta en el próximo chequeo de conexión.
      developer.log('No se pudo consultar el estado: $error', name: 'Sync');
      return 0;
    }
  }

  /// Marca la alerta como revisada: deja de mostrarse, la operación no se borra.
  Future<void> acknowledge(String operationId) async {
    await ref.read(offlineDatabaseProvider).acknowledge(operationId);
    await refreshFailures(notify: false);
  }
}

/// Empresa y usuario con permiso para operar offline (null si no aplica).
final _identityProvider = Provider<({String tenant, int userId})?>((ref) {
  final tenant = ref.watch(
    tenantControllerProvider.select((state) => state.selected?.slug),
  );
  final user = ref.watch(authControllerProvider.select((state) => state.user));
  if (tenant == null || user == null || !user.canOpenOffline) return null;
  return (tenant: tenant, userId: user.id);
});

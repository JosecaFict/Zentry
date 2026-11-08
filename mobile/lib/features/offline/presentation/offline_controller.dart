import 'dart:async';

import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/admin/data/admin_repository.dart';
import 'package:capricho_store/features/admin/domain/admin_models.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/data/offline_sync_repository.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final offlineControllerProvider =
    NotifierProvider.autoDispose<OfflineController, OfflineState>(
      OfflineController.new,
    );

class OfflineState {
  const OfflineState({
    this.loading = true,
    this.busy = false,
    this.online = true,
    this.branches = const [],
    this.branchId,
    this.catalog = const [],
    this.customers = const [],
    this.operations = const [],
    this.cart = const {},
    this.mode = OfflineOperationType.sale,
    this.customerId,
    this.query = '',
    this.message,
    this.error,
  });

  final bool loading;
  final bool busy;
  final bool online;
  final List<BranchItem> branches;
  final int? branchId;
  final List<OfflineCatalogItem> catalog;
  final List<OfflineCustomer> customers;
  final List<OfflineOperation> operations;
  final Map<int, int> cart;
  final OfflineOperationType mode;
  final int? customerId;
  final String query;
  final String? message;
  final String? error;

  bool get prepared => catalog.isNotEmpty;
  int get cartUnits => cart.values.fold(0, (sum, quantity) => sum + quantity);
  int get pending => operations
      .where(
        (operation) =>
            operation.status == OfflineOperationStatus.pending ||
            operation.status == OfflineOperationStatus.sending,
      )
      .length;
  int get conflicts => operations
      .where((operation) => operation.status == OfflineOperationStatus.conflict)
      .length;
  int get rejected => operations
      .where((operation) => operation.status == OfflineOperationStatus.rejected)
      .length;

  OfflineState copyWith({
    bool? loading,
    bool? busy,
    bool? online,
    List<BranchItem>? branches,
    int? branchId,
    List<OfflineCatalogItem>? catalog,
    List<OfflineCustomer>? customers,
    List<OfflineOperation>? operations,
    Map<int, int>? cart,
    OfflineOperationType? mode,
    int? customerId,
    String? query,
    String? message,
    String? error,
    bool clearBranch = false,
    bool clearCustomer = false,
    bool clearMessage = false,
    bool clearError = false,
  }) => OfflineState(
    loading: loading ?? this.loading,
    busy: busy ?? this.busy,
    online: online ?? this.online,
    branches: branches ?? this.branches,
    branchId: clearBranch ? null : (branchId ?? this.branchId),
    catalog: catalog ?? this.catalog,
    customers: customers ?? this.customers,
    operations: operations ?? this.operations,
    cart: cart ?? this.cart,
    mode: mode ?? this.mode,
    customerId: clearCustomer ? null : (customerId ?? this.customerId),
    query: query ?? this.query,
    message: clearMessage ? null : (message ?? this.message),
    error: clearError ? null : (error ?? this.error),
  );
}

class OfflineController extends Notifier<OfflineState> {
  StreamSubscription<List<ConnectivityResult>>? _connectivitySubscription;
  Timer? _retryTimer;
  int _retryCount = 0;
  bool _foreground = true;

  @override
  OfflineState build() {
    final lifecycle = AppLifecycleListener(
      onHide: () {
        _foreground = false;
        _retryTimer?.cancel();
      },
      onResume: () {
        _foreground = true;
        _retryCount = 0;
        _scheduleAutoSync();
      },
    );
    ref.onDispose(() {
      lifecycle.dispose();
      _retryTimer?.cancel();
      _connectivitySubscription?.cancel();
    });
    Future.microtask(initialize);
    return const OfflineState();
  }

  Future<void> initialize() async {
    try {
      final connectivity = Connectivity();
      final current = await connectivity.checkConnectivity();
      if (!ref.mounted) return;
      state = state.copyWith(online: _isOnline(current));
      _connectivitySubscription = connectivity.onConnectivityChanged.listen((
        results,
      ) {
        final online = _isOnline(results);
        if (online == state.online) return;
        state = state.copyWith(online: online);
        _retryTimer?.cancel();
        _retryCount = 0;
        if (online) _scheduleAutoSync();
      });
      final user = ref.read(authControllerProvider).user;
      final branches = await ref.read(adminRepositoryProvider).branches();
      if (!ref.mounted) return;
      final branchId =
          user?.idSucursal ?? (branches.length == 1 ? branches.first.id : null);
      state = state.copyWith(
        loading: false,
        branches: branches,
        branchId: branchId,
      );
      if (branchId != null) await _loadLocal();
      if (ref.mounted) _scheduleAutoSync();
    } catch (error) {
      if (!ref.mounted) return;
      state = state.copyWith(
        loading: false,
        error: 'No se pudo iniciar el modo offline: $error',
      );
    }
  }

  bool _isOnline(List<ConnectivityResult> results) =>
      results.any((result) => result != ConnectivityResult.none);

  OfflineScope? get _scope {
    final tenant = ref.read(tenantControllerProvider).selected;
    final user = ref.read(authControllerProvider).user;
    final branchId = state.branchId;
    if (tenant == null || user == null || branchId == null) return null;
    return OfflineScope(
      tenantSlug: tenant.slug,
      userId: user.id,
      branchId: branchId,
    );
  }

  Future<void> selectBranch(int? branchId) async {
    if (state.busy) return;
    _retryTimer?.cancel();
    _retryCount = 0;
    state = state.copyWith(
      branchId: branchId,
      clearBranch: branchId == null,
      catalog: const [],
      customers: const [],
      operations: const [],
      cart: const {},
      clearCustomer: true,
      clearMessage: true,
      clearError: true,
    );
    if (branchId != null) await _loadLocal();
    if (ref.mounted) _scheduleAutoSync();
  }

  Future<void> prepare() async {
    if (state.busy) return;
    final scope = _scope;
    if (scope == null) {
      state = state.copyWith(error: 'Selecciona una sucursal primero.');
      return;
    }
    if (!state.online) {
      state = state.copyWith(
        error: state.prepared
            ? 'Sin conexión. Se mantiene el catálogo guardado.'
            : 'Conéctate una vez para descargar el catálogo.',
      );
      return;
    }
    state = state.copyWith(busy: true, clearError: true, clearMessage: true);
    try {
      final database = ref.read(offlineDatabaseProvider);
      final deviceId = await database.ensureScope(scope);
      if (!ref.mounted || _scope?.key != scope.key) return;
      final repository = ref.read(offlineSyncRepositoryProvider);
      await repository.registerDevice(
        deviceId: deviceId,
        branchId: scope.branchId,
      );
      final results = await Future.wait<Object>([
        repository.catalog(scope.branchId),
        repository.customers(),
      ]);
      final snapshot = results[0] as OfflineSnapshot;
      final customers = results[1] as List<OfflineCustomer>;
      await database.replaceSnapshot(
        scope: scope,
        version: snapshot.version,
        generatedAt: snapshot.generatedAt,
        catalog: snapshot.items,
        customers: customers,
      );
      if (!ref.mounted || _scope?.key != scope.key) return;
      await _loadLocal();
      if (!ref.mounted) return;
      state = state.copyWith(
        busy: false,
        message:
            '${snapshot.items.length} variantes listas para trabajar sin conexión.',
      );
    } catch (error) {
      if (!ref.mounted) return;
      state = state.copyWith(busy: false, error: error.toString());
    }
  }

  Future<void> _loadLocal() async {
    final scope = _scope;
    if (scope == null) return;
    final database = ref.read(offlineDatabaseProvider);
    await database.ensureScope(scope);
    final results = await Future.wait<Object>([
      database.catalog(scope),
      database.customers(scope),
      database.operations(scope),
    ]);
    if (!ref.mounted || _scope?.key != scope.key) return;
    state = state.copyWith(
      catalog: results[0] as List<OfflineCatalogItem>,
      customers: results[1] as List<OfflineCustomer>,
      operations: results[2] as List<OfflineOperation>,
    );
  }

  int availableFor(OfflineCatalogItem item) {
    final queued = state.operations
        .where(
          (operation) =>
              operation.status == OfflineOperationStatus.pending ||
              operation.status == OfflineOperationStatus.sending,
        )
        .expand(
          (operation) =>
              operation.payload['items'] as List<dynamic>? ?? const [],
        )
        .where((raw) => (raw as Map)['id_variante'] == item.variantId)
        .fold<int>(
          0,
          (sum, raw) => sum + ((raw as Map)['cantidad'] as int? ?? 0),
        );
    return (item.availableStock - queued).clamp(0, item.availableStock).toInt();
  }

  void setQuantity(OfflineCatalogItem item, int quantity) {
    final next = Map<int, int>.from(state.cart);
    final clean = quantity.clamp(0, availableFor(item)).toInt();
    if (clean == 0) {
      next.remove(item.variantId);
    } else {
      next[item.variantId] = clean;
    }
    state = state.copyWith(cart: next, clearMessage: true, clearError: true);
  }

  void setMode(OfflineOperationType mode) {
    state = state.copyWith(
      mode: mode,
      clearCustomer: mode == OfflineOperationType.sale,
    );
  }

  void setCustomer(int? customerId) {
    state = state.copyWith(
      customerId: customerId,
      clearCustomer: customerId == null,
    );
  }

  void setQuery(String query) => state = state.copyWith(query: query);

  Future<bool> queue() async {
    final scope = _scope;
    if (scope == null || state.busy || state.cart.isEmpty) return false;
    final wasOnline = state.online;
    final type = state.mode;
    if (type == OfflineOperationType.reservation && state.customerId == null) {
      state = state.copyWith(error: 'Selecciona el cliente de la reserva.');
      return false;
    }
    final items = state.cart.entries
        .map((entry) => {'id_variante': entry.key, 'cantidad': entry.value})
        .toList(growable: false);
    final payload = type == OfflineOperationType.sale
        ? <String, dynamic>{
            'id_sucursal': scope.branchId,
            'id_cliente': null,
            'id_reserva': null,
            'modalidad_entrega': 'ENTREGA_DIRECTA',
            'items': items,
            'registrar_efectivo': true,
            'metodo_pago': 'EFECTIVO',
            'referencia_pago': null,
          }
        : <String, dynamic>{
            'id_sucursal': scope.branchId,
            'id_cliente': state.customerId,
            'fecha_cita': null,
            'observacion': 'Reserva registrada desde Zentry móvil offline',
            'items': items,
          };
    state = state.copyWith(busy: true, clearError: true, clearMessage: true);
    try {
      await ref
          .read(offlineDatabaseProvider)
          .queueOperation(scope: scope, type: type, payload: payload);
      if (!ref.mounted || _scope?.key != scope.key) return false;
      state = state.copyWith(
        cart: const {},
        clearCustomer: true,
        message: type == OfflineOperationType.sale
            ? 'Venta en efectivo guardada en este dispositivo.'
            : 'Reserva guardada; el stock se validará al sincronizar.',
      );
      await _loadLocal();
      return true;
    } catch (error) {
      if (ref.mounted) state = state.copyWith(error: error.toString());
      return false;
    } finally {
      if (ref.mounted) {
        state = state.copyWith(busy: false);
        if (!wasOnline && state.online) _scheduleAutoSync();
      }
    }
  }

  void _scheduleAutoSync([Duration delay = Duration.zero]) {
    _retryTimer?.cancel();
    if (!_foreground || !state.online || state.pending == 0) return;
    _retryTimer = Timer(delay, () => unawaited(synchronize(automatic: true)));
  }

  Future<void> synchronize({bool automatic = false}) async {
    final scope = _scope;
    if (scope == null ||
        !state.online ||
        state.busy ||
        (automatic && !_foreground)) {
      return;
    }
    if (!automatic) {
      _retryTimer?.cancel();
      _retryCount = 0;
    }
    state = state.copyWith(busy: true, clearError: true, clearMessage: true);
    Duration? nextAttempt;
    String? success;
    try {
      final database = ref.read(offlineDatabaseProvider);
      final repository = ref.read(offlineSyncRepositoryProvider);
      final batch = await database.claimSyncBatch(scope);
      if (!ref.mounted || _scope?.key != scope.key) return;
      if (batch == null) {
        state = state.copyWith(message: 'No hay operaciones pendientes.');
        return;
      }
      final deviceId = await database.ensureScope(scope);
      if (!ref.mounted || _scope?.key != scope.key) return;
      await repository.submitBatch(
        batchId: batch.id,
        deviceId: deviceId,
        operations: batch.operations,
      );
      if (!ref.mounted || _scope?.key != scope.key) return;
      final confirmed = await repository.confirmBatch(
        batchId: batch.id,
        deviceId: deviceId,
      );
      await database.applyResponses(
        confirmed['operaciones'] as List<dynamic>? ?? const [],
      );
      await database.markSuccessfulSync(scope);
      if (!ref.mounted || _scope?.key != scope.key) return;
      await _loadLocal();
      if (!ref.mounted) return;
      _retryCount = 0;
      if (state.pending > 0) nextAttempt = Duration.zero;
      success =
          'Sincronización lista: ${confirmed['total_aplicadas'] ?? 0} aplicadas, '
          '${confirmed['total_conflictos'] ?? 0} conflictos y '
          '${confirmed['total_rechazadas'] ?? 0} rechazadas.';
    } catch (error) {
      if (!ref.mounted) return;
      state = state.copyWith(error: error.toString());
      if (error is ApiException && _retryCount < 5) {
        final status = error.statusCode;
        if (status == null || status == 408 || status == 429 || status >= 500) {
          nextAttempt = Duration(seconds: 2 << _retryCount++);
        }
      }
    } finally {
      if (ref.mounted) state = state.copyWith(busy: false);
    }
    if (success != null && ref.mounted && _scope?.key == scope.key) {
      if (state.online) await prepare();
      if (ref.mounted) state = state.copyWith(message: success);
    }
    if (ref.mounted && nextAttempt != null) {
      _scheduleAutoSync(nextAttempt);
    }
  }

  Future<void> retry(String id) async {
    await ref.read(offlineDatabaseProvider).retry(id);
    await _loadLocal();
  }

  Future<void> discard(String id) async {
    await ref.read(offlineDatabaseProvider).discard(id);
    await _loadLocal();
  }
}

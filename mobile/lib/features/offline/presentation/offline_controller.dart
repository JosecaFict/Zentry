import 'dart:async';

import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/admin/data/admin_repository.dart';
import 'package:capricho_store/features/admin/domain/admin_models.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/data/offline_sync_repository.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

final offlineControllerProvider =
    NotifierProvider<OfflineController, OfflineState>(OfflineController.new);

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
      .where((operation) => operation.status == OfflineOperationStatus.pending)
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

  @override
  OfflineState build() {
    ref.onDispose(() => _connectivitySubscription?.cancel());
    Future.microtask(initialize);
    return const OfflineState();
  }

  Future<void> initialize() async {
    try {
      final connectivity = Connectivity();
      final current = await connectivity.checkConnectivity();
      _connectivitySubscription = connectivity.onConnectivityChanged.listen(
        (results) => state = state.copyWith(online: _isOnline(results)),
      );
      final user = ref.read(authControllerProvider).user;
      final branches = await ref.read(adminRepositoryProvider).branches();
      final branchId =
          user?.idSucursal ?? (branches.length == 1 ? branches.first.id : null);
      state = state.copyWith(
        loading: false,
        online: _isOnline(current),
        branches: branches,
        branchId: branchId,
      );
      if (branchId != null) await _loadLocal();
    } catch (error) {
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
  }

  Future<void> prepare() async {
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
      await _loadLocal();
      state = state.copyWith(
        busy: false,
        message:
            '${snapshot.items.length} variantes listas para trabajar sin conexión.',
      );
    } catch (error) {
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

  Future<void> queue() async {
    final scope = _scope;
    if (scope == null || state.cart.isEmpty) return;
    if (state.mode == OfflineOperationType.reservation &&
        state.customerId == null) {
      state = state.copyWith(error: 'Selecciona el cliente de la reserva.');
      return;
    }
    final items = state.cart.entries
        .map((entry) => {'id_variante': entry.key, 'cantidad': entry.value})
        .toList(growable: false);
    final payload = state.mode == OfflineOperationType.sale
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
    await ref
        .read(offlineDatabaseProvider)
        .queueOperation(scope: scope, type: state.mode, payload: payload);
    state = state.copyWith(
      cart: const {},
      clearCustomer: true,
      message: state.mode == OfflineOperationType.sale
          ? 'Venta en efectivo guardada en este dispositivo.'
          : 'Reserva guardada; el stock se validará al sincronizar.',
      clearError: true,
    );
    await _loadLocal();
  }

  Future<void> synchronize() async {
    final scope = _scope;
    if (scope == null || !state.online || state.busy) return;
    final database = ref.read(offlineDatabaseProvider);
    final pending = await database.pendingOperations(scope);
    if (pending.isEmpty) {
      state = state.copyWith(message: 'No hay operaciones pendientes.');
      return;
    }
    final batchId = const Uuid().v4();
    state = state.copyWith(busy: true, clearError: true, clearMessage: true);
    await database.markSending(
      batchId,
      pending.map((item) => item.id).toList(),
    );
    try {
      final deviceId = await database.ensureScope(scope);
      final repository = ref.read(offlineSyncRepositoryProvider);
      final submitted = await repository.submitBatch(
        batchId: batchId,
        deviceId: deviceId,
        operations: pending,
      );
      await database.applyResponses(
        submitted['operaciones'] as List<dynamic>? ?? const [],
      );
      final confirmed = await repository.confirmBatch(
        batchId: batchId,
        deviceId: deviceId,
      );
      await database.applyResponses(
        confirmed['operaciones'] as List<dynamic>? ?? const [],
      );
      await database.markSuccessfulSync(scope);
      await _loadLocal();
      state = state.copyWith(
        busy: false,
        message:
            'Sincronización lista: ${confirmed['total_aplicadas'] ?? 0} aplicadas, '
            '${confirmed['total_conflictos'] ?? 0} conflictos y '
            '${confirmed['total_rechazadas'] ?? 0} rechazadas.',
      );
      await prepare();
    } catch (error) {
      await database.releaseBatch(batchId, error.toString());
      await _loadLocal();
      state = state.copyWith(busy: false, error: error.toString());
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

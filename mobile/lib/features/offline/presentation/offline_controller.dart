import 'dart:async';

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/admin/data/admin_repository.dart';
import 'package:capricho_store/features/admin/domain/admin_models.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:capricho_store/features/offline/data/offline_sync_repository.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:capricho_store/features/offline/presentation/offline_sync_controller.dart';
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
  @override
  OfflineState build() {
    // La conexión y la sincronización automática son globales
    // (ConnectivityController y OfflineSyncController); esta pantalla solo
    // refleja su estado y recarga la cola cuando termina una sincronización.
    ref.listen(connectivityControllerProvider.select((s) => s.online), (
      _,
      online,
    ) {
      state = state.copyWith(online: online);
    });
    ref.listen(offlineSyncControllerProvider.select((s) => s.revision), (_, _) {
      unawaited(_loadLocal());
    });
    Future.microtask(initialize);
    return OfflineState(
      online: ref.read(connectivityControllerProvider).online,
    );
  }

  Future<void> initialize() async {
    try {
      final user = ref.read(authControllerProvider).user;
      final tenant = ref.read(tenantControllerProvider).selected;
      if (user == null || tenant == null) {
        state = state.copyWith(loading: false);
        return;
      }
      final saved = await ref
          .read(offlineDatabaseProvider)
          .preparedBranches(tenant.slug, user.id);
      if (!ref.mounted) return;
      var branches = [
        for (final branch in saved)
          if (user.idSucursal == null || user.idSucursal == branch.id)
            BranchItem(
              id: branch.id,
              name: branch.name,
              address: branch.address,
            ),
      ];
      if (state.online) {
        try {
          branches = await ref.read(adminRepositoryProvider).branches();
        } on ApiException catch (error) {
          final status = error.statusCode;
          if (status != null && status < 500) rethrow;
        }
      }
      if (!ref.mounted) return;
      final branchId =
          user.idSucursal ??
          saved
              .where((scope) => branches.any((branch) => branch.id == scope.id))
              .firstOrNull
              ?.id ??
          (branches.length == 1 ? branches.first.id : null);
      state = state.copyWith(
        loading: false,
        branches: branches,
        branchId: branchId,
      );
      if (branchId != null) await _loadLocal();
    } catch (error) {
      if (!ref.mounted) return;
      state = state.copyWith(
        loading: false,
        error: 'No se pudo iniciar el modo offline: $error',
      );
    }
  }

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
    final branch = state.branches
        .where((item) => item.id == scope.branchId)
        .firstOrNull;
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
      if (branch != null) {
        await database.saveBranch(scope, branch.name, branch.address);
      }
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
    final type = state.mode;
    if (type == OfflineOperationType.reservation && state.customerId == null) {
      state = state.copyWith(error: 'Selecciona el cliente de la reserva.');
      return false;
    }
    final items = state.cart.entries
        .map((entry) => {'id_variante': entry.key, 'cantidad': entry.value})
        .toList(growable: false);
    final prices = <String, int>{};
    var total = 0;
    if (type == OfflineOperationType.sale) {
      for (final item in state.catalog) {
        final quantity = state.cart[item.variantId];
        if (quantity == null || !item.price.isFinite) continue;
        final price = (item.price * 100).round();
        if (price <= 0) continue;
        prices[item.variantId.toString()] = price;
        total += price * quantity;
      }
      if (prices.length != state.cart.length) {
        state = state.copyWith(
          error: 'Falta un precio válido en el catálogo local.',
        );
        return false;
      }
    }
    final payload = type == OfflineOperationType.sale
        ? <String, dynamic>{
            'id_sucursal': scope.branchId,
            'id_cliente': state.customerId,
            'id_reserva': null,
            'modalidad_entrega': 'ENTREGA_DIRECTA',
            'items': items,
            'registrar_efectivo': true,
            'metodo_pago': 'EFECTIVO',
            'referencia_pago': null,
            'precios_cobrados': prices,
            'total_cobrado_centavos': total,
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
        // Con conexión, se envía enseguida sin esperar al próximo chequeo.
        if (state.online) {
          unawaited(ref.read(offlineSyncControllerProvider.notifier).syncNow());
        }
      }
    }
  }

  /// Sincronización manual (botón "Sincronizar" de esta pantalla).
  Future<void> synchronize() async {
    final scope = _scope;
    if (scope == null || !state.online || state.busy) return;
    state = state.copyWith(busy: true, clearError: true, clearMessage: true);
    OfflineSyncOutcome? outcome;
    try {
      outcome = await ref
          .read(offlineSyncControllerProvider.notifier)
          .syncScope(scope);
      if (!ref.mounted || _scope?.key != scope.key) return;
      await _loadLocal();
    } catch (error) {
      if (!ref.mounted) return;
      state = state.copyWith(error: error.toString());
    } finally {
      if (ref.mounted) state = state.copyWith(busy: false);
    }
    if (outcome == null || !ref.mounted || _scope?.key != scope.key) return;
    if (outcome.batches == 0) {
      state = state.copyWith(message: 'No hay operaciones pendientes.');
      return;
    }
    // Tras sincronizar, se refresca el stock local con el del servidor.
    if (state.online) await prepare();
    if (!ref.mounted) return;
    state = outcome.hasFailures
        ? state.copyWith(
            clearMessage: true,
            error:
                '${outcome.summary} Revisa abajo el motivo de cada operación '
                'no registrada.',
          )
        : state.copyWith(message: outcome.summary);
  }

  /// Venta rechazada por datos inválidos: vuelve a cargar sus prendas en el
  /// carrito para registrarla corregida como una operación nueva. La original
  /// queda revisada (en el servidor no se puede reenviar con el mismo id).
  Future<bool> reloadIntoCart(String id) async {
    final operation = state.operations.where((op) => op.id == id).firstOrNull;
    if (operation == null || state.busy) return false;
    final next = <int, int>{};
    var missing = 0;
    for (final raw
        in operation.payload['items'] as List<dynamic>? ?? const []) {
      final item = raw as Map;
      final variantId = item['id_variante'] as int?;
      final quantity = item['cantidad'] as int? ?? 0;
      final local = state.catalog
          .where((entry) => entry.variantId == variantId)
          .firstOrNull;
      final available = local == null ? 0 : availableFor(local);
      if (variantId == null || available <= 0) {
        missing++;
        continue;
      }
      next[variantId] = quantity.clamp(1, available).toInt();
    }
    if (next.isEmpty) {
      state = state.copyWith(
        error:
            'Ninguna prenda de esa operación está disponible en el catálogo '
            'local de esta sucursal.',
      );
      return false;
    }
    await ref.read(offlineSyncControllerProvider.notifier).acknowledge(id);
    if (!ref.mounted) return false;
    state = state.copyWith(
      cart: next,
      mode: operation.type,
      customerId: operation.payload['id_cliente'] as int?,
      clearCustomer: operation.payload['id_cliente'] == null,
      clearError: true,
      message: missing == 0
          ? 'Prendas cargadas: revisa los datos y vuelve a guardar.'
          : 'Prendas cargadas ($missing ya no están disponibles): revisa y '
                'vuelve a guardar.',
    );
    await _loadLocal();
    return true;
  }

  /// Marca la operación fallida como revisada (deja de alertar, no se borra).
  Future<void> acknowledge(String id) async {
    await ref.read(offlineSyncControllerProvider.notifier).acknowledge(id);
    await _loadLocal();
  }

  Future<void> discard(String id) async {
    await ref.read(offlineDatabaseProvider).discard(id);
    await _loadLocal();
    await ref.read(offlineSyncControllerProvider.notifier).refreshFailures();
  }
}

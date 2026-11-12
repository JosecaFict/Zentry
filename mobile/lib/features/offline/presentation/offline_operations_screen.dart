import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:capricho_store/features/offline/presentation/offline_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

class OfflineOperationsScreen extends ConsumerWidget {
  const OfflineOperationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(offlineControllerProvider);
    final controller = ref.read(offlineControllerProvider.notifier);
    final user = ref.watch(authControllerProvider).user;

    if (state.loading) {
      return const Center(child: CircularProgressIndicator());
    }

    final query = state.query.trim().toLowerCase();
    final catalog = state.catalog
        .where((item) {
          if (query.isEmpty) return true;
          return '${item.product} ${item.sku} ${item.size} ${item.color}'
              .toLowerCase()
              .contains(query);
        })
        .toList(growable: false);

    return SafeArea(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= 820;
          return CustomScrollView(
            slivers: [
              SliverPadding(
                padding: EdgeInsets.fromLTRB(
                  wide ? 32 : 16,
                  24,
                  wide ? 32 : 16,
                  16,
                ),
                sliver: SliverList.list(
                  children: [
                    _Header(online: state.online),
                    if (state.lastSale case final sale?) ...[
                      const SizedBox(height: 16),
                      _SaleReceipt(
                        sale: sale,
                        onClose: controller.dismissLastSale,
                      ),
                    ],
                    const SizedBox(height: 24),
                    _BranchPanel(
                      state: state,
                      locked: user?.isBranchLocked ?? false,
                      onBranch: controller.selectBranch,
                      onPrepare: controller.prepare,
                    ),
                    if (state.message != null) ...[
                      const SizedBox(height: 12),
                      _Notice(message: state.message!, success: true),
                    ],
                    if (state.error != null) ...[
                      const SizedBox(height: 12),
                      _Notice(message: state.error!, success: false),
                    ],
                    const SizedBox(height: 24),
                    _SyncPanel(state: state, onSync: controller.synchronize),
                    const SizedBox(height: 28),
                    _SectionHeader(
                      eyebrow: '03 · CATÁLOGO LOCAL',
                      title: 'Selecciona las prendas',
                      trailing: SizedBox(
                        width: wide ? 340 : 220,
                        child: TextField(
                          onChanged: controller.setQuery,
                          decoration: const InputDecoration(
                            hintText: 'Producto, SKU, talla o color',
                            prefixIcon: Icon(Icons.search_rounded),
                            isDense: true,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (!state.prepared)
                      _EmptyCatalog(state: state)
                    else if (catalog.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 32),
                        child: Center(child: Text('No hay coincidencias.')),
                      )
                    else
                      _CatalogGrid(
                        items: catalog,
                        state: state,
                        controller: controller,
                        wide: wide,
                      ),
                    const SizedBox(height: 28),
                    _QueuePanel(
                      state: state,
                      onReload: controller.reloadIntoCart,
                      onAcknowledge: controller.acknowledge,
                      onDiscard: (id) async {
                        if (await _confirmDiscard(context)) {
                          await controller.discard(id);
                        }
                      },
                    ),
                    const SizedBox(height: 100),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

Future<bool> _confirmDiscard(BuildContext context) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('¿Quitar de este dispositivo?'),
        content: const Text(
          'Solo desaparece de este teléfono. Si ya se envió al servidor, tu '
          'encargado la sigue viendo para resolverla. Si nunca se envió, se '
          'pierde por completo.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Quitar'),
          ),
        ],
      ),
    ) ??
    false;

class _Header extends StatelessWidget {
  const _Header({required this.online});
  final bool online;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'VENTA PRESENCIAL · CON O SIN INTERNET',
              style: Theme.of(context).textTheme.labelSmall,
            ),
            const SizedBox(height: 6),
            Text('Vender', style: Theme.of(context).textTheme.displaySmall),
            const SizedBox(height: 6),
            Text(
              online
                  ? 'Con internet, cada venta se registra al momento.'
                  : 'Sin internet: las ventas se guardan en el teléfono y se '
                        'envían solas al volver la conexión.',
            ),
          ],
        ),
      ),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: online ? const Color(0xFFE8F7EF) : const Color(0xFFFFF1E7),
          borderRadius: BorderRadius.circular(99),
        ),
        child: Row(
          children: [
            Icon(
              online ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
              size: 18,
              color: online ? AppColors.success : AppColors.warning,
            ),
            const SizedBox(width: 7),
            Text(online ? 'En línea' : 'Sin conexión'),
          ],
        ),
      ),
    ],
  );
}

class _BranchPanel extends StatelessWidget {
  const _BranchPanel({
    required this.state,
    required this.locked,
    required this.onBranch,
    required this.onPrepare,
  });

  final OfflineState state;
  final bool locked;
  final ValueChanged<int?> onBranch;
  final VoidCallback onPrepare;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= 650;
          final selector = DropdownButtonFormField<int>(
            initialValue: state.branchId,
            decoration: const InputDecoration(
              labelText: 'Sucursal del dispositivo',
            ),
            items: state.branches
                .map(
                  (branch) => DropdownMenuItem(
                    value: branch.id,
                    child: Text(branch.name, overflow: TextOverflow.ellipsis),
                  ),
                )
                .toList(),
            onChanged: locked || state.busy ? null : onBranch,
          );
          final downloading = state.busy || state.refreshing;
          // El catálogo se descarga solo con internet; el botón solo fuerza
          // una actualización.
          final action = FilledButton.tonalIcon(
            onPressed: state.branchId == null || downloading ? null : onPrepare,
            icon: downloading
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
            label: Text(
              downloading ? 'Actualizando catálogo…' : 'Actualizar catálogo',
            ),
          );
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '01 · CONTEXTO DE TRABAJO',
                style: Theme.of(context).textTheme.labelSmall,
              ),
              const SizedBox(height: 8),
              Text(
                state.prepared
                    ? 'Catálogo de la sucursal guardado en este teléfono: '
                          'puedes vender con o sin conexión. Con internet se '
                          'actualiza solo.'
                    : 'Con internet, el catálogo de la sucursal se descarga '
                          'solo al elegirla.',
              ),
              const SizedBox(height: 16),
              if (wide)
                Row(
                  children: [
                    Expanded(child: selector),
                    const SizedBox(width: 12),
                    action,
                  ],
                )
              else ...[
                selector,
                const SizedBox(height: 12),
                SizedBox(width: double.infinity, child: action),
              ],
            ],
          );
        },
      ),
    ),
  );
}

class _SyncPanel extends StatelessWidget {
  const _SyncPanel({required this.state, required this.onSync});
  final OfflineState state;
  final VoidCallback onSync;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: Wrap(
          spacing: 16,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              '02 · SINCRONIZACIÓN',
              style: Theme.of(context).textTheme.labelSmall,
            ),
            _Count(label: 'pendientes', value: state.pending),
            _Count(label: 'conflictos', value: state.conflicts),
            _Count(label: 'rechazadas', value: state.rejected),
          ],
        ),
      ),
      OutlinedButton.icon(
        onPressed: !state.online || state.busy || state.branchId == null
            ? null
            : onSync,
        icon: const Icon(Icons.sync_rounded),
        label: const Text('Sincronizar'),
      ),
    ],
  );
}

class _Count extends StatelessWidget {
  const _Count({required this.label, required this.value});
  final String label;
  final int value;
  @override
  Widget build(BuildContext context) => Text.rich(
    TextSpan(
      children: [
        TextSpan(
          text: '$value ',
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        TextSpan(text: label),
      ],
    ),
  );
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.eyebrow,
    required this.title,
    this.trailing,
  });
  final String eyebrow;
  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Wrap(
    alignment: WrapAlignment.spaceBetween,
    crossAxisAlignment: WrapCrossAlignment.end,
    spacing: 16,
    runSpacing: 12,
    children: [
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(eyebrow, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 6),
          Text(title, style: Theme.of(context).textTheme.headlineMedium),
        ],
      ),
      if (trailing != null) trailing!,
    ],
  );
}

class _CatalogGrid extends StatelessWidget {
  const _CatalogGrid({
    required this.items,
    required this.state,
    required this.controller,
    required this.wide,
  });

  final List<OfflineCatalogItem> items;
  final OfflineState state;
  final OfflineController controller;
  final bool wide;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: items.length,
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: wide
              ? 3
              : (MediaQuery.sizeOf(context).width >= 560 ? 2 : 1),
          mainAxisExtent: 142,
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
        ),
        itemBuilder: (context, index) {
          final item = items[index];
          final available = controller.availableFor(item);
          final quantity = state.cart[item.variantId] ?? 0;
          return Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          item.product,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                      ),
                      Text('Bs ${item.price.toStringAsFixed(2)}'),
                    ],
                  ),
                  const SizedBox(height: 5),
                  Text(
                    '${item.size} · ${item.color}  •  ${item.sku}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const Spacer(),
                  Row(
                    children: [
                      Expanded(child: Text('$available disponibles')),
                      IconButton.filledTonal(
                        onPressed: quantity > 0
                            ? () => controller.setQuantity(item, quantity - 1)
                            : null,
                        icon: const Icon(Icons.remove_rounded),
                      ),
                      SizedBox(
                        width: 34,
                        child: Text('$quantity', textAlign: TextAlign.center),
                      ),
                      IconButton.filled(
                        onPressed: quantity < available
                            ? () => controller.setQuantity(item, quantity + 1)
                            : null,
                        icon: const Icon(Icons.add_rounded),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
      if (state.cartUnits > 0) ...[
        const SizedBox(height: 14),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: () => _showCart(context),
            icon: const Icon(Icons.point_of_sale_outlined),
            label: Text('Continuar con ${state.cartUnits} unidades'),
          ),
        ),
      ],
    ],
  );

  Future<void> _showCart(BuildContext context) => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (context) => Consumer(
      builder: (context, ref, _) {
        final current = ref.watch(offlineControllerProvider);
        final ctrl = ref.read(offlineControllerProvider.notifier);
        final user = ref.watch(authControllerProvider).user;
        // Solo se ofrece lo que el backend aceptará al sincronizar.
        final canSell = user?.canSellOffline ?? false;
        final canReserve = user?.canReserveOffline ?? false;
        final selectedItems = current.catalog
            .where((item) => current.cart.containsKey(item.variantId))
            .toList(growable: false);
        final total = selectedItems.fold<double>(
          0,
          (sum, item) => sum + item.price * (current.cart[item.variantId] ?? 0),
        );
        return SafeArea(
          child: Padding(
            padding: EdgeInsets.fromLTRB(
              20,
              0,
              20,
              20 + MediaQuery.viewInsetsOf(context).bottom,
            ),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Registrar operación',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Las ventas offline se registran únicamente en efectivo.',
                  ),
                  if (canSell && canReserve) ...[
                    const SizedBox(height: 16),
                    SegmentedButton<OfflineOperationType>(
                      segments: const [
                        ButtonSegment(
                          value: OfflineOperationType.sale,
                          label: Text('Venta'),
                        ),
                        ButtonSegment(
                          value: OfflineOperationType.reservation,
                          label: Text('Reserva'),
                        ),
                      ],
                      selected: {current.mode},
                      onSelectionChanged: (value) => ctrl.setMode(value.first),
                    ),
                  ],
                  const SizedBox(height: 16),
                  DropdownButtonFormField<int>(
                    // Se reconstruye al crear un cliente para mostrarlo elegido.
                    key: ValueKey(
                      '${current.mode}-${current.customerId}-'
                      '${current.customers.length}',
                    ),
                    initialValue:
                        current.customerId ??
                        (current.mode == OfflineOperationType.sale ? 0 : null),
                    decoration: const InputDecoration(labelText: 'Cliente'),
                    items: [
                      if (current.mode == OfflineOperationType.sale)
                        const DropdownMenuItem(
                          value: 0,
                          child: Text('Consumidor final'),
                        ),
                      for (final customer in current.customers)
                        DropdownMenuItem(
                          value: customer.id,
                          child: Text(
                            customer.name,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                    onChanged: (id) => ctrl.setCustomer(id == 0 ? null : id),
                  ),
                  if (current.online)
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        onPressed: current.busy
                            ? null
                            : () => showDialog<void>(
                                context: context,
                                builder: (_) => const _NewCustomerDialog(),
                              ),
                        icon: const Icon(Icons.person_add_alt_1_outlined),
                        label: const Text('Nuevo cliente'),
                      ),
                    ),
                  const SizedBox(height: 16),
                  ...selectedItems.map(
                    (item) => ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(item.product),
                      subtitle: Text('${item.size} · ${item.color}'),
                      trailing: Text(
                        '${current.cart[item.variantId]} × Bs ${item.price.toStringAsFixed(2)}',
                      ),
                    ),
                  ),
                  const Divider(),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Total',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                      Text(
                        'Bs ${total.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                  if (current.error != null) ...[
                    const SizedBox(height: 12),
                    // Ej.: sin stock al registrar en línea; el carrito queda
                    // igual para corregirlo.
                    _Notice(message: current.error!, success: false),
                  ],
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: current.busy
                          ? null
                          : () async {
                              final saved = await ctrl.queue();
                              if (saved && context.mounted) {
                                Navigator.pop(context);
                              }
                            },
                      child: Text(
                        current.busy
                            ? 'Registrando…'
                            : current.mode == OfflineOperationType.reservation
                            ? 'Guardar reserva'
                            : current.online
                            ? 'Registrar venta en efectivo'
                            : 'Guardar venta en efectivo',
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    ),
  );
}

class _QueuePanel extends StatelessWidget {
  const _QueuePanel({
    required this.state,
    required this.onReload,
    required this.onAcknowledge,
    required this.onDiscard,
  });
  final OfflineState state;
  final ValueChanged<String> onReload;
  final ValueChanged<String> onAcknowledge;
  final ValueChanged<String> onDiscard;

  /// Las fallidas sin revisar van siempre primero y nunca quedan fuera del
  /// límite de 20 elementos.
  List<OfflineOperation> get _visible {
    final unreviewed = state.operations
        .where((op) => op.failed && op.acknowledgedAt == null)
        .toList();
    final rest = state.operations
        .where((op) => !(op.failed && op.acknowledgedAt == null))
        .take(20);
    return [...unreviewed, ...rest];
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const _SectionHeader(
        eyebrow: '04 · RESULTADOS',
        title: 'Cola del dispositivo',
      ),
      const SizedBox(height: 12),
      if (state.operations.isEmpty)
        const Card(
          child: Padding(
            padding: EdgeInsets.all(20),
            child: Text('Todavía no hay operaciones locales.'),
          ),
        )
      else
        ..._visible.map((operation) {
          final failed = operation.failed;
          final resolution = _resolution(operation);
          final unreviewed =
              failed && operation.acknowledgedAt == null && resolution == null;
          final canReload =
              failed &&
              resolution == null &&
              operation.errorCode == 'DATOS_INVALIDOS';
          final detail = resolution != null
              ? '\n$resolution'
              : failed
              ? '\n${operation.failureReason}'
                    '${operation.errorMessage == null ? '' : '\nDetalle: ${operation.errorMessage}'}'
                    '\n${canReload ? 'Puedes volver a cargarla corregida.' : 'En revisión por tu encargado.'}'
                    '${operation.acknowledgedAt == null ? '' : ' · Revisada'}'
              : (operation.errorMessage == null
                    ? ''
                    : '\n${operation.errorMessage}');
          return Card(
            shape: unreviewed
                ? RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: const BorderSide(color: AppColors.danger),
                  )
                : null,
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: failed
                    ? const Color(0xFFFFE7E3)
                    : AppColors.cobaltLight,
                child: Icon(
                  operation.type == OfflineOperationType.sale
                      ? Icons.point_of_sale_outlined
                      : Icons.event_available_outlined,
                  color: failed ? AppColors.danger : AppColors.cobalt,
                ),
              ),
              title: Text('${operation.label} · ${operation.units} unidades'),
              subtitle: Text(
                '${_status(operation.status)} · '
                '${DateFormat('dd/MM HH:mm').format(operation.createdAt.toLocal())}'
                '$detail',
              ),
              isThreeLine: detail.isNotEmpty,
              trailing: failed || resolution != null
                  ? PopupMenuButton<String>(
                      onSelected: (value) => switch (value) {
                        'reload' => onReload(operation.id),
                        'ack' => onAcknowledge(operation.id),
                        _ => onDiscard(operation.id),
                      },
                      itemBuilder: (_) => [
                        if (canReload)
                          const PopupMenuItem(
                            value: 'reload',
                            child: Text('Cargar de nuevo en el carrito'),
                          ),
                        if (unreviewed)
                          const PopupMenuItem(
                            value: 'ack',
                            child: Text('Marcar como revisada'),
                          ),
                        const PopupMenuItem(
                          value: 'discard',
                          child: Text('Quitar de este dispositivo'),
                        ),
                      ],
                    )
                  : null,
            ),
          );
        }),
    ],
  );

  static String? _resolution(
    OfflineOperation operation,
  ) => switch (operation.resolution) {
    'REAPLICADA' => 'Registrada por tu encargado',
    'ANULADA' =>
      'Anulada por tu encargado'
          '${operation.resolutionNote == null ? '' : ': ${operation.resolutionNote}'}',
    _ => null,
  };

  static String _status(OfflineOperationStatus status) => switch (status) {
    OfflineOperationStatus.pending => 'Pendiente',
    OfflineOperationStatus.sending => 'Enviando',
    OfflineOperationStatus.applied => 'Aplicada',
    OfflineOperationStatus.conflict => 'Conflicto',
    OfflineOperationStatus.rejected => 'Rechazada',
    OfflineOperationStatus.confirmed => 'Confirmada',
  };
}

class _Notice extends StatelessWidget {
  const _Notice({required this.message, required this.success});
  final String message;
  final bool success;
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: success ? const Color(0xFFE8F7EF) : const Color(0xFFFFE7E3),
      borderRadius: BorderRadius.circular(10),
    ),
    child: Text(message),
  );
}

class _EmptyCatalog extends StatelessWidget {
  const _EmptyCatalog({required this.state});
  final OfflineState state;

  String get _text {
    if (state.branchId == null) {
      return 'Selecciona la sucursal donde vas a vender.';
    }
    if (state.busy) return 'Descargando el catálogo de la sucursal…';
    if (!state.online) {
      return 'Sin conexión y sin catálogo guardado de esta sucursal. '
          'Conéctate una vez a internet y se descargará solo.';
    }
    return 'No se pudo descargar el catálogo. Pulsa “Actualizar catálogo”.';
  }

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Row(
        children: [
          if (state.busy)
            const SizedBox.square(
              dimension: 28,
              child: CircularProgressIndicator(strokeWidth: 3),
            )
          else
            const Icon(Icons.download_for_offline_outlined, size: 32),
          const SizedBox(width: 14),
          Expanded(child: Text(_text)),
        ],
      ),
    ),
  );
}

/// Comprobante de la venta registrada en línea: número, prendas y total.
class _SaleReceipt extends StatelessWidget {
  const _SaleReceipt({required this.sale, required this.onClose});

  final RegisteredSale sale;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final money = NumberFormat.currency(locale: 'es_BO', symbol: 'Bs ');
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppColors.success),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.check_circle_rounded, color: AppColors.success),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Venta #${sale.id} registrada',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                IconButton(
                  tooltip: 'Cerrar',
                  onPressed: onClose,
                  icon: const Icon(Icons.close_rounded),
                ),
              ],
            ),
            Text(
              '${DateFormat('dd/MM/yyyy HH:mm').format(sale.date)} · '
              '${sale.branch}'
              '${sale.seller == null ? '' : ' · ${sale.seller}'}',
            ),
            Text('Cliente: ${sale.customer ?? 'Consumidor final'}'),
            const Divider(),
            for (final line in sale.lines)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    Expanded(
                      child: Text('${line.quantity} × ${line.description}'),
                    ),
                    Text(money.format(line.subtotal)),
                  ],
                ),
              ),
            const Divider(),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Total cobrado en efectivo',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Text(
                  money.format(sale.total),
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Formulario de alta rápida de cliente desde la caja (necesita internet).
class _NewCustomerDialog extends ConsumerStatefulWidget {
  const _NewCustomerDialog();

  @override
  ConsumerState<_NewCustomerDialog> createState() => _NewCustomerDialogState();
}

class _NewCustomerDialogState extends ConsumerState<_NewCustomerDialog> {
  final _names = TextEditingController();
  final _surnames = TextEditingController();
  final _ci = TextEditingController();
  final _phone = TextEditingController();
  final _email = TextEditingController();

  @override
  void dispose() {
    for (final controller in [_names, _surnames, _ci, _phone, _email]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    final saved = await ref
        .read(offlineControllerProvider.notifier)
        .createCustomer(
          names: _names.text,
          surnames: _surnames.text,
          ci: _ci.text,
          phone: _phone.text,
          email: _email.text,
        );
    if (saved && mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(offlineControllerProvider);
    return AlertDialog(
      title: const Text('Nuevo cliente'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _names,
              autofocus: true,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Nombres *'),
              onChanged: (_) => setState(() {}),
            ),
            TextField(
              controller: _surnames,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Apellidos'),
            ),
            TextField(
              controller: _ci,
              decoration: const InputDecoration(labelText: 'CI'),
            ),
            TextField(
              controller: _phone,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Teléfono'),
            ),
            TextField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: 'Correo'),
            ),
            if (state.error != null) ...[
              const SizedBox(height: 12),
              Text(
                state.error!,
                style: const TextStyle(color: AppColors.danger),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: state.busy || _names.text.trim().isEmpty ? null : _save,
          child: Text(state.busy ? 'Guardando…' : 'Registrar cliente'),
        ),
      ],
    );
  }
}

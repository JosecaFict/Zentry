import 'package:capricho_store/core/theme/app_theme.dart';
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
                      const _EmptyCatalog()
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
                      onRetry: controller.retry,
                      onDiscard: controller.discard,
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
              'INVENTARIO · MODO LOCAL',
              style: Theme.of(context).textTheme.labelSmall,
            ),
            const SizedBox(height: 6),
            Text(
              'Operación offline',
              style: Theme.of(context).textTheme.displaySmall,
            ),
            const SizedBox(height: 6),
            const Text(
              'Vende o reserva aunque el dispositivo pierda conexión.',
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
          final action = FilledButton.icon(
            onPressed: state.branchId == null || state.busy ? null : onPrepare,
            icon: state.busy
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.download_for_offline_outlined),
            label: Text(
              state.prepared ? 'Actualizar catálogo' : 'Preparar dispositivo',
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
              const Text(
                'El catálogo local queda separado por empresa, usuario y sucursal.',
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
                  if (current.mode == OfflineOperationType.reservation) ...[
                    const SizedBox(height: 16),
                    DropdownButtonFormField<int>(
                      initialValue: current.customerId,
                      decoration: const InputDecoration(labelText: 'Cliente'),
                      items: current.customers
                          .map(
                            (customer) => DropdownMenuItem(
                              value: customer.id,
                              child: Text(
                                customer.name,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: ctrl.setCustomer,
                    ),
                  ],
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
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: () async {
                        await ctrl.queue();
                        if (context.mounted &&
                            ref.read(offlineControllerProvider).error == null) {
                          Navigator.pop(context);
                        }
                      },
                      child: Text(
                        current.mode == OfflineOperationType.sale
                            ? 'Guardar venta en efectivo'
                            : 'Guardar reserva',
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
    required this.onRetry,
    required this.onDiscard,
  });
  final OfflineState state;
  final ValueChanged<String> onRetry;
  final ValueChanged<String> onDiscard;

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
        ...state.operations.take(20).map((operation) {
          final failed =
              operation.status == OfflineOperationStatus.conflict ||
              operation.status == OfflineOperationStatus.rejected;
          return Card(
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
                '${operation.errorMessage == null ? '' : '\n${operation.errorMessage}'}',
              ),
              isThreeLine: operation.errorMessage != null,
              trailing: failed
                  ? PopupMenuButton<String>(
                      onSelected: (value) => value == 'retry'
                          ? onRetry(operation.id)
                          : onDiscard(operation.id),
                      itemBuilder: (_) => const [
                        PopupMenuItem(
                          value: 'retry',
                          child: Text('Reintentar'),
                        ),
                        PopupMenuItem(
                          value: 'discard',
                          child: Text('Descartar'),
                        ),
                      ],
                    )
                  : null,
            ),
          );
        }),
    ],
  );

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
  const _EmptyCatalog();
  @override
  Widget build(BuildContext context) => const Card(
    child: Padding(
      padding: EdgeInsets.all(24),
      child: Row(
        children: [
          Icon(Icons.download_for_offline_outlined, size: 32),
          SizedBox(width: 14),
          Expanded(
            child: Text(
              'Selecciona una sucursal y pulsa “Preparar dispositivo”.',
            ),
          ),
        ],
      ),
    ),
  );
}

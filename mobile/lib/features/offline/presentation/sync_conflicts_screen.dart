import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:capricho_store/features/offline/presentation/sync_conflicts_controller.dart';
import 'package:capricho_store/shared/widgets/message_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

/// Ventas y reservas offline que el servidor no registró, para que un
/// encargado o administrador decida: reaplicarlas o anularlas con una nota.
class SyncConflictsScreen extends ConsumerWidget {
  const SyncConflictsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pending = ref.watch(pendingSyncConflictsProvider);
    return DefaultTabController(
      length: 2,
      child: Column(
        children: [
          Material(
            color: Theme.of(context).colorScheme.surface,
            child: TabBar(
              tabs: [
                Tab(text: pending > 0 ? 'Pendientes ($pending)' : 'Pendientes'),
                const Tab(text: 'Historial'),
              ],
            ),
          ),
          const Expanded(
            child: TabBarView(children: [_PendingTab(), _HistoryTab()]),
          ),
        ],
      ),
    );
  }
}

final _date = DateFormat('dd/MM HH:mm');
final _money = NumberFormat.currency(locale: 'es_BO', symbol: 'Bs.');

class _PendingTab extends ConsumerWidget {
  const _PendingTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final conflicts = ref.watch(syncConflictsProvider);
    final controller = ref.read(syncConflictsProvider.notifier);
    return RefreshIndicator(
      onRefresh: controller.refresh,
      child: conflicts.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ListView(
          children: [
            MessageState(
              title: 'No se pudieron cargar los conflictos',
              message: '$error',
              onRetry: controller.refresh,
            ),
          ],
        ),
        data: (items) => items.isEmpty
            ? ListView(
                children: const [
                  MessageState(
                    title: 'Sin conflictos pendientes',
                    message:
                        'Todas las ventas offline de tu sucursal quedaron '
                        'registradas.',
                  ),
                ],
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
                itemCount: items.length,
                separatorBuilder: (_, _) => const SizedBox(height: 12),
                itemBuilder: (context, index) =>
                    _ConflictCard(conflict: items[index]),
              ),
      ),
    );
  }
}

class _HistoryTab extends ConsumerWidget {
  const _HistoryTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(resolvedSyncConflictsProvider);
    return RefreshIndicator(
      onRefresh: () => ref.refresh(resolvedSyncConflictsProvider.future),
      child: history.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ListView(
          children: [
            MessageState(
              title: 'No se pudo cargar el historial',
              message: '$error',
              onRetry: () => ref.invalidate(resolvedSyncConflictsProvider),
            ),
          ],
        ),
        data: (items) => items.isEmpty
            ? ListView(
                children: const [
                  MessageState(
                    title: 'Sin historial',
                    message: 'Aquí verás los conflictos ya resueltos.',
                  ),
                ],
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
                itemCount: items.length,
                separatorBuilder: (_, _) => const SizedBox(height: 12),
                itemBuilder: (context, index) =>
                    _ConflictCard(conflict: items[index]),
              ),
      ),
    );
  }
}

class _ConflictCard extends ConsumerStatefulWidget {
  const _ConflictCard({required this.conflict});
  final SyncConflict conflict;

  @override
  ConsumerState<_ConflictCard> createState() => _ConflictCardState();
}

class _ConflictCardState extends ConsumerState<_ConflictCard> {
  bool _busy = false;

  SyncConflict get conflict => widget.conflict;

  Future<void> _resolve(String action, {String? note}) async {
    setState(() => _busy = true);
    final error = await ref
        .read(syncConflictsProvider.notifier)
        .resolve(conflict, action: action, note: note);
    if (!mounted) return;
    setState(() => _busy = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: error == null ? AppColors.success : AppColors.danger,
        content: Text(
          error ??
              (action == 'REAPLICAR'
                  ? '${conflict.label} registrada.'
                  : '${conflict.label} anulada.'),
        ),
      ),
    );
  }

  Future<void> _confirmReapply() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('¿Registrar la ${conflict.label.toLowerCase()} ahora?'),
        content: Text(
          'Se registrará a nombre de ${conflict.seller ?? 'el vendedor'} y '
          'descontará el stock. Si sigue sin haber stock, primero ajusta el '
          'inventario de la sucursal.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Reaplicar'),
          ),
        ],
      ),
    );
    if (ok ?? false) await _resolve('REAPLICAR');
  }

  Future<void> _askCancellation() async {
    final note = await showDialog<String>(
      context: context,
      builder: (context) => const _CancelDialog(),
    );
    if (note != null) await _resolve('ANULAR', note: note);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final pending = conflict.pending;
    return Card(
      shape: pending
          ? RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: const BorderSide(color: AppColors.danger),
            )
          : null,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  conflict.operationType == 'VENTA'
                      ? Icons.point_of_sale_outlined
                      : Icons.event_available_outlined,
                  color: pending ? AppColors.danger : AppColors.inkSoft,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    '${conflict.label} de ${conflict.seller ?? 'vendedor #${conflict.sellerId}'}',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                Text(
                  _date.format(conflict.clientDate.toLocal()),
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
            const SizedBox(height: 10),
            for (final item in conflict.items)
              Text('${item.quantity} × ${item.description}'),
            if (conflict.totalCents != null) ...[
              const SizedBox(height: 4),
              Text(
                'Cobrado: ${_money.format(conflict.totalCents! / 100)}',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ],
            if (conflict.branchId != null)
              Text(
                'Sucursal #${conflict.branchId}',
                style: theme.textTheme.bodySmall,
              ),
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: pending
                    ? const Color(0xFFFFE7E3)
                    : theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    conflict.reason,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  if (conflict.message != null) Text(conflict.message!),
                ],
              ),
            ),
            const SizedBox(height: 10),
            if (pending) ...[
              Text(conflict.advice, style: theme.textTheme.bodySmall),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                alignment: WrapAlignment.end,
                children: [
                  OutlinedButton.icon(
                    onPressed: _busy ? null : _askCancellation,
                    icon: const Icon(Icons.block_rounded),
                    label: const Text('Anular'),
                  ),
                  FilledButton.icon(
                    onPressed: _busy || !conflict.canReapply
                        ? null
                        : _confirmReapply,
                    icon: _busy
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.replay_rounded),
                    label: const Text('Reaplicar'),
                  ),
                ],
              ),
            ] else
              Text(
                conflict.action == 'REAPLICADA'
                    ? 'Registrada por ${conflict.resolvedBy ?? 'un supervisor'}'
                          '${conflict.resolvedAt == null ? '' : ' · ${_date.format(conflict.resolvedAt!.toLocal())}'}'
                    : 'Anulada por ${conflict.resolvedBy ?? 'un supervisor'}'
                          '${conflict.note == null ? '' : ': ${conflict.note}'}',
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  color: conflict.action == 'REAPLICADA'
                      ? AppColors.success
                      : AppColors.inkSoft,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Pide la nota obligatoria para anular.
class _CancelDialog extends StatefulWidget {
  const _CancelDialog();

  @override
  State<_CancelDialog> createState() => _CancelDialogState();
}

class _CancelDialogState extends State<_CancelDialog> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _valid => _controller.text.trim().length >= 3;

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Anular operación'),
    content: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'No se registrará la venta. Explica cómo se resolvió con el '
          'cliente (ej.: se devolvió el dinero, se cambió por otra prenda).',
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _controller,
          autofocus: true,
          maxLength: 500,
          maxLines: 3,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(labelText: 'Nota'),
        ),
      ],
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('Cancelar'),
      ),
      FilledButton(
        style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
        onPressed: _valid
            ? () => Navigator.of(context).pop(_controller.text.trim())
            : null,
        child: const Text('Anular'),
      ),
    ],
  );
}

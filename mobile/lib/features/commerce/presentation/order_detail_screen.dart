import 'package:capricho_store/core/config/environment.dart';
import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/commerce/data/commerce_api.dart';
import 'package:capricho_store/features/commerce/domain/commerce_models.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_image.dart';
import 'package:capricho_store/shared/widgets/message_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

final orderDetailProvider =
    FutureProvider.family<Order, int>((ref, orderId) async {
  final api = ref.watch(commerceApiProvider);
  return api.getOrder(orderId);
});

final orderReturnsProvider = FutureProvider.family<List<Map<String, dynamic>>, int>((ref, saleId) async {
  final all = await ref.watch(commerceApiProvider).listReturns();
  return all.where((item) => item['id_venta'] == saleId).toList();
});

class OrderDetailScreen extends ConsumerStatefulWidget {
  final int orderId;

  const OrderDetailScreen({required this.orderId, super.key});

  @override
  ConsumerState<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends ConsumerState<OrderDetailScreen> {
  bool _isConfirming = false;

  @override
  Widget build(BuildContext context) {
    final orderAsync = ref.watch(orderDetailProvider(widget.orderId));

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded),
          tooltip: 'Volver',
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/pedidos');
            }
          },
        ),
        title: Text('Pedido #${widget.orderId}'),
        shape: const Border(
          bottom: BorderSide(color: AppColors.line, width: 1),
        ),
      ),
      body: orderAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => MessageState(
          title: 'No pudimos cargar el pedido',
          message: err.toString().replaceAll('ApiException: ', ''),
          onRetry: () => ref.refresh(orderDetailProvider(widget.orderId)),
        ),
        data: (order) => _buildContent(context, order),
      ),
    );
  }

  Widget _buildContent(BuildContext context, Order order) {
    final returns = ref.watch(orderReturnsProvider(order.idVenta));
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Confirmación de entrega pendiente
        if (order.isDelivery && order.estado == 'EN_CAMINO')
          _buildDeliveryConfirmationCard(context, order),

        // Línea de tiempo de Seguimiento
        _buildTrackingCard(order),
        const SizedBox(height: 16),

        // Datos de entrega
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Datos de Entrega',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 14.5,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Icon(
                    order.isDelivery
                        ? Icons.two_wheeler_rounded
                        : Icons.store_mall_directory_rounded,
                    color: AppColors.cobalt,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      order.isDelivery ? 'Delivery a domicilio' : 'Retiro en tienda física',
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                order.isDelivery
                    ? 'Dirección: ${order.direccionEntrega ?? "No especificada"}'
                    : 'Sucursal: ${order.sucursal}\nDirección: ${order.direccionSucursal}',
                style: const TextStyle(fontSize: 12.5, color: AppColors.inkSoft, height: 1.3),
              ),
              if (!order.isDelivery) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: AppColors.cobaltLight.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.cobalt.withValues(alpha: 0.2)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.storefront_rounded, color: AppColors.cobaltDark, size: 22),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Presenta el Pedido #${order.idPedido} al momento de retirar en sucursal.',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: AppColors.cobaltDark,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Detalle de prendas
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Prendas Compradas',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 14.5,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 12),
              ...order.items.map((item) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Row(
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: SizedBox(
                            width: 50,
                            height: 50,
                            child: AdaptiveImage(
                              imageUrl: item.imagenUrl,
                              aspectRatio: 1,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                item.producto,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  fontSize: 13,
                                  color: AppColors.ink,
                                ),
                              ),
                              Text(
                                '${item.color} · ${item.talla} · Cant: ${item.cantidad}',
                                style: const TextStyle(
                                  fontSize: 11.5,
                                  color: AppColors.inkSoft,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Text(
                          item.formattedSubtotal,
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 14,
                            color: AppColors.ink,
                          ),
                        ),
                      ],
                    ),
                  )),
              const Divider(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Total Pagado',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 16,
                      color: AppColors.ink,
                    ),
                  ),
                  Text(
                    order.formattedTotal,
                    style: const TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 18,
                      color: AppColors.cobaltDark,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),

        // Acciones: Factura oficial y Recibo de Stripe
        const SizedBox(height: 20),
        OutlinedButton.icon(
          onPressed: () => _requestReturn(order),
          icon: const Icon(Icons.swap_horiz_rounded),
          label: const Text('Solicitar cambio o devolución'),
        ),
        returns.when(
          data: (items) => Column(
            children: items.map((item) => ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('Solicitud #${item['id_devolucion']} · ${_returnKind(item['tipo_solicitud'] as String?)}'),
              subtitle: Text('Estado: ${item['estado']} · ${item['motivo']}'),
            )).toList(),
          ),
          loading: () => const LinearProgressIndicator(),
          error: (error, stackTrace) => const Text('No se pudo cargar el estado de tus solicitudes.'),
        ),
        const SizedBox(height: 10),
        FilledButton.icon(
          onPressed: () => _openInvoicePdf(context, order.idPedido),
          icon: const Icon(Icons.picture_as_pdf_rounded, color: Colors.white, size: 20),
          label: const Text(
            'Descargar Factura Oficial (PDF)',
            style: TextStyle(
              fontWeight: FontWeight.w700,
              fontSize: 14,
            ),
          ),
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.cobaltDark,
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        if (order.receiptUrl != null && order.receiptUrl!.isNotEmpty) ...[
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: () => launchUrl(
              Uri.parse(order.receiptUrl!),
              mode: LaunchMode.inAppBrowserView,
            ),
            icon: const Icon(Icons.receipt_long_rounded, color: AppColors.cobalt),
            label: const Text(
              'Ver recibo de pago oficial (Stripe)',
              style: TextStyle(
                color: AppColors.cobalt,
                fontWeight: FontWeight.w700,
              ),
            ),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
              side: const BorderSide(color: AppColors.cobalt),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ],
      ],
    );
  }

  String _returnKind(String? kind) => switch (kind) {
    'CAMBIO_TALLA' => 'Cambio de talla',
    'CAMBIO_COLOR' => 'Cambio de color',
    'CAMBIO_PRENDA' => 'Cambio de prenda',
    'REEMBOLSO' => 'Reembolso solicitado',
    'CREDITO' => 'Crédito solicitado',
    _ => 'Devolución',
  };

  Future<void> _requestReturn(Order order) async {
    if (order.items.isEmpty) return;
    var selected = order.items.first;
    var quantity = 1;
    var kind = 'CAMBIO_TALLA';
    var busy = false;
    final reason = TextEditingController();
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('Cambio o devolución'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Selecciona la prenda y explica lo que necesitas. La tienda revisará la solicitud y la prenda antes de resolverla.'),
              DropdownButtonFormField<int>(
                initialValue: selected.idDetalle,
                decoration: const InputDecoration(labelText: 'Prenda'),
                items: order.items.map((item) => DropdownMenuItem(
                  value: item.idDetalle,
                  child: Text('${item.producto} · ${item.talla}', overflow: TextOverflow.ellipsis),
                )).toList(),
                onChanged: busy ? null : (value) => setDialogState(() {
                  selected = order.items.firstWhere((item) => item.idDetalle == value);
                  quantity = 1;
                }),
              ),
              DropdownButtonFormField<String>(
                initialValue: kind,
                decoration: const InputDecoration(labelText: 'Solicitud'),
                items: const [
                  DropdownMenuItem(value: 'CAMBIO_TALLA', child: Text('Cambiar talla')),
                  DropdownMenuItem(value: 'CAMBIO_COLOR', child: Text('Cambiar color')),
                  DropdownMenuItem(value: 'CAMBIO_PRENDA', child: Text('Cambiar prenda')),
                  DropdownMenuItem(value: 'REEMBOLSO', child: Text('Solicitar reembolso')),
                  DropdownMenuItem(value: 'CREDITO', child: Text('Crédito en tienda')),
                ],
                onChanged: busy ? null : (value) => setDialogState(() => kind = value ?? kind),
              ),
              DropdownButtonFormField<int>(
                key: ValueKey(selected.idDetalle),
                initialValue: quantity,
                decoration: const InputDecoration(labelText: 'Cantidad'),
                items: List.generate(selected.cantidad, (index) => DropdownMenuItem(
                  value: index + 1,
                  child: Text('${index + 1}'),
                )),
                onChanged: busy ? null : (value) => setDialogState(() => quantity = value ?? 1),
              ),
              TextField(
                controller: reason,
                maxLength: 255,
                decoration: const InputDecoration(labelText: 'Motivo y talla/color deseado'),
              ),
            ]),
          ),
          actions: [
            TextButton(onPressed: busy ? null : () => Navigator.pop(dialogContext), child: const Text('Cancelar')),
            FilledButton(
              onPressed: busy ? null : () async {
                if (reason.text.trim().length < 3) {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Explica el motivo en al menos 3 caracteres.')));
                  return;
                }
                setDialogState(() => busy = true);
                try {
                  await ref.read(commerceApiProvider).createReturn(
                    saleId: order.idVenta,
                    detailId: selected.idDetalle,
                    quantity: quantity,
                    kind: kind,
                    reason: reason.text.trim(),
                  );
                  ref.invalidate(orderReturnsProvider(order.idVenta));
                  if (dialogContext.mounted) Navigator.pop(dialogContext);
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Solicitud enviada a la tienda.')));
                } catch (error) {
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo enviar: $error')));
                  setDialogState(() => busy = false);
                }
              },
              child: const Text('Enviar solicitud'),
            ),
          ],
        ),
      ),
    );
    reason.dispose();
  }

  Widget _buildDeliveryConfirmationCard(BuildContext context, Order order) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFECFDF5),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFA7F3D0), width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.delivery_dining_rounded,
                  color: AppColors.success,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Tu pedido está en camino 🛵',
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 14,
                        color: Color(0xFF065F46),
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      '¿El repartidor ya te entregó tus prendas?',
                      style: TextStyle(
                        fontSize: 12,
                        color: Color(0xFF047857),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _isConfirming ? null : () => _confirmDelivery(order.idPedido),
              icon: _isConfirming
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.check_circle_outline_rounded, size: 20),
              label: Text(
                _isConfirming ? 'Confirmando recepción…' : '✓ Confirmar que recibí mi pedido',
                style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5),
              ),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.success,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmDelivery(int orderId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmar entrega'),
        content: const Text(
          '¿Confirmas que recibiste todas tus prendas de forma satisfactoria? Esta acción dará por finalizado el pedido.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Aún no'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: FilledButton.styleFrom(backgroundColor: AppColors.success),
            child: const Text('Sí, lo recibí'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() => _isConfirming = true);
    try {
      await ref.read(ordersProvider.notifier).confirmDelivery(orderId);
      ref.invalidate(orderDetailProvider(orderId));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('¡Entrega confirmada con éxito! Gracias por tu compra.'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('No se pudo confirmar la entrega: $e'),
            backgroundColor: AppColors.danger,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isConfirming = false);
      }
    }
  }

  Future<void> _openInvoicePdf(BuildContext context, int orderId) async {
    try {
      final storage = ref.read(tokenStorageProvider);
      final token = await storage.read();
      final uri = Uri.parse(
          '${Environment.apiBaseUrl}/orders/$orderId/invoice${token != null ? '?token=$token' : ''}');

      final launched =
          await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!launched && context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('No pudimos abrir el visor de facturas.')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al abrir la factura: $e')),
        );
      }
    }
  }

  Widget _buildTrackingCard(Order order) {
    final step = order.stepProgress;

    final steps = [
      {'title': 'Pago Confirmado', 'subtitle': 'Orden registrada'},
      {'title': 'En Preparación', 'subtitle': 'Empacando en sucursal'},
      {
        'title': order.isDelivery ? 'En Camino' : 'Listo para Retiro',
        'subtitle': order.isDelivery ? 'Repartidor asignado' : 'Disponible en tienda'
      },
      {'title': 'Entregado', 'subtitle': 'Completado'},
    ];

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Seguimiento en Vivo',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 15,
                  color: AppColors.ink,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.cobaltLight,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  order.statusDisplay,
                  style: const TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w800,
                    color: AppColors.cobaltDark,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Stepper Visual
          ...List.generate(steps.length, (idx) {
            final isDone = idx <= step && step != -1;
            final isCurrent = idx == step;
            final isLast = idx == steps.length - 1;

            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Column(
                  children: [
                    Container(
                      width: 24,
                      height: 24,
                      decoration: BoxDecoration(
                        color: isDone ? AppColors.cobalt : AppColors.muted,
                        shape: BoxShape.circle,
                        border: isCurrent
                            ? Border.all(color: AppColors.cobaltDark, width: 2.5)
                            : null,
                      ),
                      child: Center(
                        child: Icon(
                          isDone ? Icons.check : Icons.circle,
                          size: isDone ? 14 : 8,
                          color: isDone ? Colors.white : AppColors.inkSoft,
                        ),
                      ),
                    ),
                    if (!isLast)
                      Container(
                        width: 2,
                        height: 32,
                        color: idx < step ? AppColors.cobalt : AppColors.line,
                      ),
                  ],
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          steps[idx]['title']!,
                          style: TextStyle(
                            fontWeight: isCurrent ? FontWeight.w800 : FontWeight.w600,
                            fontSize: 13.5,
                            color: isDone ? AppColors.ink : AppColors.inkSoft,
                          ),
                        ),
                        Text(
                          steps[idx]['subtitle']!,
                          style: TextStyle(fontSize: 11.5, color: AppColors.inkSoft),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            );
          }),
        ],
      ),
    );
  }
}

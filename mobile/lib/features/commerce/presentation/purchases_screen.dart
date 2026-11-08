import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../data/commerce_api.dart';
import '../domain/commerce_models.dart';
import 'return_request_dialog.dart';

final purchasesProvider = FutureProvider<List<Map<String, dynamic>>>(
  (ref) => ref.watch(commerceApiProvider).listPurchases(),
);
final customerReturnsProvider = FutureProvider<List<Map<String, dynamic>>>(
  (ref) => ref.watch(commerceApiProvider).listReturns(),
);

class PurchasesScreen extends ConsumerWidget {
  const PurchasesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final purchases = ref.watch(purchasesProvider);
    final returns = ref.watch(customerReturnsProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Compras y devoluciones'),
        actions: [
          IconButton(
            tooltip: 'Actualizar',
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(purchasesProvider);
              ref.invalidate(customerReturnsProvider);
            },
          ),
        ],
      ),
      body: purchases.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) =>
            Center(child: Text('No pudimos cargar las compras: $error')),
        data: (sales) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'Tus compras online y en tienda. Las solicitudes requieren conexión y una compra asociada a tu cuenta.',
            ),
            if (sales.isEmpty)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Text('Todavía no tienes compras registradas.'),
              ),
            ...sales.map((sale) {
              final items = (sale['items'] as List? ?? [])
                  .map(
                    (item) => CommerceLineItem.fromJson(
                      Map<String, dynamic>.from(item as Map),
                    ),
                  )
                  .toList();
              final eligible = sale['devolucion_habilitada'] == true;
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Compra #${sale['id_venta']} · ${sale['sucursal']}',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      ...items.map(
                        (item) => Text(
                          '${item.producto} · ${item.talla} / ${item.color} × ${item.cantidad}',
                        ),
                      ),
                      Text('Total: Bs ${sale['total']}'),
                      const SizedBox(height: 8),
                      if (eligible && sale['fecha_limite_devolucion'] != null)
                        Text(
                          'Solicitudes hasta ${DateFormat('dd/MM/yyyy HH:mm').format(DateTime.parse(sale['fecha_limite_devolucion'] as String).toLocal())}',
                        ),
                      if (eligible)
                        OutlinedButton.icon(
                          icon: const Icon(Icons.swap_horiz),
                          label: const Text('Solicitar cambio o devolución'),
                          onPressed: () => showReturnRequestDialog(
                            context,
                            ref,
                            saleId: sale['id_venta'] as int,
                            items: items,
                            onSaved: () =>
                                ref.invalidate(customerReturnsProvider),
                          ),
                        )
                      else
                        Text(
                          sale['fecha_inicio_devolucion'] == null
                              ? 'Disponible después de confirmar la entrega o retiro.'
                              : 'Fuera del plazo o estado habilitado.',
                        ),
                    ],
                  ),
                ),
              );
            }),
            const SizedBox(height: 20),
            Text('Solicitudes', style: Theme.of(context).textTheme.titleLarge),
            returns.when(
              loading: () => const LinearProgressIndicator(),
              error: (error, stack) =>
                  Text('No pudimos cargar tus solicitudes: $error'),
              data: (requests) => Column(
                children: [
                  if (requests.isEmpty)
                    const ListTile(
                      title: Text('Sin solicitudes de devolución.'),
                    ),
                  ...requests.map((item) => ReturnStatusCard(item: item)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ReturnStatusCard extends StatelessWidget {
  const ReturnStatusCard({required this.item, super.key});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final receipt = item['cierre'] is Map
        ? Map<String, dynamic>.from(item['cierre'] as Map)
        : null;
    final replacementLines = receipt?['items'] as List? ?? [];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Solicitud #${item['id_devolucion']} · Compra #${item['id_venta']}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              'Estado: ${{'PENDIENTE': 'Pendiente', 'APROBADA': 'Aprobada', 'COMPLETADA': 'Completada', 'RECHAZADA': 'Rechazada'}[item['estado']] ?? item['estado']}',
            ),
            Text('${item['motivo']}'),
            ...(item['items'] as List? ?? [])
                .whereType<Map>()
                .where((line) => line['id_variante_solicitada'] != null)
                .map(
                  (line) => Text(
                    'Devuelves: ${line['producto']} · ${line['talla']} / ${line['color']}. Solicitas: ${line['talla_solicitada']} / ${line['color_solicitado']}.',
                  ),
                ),
            if (item['estado'] == 'APROBADA')
              const Text(
                'Presenta las prendas y el comprobante en la sucursal para la inspección.',
              ),
            if (receipt != null) ...[
              const Divider(),
              Text('Comprobante ${receipt['comprobante']}'),
              Text(
                '${receipt['tipo'] == 'CAMBIO' ? 'Cambio de prenda' : 'Reembolso'} · ${{'COBRAR': 'Adicional pagado', 'REEMBOLSAR': 'Importe reembolsado', 'SIN_DIFERENCIA': 'Sin diferencia'}[receipt['accion']]} · Bs ${receipt['monto']}',
              ),
              ...replacementLines
                  .whereType<Map>()
                  .where((line) => line['producto'] != null)
                  .map(
                    (line) => Text(
                      'Entregado: ${line['producto']} · ${line['talla']} / ${line['color']} × ${line['cantidad']}',
                    ),
                  ),
              Text(
                'Medio: ${receipt['medio'] ?? 'Sin diferencia'} · Referencia: ${receipt['referencia'] ?? 'No corresponde'}',
              ),
            ],
          ],
        ),
      ),
    );
  }
}

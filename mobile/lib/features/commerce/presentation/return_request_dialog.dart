import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/commerce_api.dart';
import '../domain/commerce_models.dart';

Future<void> showReturnRequestDialog(
  BuildContext context,
  WidgetRef ref, {
  required int saleId,
  required List<CommerceLineItem> items,
  VoidCallback? onSaved,
}) async {
  if (items.isEmpty) return;
  var selected = items.first;
  var quantity = 1;
  var kind = 'CAMBIO_TALLA';
  var busy = false;
  var requirementsAccepted = false;
  var reason = '';
  var options = <Map<String, dynamic>>[];
  int? requestedVariant;
  var loadingOptions = false;
  var optionError = '';
  var optionsVersion = 0;
  var initialized = false;
  bool specificExchange() => kind == 'CAMBIO_TALLA' || kind == 'CAMBIO_COLOR';

  Future<void> loadOptions(
    BuildContext dialogContext,
    StateSetter setDialogState,
  ) async {
    final version = ++optionsVersion;
    setDialogState(() {
      requestedVariant = null;
      options = [];
      optionError = '';
      loadingOptions = specificExchange();
    });
    if (!specificExchange()) return;
    try {
      final result = await ref
          .read(commerceApiProvider)
          .returnOptions(saleId, selected.idDetalle, kind);
      if (dialogContext.mounted && version == optionsVersion)
        setDialogState(() {
          options = result;
          loadingOptions = false;
        });
    } catch (error) {
      if (dialogContext.mounted && version == optionsVersion)
        setDialogState(() {
          optionError = 'No pudimos cargar las variantes: $error';
          loadingOptions = false;
        });
    }
  }

  await showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) => StatefulBuilder(
      builder: (dialogContext, setDialogState) {
        if (!initialized) {
          initialized = true;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (dialogContext.mounted)
              loadOptions(dialogContext, setDialogState);
          });
        }
        return PopScope(
          canPop: !busy,
          child: AlertDialog(
            title: const Text('Cambio o devolución'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Selecciona la prenda y explica lo que necesitas. La tienda revisará la solicitud y la prenda antes de resolverla.',
                  ),
                  DropdownButtonFormField<int>(
                    isExpanded: true,
                    initialValue: selected.idDetalle,
                    decoration: const InputDecoration(labelText: 'Prenda'),
                    items: items
                        .map(
                          (item) => DropdownMenuItem(
                            value: item.idDetalle,
                            child: Text(
                              '${item.producto} · ${item.talla} / ${item.color}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: busy
                        ? null
                        : (value) {
                            setDialogState(() {
                              selected = items.firstWhere(
                                (item) => item.idDetalle == value,
                              );
                              quantity = 1;
                            });
                            loadOptions(dialogContext, setDialogState);
                          },
                  ),
                  DropdownButtonFormField<String>(
                    isExpanded: true,
                    initialValue: kind,
                    decoration: const InputDecoration(labelText: 'Solicitud'),
                    items: const [
                      DropdownMenuItem(
                        value: 'CAMBIO_TALLA',
                        child: Text('Cambiar talla'),
                      ),
                      DropdownMenuItem(
                        value: 'CAMBIO_COLOR',
                        child: Text('Cambiar color'),
                      ),
                      DropdownMenuItem(
                        value: 'CAMBIO_PRENDA',
                        child: Text('Cambiar prenda'),
                      ),
                      DropdownMenuItem(
                        value: 'REEMBOLSO',
                        child: Text('Solicitar reembolso'),
                      ),
                    ],
                    onChanged: busy
                        ? null
                        : (value) {
                            setDialogState(() => kind = value ?? kind);
                            loadOptions(dialogContext, setDialogState);
                          },
                  ),
                  DropdownButtonFormField<int>(
                    isExpanded: true,
                    key: ValueKey(selected.idDetalle),
                    initialValue: quantity,
                    decoration: const InputDecoration(labelText: 'Cantidad'),
                    items: List.generate(
                      selected.cantidad,
                      (index) => DropdownMenuItem(
                        value: index + 1,
                        child: Text('${index + 1}'),
                      ),
                    ),
                    onChanged: busy
                        ? null
                        : (value) => setDialogState(() {
                            quantity = value ?? 1;
                            requestedVariant = null;
                          }),
                  ),
                  if (specificExchange()) ...[
                    Text(
                      'Devuelves: ${selected.producto} · Talla ${selected.talla} · Color ${selected.color}',
                    ),
                    Text(
                      kind == 'CAMBIO_TALLA'
                          ? 'Se conserva el color original.'
                          : 'Se conserva la talla original.',
                    ),
                    if (loadingOptions) const LinearProgressIndicator(),
                    if (optionError.isNotEmpty) Text(optionError),
                    DropdownButtonFormField<int>(
                      key: ValueKey('requested-$optionsVersion-$quantity'),
                      initialValue: requestedVariant,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Variante solicitada',
                        hintText: 'Seleccionar talla o color',
                      ),
                      items: options
                          .map(
                            (option) => DropdownMenuItem<int>(
                              value: option['id_variante'] as int,
                              enabled:
                                  (option['stock_disponible'] as num) >=
                                  quantity,
                              child: Text(
                                'Talla ${option['talla']} · ${option['color']} · Stock ${option['stock_disponible']}',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: busy || loadingOptions
                          ? null
                          : (value) =>
                                setDialogState(() => requestedVariant = value),
                    ),
                    if (!loadingOptions &&
                        options.isEmpty &&
                        optionError.isEmpty)
                      const Text(
                        'No hay variantes compatibles en la sucursal de la compra.',
                      ),
                    const Text(
                      'La disponibilidad se confirma al recibir la prenda. La solicitud no reserva stock.',
                    ),
                  ],
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: requirementsAccepted,
                    onChanged: busy
                        ? null
                        : (value) => setDialogState(
                            () => requirementsAccepted = value ?? false,
                          ),
                    title: const Text('Leí los requisitos de devolución'),
                    subtitle: const Text(
                      'Sin uso, sin lavado, etiquetas conservadas y sin daños atribuibles al cliente. Presenta tu comprobante para la inspección.',
                    ),
                  ),
                  TextField(
                    onChanged: (value) => reason = value,
                    maxLength: 255,
                    decoration: const InputDecoration(
                      labelText: 'Motivo y talla/color deseado',
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: busy ? null : () => Navigator.pop(dialogContext),
                child: const Text('Cancelar'),
              ),
              FilledButton(
                onPressed:
                    busy ||
                        !requirementsAccepted ||
                        (specificExchange() && requestedVariant == null)
                    ? null
                    : () async {
                        if (reason.trim().length < 3) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Explica el motivo en al menos 3 caracteres.',
                              ),
                            ),
                          );
                          return;
                        }
                        setDialogState(() => busy = true);
                        try {
                          await ref
                              .read(commerceApiProvider)
                              .createReturn(
                                saleId: saleId,
                                detailId: selected.idDetalle,
                                quantity: quantity,
                                kind: kind,
                                reason: reason.trim(),
                                requestedVariantId: specificExchange()
                                    ? requestedVariant
                                    : null,
                              );
                          if (context.mounted) onSaved?.call();
                          if (dialogContext.mounted)
                            Navigator.pop(dialogContext);
                          if (context.mounted)
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Solicitud enviada a la tienda.'),
                              ),
                            );
                        } catch (error) {
                          if (context.mounted)
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('No se pudo enviar: $error'),
                              ),
                            );
                          if (dialogContext.mounted)
                            setDialogState(() => busy = false);
                        }
                      },
                child: const Text('Enviar solicitud'),
              ),
            ],
          ),
        );
      },
    ),
  );
}

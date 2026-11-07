import 'dart:async';

import 'package:capricho_store/features/commerce/data/commerce_api.dart';
import 'package:capricho_store/features/commerce/domain/commerce_models.dart';
import 'package:capricho_store/features/commerce/presentation/purchases_screen.dart';
import 'package:capricho_store/features/commerce/presentation/return_request_dialog.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class ReturnTestApi extends CommerceApi {
  ReturnTestApi() : super(Dio());
  int requests = 0;
  final pending = Completer<void>();

  @override
  Future<void> createReturn({
    required int saleId,
    required int detailId,
    required int quantity,
    required String kind,
    required String reason,
  }) {
    requests++;
    return pending.future;
  }
}

void main() {
  testWidgets('solicitud requiere leer requisitos y bloquea envíos repetidos', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = ReturnTestApi();
    final item = CommerceLineItem.fromJson({
      'id_detalle': 4,
      'id_variante': 7,
      'producto': 'Polera de prueba',
      'talla': 'M',
      'color': 'Azul',
      'cantidad': 2,
      'precio_unitario': '120',
      'subtotal': '240',
    });
    await tester.pumpWidget(
      ProviderScope(
        overrides: [commerceApiProvider.overrideWithValue(api)],
        child: MaterialApp(
          home: Consumer(
            builder: (context, ref, child) => Scaffold(
              body: TextButton(
                onPressed: () => showReturnRequestDialog(
                  context,
                  ref,
                  saleId: 1,
                  items: [item],
                ),
                child: const Text('Abrir solicitud'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Abrir solicitud'));
    await tester.pumpAndSettle();
    final send = find.widgetWithText(FilledButton, 'Enviar solicitud');
    expect(tester.widget<FilledButton>(send).onPressed, isNull);
    await tester.tap(find.byType(CheckboxListTile));
    await tester.enterText(find.byType(TextField), 'La talla me quedó pequeña');
    await tester.pump();
    await tester.tap(send);
    await tester.pump();
    expect(tester.widget<FilledButton>(send).onPressed, isNull);
    expect(api.requests, 1);
    api.pending.complete();
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('Solicitud enviada a la tienda.'), findsOneWidget);
  });

  testWidgets('historial muestra el reemplazo y la liquidación registrada', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ReturnStatusCard(
            item: {
              'id_devolucion': 3,
              'id_venta': 1,
              'estado': 'COMPLETADA',
              'motivo': 'Cambio de talla',
              'cierre': {
                'comprobante': 'DEV-000003',
                'tipo': 'CAMBIO',
                'accion': 'SIN_DIFERENCIA',
                'monto': '0.00',
                'items': [
                  {
                    'producto': 'Polera',
                    'talla': 'L',
                    'color': 'Azul',
                    'cantidad': 1,
                  },
                ],
              },
            },
          ),
        ),
      ),
    );
    expect(find.textContaining('DEV-000003'), findsOneWidget);
    expect(find.textContaining('Entregado: Polera'), findsOneWidget);
    expect(find.textContaining('Sin diferencia'), findsWidgets);
  });
}

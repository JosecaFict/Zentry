import 'package:capricho_store/features/assistant/assistant_api.dart';
import 'package:capricho_store/features/assistant/assistant_screen.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _AssistantFixture extends AssistantApi {
  _AssistantFixture({this.history = const []}) : super(Dio());

  final List<AssistantMessage> history;
  String? question;

  final conversation = AssistantConversation({
    'id_conversacion': 'conversation-1',
    'estado': 'ACTIVA',
  });

  @override
  Future<List<AssistantConversation>> conversations(AssistantMode mode) async =>
      history.isEmpty ? [] : [conversation];

  @override
  Future<AssistantConversation> create(AssistantMode mode) async =>
      conversation;

  @override
  Future<List<AssistantMessage>> messages(String id) async => history;

  @override
  Future<List<AssistantMessage>> send(String id, String content) async {
    expect(id, conversation.id);
    question = content;
    return [
      AssistantMessage({
        'id_mensaje': 1,
        'rol': 'USUARIO',
        'contenido': content,
      }),
      AssistantMessage({
        'id_mensaje': 2,
        'rol': 'ASISTENTE',
        'contenido': 'Encontré esta opción.',
        'productos': [
          {
            'id_producto': 1,
            'nombre': 'Polo clásico',
            'marca': 'Capricho',
            'categoria': 'Polo',
            'precio': '180.00',
            'precio_original': '200.00',
            'promocion_nombre': 'Oferta de temporada',
            'tallas': ['M'],
            'colores': ['Azul marino'],
          },
        ],
      }),
    ];
  }
}

Future<void> _show(
  WidgetTester tester,
  AssistantMode mode,
  AssistantApi api,
) async {
  await tester.binding.setSurfaceSize(const Size(390, 740));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    ProviderScope(
      overrides: [assistantApiProvider.overrideWithValue(api)],
      child: MaterialApp(home: AssistantScreen(mode: mode)),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('sends a customer question and displays the promoted product', (
    tester,
  ) async {
    final api = _AssistantFixture();
    await _show(tester, AssistantMode.customer, api);
    await tester.enterText(find.byType(TextField), '¿Hay promociones hoy?');
    await tester.tap(find.byTooltip('Enviar consulta'));
    await tester.pumpAndSettle();

    expect(api.question, '¿Hay promociones hoy?');
    expect(find.text('Polo clásico'), findsOneWidget);
    expect(find.text('Oferta de temporada'), findsOneWidget);
    expect(find.text('Colores: Azul marino'), findsOneWidget);
  });

  testWidgets('only offers exports for reports marked as exportable', (
    tester,
  ) async {
    final api = _AssistantFixture(
      history: [
        AssistantMessage({
          'id_mensaje': 1,
          'rol': 'ASISTENTE',
          'contenido': 'Consulta general.',
          'reporte_exportable': false,
        }),
        AssistantMessage({
          'id_mensaje': 2,
          'rol': 'ASISTENTE',
          'contenido': 'Reporte de ventas.\n\n| Prenda | Unidades |\n| --- | --- |\n| **Polo** | 21 |',
          'reporte_exportable': true,
        }),
      ],
    );
    await _show(tester, AssistantMode.business, api);

    expect(find.text('PDF'), findsOneWidget);
    expect(find.text('Excel'), findsOneWidget);
    expect(find.byType(DataTable), findsOneWidget);
    expect(find.byTooltip('Dictar consulta'), findsNothing);
  });
}

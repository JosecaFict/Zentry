import 'package:capricho_store/app/navigation_memory.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:capricho_store/features/offline/presentation/sync_conflicts_controller.dart';
import 'package:capricho_store/features/offline/presentation/sync_conflicts_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

AppUser user({
  List<String> roles = const ['ENCARGADO_SUCURSAL'],
  List<String> permissions = const ['inventario.ver'],
  int? branch = 1,
}) => AppUser(
  id: 4,
  names: 'Luis',
  surnames: 'Encargado',
  email: 'luis@example.com',
  status: 'ACTIVO',
  roles: roles,
  permissions: permissions,
  idSucursal: branch,
);

Map<String, dynamic> conflictJson({
  String estado = 'PENDIENTE',
  String codigo = 'STOCK_INSUFICIENTE',
  bool reapply = true,
  String? accion,
}) => {
  'id_conflicto': 11,
  'id_operacion': '7c9e6679-7425-40de-944b-e07fc1f90ae7',
  'tipo_operacion': 'VENTA',
  'codigo': codigo,
  'mensaje': 'Stock insuficiente para completar la venta',
  'estado': estado,
  'id_sucursal': 1,
  'id_vendedor': 9,
  'vendedor': 'Ana Vendedora',
  'items': [
    {'id_variante': 2, 'cantidad': 1, 'descripcion': 'Polo básico M Negro'},
  ],
  'total_cobrado_centavos': 9990,
  'fecha_cliente': '2026-11-11T14:30:00Z',
  'created_at': '2026-11-11T15:00:00Z',
  'puede_reaplicar': reapply,
  'accion': accion,
  'resolucion': accion == 'ANULADA' ? 'Se devolvió el dinero' : null,
  'resuelto_por': accion == null ? null : 'Luis Encargado',
  'resuelto_at': accion == null ? null : '2026-11-11T16:00:00Z',
};

class _FixedConflicts extends SyncConflictsController {
  _FixedConflicts(this.items);
  final List<SyncConflict> items;

  @override
  Future<List<SyncConflict>> build() async => items;
}

void main() {
  setUpAll(() => initializeDateFormatting('es_BO'));

  group('quién revisa conflictos', () {
    test('encargado con sucursal y administrador sí', () {
      expect(user().canReviewSyncConflicts, isTrue);
      expect(
        user(roles: ['ADMIN'], branch: null).canReviewSyncConflicts,
        isTrue,
      );
      expect(
        user(
          roles: ['CAJERO'],
          permissions: ['ventas.sucursales_todas'],
        ).canReviewSyncConflicts,
        isTrue,
      );
    });

    test('cajero o encargado sin sucursal no', () {
      expect(user(roles: ['CAJERO']).canReviewSyncConflicts, isFalse);
      expect(user(branch: null).canReviewSyncConflicts, isFalse);
    });

    test('la ruta del panel respeta el permiso', () {
      expect(
        NavigationMemory.canOpenPanelLocation(user(), syncConflictsRoute),
        isTrue,
      );
      expect(
        NavigationMemory.canOpenPanelLocation(
          user(roles: ['CAJERO']),
          syncConflictsRoute,
        ),
        isFalse,
      );
    });
  });

  test('SyncConflict lee el contrato del backend', () {
    final conflict = SyncConflict.fromJson(conflictJson());
    expect(conflict.pending, isTrue);
    expect(conflict.label, 'Venta');
    expect(conflict.items.single.description, 'Polo básico M Negro');
    expect(conflict.totalCents, 9990);
    expect(conflict.reason, contains('No había stock'));
    expect(conflict.advice, contains('ajusta el inventario'));

    final cancelled = SyncConflict.fromJson(
      conflictJson(estado: 'DESCARTADO', reapply: false, accion: 'ANULADA'),
    );
    expect(cancelled.pending, isFalse);
    expect(cancelled.note, 'Se devolvió el dinero');
    expect(cancelled.resolvedAt, isNotNull);
  });

  group('pantalla de conflictos', () {
    Future<void> pump(WidgetTester tester, List<SyncConflict> items) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            syncConflictsProvider.overrideWith(() => _FixedConflicts(items)),
            resolvedSyncConflictsProvider.overrideWith((ref) async => const []),
          ],
          child: const MaterialApp(home: Scaffold(body: SyncConflictsScreen())),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('muestra vendedor, prendas, monto, motivo y acciones', (
      tester,
    ) async {
      await pump(tester, [SyncConflict.fromJson(conflictJson())]);

      expect(find.text('Pendientes (1)'), findsOneWidget);
      expect(find.text('Venta de Ana Vendedora'), findsOneWidget);
      expect(find.text('1 × Polo básico M Negro'), findsOneWidget);
      expect(find.textContaining('99,90'), findsOneWidget);
      expect(find.textContaining('No había stock'), findsOneWidget);
      expect(find.text('Reaplicar'), findsOneWidget);
      expect(find.text('Anular'), findsOneWidget);
    });

    testWidgets('datos inválidos: no se puede reaplicar, solo anular', (
      tester,
    ) async {
      await pump(tester, [
        SyncConflict.fromJson(
          conflictJson(codigo: 'DATOS_INVALIDOS', reapply: false),
        ),
      ]);
      final reapply = tester.widget<ButtonStyleButton>(
        find.ancestor(
          of: find.text('Reaplicar'),
          matching: find.bySubtype<ButtonStyleButton>(),
        ),
      );
      expect(reapply.onPressed, isNull);
    });

    testWidgets('anular exige escribir una nota', (tester) async {
      await pump(tester, [SyncConflict.fromJson(conflictJson())]);
      await tester.tap(find.text('Anular'));
      await tester.pumpAndSettle();

      ButtonStyleButton confirm() => tester.widget<ButtonStyleButton>(
        find.ancestor(
          of: find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text('Anular'),
          ),
          matching: find.bySubtype<ButtonStyleButton>(),
        ),
      );
      expect(confirm().onPressed, isNull);
      await tester.enterText(find.byType(TextField), 'Se devolvió el dinero');
      await tester.pump();
      expect(confirm().onPressed, isNotNull);
    });

    testWidgets('sin pendientes lo dice claramente', (tester) async {
      await pump(tester, const []);
      expect(find.text('Sin conflictos pendientes'), findsOneWidget);
    });
  });
}

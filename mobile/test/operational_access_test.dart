import 'package:capricho_store/app/navigation_memory.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('acceso al panel operativo', () {
    test('un cliente no accede aunque reciba un permiso operativo', () {
      final user = _user(
        roles: const ['CLIENTE'],
        permissions: const [OperationalPermissions.inventoryView],
      );

      expect(user.canAccessOperationalPanel, isFalse);
    });

    test('una cuenta inactiva no accede', () {
      final user = _user(
        status: 'INACTIVO',
        roles: const ['ADMIN'],
        permissions: const [OperationalPermissions.inventoryView],
      );

      expect(user.canAccessOperationalPanel, isFalse);
    });

    test('el auxiliar solo abre secciones cubiertas por sus permisos', () {
      final user = _user(
        roles: const ['AUXILIAR_INVENTARIO'],
        permissions: const [OperationalPermissions.inventoryView],
      );

      expect(user.canAccessOperationalPanel, isTrue);
      expect(user.canAccessSection(OperationalSection.inventory), isTrue);
      expect(user.canAccessSection(OperationalSection.operations), isTrue);
      expect(user.canManageInventory, isFalse);
      expect(user.canViewPurchaseOrders, isFalse);
      expect(user.canViewReceipts, isFalse);
    });

    test('inventario de solo lectura no habilita mutaciones', () {
      final user = _user(
        roles: const ['ENCARGADO_SUCURSAL'],
        permissions: const [OperationalPermissions.inventoryView],
      );

      expect(user.canViewInventory, isTrue);
      expect(user.canViewTransfers, isTrue);
      expect(user.canManageInventory, isFalse);
    });

    test('el cajero puede tener resumen limitado con productos.ver', () {
      final user = _user(
        roles: const ['CAJERO'],
        permissions: const [OperationalPermissions.productsView],
      );

      expect(user.canAccessOperationalPanel, isTrue);
      expect(user.canAccessSection(OperationalSection.summary), isTrue);
      expect(user.canAccessSection(OperationalSection.inventory), isFalse);
      expect(user.canAccessSection(OperationalSection.operations), isFalse);
    });
  });

  test('la memoria evita restaurar una ruta cuyo permiso fue revocado', () {
    final allowed = _user(
      roles: const ['ADMIN'],
      permissions: const [OperationalPermissions.inventoryView],
    );
    NavigationMemory.rememberPanel('/admin/inventario');
    expect(NavigationMemory.panelTarget(allowed), '/admin/inventario');

    final revoked = _user(
      roles: const ['ADMIN'],
      permissions: const [OperationalPermissions.productsView],
    );
    expect(NavigationMemory.panelTarget(revoked), '/admin/resumen');
  });

  group('protección de rutas del panel', () {
    test('Offline abre para un administrador con acceso a inventario', () {
      final user = _user(
        roles: const ['ADMIN'],
        permissions: const [OperationalPermissions.inventoryView],
      );
      expect(
        NavigationMemory.panelRedirect(
          initialized: true,
          user: user,
          location: '/admin/offline',
        ),
        isNull,
      );
    });

    test(
      'Offline exige acceso a inventario también al abrir la ruta directamente',
      () {
        final user = _user(
          roles: const ['CAJERO'],
          permissions: const [OperationalPermissions.salesCreate],
        );
        expect(
          NavigationMemory.panelRedirect(
            initialized: true,
            user: user,
            location: '/admin/offline',
          ),
          '/admin/403',
        );
      },
    );

    test('un deep link sin sesión conserva returnUrl para el login', () {
      final redirect = NavigationMemory.panelRedirect(
        initialized: true,
        user: null,
        location: '/admin/inventario',
      );

      expect(redirect, '/login?returnUrl=%2Fadmin%2Finventario');
    });

    test('un cliente autenticado es enviado al acceso denegado', () {
      final redirect = NavigationMemory.panelRedirect(
        initialized: true,
        user: _user(roles: const ['CLIENTE'], permissions: const []),
        location: '/admin/resumen',
      );

      expect(redirect, '/admin/403');
    });

    test(
      'un permiso de lectura abre inventario pero no habilita escritura',
      () {
        final user = _user(
          roles: const ['AUXILIAR_INVENTARIO'],
          permissions: const [OperationalPermissions.inventoryView],
        );

        expect(
          NavigationMemory.panelRedirect(
            initialized: true,
            user: user,
            location: '/admin/inventario',
          ),
          isNull,
        );
        expect(user.canManageInventory, isFalse);
      },
    );
  });
}

AppUser _user({
  String status = 'ACTIVO',
  required List<String> roles,
  required List<String> permissions,
}) {
  return AppUser(
    id: 1,
    names: 'Jose Carlos',
    surnames: 'Villarroel Dueñas',
    email: 'persona@example.com',
    status: status,
    roles: roles,
    permissions: permissions,
  );
}

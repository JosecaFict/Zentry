import 'package:capricho_store/features/auth/domain/app_user.dart';

enum OperationalSection { summary, inventory, operations, account }

abstract final class OperationalPermissions {
  static const inventoryView = 'inventario.ver';
  static const inventoryMovement = 'inventario.movimiento';
  static const receiptRegister = 'recepcion.registrar';
  static const suppliersView = 'proveedores.ver';
  static const suppliersManage = 'proveedores.gestionar';
  static const productsView = 'productos.ver';
  static const salesView = 'ventas.ver';
  static const salesCreate = 'ventas.crear';

  static const mobileCapabilities = {
    inventoryView,
    inventoryMovement,
    receiptRegister,
    suppliersView,
    suppliersManage,
    productsView,
    salesView,
    salesCreate,
  };
}

extension OperationalAccess on AppUser {
  bool get isActive => status.trim().toUpperCase() == 'ACTIVO';

  bool get hasOperationalRole => roles.any(
    const {
      'ADMIN',
      'ADMINISTRADOR',
      'ENCARGADO_SUCURSAL',
      'AUXILIAR_INVENTARIO',
      'CAJERO',
    }.contains,
  );

  bool get canAccessOperationalPanel =>
      isActive &&
      hasOperationalRole &&
      (isAdmin ||
          permissions.any(OperationalPermissions.mobileCapabilities.contains));

  bool get canViewInventory =>
      hasPermission(OperationalPermissions.inventoryView);

  bool get canOpenOffline => canViewInventory && canManageOrders;

  /// Puede revisar y resolver ventas offline no registradas (mismo criterio
  /// que el backend: administradores, ventas en todas las sucursales o
  /// encargados con sucursal asignada).
  bool get canReviewSyncConflicts =>
      isActive &&
      (isAdmin ||
          hasPermission('ventas.sucursales_todas') ||
          (roles.contains('ENCARGADO_SUCURSAL') && idSucursal != null));

  bool get canManageInventory =>
      hasPermission(OperationalPermissions.inventoryMovement);

  bool get canViewPurchaseOrders =>
      hasPermission(OperationalPermissions.suppliersView);

  bool get canViewReceipts =>
      hasPermission(OperationalPermissions.receiptRegister);

  bool get canViewTransfers => canViewInventory;

  bool get canManageOrders =>
      isAdmin ||
      roles.contains('ENCARGADO_SUCURSAL') ||
      roles.contains('CAJERO') ||
      hasPermission(OperationalPermissions.salesView) ||
      hasPermission(OperationalPermissions.salesCreate);

  bool get canViewOperations =>
      canViewPurchaseOrders ||
      canViewReceipts ||
      canViewTransfers ||
      canManageOrders;

  bool canAccessSection(OperationalSection section) => switch (section) {
    OperationalSection.summary => canAccessOperationalPanel,
    OperationalSection.inventory => canViewInventory,
    OperationalSection.operations => canViewOperations,
    OperationalSection.account => canAccessOperationalPanel,
  };

  String get operationalContextLabel {
    if (branchName != null && !isAdmin) {
      if (roles.contains('ENCARGADO_SUCURSAL')) return '$branchName · Encargado';
      if (roles.contains('AUXILIAR_INVENTARIO')) return '$branchName · Inventario';
      if (roles.contains('CAJERO')) return '$branchName · Operaciones';
      return '$branchName · $roleName';
    }
    if (roles.contains('ENCARGADO_SUCURSAL')) return 'Operaciones de sucursal';
    if (roles.contains('AUXILIAR_INVENTARIO')) return 'Inventario';
    if (roles.contains('CAJERO')) return 'Operaciones';
    return 'Panel operativo';
  }
}

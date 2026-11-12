import { availableAdminModules, visibleAdminNavigation } from './admin-navigation';

describe('admin navigation permissions', () => {
  it('keeps master data hidden for a read-only cashier', () => {
    const labels = availableAdminModules([
      'productos.ver',
      'ventas.ver',
      'ventas.crear',
      'pagos.registrar',
    ]).map((item) => item.label);

    expect(labels).toEqual([
      'Productos',
      'Venta presencial',
      'Pedidos',
      'Clientes',
      'Devoluciones',
      'Notificaciones',
      'Reportes y asistente IA',
      'Historial de ventas',
    ]);
  });

  it('hides cash sales when payment permission is revoked', () => {
    const labels = availableAdminModules(['ventas.crear']).map((item) => item.label);

    expect(labels).not.toContain('Venta presencial');
  });

  it('limits an inventory assistant to receiving and inventory modules', () => {
    const labels = availableAdminModules([
      'inventario.ver',
      'inventario.movimiento',
      'recepcion.registrar',
    ]).map((item) => item.label);

    // Ver inventario ya no basta para vender offline (el backend exige cobrar).
    expect(labels).toEqual([
      'Recepciones',
      'Existencias',
      'Lotes',
      'Movimientos',
      'Transferencias',
    ]);
  });

  it('lets the default cashier sell offline without inventory access', () => {
    // Permisos del rol CAJERO en la base de datos.
    const permisos = ['ventas.ver', 'ventas.crear', 'pagos.registrar', 'productos.ver'];
    const labels = availableAdminModules(permisos, { roles: ['CAJERO'], permisos, id_sucursal: 3 })
      .map((item) => item.label);

    expect(labels).toContain('Venta presencial');
    expect(labels).toContain('Operación offline');
    expect(labels).not.toContain('Conflictos offline');
    expect(labels).not.toContain('Existencias');
  });

  it('shows offline conflicts only to branch managers and administrators', () => {
    const labels = (roles: string[], id_sucursal: number | null = 3) =>
      availableAdminModules(['inventario.ver'], { roles, permisos: ['inventario.ver'], id_sucursal })
        .map((item) => item.label);

    expect(labels(['ENCARGADO_SUCURSAL'])).toContain('Conflictos offline');
    expect(labels(['ADMIN'], null)).toContain('Conflictos offline');
    expect(labels(['ENCARGADO_SUCURSAL'], null)).not.toContain('Conflictos offline');
    expect(labels(['CAJERO'])).not.toContain('Conflictos offline');
  });

  it('shows branches only to users with organization access', () => {
    expect(availableAdminModules(['sucursales.ver']).map((item) => item.label)).toEqual([
      'Sucursales',
    ]);
    expect(availableAdminModules(['productos.ver']).map((item) => item.label)).not.toContain(
      'Sucursales',
    );
  });

  it('marks only route roots that must use exact active matching', () => {
    const items = visibleAdminNavigation(['inventario.ver']).flatMap((group) => group.items);

    expect(items.find((item) => item.label === 'Dashboard')?.exact).toBe(true);
    expect(items.find((item) => item.label === 'Existencias')?.exact).toBe(true);
    expect(items.find((item) => item.label === 'Lotes')?.exact).toBeUndefined();
  });
});

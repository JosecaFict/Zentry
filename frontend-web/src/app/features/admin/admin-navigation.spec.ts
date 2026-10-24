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
      'Reportes comerciales',
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

    expect(labels).toEqual([
      'Recepciones',
      'Existencias',
      'Lotes',
      'Movimientos',
      'Transferencias',
    ]);
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

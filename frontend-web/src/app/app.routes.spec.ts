import { routes } from './app.routes';

describe('Cycle II routes', () => {
  it('protects every customer commerce route', () => {
    const publicRoutes = routes.find((route) => route.path === '' && route.children)?.children ?? [];
    const commercePaths = [
      'carrito',
      'checkout',
      'reservas',
      'pedidos',
      'historial',
      'direcciones',
      'notificaciones',
    ];

    for (const path of commercePaths) {
      expect(publicRoutes.find((route) => route.path === path)?.canActivate).toHaveLength(1);
    }
  });

  it('registers the operational commerce modules under admin', () => {
    const adminRoutes = routes.find((route) => route.path === 'admin')?.children ?? [];

    expect(adminRoutes.map((route) => route.path)).toEqual(
      expect.arrayContaining([
        'ventas',
        'pedidos',
        'reservas',
        'devoluciones',
        'compras-proveedores',
      ]),
    );
  });
});

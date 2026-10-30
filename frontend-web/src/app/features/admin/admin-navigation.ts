export interface AdminNavItem {
  label: string;
  path: string;
  permissions: string[];
  exact?: boolean;
  requireAll?: boolean;
}
export interface AdminNavGroup {
  label: string;
  items: AdminNavItem[];
}

export const ADMIN_NAVIGATION: AdminNavGroup[] = [
  {
    label: 'Vista general',
    items: [{ label: 'Dashboard', path: '/admin', permissions: [], exact: true }],
  },
  {
    label: 'Personal',
    items: [{ label: 'Empleados', path: '/admin/empleados', permissions: ['empleados.ver'] }],
  },
  {
    label: 'Organización',
    items: [
      {
        label: 'Sucursales',
        path: '/admin/organizacion/sucursales',
        permissions: ['sucursales.ver'],
      },
    ],
  },
  {
    label: 'Catálogo',
    items: [
      {
        label: 'Productos',
        path: '/admin/productos',
        permissions: ['productos.ver', 'productos.crear', 'productos.editar'],
      },
      {
        label: 'Datos maestros',
        path: '/admin/catalogo/datos-maestros',
        permissions: ['productos.crear', 'productos.editar'],
      },
    ],
  },
  {
    label: 'Compras',
    items: [
      {
        label: 'Proveedores',
        path: '/admin/proveedores',
        permissions: ['proveedores.ver', 'proveedores.gestionar'],
      },
      {
        label: 'Órdenes de compra',
        path: '/admin/ordenes-compra',
        permissions: ['proveedores.ver', 'proveedores.gestionar'],
      },
      { label: 'Recepciones', path: '/admin/recepciones', permissions: ['recepcion.registrar'] },
    ],
  },
  {
    label: 'Ventas y pedidos',
    items: [
      {
        label: 'Venta presencial',
        path: '/admin/ventas',
        permissions: ['ventas.crear', 'pagos.registrar'],
        requireAll: true,
      },
      { label: 'Pedidos', path: '/admin/pedidos', permissions: ['ventas.ver'] },
      { label: 'Reservas', path: '/admin/reservas', permissions: ['reservas.ver'] },
      { label: 'Clientes', path: '/admin/clientes', permissions: ['ventas.ver'] },
      { label: 'Devoluciones', path: '/admin/devoluciones', permissions: ['ventas.ver'] },
      { label: 'Notificaciones', path: '/admin/notificaciones', permissions: ['ventas.ver'] },
    ],
  },
  {
    label: 'Marketing',
    items: [
      {
        label: 'Promociones',
        path: '/admin/promociones',
        permissions: ['promociones.gestionar'],
      },
      {
        label: 'Campañas',
        path: '/admin/campanias',
        permissions: ['promociones.gestionar'],
      },
      {
        label: 'Recomendador IA',
        path: '/admin/recomendador',
        permissions: ['promociones.gestionar'],
      },
    ],
  },
  {
    label: 'Análisis',
    items: [
      { label: 'Reportes comerciales', path: '/admin/reportes', permissions: ['ventas.ver'] },
      {
        label: 'Analítica inteligente',
        path: '/admin/analitica',
        permissions: ['ventas.ver', 'inventario.ver'],
        requireAll: true,
      },
    ],
  },
  {
    label: 'Historiales',
    items: [
      {
        label: 'Historial de ventas',
        path: '/admin/historial-ventas',
        permissions: ['ventas.ver'],
      },
      {
        label: 'Historial de compras',
        path: '/admin/compras-proveedores',
        permissions: ['proveedores.ver'],
      },
    ],
  },
  {
    label: 'Inventario',
    items: [
      {
        label: 'Existencias',
        path: '/admin/inventario',
        permissions: ['inventario.ver'],
        exact: true,
      },
      { label: 'Lotes', path: '/admin/inventario/lotes', permissions: ['inventario.ver'] },
      {
        label: 'Movimientos',
        path: '/admin/inventario/movimientos',
        permissions: ['inventario.ver'],
      },
      {
        label: 'Transferencias',
        path: '/admin/inventario/transferencias',
        permissions: ['inventario.ver', 'inventario.movimiento'],
      },
      {
        label: 'Operación offline',
        path: '/admin/inventario/offline',
        permissions: ['inventario.ver'],
      },
    ],
  },
  {
    label: 'Seguridad',
    items: [
      {
        label: 'Marca de la empresa',
        path: '/admin/configuracion/marca',
        permissions: ['permisos.asignar'],
      },
      {
        label: 'Roles y permisos',
        path: '/admin/seguridad/roles-permisos',
        permissions: ['permisos.asignar'],
      },
      {
        label: 'Bitácora',
        path: '/admin/seguridad/bitacora',
        permissions: ['permisos.asignar'],
      },
    ],
  },
];

export function visibleAdminNavigation(permissionCodes: readonly string[]): AdminNavGroup[] {
  const permissions = new Set(permissionCodes);
  return ADMIN_NAVIGATION.map((group) => ({
    ...group,
    items: group.items.filter(
      (item) =>
        !item.permissions.length ||
        (item.requireAll
          ? item.permissions.every((permission) => permissions.has(permission))
          : item.permissions.some((permission) => permissions.has(permission))),
    ),
  })).filter((group) => group.items.length);
}

export function availableAdminModules(permissionCodes: readonly string[]): AdminNavItem[] {
  return visibleAdminNavigation(permissionCodes)
    .flatMap((group) => group.items)
    .filter((item) => item.path !== '/admin');
}

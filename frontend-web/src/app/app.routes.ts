import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import {
  adminGuard,
  platformGuard,
  requireAllPermissions,
  requireAnyPermission,
} from './core/guards/permission.guard';
import { mainSurfaceGuard, tenantSurfaceGuard } from './core/guards/surface.guard';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    canMatch: [mainSurfaceGuard],
    title: 'Zentry | Software comercial para empresas',
    loadComponent: () =>
      import('./features/zentry-landing/zentry-landing').then((m) => m.ZentryLanding),
  },
  {
    path: 'servicio-no-disponible',
    canMatch: [tenantSurfaceGuard],
    title: 'Servicio no disponible | Zentry',
    loadComponent: () =>
      import('./features/tenant-unavailable/tenant-unavailable').then(
        (m) => m.TenantUnavailable,
      ),
  },
  {
    path: '',
    canMatch: [tenantSurfaceGuard],
    loadComponent: () =>
      import('./layouts/public-layout/public-layout').then((m) => m.PublicLayout),
    children: [
      {
        path: '', // [CU-04 / CU-17 / CU-19] Inicio: Catálogo destacado, recomendaciones y banners
        title: 'Inicio | Tienda',
        loadComponent: () => import('./features/home/home').then((m) => m.Home),
      },
      {
        path: 'catalogo', // [CU-04] Catálogo de prendas y filtros
        title: 'Catálogo | Tienda',
        loadComponent: () => import('./features/catalog/catalog').then((m) => m.Catalog),
      },
      {
        path: 'productos/:id', // [CU-05] Detalle de prenda y matriz de variantes  // [CU-04 / CU-18] Detalle de producto y probador virtual
        title: 'Producto | Tienda',
        loadComponent: () =>
          import('./features/catalog/product-detail').then((m) => m.ProductDetail),
      },
      {
        path: 'login', // [CU-01] Inicio de sesión (Login)
        title: 'Ingresar | Tienda',
        loadComponent: () => import('./features/auth/login').then((m) => m.Login),
      },
      {
        path: 'registro', // [CU-01] Registro de clientes
        title: 'Crear cuenta | Tienda',
        loadComponent: () => import('./features/auth/register').then((m) => m.Register),
      },
      {
        path: 'recuperar-contrasena', // [CU-08] Recuperación de cuenta vía OTP
        title: 'Recuperar contraseña | Tienda',
        loadComponent: () =>
          import('./features/auth/password-recovery').then((m) => m.PasswordRecovery),
      },
      {
        path: 'cuenta', // [CU-01] Mi cuenta y perfil de usuario
        title: 'Mi cuenta | Tienda',
        canActivate: [authGuard],
        loadComponent: () => import('./features/auth/account').then((m) => m.Account),
      },
      { path: 'cuenta/pedidos', redirectTo: 'pedidos' }, // [CU-13] Redirección a pedidos
      { path: 'cuenta/reservas', redirectTo: 'reservas' }, // [CU-10] Redirección a reservas
      { path: 'cuenta/historial', redirectTo: 'historial' }, // [CU-11] Redirección a historial
      { path: 'cuenta/direcciones', redirectTo: 'direcciones' }, // [CU-09] Redirección a direcciones
      { path: 'cuenta/notificaciones', redirectTo: 'notificaciones' }, // [CU-20] Redirección a notificaciones
      {
        path: 'carrito', // [CU-09] Carrito de compras y entrega
        title: 'Carrito | Tienda',
        canActivate: [authGuard],
        loadComponent: () => import('./features/commerce/commerce-pages').then((m) => m.CartPage),
      },
      {
        path: 'checkout', // [CU-12] Checkout y pago en línea con Stripe
        title: 'Confirmar pedido | Tienda',
        canActivate: [authGuard],
        loadComponent: () =>
          import('./features/commerce/commerce-pages').then((m) => m.CheckoutPage),
      },
      {
        path: 'reservas', // [CU-10] Gestión operativa de reservas  // [CU-10] Reservas presenciales 48h hábiles
        title: 'Reservas | Tienda',
        canActivate: [authGuard],
        loadComponent: () =>
          import('./features/commerce/commerce-pages').then((m) => m.ReservationsPage),
      },
      {
        path: 'pedidos', // [CU-13] Gestión y despacho de pedidos  // [CU-13] Seguimiento de pedidos del cliente
        title: 'Pedidos | Tienda',
        canActivate: [authGuard],
        loadComponent: () => import('./features/commerce/commerce-pages').then((m) => m.OrdersPage),
      },
      {
        path: 'historial', // [CU-11] Historial de compras de cliente
        title: 'Historial | Tienda',
        canActivate: [authGuard],
        loadComponent: () =>
          import('./features/commerce/commerce-pages').then((m) => m.HistoryPage),
      },
      {
        path: 'direcciones', // [CU-09] Direcciones de entrega
        title: 'Direcciones | Tienda',
        canActivate: [authGuard],
        loadComponent: () =>
          import('./features/commerce/commerce-pages').then((m) => m.AddressesPage),
      },
      {
        path: 'notificaciones', // [CU-20] Auditoría y envío de notificaciones  // [CU-20] Bandeja de notificaciones
        title: 'Notificaciones | Tienda',
        canActivate: [authGuard],
        loadComponent: () =>
          import('./features/commerce/commerce-pages').then((m) => m.NotificationsPage),
      },
    ],
  },
  {
    path: 'platform/login',
    canMatch: [mainSurfaceGuard],
    title: 'Acceso de plataforma | Zentry',
    data: { platformLogin: true },
    loadComponent: () => import('./features/auth/login').then((m) => m.Login),
  },
  {
    path: 'platform',
    canMatch: [mainSurfaceGuard],
    canActivate: [platformGuard],
    loadComponent: () =>
      import('./features/platform/platform-layout').then((m) => m.PlatformLayout),
    children: [
      {
        path: '',
        pathMatch: 'full',
        title: 'Plataforma | Zentry',
        loadComponent: () =>
          import('./features/platform/platform-pages').then((m) => m.PlatformOverviewPage),
      },
      {
        path: 'empresas',
        title: 'Empresas | Zentry',
        loadComponent: () =>
          import('./features/platform/platform-pages').then((m) => m.PlatformTenantsPage),
      },
      {
        path: 'empresas/nueva',
        title: 'Nueva empresa | Zentry',
        loadComponent: () =>
          import('./features/platform/platform-pages').then((m) => m.PlatformTenantCreatePage),
      },
      {
        path: 'empresas/:id',
        title: 'Detalle de empresa | Zentry',
        loadComponent: () =>
          import('./features/platform/platform-pages').then((m) => m.PlatformTenantDetailPage),
      },
      {
        path: 'planes',
        title: 'Planes | Zentry',
        loadComponent: () =>
          import('./features/platform/platform-pages').then((m) => m.PlatformPlansPage),
      },
      { path: '**', redirectTo: '' },
    ],
  },
  {
    path: 'admin',
    canActivate: [authGuard],
    loadComponent: () => import('./features/admin/admin-layout').then((m) => m.AdminLayout),
    children: [
      {
        path: '403',
        loadComponent: () =>
          import('./features/admin/admin-status-pages').then((m) => m.AdminForbidden),
      },
      {
        path: 'perfil', // [CU-01] Perfil de administrador/empleado
        title: 'Mi Perfil | Tienda',
        loadComponent: () => import('./features/admin/profile-admin').then((m) => m.ProfileAdmin),
      },
      {
        path: 'configuracion/marca',
        title: 'Marca de la empresa | Zentry',
        canActivate: [requireAnyPermission('permisos.asignar')],
        loadComponent: () =>
          import('./features/admin/tenant-brand-admin').then((m) => m.TenantBrandAdmin),
      },
      {
        path: '', // [CU-16] Dashboard comercial con KPIs y métricas
        pathMatch: 'full',
        canActivate: [adminGuard],
        title: 'Panel operativo | Tienda',
        loadComponent: () => import('./features/admin/dashboard').then((m) => m.AdminDashboard),
      },
      {
        path: 'empleados', // [CU-02] Gestión de empleados y roles
        canActivate: [requireAnyPermission('empleados.ver')],
        loadComponent: () =>
          import('./features/admin/employees-admin').then((m) => m.EmployeesAdmin),
      },
      {
        path: 'empleados/:id', // [CU-02] Detalle y asignación de empleado
        canActivate: [requireAnyPermission('empleados.ver')],
        loadComponent: () =>
          import('./features/admin/employees-admin').then((m) => m.EmployeeDetail),
      },
      {
        path: 'organizacion/sucursales', // [CU-03] Sucursales y ciudades
        title: 'Sucursales | Tienda',
        canActivate: [requireAnyPermission('sucursales.ver')],
        loadComponent: () => import('./features/admin/branches-admin').then((m) => m.BranchesAdmin),
      },
      {
        path: 'productos', // [CU-05] Administración de prendas y variantes
        canActivate: [requireAnyPermission('productos.ver', 'productos.crear', 'productos.editar')],
        loadComponent: () => import('./features/admin/catalog-admin').then((m) => m.ProductsAdmin),
      },
      {
        path: 'productos/:id',
        canActivate: [requireAnyPermission('productos.ver', 'productos.crear', 'productos.editar')],
        loadComponent: () =>
          import('./features/admin/catalog-admin').then((m) => m.ProductAdminDetail),
      },
      {
        path: 'catalogo/datos-maestros', // [CU-05] Categorías, marcas, tallas y colores
        canActivate: [requireAnyPermission('productos.crear', 'productos.editar')],
        loadComponent: () =>
          import('./features/admin/catalog-admin').then((m) => m.MasterDataAdmin),
      },
      {
        path: 'proveedores', // [CU-06] Gestión de proveedores
        canActivate: [requireAnyPermission('proveedores.ver', 'proveedores.gestionar')],
        loadComponent: () =>
          import('./features/admin/operations-admin').then((m) => m.SuppliersAdmin),
      },
      {
        path: 'proveedores/:id', // [CU-06] Detalle y catálogo de proveedor
        canActivate: [requireAnyPermission('proveedores.ver', 'proveedores.gestionar')],
        loadComponent: () =>
          import('./features/admin/operations-admin').then((m) => m.SupplierDetail),
      },
      {
        path: 'ordenes-compra', // [CU-06] Órdenes de compra a proveedores
        canActivate: [requireAnyPermission('proveedores.ver', 'proveedores.gestionar')],
        loadComponent: () =>
          import('./features/admin/operations-admin').then((m) => m.PurchasesAdmin),
      },
      {
        path: 'recepciones', // [CU-06] Recepción de mercadería en almacén
        canActivate: [requireAnyPermission('recepcion.registrar')],
        loadComponent: () =>
          import('./features/admin/operations-admin').then((m) => m.ReceiptsAdmin),
      },
      {
        path: 'compras-proveedores', // [CU-06] Histórico de compras a proveedores
        canActivate: [requireAnyPermission('proveedores.ver')],
        loadComponent: () =>
          import('./features/admin/commerce-admin').then((m) => m.SupplierHistoryAdmin),
      },
      {
        path: 'reportes',
        title: 'Reportes comerciales | Zentry',
        canActivate: [requireAnyPermission('ventas.ver')],
        loadComponent: () =>
          import('./features/admin/reports-admin').then((m) => m.ReportsAdmin),
      },
      {
        path: 'historial-ventas', // [CU-11] Reporte y bitácora de ventas
        canActivate: [requireAnyPermission('ventas.ver')],
        loadComponent: () =>
          import('./features/admin/commerce-admin').then((m) => m.SalesHistoryAdmin),
      },
      {
        path: 'ventas', // [CU-11] Punto de Venta (POS) en caja
        canActivate: [requireAllPermissions('ventas.crear', 'pagos.registrar')],
        loadComponent: () => import('./features/admin/commerce-admin').then((m) => m.PosSalesAdmin),
      },
      {
        path: 'pedidos',
        canActivate: [requireAnyPermission('ventas.ver')],
        loadComponent: () => import('./features/admin/commerce-admin').then((m) => m.OrdersAdmin),
      },
      {
        path: 'reservas',
        canActivate: [requireAnyPermission('reservas.ver')],
        loadComponent: () =>
          import('./features/admin/commerce-admin').then((m) => m.ReservationsAdmin),
      },
      {
        path: 'clientes', // [CU-01 / CU-11] Directorio de clientes y métricas
        canActivate: [requireAnyPermission('ventas.ver')],
        loadComponent: () =>
          import('./features/admin/customers-admin').then((m) => m.CustomersAdmin),
      },
      {
        path: 'devoluciones', // [CU-14] Devoluciones y notas de crédito
        canActivate: [requireAnyPermission('ventas.ver')],
        loadComponent: () => import('./features/admin/commerce-admin').then((m) => m.ReturnsAdmin),
      },
      {
        path: 'notificaciones',
        title: 'Notificaciones Operativas | Tienda',
        canActivate: [requireAnyPermission('ventas.ver')],
        loadComponent: () =>
          import('./features/admin/notifications-admin').then((m) => m.NotificationsAdmin),
      },
      {
        path: 'promociones', // [CU-19] Reglas de promociones y descuentos
        title: 'Promociones y Descuentos | Tienda',
        canActivate: [requireAnyPermission('promociones.gestionar')],
        loadComponent: () =>
          import('./features/admin/promotions-admin').then((m) => m.PromotionsAdmin),
      },
      {
        path: 'campanias', // [CU-19 / CU-20] Campañas comerciales y difusión push
        title: 'Campañas y Difusión | Tienda',
        canActivate: [requireAnyPermission('promociones.gestionar')],
        loadComponent: () =>
          import('./features/admin/campaigns-admin').then((m) => m.CampaignsAdmin),
      },
      {
        path: 'recomendador', // [CU-17] Calibración y simulación de recomendaciones
        title: 'Recomendador IA | Tienda',
        canActivate: [requireAnyPermission('promociones.gestionar')],
        loadComponent: () =>
          import('./features/admin/recommendations-admin').then((m) => m.RecommendationsAdmin),
      },
      {
        path: 'inventario', // [CU-15] Existencias y stock mínimo
        canActivate: [requireAnyPermission('inventario.ver')],
        loadComponent: () =>
          import('./features/admin/operations-admin').then((m) => m.InventoryAdmin),
      },
      {
        path: 'inventario/lotes', // [CU-06] Trazabilidad de lotes recibidos
        canActivate: [requireAnyPermission('inventario.ver')],
        data: { mode: 'lots' },
        loadComponent: () => import('./features/admin/operations-admin').then((m) => m.TraceAdmin),
      },
      {
        path: 'inventario/movimientos', // [CU-15] Kardex de movimientos y ajustes
        canActivate: [requireAnyPermission('inventario.ver')],
        data: { mode: 'movements' },
        loadComponent: () => import('./features/admin/operations-admin').then((m) => m.TraceAdmin),
      },
      {
        path: 'inventario/transferencias', // [CU-07] Transferencias intersucursales
        canActivate: [requireAnyPermission('inventario.ver', 'inventario.movimiento')],
        data: { mode: 'transfers' },
        loadComponent: () => import('./features/admin/operations-admin').then((m) => m.TraceAdmin),
      },
      {
        path: 'seguridad/roles-permisos', // [CU-02] Matriz de roles y permisos
        title: 'Roles y permisos | Tienda',
        canActivate: [requireAnyPermission('permisos.asignar')],
        loadComponent: () =>
          import('./features/admin/employees-admin').then((m) => m.RolesPermissionsAdmin),
      },
      {
        path: 'seguridad/bitacora', // [CU-16] Bitácora de auditoría de seguridad
        title: 'Bitácora de seguridad | Tienda',
        canActivate: [requireAnyPermission('permisos.asignar')],
        loadComponent: () => import('./features/admin/audit-admin').then((m) => m.AuditAdmin),
      },
      {
        path: '**',
        loadComponent: () =>
          import('./features/admin/admin-status-pages').then((m) => m.AdminNotFound),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];

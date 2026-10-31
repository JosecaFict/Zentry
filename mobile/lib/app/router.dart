import 'package:capricho_store/app/navigation_memory.dart';
import 'package:capricho_store/features/admin/presentation/admin_dashboard_screen.dart';
import 'package:capricho_store/features/admin/presentation/admin_inventory_screen.dart';
import 'package:capricho_store/features/admin/presentation/admin_operations_screen.dart';
import 'package:capricho_store/features/admin/presentation/admin_profile_screen.dart';
import 'package:capricho_store/features/admin/presentation/admin_shell.dart';
import 'package:capricho_store/features/admin/presentation/operational_access_screen.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/auth/presentation/login_screen.dart';
import 'package:capricho_store/features/auth/presentation/password_recovery_screen.dart';
import 'package:capricho_store/features/auth/presentation/profile_screen.dart';
import 'package:capricho_store/features/auth/presentation/register_screen.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/catalog/presentation/catalog_screen.dart';
import 'package:capricho_store/features/catalog/presentation/product_detail_screen.dart';
import 'package:capricho_store/features/fitting/presentation/virtual_fitting_screen.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/tenant/presentation/company_selection_screen.dart';
import 'package:capricho_store/features/commerce/presentation/addresses_screen.dart';
import 'package:capricho_store/features/commerce/presentation/cart_screen.dart';
import 'package:capricho_store/features/commerce/presentation/checkout_complete_screen.dart';
import 'package:capricho_store/features/commerce/presentation/checkout_screen.dart';
import 'package:capricho_store/features/commerce/presentation/notifications_screen.dart';
import 'package:capricho_store/features/commerce/presentation/order_detail_screen.dart';
import 'package:capricho_store/features/commerce/presentation/orders_screen.dart';
import 'package:capricho_store/features/commerce/presentation/reservations_screen.dart';
import 'package:capricho_store/features/home/presentation/home_screen.dart';
import 'package:capricho_store/features/home/presentation/splash_screen.dart';
import 'package:capricho_store/features/offline/presentation/offline_operations_screen.dart';
import 'package:capricho_store/shared/widgets/app_shell.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');
final _shellNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'storeShell');
final _adminShellNavigatorKey = GlobalKey<NavigatorState>(
  debugLabel: 'adminShell',
);

/// Construye páginas nativas adaptativas:
/// - En iOS: CupertinoPage, activando el gesto físico de deslizamiento para volver atrás (Swipe-to-back) y animaciones nativas de iOS.
/// - En Android: MaterialPage con transiciones Material 3.
Page<dynamic> _adaptivePage({
  required LocalKey key,
  required Widget child,
  String? title,
}) {
  if (defaultTargetPlatform == TargetPlatform.iOS) {
    return CupertinoPage(key: key, title: title, child: child);
  }
  return MaterialPage(key: key, child: child);
}

final appRouterProvider = Provider<GoRouter>((ref) {
  final refresh = _RouterRefreshNotifier();
  ref.listen(authControllerProvider, (_, _) => refresh.notify());
  ref.listen(tenantControllerProvider, (_, _) => refresh.notify());
  ref.onDispose(refresh.dispose);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) {
      final uri = state.uri;

      // Interceptar esquema zentry:// o deep links de checkout-complete
      if (uri.scheme == 'zentry' ||
          uri.host == 'checkout-complete' ||
          uri.path == '/checkout-complete' ||
          uri.toString().contains('checkout-complete')) {
        final query = uri.hasQuery ? '?${uri.query}' : '';
        return '/checkout-complete$query';
      }

      final location = uri.path;
      if (location == '/splash') return null;

      final tenant = ref.read(tenantControllerProvider);
      if (location == '/empresa') {
        return tenant.selected == null ? null : '/inicio';
      }
      if (tenant.initialized && tenant.selected == null) return '/empresa';

      // [CU-18] Proteger acceso al vestidor virtual con IA: requiere sesión activa
      if (location == '/vestidor') {
        final auth = ref.read(authControllerProvider);
        if (auth.initialized && !auth.isAuthenticated) {
          return '/login?returnUrl=/vestidor';
        }
      }

      final isPanelRoute =
          location == '/admin' || location.startsWith('/admin/');
      if (!isPanelRoute) return null;

      final auth = ref.read(authControllerProvider);
      return NavigationMemory.panelRedirect(
        initialized: auth.initialized,
        user: auth.user,
        location: state.uri.toString(),
      );
    },
    errorBuilder: (context, state) {
      debugPrint('[GoRouter] Error de navegación: ${state.uri}');
      final uri = state.uri;
      if (uri.scheme == 'zentry' ||
          uri.host == 'checkout-complete' ||
          uri.toString().contains('checkout-complete')) {
        return CheckoutCompleteScreen(
          sessionId: uri.queryParameters['session_id'],
          status: uri.queryParameters['status'],
        );
      }
      return Scaffold(
        appBar: AppBar(title: const Text('Página no encontrada')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.search_off_rounded,
                  size: 64,
                  color: AppColors.inkSoft,
                ),
                const SizedBox(height: 16),
                const Text(
                  'No encontramos la página solicitada.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: () => context.go('/inicio'),
                  child: const Text('Volver al inicio'),
                ),
              ],
            ),
          ),
        ),
      );
    },
    routes: [
      GoRoute(
        path: '/splash', // Splash de bienvenida
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: '/empresa',
        pageBuilder: (context, state) => _adaptivePage(
          key: state.pageKey,
          child: const CompanySelectionScreen(),
        ),
      ),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) =>
            AppShell(location: state.uri.path, child: child),
        routes: [
          GoRoute(
            path: '/inicio', // [CU-04 / CU-17 / CU-19] Inicio: Banners, catálogo y recomendaciones
            builder: (context, state) => const HomeScreen(),
          ),
          GoRoute(
            path: '/catalogo', // [CU-04] Catálogo de prendas y filtros
            builder: (context, state) => const CatalogScreen(),
          ),
          GoRoute(
            path: '/carrito', // [CU-09] Carrito de compras
            builder: (context, state) => const CartScreen(),
          ),
          GoRoute(
            path: '/pedidos', // [CU-13] Lista de pedidos del cliente
            builder: (context, state) => const OrdersScreen(),
          ),
          GoRoute(
            path: '/cuenta', // [CU-01] Perfil de usuario y datos personales
            builder: (context, state) => const ProfileScreen(),
          ),
        ],
      ),
      GoRoute(path: '/admin', builder: (_, _) => const SizedBox.shrink()),
      ShellRoute(
        navigatorKey: _adminShellNavigatorKey,
        builder: (context, state, child) =>
            AdminShell(location: state.uri.path, child: child),
        routes: [
          GoRoute(
            path: '/admin/resumen', // [CU-16] Dashboard operativo móvil
            builder: (context, state) => const AdminDashboardScreen(),
          ),
          GoRoute(
            path: '/admin/inventario', // [CU-15] Gestión de inventario móvil
            builder: (context, state) => const AdminInventoryScreen(),
          ),
          GoRoute(
            path: '/admin/operaciones', // [CU-06 / CU-07] Operaciones de abastecimiento y transferencias
            builder: (context, state) => const AdminOperationsScreen(),
          ),
          GoRoute(
            path: '/admin/offline',
            builder: (context, state) => const OfflineOperationsScreen(),
          ),
          GoRoute(
            path: '/admin/perfil', // [CU-01] Perfil de empleado / admin
            builder: (context, state) => const AdminProfileScreen(),
          ),
        ],
      ),
      GoRoute(
        path: '/admin/403', // [CU-02] Pantalla de acceso denegado por permisos
        pageBuilder: (context, state) => _adaptivePage(
          key: state.pageKey,
          child: const OperationalAccessScreen(),
        ),
      ),
      GoRoute(
        path:
            '/productos/:id', // [CU-04 / CU-18] Detalle de prenda y probador AR
        pageBuilder: (context, state) => _adaptivePage(
          key: state.pageKey,
          child: ProductDetailScreen(
            productId: int.parse(state.pathParameters['id']!),
            branchId: int.tryParse(state.uri.queryParameters['sucursal'] ?? ''),
          ),
        ),
      ),
      GoRoute(
        path: '/login', // [CU-01] Inicio de sesión (Login)
        pageBuilder: (context, state) =>
            _adaptivePage(key: state.pageKey, child: const LoginScreen()),
      ),
      GoRoute(
        path: '/registro', // [CU-01] Registro de cliente
        pageBuilder: (context, state) =>
            _adaptivePage(key: state.pageKey, child: const RegisterScreen()),
      ),
      GoRoute(
        path: '/recuperar-password', // [CU-08] Recuperación de cuenta vía OTP
        pageBuilder: (context, state) => _adaptivePage(
          key: state.pageKey,
          child: const PasswordRecoveryScreen(),
        ),
      ),
      GoRoute(
        path: '/checkout', // [CU-12] Checkout y pago con Stripe
        pageBuilder: (context, state) =>
            _adaptivePage(key: state.pageKey, child: const CheckoutScreen()),
      ),
      GoRoute(
        path: '/checkout-complete', // [CU-12] Confirmación y resultado de pago
        pageBuilder: (context, state) => _adaptivePage(
          key: state.pageKey,
          child: CheckoutCompleteScreen(
            sessionId: state.uri.queryParameters['session_id'],
            status: state.uri.queryParameters['status'],
          ),
        ),
      ),
      GoRoute(
        path: '/reservas', // [CU-10] Mis reservas presenciales (48h)
        pageBuilder: (context, state) => _adaptivePage(
          key: state.pageKey,
          child: const ReservationsScreen(),
        ),
      ),
      GoRoute(
        path: '/pedidos/:id', // [CU-13] Detalle y seguimiento de pedido
        pageBuilder: (context, state) => _adaptivePage(
          key: state.pageKey,
          child: OrderDetailScreen(
            orderId: int.parse(state.pathParameters['id']!),
          ),
        ),
      ),
      GoRoute(
        path: '/direcciones', // [CU-09] Direcciones de entrega
        pageBuilder: (context, state) =>
            _adaptivePage(key: state.pageKey, child: const AddressesScreen()),
      ),
      GoRoute(
        path: '/notificaciones', // [CU-20] Notificaciones push recibidas
        pageBuilder: (context, state) => _adaptivePage(
          key: state.pageKey,
          child: const NotificationsScreen(),
        ),
      ),
      GoRoute(
        path:
            '/vestidor', // [CU-18] Probador Virtual con Realidad Aumentada (AR)
        pageBuilder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return _adaptivePage(
            key: state.pageKey,
            child: VirtualFittingScreen(
              product: extra['product'] as Product,
              measurements:
                  (extra['measurements'] as List<ProductMeasurement>?) ??
                  const [],
              initialVariant: extra['initialVariant'] as ProductVariant?,
              images: (extra['images'] as List<ProductImage>?) ?? const [],
            ),
          );
        },
      ),
    ],
  );
});

class _RouterRefreshNotifier extends ChangeNotifier {
  void notify() => notifyListeners();
}

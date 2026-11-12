import 'package:capricho_store/app/navigation_memory.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/commerce/domain/commerce_models.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:capricho_store/shared/widgets/connection_banners.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

class AppShell extends ConsumerWidget {
  const AppShell({required this.location, required this.child, super.key});
  final String location;
  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    NavigationMemory.rememberStore(location);
    final cartCount = ref.watch(cartItemCountProvider);
    final user = ref.watch(authControllerProvider).user;
    final isStaff = user != null && user.canAccessOperationalPanel;

    final orders = ref.watch(ordersProvider).maybeWhen(
      data: (items) => items,
      orElse: () => const <Order>[],
    );
    final activeOrdersCount = orders.where((o) =>
        o.estado == 'PENDIENTE' ||
        o.estado == 'PREPARANDO' ||
        o.estado == 'LISTO_PARA_RETIRO' ||
        o.estado == 'LISTO_PARA_ENVIO' ||
        o.estado == 'EN_CAMINO'
    ).length;

    int selectedIndex = 0;
    if (location.startsWith('/cuenta')) {
      selectedIndex = 4;
    } else if (location.startsWith('/pedidos')) {
      selectedIndex = 3;
    } else if (location.startsWith('/carrito')) {
      selectedIndex = 2;
    } else if (location.startsWith('/catalogo')) {
      selectedIndex = 1;
    }

    return Scaffold(
      body: child,
      bottomNavigationBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const ConnectionBanners(),
          Container(
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: AppColors.line, width: 1)),
            ),
            child: NavigationBar(
              selectedIndex: selectedIndex,
              onDestinationSelected: (index) {
                switch (index) {
                  case 0:
                    context.go('/inicio');
                    break;
                  case 1:
                    context.go('/catalogo');
                    break;
                  case 2:
                    if (isStaff) {
                      context.go(NavigationMemory.panelTarget(user));
                    } else {
                      context.go('/carrito');
                    }
                    break;
                  case 3:
                    context.go('/pedidos');
                    break;
                  case 4:
                    context.go('/cuenta');
                    break;
                }
              },
              destinations: [
                const NavigationDestination(
                  icon: Icon(Icons.home_outlined),
                  selectedIcon: Icon(Icons.home_rounded),
                  label: 'Inicio',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.grid_view_outlined),
                  selectedIcon: Icon(Icons.grid_view_rounded),
                  label: 'Catálogo',
                ),
                if (isStaff)
                  const NavigationDestination(
                    icon: Icon(Icons.shield_outlined),
                    selectedIcon: Icon(Icons.shield_rounded),
                    label: 'Panel',
                  )
                else
                  NavigationDestination(
                    icon: Badge(
                      isLabelVisible: cartCount > 0,
                      label: Text('$cartCount'),
                      backgroundColor: AppColors.cobalt,
                      child: const Icon(Icons.shopping_bag_outlined),
                    ),
                    selectedIcon: Badge(
                      isLabelVisible: cartCount > 0,
                      label: Text('$cartCount'),
                      backgroundColor: AppColors.cobalt,
                      child: const Icon(Icons.shopping_bag_rounded),
                    ),
                    label: 'Carrito',
                  ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: activeOrdersCount > 0,
                    label: Text('$activeOrdersCount'),
                    backgroundColor: AppColors.cobalt,
                    child: const Icon(Icons.inventory_2_outlined),
                  ),
                  selectedIcon: Badge(
                    isLabelVisible: activeOrdersCount > 0,
                    label: Text('$activeOrdersCount'),
                    backgroundColor: AppColors.cobalt,
                    child: const Icon(Icons.inventory_2_rounded),
                  ),
                  label: 'Pedidos',
                ),
                NavigationDestination(
                  icon: const Icon(Icons.person_outline_rounded),
                  selectedIcon: const Icon(Icons.person_rounded),
                  label: isStaff ? 'Perfil' : 'Mi cuenta',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
